from decimal import Decimal
from mobile_desk.database import Database, audit
from mobile_desk.services.common import require, payment, remember, check_line_total
from mobile_desk.services.stock import chronological, move
from mobile_desk.values import BusinessError, business_date, decimal, money, quantity, rounded_paisa, text, timestamp


def price_line(line: dict, purchase_type: str, default_rate='1', default_carry='0', default_carry_currency='PKR', default_carry_basis='PER_UNIT') -> dict:
    qty = quantity(line['quantity'])
    carry_currency = line.get('carry_currency', default_carry_currency)
    if carry_currency not in ('PKR','CNY') or (carry_currency=='CNY' and purchase_type!='CHINA_IMPORT'):
        raise BusinessError('RMB carry is only available for China imports; local purchases use PKR.')
    if purchase_type == 'CHINA_IMPORT':
        foreign = decimal(line['unit_price'], 'RMB price')
        rate = decimal(line.get('exchange_rate', default_rate), 'Exchange rate', True)
        unit = rounded_paisa(foreign * rate)
    else:
        foreign, rate = None, None
        unit = money(line['unit_price'], 'Purchase price')
    basis=line.get('carry_basis',default_carry_basis)
    if basis not in ('PER_UNIT','STACK_TOTAL'):
        raise BusinessError('Choose carry for the whole stack or per piece.')
    entered_carry=decimal(line.get('carry',default_carry),'Carry',places=6 if carry_currency=='CNY' else 2)
    converted=rounded_paisa(entered_carry*rate) if carry_currency=='CNY' else money(str(entered_carry),'Carry')
    carry_total=converted if basis=='STACK_TOTAL' else qty*converted
    # Preserve every paisa of a stack charge. If it cannot be divided equally,
    # adjacent cost lots differ by one paisa; original stack input stays intact.
    lower,extra=divmod(carry_total,qty)
    allocations=[]
    for count,per_piece in ((qty-extra,lower),(extra,lower+1)):
        if count:
            allocations.append(dict(quantity=count,additional_cost_per_unit=per_piece,landed_unit_cost=unit+per_piece,line_total_cost=count*(unit+per_piece)))
    carry=int((Decimal(carry_total)/qty).quantize(Decimal('1'),rounding='ROUND_HALF_UP'))
    foreign_carry=(entered_carry/qty if basis=='STACK_TOTAL' else entered_carry) if carry_currency=='CNY' else None
    total = qty*unit+carry_total
    check_line_total(total)
    return dict(quantity=qty, foreign_unit_price=str(foreign) if foreign is not None else None, exchange_rate_snapshot=str(rate) if rate is not None else None, pkr_unit_purchase_cost=unit, additional_cost_per_unit=carry, landed_unit_cost=unit+carry, line_total_cost=total,carry_currency=carry_currency,foreign_carry_per_unit=str(foreign_carry) if foreign_carry is not None else None,carry_basis=basis,carry_input=str(entered_carry),additional_cost_total=carry_total,allocations=allocations)


