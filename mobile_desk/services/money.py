from mobile_desk.database import audit
from mobile_desk.services.common import require, remember, payment
from mobile_desk.values import BusinessError, business_date, decimal, money, text, timestamp, today


class MoneyService:
    def __init__(self, db):
        self.db = db

    def accounts(self, active_only=False):
        return self.db.rows('SELECT a.*,COALESCE((SELECT SUM(amount) FROM money_ledger WHERE account_id=a.id),0) AS balance FROM accounts a ' + ('WHERE active=1 ' if active_only else '') + 'ORDER BY a.id')

    def account(self, name, account_type='BANK', opening='0', day='1900-01-01', *, account_id=None, active=True, negative_opening=False):
        name = text(name, 'Account name', True)
        business_date(day)
        if account_type not in ('CASH', 'BANK'):
            raise BusinessError('Choose Cash or Bank.')
        value = money(opening) * (-1 if negative_opening else 1)
        with self.db.connect(write=True) as c:
            if c.execute('SELECT id FROM accounts WHERE name=? AND id!=?', (name, account_id or 0)).fetchone():
                raise BusinessError('An account already has that name.')
            if account_id:
                original = c.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone()
                if not original:
                    raise BusinessError('Account not found.')
                activity=c.execute("SELECT 1 FROM money_ledger WHERE account_id=? AND kind!='OPENING' LIMIT 1",(account_id,)).fetchone()
                if activity and (value!=original['opening_balance'] or day!=original['opening_date']):
                    raise BusinessError('This account already has transactions. Its opening balance and date are preserved.')
                c.execute('UPDATE accounts SET name=?,active=?,opening_balance=?,opening_date=? WHERE id=?', (name, int(active), value, day, account_id))
            else:
                account_id = c.execute('INSERT INTO accounts(name,account_type,opening_balance,opening_date,active) VALUES(?,?,?,?,?)', (name, account_type, value, day, int(active))).lastrowid
            audit(c, 'SAVE', 'account', account_id)
            return account_id

    def collect(self, party_id, day, account_id, amount, reference='', notes='', key=None):
        business_date(day)
        value = money(amount, 'Payment', True)
        payload = dict(party_id=party_id, day=day, account_id=account_id, amount=amount, reference=reference, notes=notes)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            require(c, 'parties', party_id, 'is_customer')
            identity = payment(c, day, account_id, value, 'CUSTOMER_PAYMENT', party_id=party_id, reference=reference, notes=notes)
            audit(c, 'POST', 'payment', identity)
            remember(c, key, payload, identity)
            return identity

    def expense(self, day, description, amount, account_id, category='', notes='', key=None):
        business_date(day)
        value = money(amount, 'Expense', True)
        description = text(description, 'Description', True)
        payload = dict(day=day, description=description, amount=amount, account_id=account_id, category=category, notes=notes)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            account = require(c, 'accounts', account_id)
            if day < account['opening_date']:
                raise BusinessError('Expense date is before the account opening date.')
            identity = c.execute('INSERT INTO expenses(transaction_date,description,amount,account_id,category,notes,created_at) VALUES(?,?,?,?,?,?,?)', (day, description, value, account_id, text(category), text(notes, limit=2000), timestamp())).lastrowid
            audit(c, 'POST', 'expense', identity)
            remember(c, key, payload, identity)
            return identity

    def pay_supplier(self,party_id,day,account_id,amount,reference='',notes='',key=None):
        business_date(day)
        value=money(amount,'Supplier payment',True)
        payload=dict(party_id=party_id,day=day,account_id=account_id,amount=amount,reference=reference,notes=notes,role='SUPPLIER')
        with self.db.connect(write=True) as c:
            prior=remember(c,key,payload)
            if prior:
                return prior
            require(c,'parties',party_id,'is_supplier')
            identity=payment(c,day,account_id,value,'PURCHASE_PAYMENT',party_id=party_id,reference=reference,notes=notes)
            audit(c,'POST_SUPPLIER_PAYMENT','payment',identity)
            remember(c,key,payload,identity)
            return identity

    def pay_carry(self,purchase_id,day,account_id,amount,notes='',key=None):
        business_date(day)
        value=money(amount,'Carry payment',True)
        payload=dict(purchase_id=purchase_id,day=day,account_id=account_id,amount=amount,notes=notes,role='NONE')
        with self.db.connect(write=True) as c:
            prior=remember(c,key,payload)
            if prior:
                return prior
            batch=require(c,'purchase_batches',purchase_id)
            if batch['status']!='POSTED' or batch['purchase_type']=='OPENING' or batch['carry_billed_to_supplier'] or batch['shipment_status'] in ('CANCELLED','RETURNED'):
                raise BusinessError('Separate transport payment is not available for this purchase.')
            if day<batch['transaction_date']:
                raise BusinessError('Payment date cannot be before the purchase.')
            if value>self._carry_remaining(c,purchase_id):
                raise BusinessError('Payment cannot exceed the remaining transport / carry cost.')
            identity=payment(c,day,account_id,value,'PURCHASE_PAYMENT',purchase_id=purchase_id,reference=batch['reference'],notes=notes or 'Transport / carry cost payment',ledger_role='NONE')
            audit(c,'POST_CARRY_PAYMENT','payment',identity)
            remember(c,key,payload,identity)
            return identity

    @staticmethod
    def _carry_remaining(c,purchase_id):
        total=c.execute('SELECT COALESCE(SUM(quantity*additional_cost_per_unit),0) FROM purchase_items WHERE purchase_batch_id=?',(purchase_id,)).fetchone()[0]
        returned=c.execute('SELECT COALESCE(SUM(stock_cost-supplier_credit),0) FROM purchase_returns WHERE purchase_batch_id=?',(purchase_id,)).fetchone()[0]
        paid=c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE purchase_batch_id=? AND ledger_role='NONE' AND voided_at IS NULL",(purchase_id,)).fetchone()[0]
        refunded=c.execute("SELECT COALESCE(SUM(f.amount),0) FROM purchase_refunds f JOIN purchase_returns r ON r.id=f.purchase_return_id WHERE r.purchase_batch_id=? AND f.payer_kind='CARRIER'",(purchase_id,)).fetchone()[0]
        return max(0,total-returned-paid+refunded)

    def carry_remaining(self,purchase_id):
        with self.db.connect() as c:
            batch=require(c,'purchase_batches',purchase_id)
            if batch['status']!='POSTED' or batch['purchase_type']=='OPENING' or batch['carry_billed_to_supplier'] or batch['shipment_status'] in ('CANCELLED','RETURNED'):
                return 0
            return self._carry_remaining(c,purchase_id)

    def transfer(self, day, from_account, to_account, amount, reference='', notes='', key=None):
        business_date(day)
        value = money(amount, 'Transfer', True)
        if from_account == to_account:
            raise BusinessError('Choose two different accounts.')
        payload = dict(day=day, from_account=from_account, to_account=to_account, amount=amount, reference=reference, notes=notes)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            for account_id in (from_account, to_account):
                account = require(c, 'accounts', account_id)
                if day < account['opening_date']:
                    raise BusinessError('Transfer date is before an account opening date.')
            identity = c.execute('INSERT INTO account_transfers(transaction_date,from_account,to_account,amount,reference,notes,created_at) VALUES(?,?,?,?,?,?,?)', (day, from_account, to_account, value, text(reference), text(notes, limit=2000), timestamp())).lastrowid
            audit(c, 'POST', 'transfer', identity)
            remember(c, key, payload, identity)
            return identity

    def void(self, kind, identity, reason=''):
        table = {'payment': 'payments', 'expense': 'expenses', 'transfer': 'account_transfers', 'adjustment': 'party_adjustments'}.get(kind)
        if table is None:
            raise BusinessError('Unsupported correction.')
        reason = text(reason, 'Action details', limit=2000) or kind.replace('_',' ').title()+' entry undone'
        with self.db.connect(write=True) as c:
            row = c.execute(f'SELECT * FROM {table} WHERE id=?', (identity,)).fetchone()
            if not row or row['voided_at']:
                raise BusinessError('This record is missing or already void.')
            if row['data_origin']=='EXCEL_MIGRATION':
                raise BusinessError('Imported history is preserved. Enter a dated correction with source notes instead of voiding the migration record.')
            if table == 'payments' and not (row['purpose']=='CUSTOMER_PAYMENT' or (row['purpose']=='PURCHASE_PAYMENT' and (row['purchase_batch_id'] is None or row['ledger_role']=='NONE'))):
                raise BusinessError('Correct this payment through its original sale, purchase or return.')
            if table=='payments' and row['purpose']=='PURCHASE_PAYMENT':
                if row['purchase_batch_id'] is not None and c.execute('SELECT 1 FROM purchase_returns WHERE purchase_batch_id=? LIMIT 1',(row['purchase_batch_id'],)).fetchone():
                    raise BusinessError('This purchase has a return or cancellation. Keep its original payments and use the recorded refund history.')
                if row['purchase_batch_id'] is None and row['ledger_role']=='SUPPLIER' and c.execute("SELECT 1 FROM purchase_refunds f JOIN purchase_returns r ON r.id=f.purchase_return_id JOIN purchase_batches b ON b.id=r.purchase_batch_id WHERE b.supplier_id=? AND f.payer_kind='SUPPLIER' LIMIT 1",(row['party_id'],)).fetchone():
                    raise BusinessError('This supplier has confirmed refund history. Keep its original payments so the refunded amounts remain supported.')
            c.execute(f'UPDATE {table} SET voided_at=?,void_reason=? WHERE id=?', (timestamp(), reason, identity))
            audit(c, 'VOID', kind, identity, reason)

    def rates(self):
        return self.db.rows('SELECT * FROM exchange_rate_history ORDER BY transaction_date DESC,id DESC LIMIT 200')

    def add_rate(self, day, rate, notes=''):
        business_date(day)
        rate = str(decimal(rate, 'Exchange rate', True))
        with self.db.connect(write=True) as c:
            identity = c.execute('INSERT INTO exchange_rate_history(transaction_date,rate,notes) VALUES(?,?,?)', (day, rate, text(notes))).lastrowid
            audit(c, 'ADD', 'exchange_rate', identity)
            return identity

    def save_settings(self, **values):
        allowed = {'shop_name', 'shop_phone', 'shop_address', 'invoice_prefix', 'next_invoice', 'setup_complete', 'backup_folder'}
        if set(values) - allowed:
            raise BusinessError('Unknown setting.')
        if 'next_invoice' in values:
            try:
                sequence = int(values['next_invoice'])
                if not 1 <= sequence <= 999999999:
                    raise ValueError
            except (ValueError, TypeError):
                raise BusinessError('Invoice sequence must be a positive whole number.') from None
        with self.db.connect(write=True) as c:
            for key, value in values.items():
                c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, text(value, key, key in ('shop_name', 'invoice_prefix'))))
            audit(c, 'SAVE', 'settings', 'shop')
