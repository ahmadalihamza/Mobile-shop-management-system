from mobile_desk.database import Database, audit
from mobile_desk.services.common import require, remember, payment, check_line_total
from mobile_desk.services.stock import chronological, allocate, move
from mobile_desk.values import BusinessError, business_date, money, quantity, text, timestamp


class SaleService:
    def __init__(self, db: Database):
        self.db = db

    def post(self, day, lines, *, customer_id=None, payments=(), notes='', legacy_reference='', key=None):
        business_date(day)
        if not lines:
            raise BusinessError('Add at least one product.')
        prepared = [(line['product_id'], quantity(line['quantity']), money(line['selling_rate'], 'Selling price')) for line in lines]
        total = sum(qty * rate for _, qty, rate in prepared)
        check_line_total(total)
        pays = [(p['account_id'], money(p['amount'], 'Payment', True)) for p in payments]
        paid = sum(value for _, value in pays)
        if paid > total:
            raise BusinessError('Amount paid cannot exceed the invoice total.')
        if total > paid and not customer_id:
            raise BusinessError('Select a customer for the unpaid amount.')
        payload = dict(day=day, lines=lines, customer_id=customer_id, payments=list(payments), notes=notes, legacy_reference=legacy_reference)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            customer = require(c, 'parties', customer_id, 'is_customer')['name'] if customer_id else 'Walk-in'
            settings = {r['key']: r['value'] for r in c.execute("SELECT * FROM settings WHERE key IN('invoice_prefix','next_invoice')")}
            seq = int(settings['next_invoice'])
            while c.execute('SELECT 1 FROM sales WHERE invoice_number=?', (settings['invoice_prefix']+str(seq).zfill(6),)).fetchone():
                seq += 1
            number = settings['invoice_prefix'] + str(seq).zfill(6)
            c.execute("UPDATE settings SET value=? WHERE key='next_invoice'", (str(seq+1),))
            identity = c.execute('INSERT INTO sales(invoice_number,transaction_date,customer_id,customer_snapshot,subtotal,total,notes,legacy_reference,created_at) VALUES(?,?,?,?,?,?,?,?,?)', (number, day, customer_id, customer, total, total, text(notes, limit=2000), text(legacy_reference), timestamp())).lastrowid
            for product_id, qty, rate in prepared:
                product = require(c, 'products', product_id)
                chronological(c, product_id, day)
                item_id = c.execute('INSERT INTO sale_items(sale_id,product_id,quantity,selling_rate,line_total,cogs,gross_profit,product_description_snapshot) VALUES(?,?,?,?,?,0,0,?)', (identity, product_id, qty, rate, qty*rate, product['custom_name'])).lastrowid
                cogs = allocate(c, item_id, product_id, day, qty)
                c.execute('UPDATE sale_items SET cogs=?,gross_profit=? WHERE id=?', (cogs, qty*rate-cogs, item_id))
            for account_id, value in pays:
                payment(c, day, account_id, value, 'SALE_RECEIPT', party_id=customer_id, sale_id=identity, reference=number)
            audit(c, 'POST', 'sale', identity)
            remember(c, key, payload, identity)
            return identity

    def list(self, start='1900-01-01', end='9999-12-31', query='', customer_id=None, limit=200, offset=0):
        clauses = ['s.transaction_date BETWEEN ? AND ?', '(s.invoice_number LIKE ? OR s.customer_snapshot LIKE ? OR s.legacy_reference LIKE ? OR s.notes LIKE ? OR EXISTS(SELECT 1 FROM sale_items si WHERE si.sale_id=s.id AND si.product_description_snapshot LIKE ?))']
        params = [start, end, '%'+query+'%', '%'+query+'%', '%'+query+'%', '%'+query+'%', '%'+query+'%']
        if customer_id:
            clauses.append('s.customer_id=?')
            params.append(customer_id)
        return self.db.rows("SELECT s.*,COALESCE((SELECT SUM(amount) FROM payments p WHERE p.sale_id=s.id AND p.purpose='SALE_RECEIPT' AND p.voided_at IS NULL),0) AS paid,COALESCE((SELECT SUM(quantity) FROM sale_items WHERE sale_id=s.id),0) AS quantity,COALESCE((SELECT SUM(total) FROM returns r WHERE r.original_sale_id=s.id AND r.status='POSTED'),0) AS returned FROM sales s WHERE " + ' AND '.join(clauses) + ' ORDER BY s.transaction_date DESC,s.id DESC LIMIT ? OFFSET ?', (*params, limit, offset))

    def details(self, identity):
        header = self.db.one('SELECT * FROM sales WHERE id=?', (identity,))
        items = self.db.rows("SELECT i.*,COALESCE((SELECT SUM(r.quantity) FROM return_items r JOIN returns h ON h.id=r.return_id WHERE r.original_sale_item_id=i.id AND h.status='POSTED'),0) AS returned_quantity FROM sale_items i WHERE i.sale_id=? ORDER BY i.id", (identity,))
        payments = self.db.rows('SELECT p.*,a.name AS account FROM payments p JOIN accounts a ON a.id=p.account_id WHERE p.sale_id=? ORDER BY p.id', (identity,))
        return header, items, payments

    def void(self, identity, reason=''):
        reason = text(reason, 'Action details', limit=2000) or 'Sale entry undone'
        with self.db.connect(write=True) as c:
            sale = require(c, 'sales', identity)
            if sale['data_origin'] == 'EXCEL_MIGRATION':
                raise BusinessError('Historical source records need a migration correction. Use a dated balance or stock correction instead of voiding imported evidence.')
            if sale['status'] != 'POSTED':
                raise BusinessError('This invoice is already void.')
            if c.execute("SELECT 1 FROM returns WHERE original_sale_id=? AND status='POSTED'", (identity,)).fetchone():
                raise BusinessError('This invoice has a return. Correct the return first.')
            for a in c.execute('SELECT a.* FROM stock_allocations a JOIN sale_items i ON i.id=a.sale_item_id WHERE i.sale_id=?', (identity,)).fetchall():
                move(c, a['purchase_item_id'], sale['transaction_date'], a['quantity'], 'VOID_SALE', identity)
            c.execute("UPDATE sales SET status='VOID',voided_at=?,void_reason=? WHERE id=?", (timestamp(), reason, identity))
            c.execute('UPDATE payments SET voided_at=?,void_reason=? WHERE sale_id=? AND voided_at IS NULL', (timestamp(), reason, identity))
            audit(c, 'VOID', 'sale', identity, reason)