class PurchaseService:
    def __init__(self, db: Database, security=None):
        self.db = db
        if security is None:
            from mobile_desk.services.security import SecurityService
            security=SecurityService(db.path.parent.parent)
        self.security=security

    def post(self, day, lines, *, purchase_type='LOCAL', supplier_id=None, reference='', default_rate='1', default_carry='0', payments=(), notes='', legacy_reference='', key=None, carry_billed_to_supplier=False, carry_payment='0', carry_account_id=None,carry_currency='PKR',received=True,carry_basis='PER_UNIT'):
        business_date(day)
        if purchase_type not in ('LOCAL', 'CHINA_IMPORT', 'OPENING') or not lines:
            raise BusinessError('Select the purchase type and add at least one product.')
        if purchase_type=='OPENING' and not received:
            raise BusinessError('Opening stock must be physically present.')
        prepared = [price_line(line, purchase_type, default_rate, default_carry,carry_currency,carry_basis) for line in lines]
        total = sum(p['line_total_cost'] for p in prepared)
        check_line_total(total)
        additional = sum(p['additional_cost_total'] for p in prepared)
        supplier_total = 0 if purchase_type=='OPENING' else total-(0 if carry_billed_to_supplier else additional)
        carry_paid = money(carry_payment, 'Additional cost paid')
        if carry_paid and (carry_billed_to_supplier or carry_paid>additional or purchase_type=='OPENING'):
            raise BusinessError('Separate carry payment must not exceed carry costs, and cannot also be billed by the supplier.')
        pays = [(p['account_id'], money(p['amount'], 'Payment', True)) for p in payments]
        if sum(p[1] for p in pays) > supplier_total:
            raise BusinessError('Purchase payment cannot exceed the supplier bill.')
        payload = dict(day=day, lines=lines, purchase_type=purchase_type, supplier_id=supplier_id, reference=reference, default_rate=default_rate, default_carry=default_carry, payments=list(payments), notes=notes, legacy_reference=legacy_reference,carry_billed_to_supplier=carry_billed_to_supplier,carry_payment=carry_payment,carry_account_id=carry_account_id,carry_currency=carry_currency,received=received,carry_basis=carry_basis)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            supplier = require(c, 'parties', supplier_id, 'is_supplier')['name'] if supplier_id else ''
            ref = text(reference, 'Batch reference') or 'P-' + str(c.execute('SELECT COALESCE(MAX(id),0)+1 FROM purchase_batches').fetchone()[0]).zfill(6)
            if c.execute('SELECT 1 FROM purchase_batches WHERE reference=?', (ref,)).fetchone():
                raise BusinessError('That batch reference already exists. Choose a different reference.')
            currency = 'CNY' if purchase_type == 'CHINA_IMPORT' else 'PKR'
            default_rate_value = str(decimal(default_rate, 'Exchange rate', True)) if currency == 'CNY' else None
            default_carry_pkr=rounded_paisa(decimal(default_carry)*decimal(default_rate)) if carry_currency=='CNY' else money(default_carry)
            identity = c.execute('INSERT INTO purchase_batches(reference,transaction_date,purchase_type,supplier_id,supplier_snapshot,currency,default_exchange_rate,default_additional_cost,total,notes,legacy_reference,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (ref, day, purchase_type, supplier_id, supplier, currency, default_rate_value, default_carry_pkr, total, text(notes, limit=2000), text(legacy_reference), timestamp())).lastrowid
            c.execute('UPDATE purchase_batches SET supplier_total=?,carry_billed_to_supplier=?,default_carry_currency=?,shipment_status=?,received_date=? WHERE id=?',(supplier_total,int(carry_billed_to_supplier),carry_currency,'RECEIVED' if received else 'IN_TRANSIT',day if received else None,identity))
            for line, cost in zip(lines, prepared):
                product = require(c, 'products', line['product_id'])
                if received:
                    chronological(c, product['id'], day)
                stack=c.execute('INSERT INTO purchase_stacks(purchase_batch_id,product_id,quantity,carry_basis,carry_currency,carry_input,total_carry_cost,line_total_cost,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(identity,product['id'],cost['quantity'],cost['carry_basis'],cost['carry_currency'],cost['carry_input'],cost['additional_cost_total'],cost['line_total_cost'],timestamp())).lastrowid
                for allocation in cost['allocations']:
                    lot = c.execute('INSERT INTO purchase_items(purchase_batch_id,product_id,quantity,original_currency,foreign_unit_price,exchange_rate_snapshot,pkr_unit_purchase_cost,additional_cost_per_unit,landed_unit_cost,line_total_cost,product_description_snapshot,created_at,carry_currency,foreign_carry_per_unit,stack_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (identity, product['id'], allocation['quantity'], currency, cost['foreign_unit_price'], cost['exchange_rate_snapshot'], cost['pkr_unit_purchase_cost'], allocation['additional_cost_per_unit'], allocation['landed_unit_cost'], allocation['line_total_cost'], product['custom_name'], timestamp(),cost['carry_currency'],cost['foreign_carry_per_unit'],stack)).lastrowid
                    if received:
                        move(c, lot, day, allocation['quantity'], 'PURCHASE', identity)
            for account, value in pays:
                payment(c, day, account, value, 'PURCHASE_PAYMENT', party_id=supplier_id, purchase_id=identity, reference=ref)
            if carry_paid:
                payment(c,day,carry_account_id,carry_paid,'PURCHASE_PAYMENT',purchase_id=identity,reference=ref,notes='Separate carry / additional cost payment',ledger_role='NONE')
            audit(c, 'POST', 'purchase', identity)
            if purchase_type!='OPENING':
                c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('last_purchase_type',purchase_type))
                c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('last_purchase_supplier',str(supplier_id or '')))
            remember(c, key, payload, identity)
            return identity

    def receive(self,identity,day):
        business_date(day)
        with self.db.connect(write=True) as c:
            batch=require(c,'purchase_batches',identity)
            if batch['status']!='POSTED' or batch['shipment_status']!='IN_TRANSIT':
                raise BusinessError('Only a shipment awaiting arrival can be marked received.')
            if day<batch['transaction_date']:
                raise BusinessError('Arrival date cannot precede the purchase date.')
            last_return=c.execute('SELECT MAX(transaction_date) FROM purchase_returns WHERE purchase_batch_id=?',(identity,)).fetchone()[0]
            if last_return and day<last_return:
                raise BusinessError('Arrival date cannot precede an existing cancellation or return dated '+last_return+'.')
            for lot in c.execute('SELECT * FROM purchase_items WHERE purchase_batch_id=?',(identity,)).fetchall():
                returned=c.execute('SELECT COALESCE(SUM(quantity),0) FROM purchase_return_items WHERE purchase_item_id=?',(lot['id'],)).fetchone()[0]
                remaining=lot['quantity']-returned
                if remaining:
                    chronological(c,lot['product_id'],day)
                    move(c,lot['id'],day,remaining,'RECEIVE_PURCHASE',identity)
            c.execute("UPDATE purchase_batches SET shipment_status='RECEIVED',received_date=? WHERE id=?",(day,identity))
            audit(c,'RECEIVE','purchase',identity,'Shipment physically received on '+day)
            return identity

    def list(self, start='1900-01-01', end='9999-12-31', query='', kind='', supplier_id=None, limit=200, offset=0):
        clauses = ['transaction_date BETWEEN ? AND ?', '(reference LIKE ? OR supplier_snapshot LIKE ? OR legacy_reference LIKE ? OR EXISTS(SELECT 1 FROM purchase_items i WHERE i.purchase_batch_id=purchase_batches.id AND i.product_description_snapshot LIKE ?))']
        params = [start, end, '%'+query+'%', '%'+query+'%', '%'+query+'%', '%'+query+'%']
        if kind:
            clauses.append('purchase_type=?')
            params.append(kind)
        if supplier_id:
            clauses.append('supplier_id=?')
            params.append(supplier_id)
        return self.db.rows("""SELECT purchase_batches.*,
            COALESCE((SELECT GROUP_CONCAT(product_description_snapshot, '; ')
                FROM (SELECT product_description_snapshot FROM purchase_items
                      WHERE purchase_batch_id=purchase_batches.id
                      GROUP BY product_description_snapshot ORDER BY MIN(id))), '') AS product_names
            FROM purchase_batches WHERE """ + ' AND '.join(clauses) + ' ORDER BY transaction_date DESC,id DESC LIMIT ? OFFSET ?', (*params, limit, offset))

    def details(self, identity):
        return self.db.one('SELECT * FROM purchase_batches WHERE id=?', (identity,)), self.db.rows('SELECT * FROM lot_stock WHERE purchase_batch_id=? ORDER BY id', (identity,))

    def stacks(self,identity):
        return self.db.rows('SELECT s.*,COALESCE((SELECT product_description_snapshot FROM purchase_items WHERE stack_id=s.id LIMIT 1),p.custom_name) product_description_snapshot FROM purchase_stacks s JOIN products p ON p.id=s.product_id WHERE s.purchase_batch_id=? ORDER BY s.id',(identity,))

    def void(self, identity, reason='', *, username='', password=''):
        self.security.authorize(username,password)
        reason = text(reason, 'Action details', limit=2000) or 'Purchase entry undone'
        with self.db.connect(write=True) as c:
            batch = require(c, 'purchase_batches', identity)
            if batch['data_origin'] == 'EXCEL_MIGRATION':
                raise BusinessError('Historical batches retain their original source costs. Resolve their stock in Stock & Products instead of voiding them.')
            if batch['status'] != 'POSTED':
                raise BusinessError('This batch is already void.')
            if c.execute('SELECT 1 FROM purchase_returns WHERE purchase_batch_id=?',(identity,)).fetchone():
                raise BusinessError('This purchase has return history. Use Stock Return / Purchase Cancellation instead of undoing its original records.')
            lots = c.execute('SELECT * FROM lot_stock WHERE purchase_batch_id=?', (identity,)).fetchall()
            for lot in lots:
                allocations = c.execute("SELECT 1 FROM stock_allocations a JOIN sale_items i ON i.id=a.sale_item_id JOIN sales s ON s.id=i.sale_id WHERE a.purchase_item_id=? AND s.status='POSTED'", (lot['id'],)).fetchone()
                if allocations or lot['remaining_quantity'] != (lot['quantity'] if batch['shipment_status']=='RECEIVED' else 0):
                    raise BusinessError('This batch has stock used by a posted sale. Correct the dependent sale first.')
            for lot in lots:
                if lot['remaining_quantity']:
                    move(c, lot['id'], batch['received_date'] or batch['transaction_date'], -lot['quantity'], 'VOID_PURCHASE', identity)
            c.execute("UPDATE purchase_batches SET status='VOID',voided_at=?,void_reason=? WHERE id=?", (timestamp(), reason, identity))
            c.execute('UPDATE payments SET voided_at=?,void_reason=? WHERE purchase_batch_id=? AND voided_at IS NULL', (timestamp(), reason, identity))
            audit(c, 'VOID', 'purchase', identity, 'Owner '+self.security.username+': '+reason)
