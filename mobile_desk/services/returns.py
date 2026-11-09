from mobile_desk.database import audit
from mobile_desk.services.common import require, payment, remember
from mobile_desk.services.stock import chronological, move
from mobile_desk.values import BusinessError, business_date, quantity, money, text, timestamp


class ReturnService:
    def __init__(self, db):
        self.db = db

    def post(self, day, sale_id, lines, *, refund='0', account_id=None, notes='', key=None):
        business_date(day)
        if not lines:
            raise BusinessError('Select at least one item to return.')
        refund_value = money(refund, 'Refund')
        payload = dict(day=day, sale_id=sale_id, lines=lines, refund=refund, account_id=account_id, notes=notes)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            sale = require(c, 'sales', sale_id)
            if c.execute('SELECT 1 FROM sale_items WHERE sale_id=? AND cogs_known=0', (sale_id,)).fetchone():
                raise BusinessError('This invoice has no verified cost allocation. Correct its stock costs before processing a return.')
            if sale['status'] != 'POSTED' or day < sale['transaction_date']:
                raise BusinessError('Choose a posted invoice and a return date on or after the sale.')
            prepared, seen, total = [], set(), 0
            for line in lines:
                item = require(c, 'sale_items', line['sale_item_id'])
                qty = quantity(line['quantity'])
                if item['sale_id'] != sale_id or item['id'] in seen:
                    raise BusinessError('Each returned line must appear once and belong to the selected invoice.')
                seen.add(item['id'])
                returned = c.execute("SELECT COALESCE(SUM(i.quantity),0) FROM return_items i JOIN returns r ON r.id=i.return_id WHERE i.original_sale_item_id=? AND r.status='POSTED'", (item['id'],)).fetchone()[0]
                if qty + returned > item['quantity']:
                    raise BusinessError('Return quantity exceeds the unreturned quantity on this invoice.')
                chronological(c, item['product_id'], day)
                prepared.append((item, qty))
                total += qty * item['selling_rate']
            if refund_value > total:
                raise BusinessError('Refund cannot exceed the returned value.')
            if not sale['customer_id'] and refund_value != total:
                raise BusinessError('A walk-in return must be refunded in full.')
            if refund_value and not account_id:
                raise BusinessError('Choose the account paying the refund.')
            identity = c.execute('INSERT INTO returns(transaction_date,customer_id,customer_snapshot,original_sale_id,total,cogs_reversed,notes,created_at) VALUES(?,?,?,?,?,0,?,?)', (day, sale['customer_id'], sale['customer_snapshot'], sale_id, total, text(notes, limit=2000), timestamp())).lastrowid
            all_cost = 0
            for item, qty in prepared:
                return_item = c.execute('INSERT INTO return_items(return_id,product_id,original_sale_item_id,quantity,return_rate,line_total,cogs_reversed,product_description_snapshot) VALUES(?,?,?,?,?,?,0,?)', (identity, item['product_id'], item['id'], qty, item['selling_rate'], qty*item['selling_rate'], item['product_description_snapshot'])).lastrowid
                allocations = c.execute("SELECT a.*,COALESCE((SELECT SUM(ra.quantity) FROM return_allocations ra JOIN return_items ri ON ri.id=ra.return_item_id JOIN returns r ON r.id=ri.return_id WHERE ra.stock_allocation_id=a.id AND r.status='POSTED'),0) AS returned FROM stock_allocations a WHERE a.sale_item_id=? ORDER BY a.id", (item['id'],)).fetchall()
                left, cost = qty, 0
                for a in allocations:
                    take = min(left, a['quantity']-a['returned'])
                    if take:
                        c.execute('INSERT INTO return_allocations(return_item_id,stock_allocation_id,quantity,unit_cost) VALUES(?,?,?,?)', (return_item, a['id'], take, a['unit_cost']))
                        move(c, a['purchase_item_id'], day, take, 'RETURN', return_item)
                        cost += take * a['unit_cost']
                        left -= take
                    if not left:
                        break
                if left:
                    raise BusinessError('Original cost allocations are incomplete. The return was not saved.')
                c.execute('UPDATE return_items SET cogs_reversed=? WHERE id=?', (cost, return_item))
                all_cost += cost
            c.execute('UPDATE returns SET cogs_reversed=? WHERE id=?', (all_cost, identity))
            if refund_value:
                payment(c, day, account_id, refund_value, 'RETURN_REFUND', party_id=sale['customer_id'], return_id=identity, reference=f'R-{identity}')
            audit(c, 'POST', 'return', identity)
            remember(c, key, payload, identity)
            return identity

    def void(self, identity, reason=''):
        reason = text(reason, 'Action details', limit=2000) or 'Customer return entry undone'
        with self.db.connect(write=True) as c:
            ret = require(c, 'returns', identity)
            if ret['data_origin'] == 'EXCEL_MIGRATION':
                raise BusinessError('Imported returns require a migration correction; their source history is preserved.')
            for item in c.execute('SELECT * FROM return_items WHERE return_id=? AND stock_lot_id IS NOT NULL',(identity,)).fetchall():
                lot=c.execute('SELECT * FROM lot_stock WHERE id=?',(item['stock_lot_id'],)).fetchone()
                if lot['remaining_quantity']<item['quantity'] or c.execute("SELECT 1 FROM stock_allocations a JOIN sale_items si ON si.id=a.sale_item_id JOIN sales s ON s.id=si.sale_id WHERE a.purchase_item_id=? AND s.status='POSTED'",(lot['id'],)).fetchone():
                    raise BusinessError('Returned stock was used by a later sale. Correct that sale first.')
                move(c,lot['id'],ret['transaction_date'],-item['quantity'],'VOID_UNLINKED_RETURN',identity)
                c.execute("UPDATE purchase_batches SET status='VOID',voided_at=?,void_reason=? WHERE id=?",(timestamp(),reason,lot['purchase_batch_id']))
            if ret['status'] != 'POSTED':
                raise BusinessError('This return is already void.')
            lines = c.execute('SELECT ra.*,a.purchase_item_id,pi.product_id FROM return_allocations ra JOIN return_items ri ON ri.id=ra.return_item_id JOIN stock_allocations a ON a.id=ra.stock_allocation_id JOIN purchase_items pi ON pi.id=a.purchase_item_id WHERE ri.return_id=?', (identity,)).fetchall()
            required_by_lot={}
            for line in lines:
                # Voided dependents no longer block reversing the preceding return.
                later = c.execute("""SELECT 1 FROM stock_movements m JOIN purchase_items p ON p.id=m.purchase_item_id
                    WHERE p.product_id=? AND m.created_at>? AND (
                      (m.kind='PURCHASE' AND EXISTS(SELECT 1 FROM purchase_batches b WHERE b.id=m.reference_id AND b.status='POSTED')) OR
                      (m.kind='SALE' AND EXISTS(SELECT 1 FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE i.id=m.reference_id AND s.status='POSTED')) OR
                      (m.kind='RETURN' AND EXISTS(SELECT 1 FROM return_items i JOIN returns r ON r.id=i.return_id WHERE i.id=m.reference_id AND r.status='POSTED' AND r.id!=?))) LIMIT 1""", (line['product_id'], ret['created_at'], identity)).fetchone()
                if later:
                    raise BusinessError('Stock has changed since this return. Correct the later transactions first.')
                lot=line['purchase_item_id']
                required_by_lot[lot]=required_by_lot.get(lot,0)+line['quantity']
            for lot,needed in required_by_lot.items():
                available = c.execute('SELECT remaining_quantity FROM lot_stock WHERE id=?', (lot,)).fetchone()[0]
                if available < needed:
                    raise BusinessError('The returned stock is no longer available.')
            for line in lines:
                move(c, line['purchase_item_id'], ret['transaction_date'], -line['quantity'], 'VOID_RETURN', identity)
            c.execute("UPDATE returns SET status='VOID',voided_at=?,void_reason=? WHERE id=?", (timestamp(), reason, identity))
            c.execute('UPDATE payments SET voided_at=?,void_reason=? WHERE return_id=? AND voided_at IS NULL', (timestamp(), reason, identity))
            audit(c, 'VOID', 'return', identity, reason)
