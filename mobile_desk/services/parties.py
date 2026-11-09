from mobile_desk.database import Database, audit
from mobile_desk.services.common import require
from mobile_desk.values import BusinessError, business_date, money, normalize, text, timestamp


class PartyService:
    def __init__(self, db: Database):
        self.db = db

    def save(self, name, *, party_id=None, is_customer=True, is_supplier=False, phone='', address='', notes='', active=True):
        name = text(name, 'Party name', True)
        if not is_customer and not is_supplier:
            raise BusinessError('Choose Customer, Supplier, or both.')
        with self.db.connect(write=True) as c:
            existing = c.execute('SELECT * FROM parties WHERE id=?', (party_id,)).fetchone() if party_id else None
            if party_id and not existing:
                raise BusinessError('Party not found.')
            # Older shops can contain duplicate accounts. Keep their history editable,
            # but never create another duplicate or rename an account into one.
            if not existing or normalize(name) != existing['normalized_name']:
                duplicate = c.execute('SELECT name FROM parties WHERE normalized_name=? AND id!=? LIMIT 1',
                                      (normalize(name), party_id or 0)).fetchone()
                if duplicate:
                    raise BusinessError(f'A contact named "{duplicate["name"]}" already exists. Choose it from the existing contacts list. If it is inactive or needs another role, edit that contact. For a different business, use a distinct name, such as its location.')
            vals = (name, normalize(name), int(is_customer), int(is_supplier), text(phone), text(address), text(notes, limit=2000), int(active))
            if party_id:
                if not is_customer and any(c.execute(query,(party_id,)).fetchone() for query in (
                    'SELECT 1 FROM sales WHERE customer_id=? LIMIT 1',
                    'SELECT 1 FROM payments WHERE party_id=? AND purpose IN (\'CUSTOMER_PAYMENT\',\'SALE_RECEIPT\',\'RETURN_REFUND\') LIMIT 1',
                    "SELECT 1 FROM party_adjustments WHERE party_id=? AND ledger_role='CUSTOMER' LIMIT 1",
                )):
                    raise BusinessError('Keep the Customer role for a party with customer history. You can deactivate the party instead.')
                if not is_supplier and any(c.execute(query,(party_id,)).fetchone() for query in (
                    'SELECT 1 FROM purchase_batches WHERE supplier_id=? LIMIT 1',
                    "SELECT 1 FROM payments WHERE party_id=? AND ledger_role='SUPPLIER' LIMIT 1",
                    "SELECT 1 FROM party_adjustments WHERE party_id=? AND ledger_role='SUPPLIER' LIMIT 1",
                )):
                    raise BusinessError('Keep the Supplier role for a supplier with purchases or payments. Deactivate it instead.')
                c.execute('UPDATE parties SET name=?,normalized_name=?,is_customer=?,is_supplier=?,phone=?,address=?,notes=?,active=? WHERE id=?', (*vals, party_id))
            else:
                party_id = c.execute('INSERT INTO parties(name,normalized_name,is_customer,is_supplier,phone,address,notes,active,created_at) VALUES(?,?,?,?,?,?,?,?,?)', (*vals, timestamp())).lastrowid
            audit(c, 'SAVE', 'party', party_id)
            return party_id

    def search(self, query='', role=None, limit=200, offset=0, active_only=False):
        clauses, params = ['1=1'], []
        if role in ('is_customer', 'is_supplier'):
            clauses.append(role + '=1')
        elif role == 'both':
            clauses.append('is_customer=1 AND is_supplier=1')
        if active_only:
            clauses.append('active=1')
        for token in normalize(query).split():
            clauses.append("(instr(replace(normalized_name,' ',''),?)>0 OR instr(phone,?)>0)")
            params.extend([token, token])
        return self.db.rows('SELECT p.*,(SELECT COUNT(*) FROM parties other WHERE other.normalized_name=p.normalized_name) AS name_count,COALESCE((SELECT SUM(amount) FROM party_ledger WHERE party_id=p.id),0) AS balance,COALESCE((SELECT SUM(amount) FROM supplier_ledger WHERE party_id=p.id),0) AS supplier_balance FROM parties p WHERE ' + ' AND '.join(clauses) + ' ORDER BY name,id LIMIT ? OFFSET ?', (*params, limit, offset))

    @staticmethod
    def ledger(role):
        if role not in ('CUSTOMER','SUPPLIER'):
            raise BusinessError('Choose Customer or Supplier.')
        return 'supplier_ledger' if role=='SUPPLIER' else 'party_ledger'

    def balance(self, party_id, until='9999-12-31', *, role='CUSTOMER') -> int:
        return self.db.one('SELECT COALESCE(SUM(amount),0) AS value FROM '+self.ledger(role)+' WHERE party_id=? AND transaction_date<=?', (party_id, until))['value']

    def adjustment(self, party_id, day, kind, amount, reason='', *, opening_credit=False, role='CUSTOMER'):
        business_date(day)
        reason = text(reason, 'Action details', limit=2000) or {'OPENING_BALANCE':'Opening balance entered','DISCOUNT':'Agreed discount recorded','MANUAL_CREDIT':'Balance reduced','MANUAL_DEBIT':'Balance increased'}.get(kind,'Balance adjusted')
        value = money(amount, positive=True)
        if kind not in ('OPENING_BALANCE', 'DISCOUNT', 'MANUAL_CREDIT', 'MANUAL_DEBIT'):
            raise BusinessError('Choose a valid balance adjustment.')
        self.ledger(role)
        if role=='SUPPLIER' and kind=='DISCOUNT':
            raise BusinessError('Correct a supplier invoice through its purchase; do not change saved stock costs with a discount.')
        if kind in ('DISCOUNT', 'MANUAL_CREDIT') or (kind == 'OPENING_BALANCE' and opening_credit):
            value = -value
        with self.db.connect(write=True) as c:
            require(c, 'parties', party_id, 'is_supplier' if role=='SUPPLIER' else 'is_customer')
            identity = c.execute('INSERT INTO party_adjustments(party_id,transaction_date,adjustment_type,amount,reason,created_at,ledger_role) VALUES(?,?,?,?,?,?,?)', (party_id, day, kind, value, reason, timestamp(),role)).lastrowid
            audit(c, 'ADJUST', 'party', party_id, reason)
            audit(c, 'POST', 'adjustment', identity, reason)
            return identity

    def statement(self, party_id, start='1900-01-01', end='9999-12-31', *, role='CUSTOMER'):
        ledger=self.ledger(role)
        opening = self.db.one('SELECT COALESCE(SUM(amount),0) AS value FROM '+ledger+' WHERE party_id=? AND transaction_date<?', (party_id, start))['value']
        rows = self.db.rows('SELECT * FROM '+ledger+' WHERE party_id=? AND transaction_date BETWEEN ? AND ? ORDER BY transaction_date,created_at,kind,source_id', (party_id, start, end))
        result = [dict(transaction_date=start, reference='', description='Balance brought forward', added=max(opening, 0), reduction=max(-opening, 0), balance=opening)]
        for r in rows:
            opening += r['amount']
            result.append(dict(transaction_date=r['date_label'] or r['transaction_date'], reference=r['reference'], description=r['description'].replace('_', ' ').title(), added=max(r['amount'], 0), reduction=max(-r['amount'], 0), balance=opening))
        return result

    def documents(self,party_id,until='9999-12-31',*,role='CUSTOMER'):
        """Current outstanding: linked receipts/returns stay with their document;
        on-account payments and advances reduce the oldest remaining debit.
        Original receipts and invoice snapshots are never rewritten.
        """
        ledger=self.ledger(role)
        kind='PURCHASE' if role=='SUPPLIER' else 'SALE'
        rows=self.db.rows('SELECT * FROM '+ledger+' WHERE party_id=? AND transaction_date<=? ORDER BY transaction_date,created_at,kind,source_id',(party_id,until))
        buckets={}
        for r in rows:
            if r['kind'] in (kind,'ADJUSTMENT') and r['amount']>0:
                buckets[(r['kind'],r['source_id'])]=dict(transaction_date=r['transaction_date'],reference=r['reference'],description=r['description'],original_amount=r['amount'],outstanding=r['amount'],created_at=r['created_at'])
        payments={r['id']:r for r in self.db.rows('SELECT * FROM payments WHERE party_id=? AND ledger_role=? AND voided_at IS NULL AND transaction_date<=?',(party_id,role,until))}
        returns={r['id']:r for r in self.db.rows("SELECT * FROM returns WHERE customer_id=? AND status='POSTED' AND transaction_date<=?",(party_id,until))} if role=='CUSTOMER' else {}
        purchase_returns={r['id']:r for r in self.db.rows('SELECT r.* FROM purchase_returns r JOIN purchase_batches b ON b.id=r.purchase_batch_id WHERE b.supplier_id=? AND r.transaction_date<=?',(party_id,until))} if role=='SUPPLIER' else {}
        purchase_refunds={r['id']:r for r in self.db.rows("SELECT f.id,r.purchase_batch_id FROM purchase_refunds f JOIN purchase_returns r ON r.id=f.purchase_return_id JOIN purchase_batches b ON b.id=r.purchase_batch_id WHERE b.supplier_id=? AND f.payer_kind='SUPPLIER' AND f.transaction_date<=?",(party_id,until))} if role=='SUPPLIER' else {}
        credit=0
        for r in rows:
            if (r['kind'],r['source_id']) in buckets:
                continue
            target=None
            if r['kind']=='PAYMENT':
                p=payments[r['source_id']]
                identity=p['purchase_batch_id'] if role=='SUPPLIER' else p['sale_id']
                if role=='CUSTOMER' and p['return_id'] in returns:
                    identity=returns[p['return_id']]['original_sale_id']
                target=(kind,identity)
            elif r['kind']=='RETURN':
                target=(kind,returns[r['source_id']]['original_sale_id'])
            elif r['kind']=='PURCHASE_RETURN':
                target=(kind,purchase_returns[r['source_id']]['purchase_batch_id'])
            elif r['kind']=='PURCHASE_REFUND':
                target=(kind,purchase_refunds[r['source_id']]['purchase_batch_id'])
            if target in buckets:
                buckets[target]['outstanding']+=r['amount']
            elif r['amount']<0:
                credit-=r['amount']
            elif r['amount']>0:
                buckets[(r['kind'],r['source_id'])]=dict(transaction_date=r['transaction_date'],reference=r['reference'],description=r['description'],original_amount=r['amount'],outstanding=r['amount'],created_at=r['created_at'])
        for b in buckets.values():
            if b['outstanding']<0:
                credit-=b['outstanding']
                b['outstanding']=0
        ordered=sorted(buckets.values(),key=lambda b:(b['transaction_date'],b['created_at'],b['reference']))
        for b in ordered:
            applied=min(credit,b['outstanding'])
            b['outstanding']-=applied
            credit-=applied
            b['settled']=b['original_amount']-b['outstanding']
        return ordered
