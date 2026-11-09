"""Read models used by list and detail screens."""


class ActivityService:
    def __init__(self,db):
        self.db=db

    def expenses(self,start,end,query='',limit=101,offset=0):
        return self.db.rows('SELECT e.*,a.name account FROM expenses e JOIN accounts a ON a.id=e.account_id WHERE transaction_date BETWEEN ? AND ? AND (description LIKE ? OR category LIKE ?) ORDER BY transaction_date DESC,e.id DESC LIMIT ? OFFSET ?',(start,end,'%'+query+'%','%'+query+'%',limit,offset))

    def transfers(self,start,end,query='',limit=101,offset=0):
        return self.db.rows('SELECT t.*,a.name source,b.name destination FROM account_transfers t JOIN accounts a ON a.id=t.from_account JOIN accounts b ON b.id=t.to_account WHERE transaction_date BETWEEN ? AND ? AND (reference LIKE ? OR a.name LIKE ? OR b.name LIKE ?) ORDER BY transaction_date DESC,t.id DESC LIMIT ? OFFSET ?',(start,end,'%'+query+'%','%'+query+'%','%'+query+'%',limit,offset))

    def payments(self,start,end,query='',limit=101,offset=0,party_id=None):
        return self.db.rows('SELECT p.*,a.name account FROM payments p JOIN accounts a ON a.id=p.account_id WHERE transaction_date BETWEEN ? AND ? AND (p.party_snapshot LIKE ? OR p.reference LIKE ?)'+(' AND party_id=?' if party_id else '')+' ORDER BY transaction_date DESC,p.id DESC LIMIT ? OFFSET ?',(start,end,'%'+query+'%','%'+query+'%',*((party_id,) if party_id else ()),limit,offset))

    def account_history(self,account_id,start='1900-01-01',end='9999-12-31',limit=1000):
        return self.db.rows('SELECT * FROM money_ledger WHERE account_id=? AND transaction_date BETWEEN ? AND ? ORDER BY transaction_date DESC,created_at DESC LIMIT ?',(account_id,start,end,limit))

    def product_history(self,product_id,limit=500):
        return self.db.rows('SELECT s.transaction_date,s.invoice_number,s.customer_snapshot,s.status,i.quantity,i.selling_rate,i.line_total,i.cogs,i.gross_profit FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE product_id=? ORDER BY s.transaction_date DESC,i.id DESC LIMIT ?',(product_id,limit))
