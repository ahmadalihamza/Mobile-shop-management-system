"""Undo saved transactions using the existing audited reversal rules."""
from mobile_desk.values import BusinessError


class CorrectionService:
    def __init__(self, ctx):
        self.ctx = ctx

    def latest(self):
        # Audit IDs establish save order even when entries share one timestamp.
        return self.ctx.db.one('''SELECT * FROM (
            SELECT a.id audit_id,'sale' kind,s.id,s.invoice_number reference,s.transaction_date,s.total amount
              FROM audit_log a JOIN sales s ON CAST(s.id AS TEXT)=a.entity_id
              WHERE a.action='POST' AND a.entity='sale' AND s.status='POSTED'
            UNION ALL SELECT a.id,'purchase',p.id,p.reference,p.transaction_date,p.total
              FROM audit_log a JOIN purchase_batches p ON CAST(p.id AS TEXT)=a.entity_id
              WHERE a.action='POST' AND a.entity='purchase' AND p.status='POSTED'
            UNION ALL SELECT a.id,'return',r.id,'R-'||r.id,r.transaction_date,r.total
              FROM audit_log a JOIN returns r ON CAST(r.id AS TEXT)=a.entity_id
              WHERE a.action='POST' AND a.entity='return' AND r.status='POSTED'
            UNION ALL SELECT a.id,'payment',p.id,'PAY-'||p.id,p.transaction_date,p.amount
              FROM audit_log a JOIN payments p ON CAST(p.id AS TEXT)=a.entity_id
              WHERE a.action IN('POST','POST_SUPPLIER_PAYMENT','POST_CARRY_PAYMENT')
                AND a.entity='payment' AND p.voided_at IS NULL
            UNION ALL SELECT a.id,'expense',e.id,'EXP-'||e.id,e.transaction_date,e.amount
              FROM audit_log a JOIN expenses e ON CAST(e.id AS TEXT)=a.entity_id
              WHERE a.action='POST' AND a.entity='expense' AND e.voided_at IS NULL
            UNION ALL SELECT a.id,'transfer',t.id,'TR-'||t.id,t.transaction_date,t.amount
              FROM audit_log a JOIN account_transfers t ON CAST(t.id AS TEXT)=a.entity_id
              WHERE a.action='POST' AND a.entity='transfer' AND t.voided_at IS NULL
            UNION ALL SELECT a.id,'adjustment',p.id,'ADJ-'||p.id,p.transaction_date,ABS(p.amount)
              FROM audit_log a JOIN party_adjustments p ON CAST(p.id AS TEXT)=a.entity_id
              WHERE a.action='POST' AND a.entity='adjustment' AND p.voided_at IS NULL
            ) ORDER BY audit_id DESC LIMIT 1''')

    def undo_latest(self, audit_id, reason='', **credentials):
        entry = self.latest()
        if not entry or entry['audit_id'] != audit_id:
            raise BusinessError('The latest saved entry has changed. Review it again before undoing.')
        self.undo(entry['kind'], entry['id'], reason,**credentials)
        return entry

    def undo(self, kind, identity, reason='', **credentials):
        if kind=='purchase':
            return self.ctx.purchases.void(identity,reason,**credentials)
        handler = {'sale':self.ctx.sales.void, 'purchase':self.ctx.purchases.void,
                   'return':self.ctx.returns.void}.get(kind)
        if handler:
            handler(identity, reason)
        else:
            self.ctx.money.void(kind, identity, reason)
