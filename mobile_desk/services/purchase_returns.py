"""Owner-authorized purchase returns and confirmed incoming refunds.

Purchases, their saved cost snapshots and their original payments are immutable.
A return reduces stock and the supplier bill; cash only changes when a separate
refund is explicitly confirmed. All amounts stored or exposed here are paisa.
"""
import json

from mobile_desk.database import audit
from mobile_desk.services.common import check_line_total, remember, require
from mobile_desk.services.stock import chronological, move
from mobile_desk.values import BusinessError, business_date, money, quantity, text, timestamp


class PurchaseReturnService:
    def __init__(self, db, security):
        self.db = db
        self.security = security

    @staticmethod
    def _batch(c, purchase_id):
        batch = c.execute('SELECT * FROM purchase_batches WHERE id=?', (purchase_id,)).fetchone()
        if not batch:
            raise BusinessError('Choose an existing purchase shipment.')
        return dict(batch)

    @staticmethod
    def _return(c, return_id):
        row = c.execute('SELECT * FROM purchase_returns WHERE id=?', (return_id,)).fetchone()
        if not row:
            raise BusinessError('Choose an existing purchase return or cancellation.')
        return dict(row)

    @staticmethod
    def _lines(c, purchase_id):
        return [dict(row) for row in c.execute('''
            SELECT l.*,
                COALESCE((SELECT SUM(ri.quantity) FROM purchase_return_items ri
                          WHERE ri.purchase_item_id=l.id),0) AS returned_quantity
            FROM lot_stock l WHERE l.purchase_batch_id=? ORDER BY l.id
        ''', (purchase_id,))]

    @staticmethod
    def _enrich_lines(batch, lines):
        pending = batch['shipment_status'] == 'IN_TRANSIT'
        eligible = (batch['status'] == 'POSTED'
                    and batch['purchase_type'] != 'OPENING'
                    and batch['shipment_status'] in ('IN_TRANSIT', 'RECEIVED'))
        for line in lines:
            outstanding = line['quantity'] - line['returned_quantity']
            line['unreturned_quantity'] = max(0, outstanding)
            line['returnable_quantity'] = (max(0, outstanding if pending else min(outstanding, line['remaining_quantity']))
                                           if eligible else 0)
            line['remaining_returnable_quantity'] = line['returnable_quantity']
            line['supplier_credit_per_unit'] = line['pkr_unit_purchase_cost'] + (
                line['additional_cost_per_unit'] if batch['carry_billed_to_supplier'] else 0)
            line['external_carry_per_unit'] = (0 if batch['carry_billed_to_supplier']
                                                else line['additional_cost_per_unit'])
        return lines

    def preview(self, purchase_id):
        """Return one shipment, its eligible quantities, and preserved history."""
        with self.db.connect() as c:
            batch = self._batch(c, purchase_id)
            lines = self._enrich_lines(batch, self._lines(c, purchase_id))
            returns = self._list(c, purchase_id=purchase_id)
            refunds = self._refund_history(c, purchase_id=purchase_id)
            return dict(header=batch, purchase=batch, lines=lines, lots=lines,
                        returns=returns, refunds=refunds,
                        kind='CANCELLATION' if batch['shipment_status'] == 'IN_TRANSIT' else 'RETURN',
                        returnable_quantity=sum(row['returnable_quantity'] for row in lines))

    def post(self, purchase_id, day, lines, reason='', username='', password='', *,
             refund_amount='0', refund_account_id=None, refund_payer='SUPPLIER', key=None):
        """Return selected quantities and optionally confirm one actual refund."""
        self.security.authorize(username, password)
        owner = self.security.username
        business_date(day)
        reason = text(reason, 'Action details', limit=2000)
        refund_value = money(refund_amount, 'Confirmed refund')
        self._payer(refund_payer)
        if not lines:
            raise BusinessError('Select at least one purchase line and quantity to return.')
        payload = dict(operation='PURCHASE_RETURN', purchase_id=purchase_id, day=day,
                       lines=lines, reason=reason, owner=owner, refund_amount=refund_amount,
                       refund_account_id=refund_account_id, refund_payer=refund_payer)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            batch = self._batch(c, purchase_id)
            if batch['status'] != 'POSTED' or batch['shipment_status'] not in ('IN_TRANSIT', 'RECEIVED'):
                raise BusinessError('This purchase is already void, cancelled, or fully returned.')
            if batch['purchase_type'] == 'OPENING':
                raise BusinessError('Opening stock is not a supplier purchase and cannot be returned to a supplier.')
            if day < batch['transaction_date']:
                raise BusinessError('Return date cannot precede the purchase date.')
            pending = batch['shipment_status'] == 'IN_TRANSIT'
            if not pending and batch['received_date'] and day < batch['received_date']:
                raise BusinessError('Stock return date cannot precede the shipment arrival date.')
            latest = c.execute('SELECT MAX(transaction_date) FROM purchase_returns WHERE purchase_batch_id=?',
                               (purchase_id,)).fetchone()[0]
            if latest and day < latest:
                raise BusinessError('Use a return date on or after the previous return for this shipment.')
            available = {row['id']: row for row in self._enrich_lines(batch, self._lines(c, purchase_id))}
            prepared, seen = [], set()
            total_cost = total_credit = 0
            for line in lines:
                item_id = line.get('purchase_item_id')
                item = available.get(item_id)
                qty = quantity(line.get('quantity'))
                if item is None or item_id in seen:
                    raise BusinessError('Each returned line must appear once and belong to the selected purchase.')
                seen.add(item_id)
                if qty > item['unreturned_quantity']:
                    raise BusinessError('Return quantity exceeds the unreturned quantity on this purchase.')
                if not pending:
                    chronological(c, item['product_id'], day)
                    if qty > item['remaining_quantity']:
                        raise BusinessError('Some phones from this batch have been sold or used. Only stock still available can be returned.')
                cost = qty * item['landed_unit_cost']
                credit = qty * item['supplier_credit_per_unit']
                total_cost += cost
                total_credit += credit
                prepared.append((item, qty, cost, credit))
            check_line_total(total_cost)
            kind = 'CANCELLATION' if pending else 'RETURN'
            reason = reason or ('Shipment cancelled' if pending else 'Stock returned to supplier')
            identity = c.execute('''INSERT INTO purchase_returns(
                purchase_batch_id,transaction_date,kind,reason,owner_username,supplier_credit,stock_cost,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (purchase_id, day, kind, reason, owner, total_credit, total_cost, timestamp())).lastrowid
            for item, qty, cost, credit in prepared:
                c.execute('''INSERT INTO purchase_return_items(
                    return_id,purchase_item_id,quantity,stock_cost,supplier_credit) VALUES(?,?,?,?,?)''',
                    (identity, item['id'], qty, cost, credit))
                if not pending:
                    move(c, item['id'], day, -qty, 'PURCHASE_RETURN', identity)
            left = c.execute('''SELECT COALESCE(SUM(i.quantity),0) -
                COALESCE((SELECT SUM(ri.quantity) FROM purchase_return_items ri
                  JOIN purchase_returns r ON r.id=ri.return_id WHERE r.purchase_batch_id=?),0)
                FROM purchase_items i WHERE i.purchase_batch_id=?''', (purchase_id, purchase_id)).fetchone()[0]
            if not left:
                c.execute('UPDATE purchase_batches SET shipment_status=? WHERE id=?',
                          ('CANCELLED' if pending else 'RETURNED', purchase_id))
            audit(c, kind, 'purchase_return', identity, json.dumps(dict(
                owner_username=owner, reason=reason, purchase_batch_id=purchase_id,
                reference=batch['reference'], kind=kind,
                lines=[dict(purchase_item_id=item['id'], product=item['product_description_snapshot'],
                            quantity=qty, stock_cost=cost, supplier_credit=credit)
                       for item, qty, cost, credit in prepared],
                stock_cost=total_cost, supplier_credit=total_credit,
                confirmed_refund=refund_value, refund_account_id=refund_account_id if refund_value else None,
                refund_payer=refund_payer if refund_value else None), ensure_ascii=False, sort_keys=True))
            if refund_value:
                self._confirm_refund(c, identity, day, refund_account_id, refund_value, owner,
                                     refund_payer, '', 'Refund confirmed with the purchase return')
            remember(c, key, payload, identity)
            return identity

    @staticmethod
    def _payer(payer):
        if payer not in ('SUPPLIER', 'CARRIER'):
            raise BusinessError('Choose Supplier or Carrier as the refund payer.')

    @classmethod
    def _refund_limits(cls, c, return_id, day=None):
        ret = cls._return(c, return_id)
        batch = cls._batch(c, ret['purchase_batch_id'])
        day = day or '9999-12-31'
        already = {row['payer_kind']: row['amount'] for row in c.execute('''
            SELECT payer_kind,SUM(amount) AS amount FROM purchase_refunds
            WHERE purchase_return_id=? GROUP BY payer_kind''', (return_id,))}
        return_supplier_left = max(0, ret['supplier_credit']-already.get('SUPPLIER', 0))
        return_carrier_left = max(0, ret['stock_cost']-ret['supplier_credit']-already.get('CARRIER', 0))
        # A credit on a named supplier account can be refunded or used against
        # another purchase, never both. Check both dated and present balances.
        if batch['supplier_id']:
            current = c.execute('SELECT COALESCE(SUM(amount),0) FROM supplier_ledger WHERE party_id=?',
                                (batch['supplier_id'],)).fetchone()[0]
            dated = c.execute('''SELECT COALESCE(SUM(amount),0) FROM supplier_ledger
                WHERE party_id=? AND transaction_date<=?''', (batch['supplier_id'], day)).fetchone()[0]
            supplier_available = max(0, min(-current, -dated))
        else:
            # Anonymous purchases have no supplier ledger. Refund only money
            # actually paid on this purchase, excluding separate carry costs.
            supplier_paid = c.execute('''SELECT COALESCE(SUM(amount),0) FROM payments
                WHERE purchase_batch_id=? AND ledger_role='SUPPLIER' AND direction='OUT'
                  AND voided_at IS NULL AND transaction_date<=?''', (batch['id'], day)).fetchone()[0]
            supplier_refunded = c.execute('''SELECT COALESCE(SUM(f.amount),0)
                FROM purchase_refunds f JOIN purchase_returns r ON r.id=f.purchase_return_id
                WHERE r.purchase_batch_id=? AND f.payer_kind='SUPPLIER' ''', (batch['id'],)).fetchone()[0]
            supplier_available = max(0, supplier_paid-supplier_refunded)
        carrier_paid = c.execute('''SELECT COALESCE(SUM(amount),0) FROM payments
            WHERE purchase_batch_id=? AND ledger_role='NONE' AND direction='OUT'
              AND voided_at IS NULL AND transaction_date<=?''', (batch['id'], day)).fetchone()[0]
        carrier_refunded = c.execute('''SELECT COALESCE(SUM(f.amount),0)
            FROM purchase_refunds f JOIN purchase_returns r ON r.id=f.purchase_return_id
            WHERE r.purchase_batch_id=? AND f.payer_kind='CARRIER' ''', (batch['id'],)).fetchone()[0]
        return dict(supplier=min(return_supplier_left, supplier_available),
                    carrier=min(return_carrier_left, max(0, carrier_paid-carrier_refunded)),
                    supplier_credit_remaining=return_supplier_left,
                    external_carry_credit_remaining=return_carrier_left,
                    supplier_available_credit=supplier_available,
                    carrier_available_paid=max(0, carrier_paid-carrier_refunded))

    def refund_limits(self, return_id, day=None):
        if day:
            business_date(day)
        with self.db.connect() as c:
            return self._refund_limits(c, return_id, day)

    @classmethod
    def _confirm_refund(cls, c, return_id, day, account_id, amount, owner, payer, reference, notes):
        cls._payer(payer)
        ret = cls._return(c, return_id)
        batch = cls._batch(c, ret['purchase_batch_id'])
        if batch['status'] != 'POSTED':
            raise BusinessError('The original purchase is void. A refund cannot be recorded.')
        if day < ret['transaction_date']:
            raise BusinessError('Refund date cannot precede the return or cancellation date.')
        account = require(c, 'accounts', account_id)
        if day < account['opening_date']:
            raise BusinessError('Refund date cannot precede the account opening date.')
        limits = cls._refund_limits(c, return_id, day)
        allowed = limits['supplier' if payer == 'SUPPLIER' else 'carrier']
        if amount > allowed:
            if payer == 'SUPPLIER':
                raise BusinessError('Refund exceeds the unrefunded return credit or the supplier credit available. Unpaid bills are reduced without creating cash.')
            raise BusinessError('Carrier refund exceeds the returned carry cost or the carry amount actually paid for this shipment.')
        identity = c.execute('''INSERT INTO purchase_refunds(
            purchase_return_id,transaction_date,account_id,amount,payer_kind,owner_username,reference,notes,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)''', (return_id, day, account_id, amount, payer, owner,
            text(reference), text(notes, 'Refund notes', limit=2000), timestamp())).lastrowid
        audit(c, 'CONFIRM_PURCHASE_REFUND', 'purchase_refund', identity, json.dumps(dict(
            owner_username=owner, purchase_return_id=return_id, purchase_batch_id=batch['id'],
            account_id=account_id, amount=amount, payer_kind=payer, reference=reference, notes=notes),
            ensure_ascii=False, sort_keys=True))
        return identity

    def confirm_refund(self, return_id, day, account_id, amount, username, password, *,
                       payer='SUPPLIER', reference='', notes='', key=None):
        self.security.authorize(username, password)
        owner = self.security.username
        business_date(day)
        value = money(amount, 'Confirmed refund', True)
        self._payer(payer)
        reference = text(reference, 'Refund reference')
        notes = text(notes, 'Refund notes', limit=2000)
        payload = dict(operation='PURCHASE_REFUND', return_id=return_id, day=day,
                       account_id=account_id, amount=amount, owner=owner, payer=payer,
                       reference=reference, notes=notes)
        with self.db.connect(write=True) as c:
            prior = remember(c, key, payload)
            if prior:
                return prior
            identity = self._confirm_refund(c, return_id, day, account_id, value, owner, payer, reference, notes)
            remember(c, key, payload, identity)
            return identity

    @staticmethod
    def _list(c, *, purchase_id=None, start='1900-01-01', end='9999-12-31', query='', limit=200, offset=0):
        clauses = ['r.transaction_date BETWEEN ? AND ?',
                   '(b.reference LIKE ? OR b.supplier_snapshot LIKE ? OR r.reason LIKE ?)']
        params = [start, end, '%'+query+'%', '%'+query+'%', '%'+query+'%']
        if purchase_id is not None:
            clauses.append('r.purchase_batch_id=?')
            params.append(purchase_id)
        return [dict(row) for row in c.execute('''SELECT r.*,b.reference AS purchase_reference,
            b.supplier_snapshot,b.supplier_id,
            (SELECT COALESCE(SUM(i.quantity),0) FROM purchase_return_items i WHERE i.return_id=r.id) AS quantity,
            (SELECT COALESCE(SUM(f.amount),0) FROM purchase_refunds f WHERE f.purchase_return_id=r.id) AS refunded_amount
            FROM purchase_returns r JOIN purchase_batches b ON b.id=r.purchase_batch_id WHERE '''
            + ' AND '.join(clauses) + ' ORDER BY r.transaction_date DESC,r.id DESC LIMIT ? OFFSET ?',
            (*params, limit, offset))]

    def list(self, start='1900-01-01', end='9999-12-31', query='', *, purchase_id=None, limit=200, offset=0):
        with self.db.connect() as c:
            return self._list(c, purchase_id=purchase_id, start=start, end=end, query=query, limit=limit, offset=offset)

    @staticmethod
    def _refund_history(c, *, return_id=None, purchase_id=None):
        clauses, params = ['1=1'], []
        if return_id is not None:
            clauses.append('f.purchase_return_id=?')
            params.append(return_id)
        if purchase_id is not None:
            clauses.append('r.purchase_batch_id=?')
            params.append(purchase_id)
        return [dict(row) for row in c.execute('''SELECT f.*,a.name AS account_name,
            b.reference AS purchase_reference,r.purchase_batch_id FROM purchase_refunds f
            JOIN purchase_returns r ON r.id=f.purchase_return_id
            JOIN purchase_batches b ON b.id=r.purchase_batch_id JOIN accounts a ON a.id=f.account_id
            WHERE ''' + ' AND '.join(clauses) + ' ORDER BY f.transaction_date,f.id', params)]

    def refunds(self, return_id=None, *, purchase_id=None):
        with self.db.connect() as c:
            return self._refund_history(c, return_id=return_id, purchase_id=purchase_id)

    def details(self, return_id):
        with self.db.connect() as c:
            header = self._return(c, return_id)
            batch = self._batch(c, header['purchase_batch_id'])
            lines = [dict(row) for row in c.execute('''SELECT ri.*,i.product_id,
                i.product_description_snapshot,i.landed_unit_cost,i.additional_cost_per_unit,
                i.pkr_unit_purchase_cost FROM purchase_return_items ri
                JOIN purchase_items i ON i.id=ri.purchase_item_id WHERE ri.return_id=? ORDER BY ri.id''', (return_id,))]
            return dict(header=header, purchase=batch, lines=lines,
                        refunds=self._refund_history(c, return_id=return_id),
                        refund_limits=self._refund_limits(c, return_id))
