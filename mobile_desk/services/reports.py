"""Database-derived reports. Monetary SQL aggregation uses integers only."""
from decimal import Decimal, ROUND_HALF_UP
from mobile_desk.values import business_date, today
from mobile_desk.services.parties import PartyService
from mobile_desk.services.stock import StockService


class ReportService:
    def __init__(self, db):
        self.db = db

    def period_profit(self, start, end):
        business_date(start)
        business_date(end)
        all_history=start=='1900-01-01' and end=='9999-12-31'
        sale_date='' if all_history else " AND s.date_basis!='UNKNOWN'"
        return_date='' if all_history else " AND date_basis!='UNKNOWN'"
        sale = self.db.one("SELECT COALESCE(SUM(i.line_total),0) revenue,COALESCE(SUM(i.cogs),0) cogs,COALESCE(SUM(i.quantity),0) quantity FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE s.status='POSTED' AND s.transaction_date BETWEEN ? AND ?"+sale_date, (start, end))
        ret = self.db.one("SELECT COALESCE(SUM(total),0) revenue,COALESCE(SUM(cogs_reversed),0) cogs FROM returns WHERE status='POSTED' AND transaction_date BETWEEN ? AND ?"+return_date, (start, end))
        expenses = self.db.one('SELECT COALESCE(SUM(amount),0) value FROM expenses WHERE voided_at IS NULL AND transaction_date BETWEEN ? AND ?', (start, end))['value']
        discounts = -self.db.one("SELECT COALESCE(SUM(amount),0) value FROM party_adjustments WHERE voided_at IS NULL AND ledger_role='CUSTOMER' AND adjustment_type='DISCOUNT' AND transaction_date BETWEEN ? AND ?", (start, end))['value']
        # Returning stock removes its capitalized cost. Only the part credited by
        # the supplier remains recoverable; external carry is a loss until its
        # actual refund is confirmed. Supplier refunds settle an asset/balance,
        # and are never sales revenue or profit.
        purchase_return_loss = self.db.one('SELECT COALESCE(SUM(stock_cost-supplier_credit),0) value FROM purchase_returns WHERE transaction_date BETWEEN ? AND ?', (start, end))['value']
        carry_refunds = self.db.one("SELECT COALESCE(SUM(amount),0) value FROM purchase_refunds WHERE payer_kind='CARRIER' AND transaction_date BETWEEN ? AND ?", (start, end))['value']
        revenue, cogs = sale['revenue']-ret['revenue'], sale['cogs']-ret['cogs']
        unknown_sale = self.db.one("SELECT COALESCE(SUM(i.line_total),0) value FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE s.status='POSTED' AND i.cogs_known=0 AND s.transaction_date BETWEEN ? AND ?"+sale_date, (start,end))['value']
        ret_alias=return_date.replace('date_basis','r.date_basis')
        unknown_return = self.db.one("SELECT COALESCE(SUM(i.line_total),0) value FROM return_items i JOIN returns r ON r.id=i.return_id WHERE r.status='POSTED' AND i.cogs_known=0 AND r.transaction_date BETWEEN ? AND ?"+ret_alias, (start,end))['value']
        incomplete = self.db.one("SELECT COUNT(*) n FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE s.status='POSTED' AND i.cogs_known=0 AND s.transaction_date BETWEEN ? AND ?"+sale_date, (start,end))['n'] or self.db.one("SELECT COUNT(*) n FROM return_items i JOIN returns r ON r.id=i.return_id WHERE r.status='POSTED' AND i.cogs_known=0 AND r.transaction_date BETWEEN ? AND ?"+ret_alias, (start,end))['n']
        return dict(sales_before_returns=sale['revenue'], returns=ret['revenue'], net_sales=revenue, cogs=None if incomplete else cogs, gross_profit=None if incomplete else revenue-cogs, recorded_expenses=expenses, discounts=discounts, purchase_return_cost_loss=purchase_return_loss, carry_refunds_received=carry_refunds, profit_after_expenses=None if incomplete else revenue-cogs-expenses-discounts-purchase_return_loss+carry_refunds, sales_with_unresolved_cost=unknown_sale, returns_with_unresolved_cost=unknown_return)

    def sales_summary(self, start, end, monthly=False):
        base = "substr(transaction_date,1,7)" if monthly else 'transaction_date'
        period = "CASE WHEN date_basis='UNKNOWN' THEN 'Date unknown' ELSE "+base+" END"
        rows = self.db.rows(f"SELECT {period} period,COALESCE(SUM(total),0) sales,COUNT(*) invoices FROM sales WHERE status='POSTED' AND transaction_date BETWEEN ? AND ? GROUP BY period ORDER BY period", (start, end))
        piece_period="CASE WHEN s.date_basis='UNKNOWN' THEN 'Date unknown' ELSE "+('substr(s.transaction_date,1,7)' if monthly else 's.transaction_date')+' END'
        pieces = {r['period']: r['quantity'] for r in self.db.rows(f"SELECT {piece_period} period,SUM(i.quantity) quantity FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE s.status='POSTED' AND s.transaction_date BETWEEN ? AND ? GROUP BY period", (start, end))}
        payment_rows = self.db.rows(f"SELECT {period} period,SUM(CASE WHEN purpose='SALE_RECEIPT' THEN amount ELSE 0 END) receipts,SUM(CASE WHEN purpose='CUSTOMER_PAYMENT' THEN amount ELSE 0 END) collections FROM payments WHERE voided_at IS NULL AND transaction_date BETWEEN ? AND ? GROUP BY period", (start, end))
        by_period = {r['period']: r for r in rows}
        for p in payment_rows:
            by_period.setdefault(p['period'], dict(period=p['period'], sales=0, invoices=0)).update(receipts=p['receipts'], collections=p['collections'])
        for r in self.db.rows(f"SELECT {period} period,SUM(total) amount FROM returns WHERE status='POSTED' AND transaction_date BETWEEN ? AND ? GROUP BY period", (start, end)):
            by_period.setdefault(r['period'], dict(period=r['period'], sales=0, invoices=0))['returns'] = r['amount']
        for key, r in by_period.items():
            r.update(quantity=pieces.get(key, 0), receipts=r.get('receipts', 0), collections=r.get('collections', 0), returns=r.get('returns', 0))
            known = self.db.one("SELECT COALESCE(SUM(total),0) value FROM sales WHERE status='POSTED' AND settlement_status='KNOWN' AND transaction_date BETWEEN ? AND ? AND (" + period + ")=?", (start,end,key))['value']
            r['credit_sales'] = known-r['receipts']
            r['unresolved_settlement'] = r['sales']-known
            r['net_sales'] = r['sales']-r['returns']
        return sorted(by_period.values(), key=lambda r: r['period'])

    def product_sales(self, start, end, product_id=None):
        extra, args = (' AND i.product_id=?', (start, end, product_id)) if product_id else ('', (start, end))
        sale_date='' if start=='1900-01-01' and end=='9999-12-31' else " AND s.date_basis!='UNKNOWN'"
        extra=sale_date+extra
        sales = self.db.rows("SELECT i.product_id,p.custom_name,SUM(i.quantity) quantity,SUM(i.line_total) sales,SUM(i.cogs) cogs FROM sale_items i JOIN sales s ON s.id=i.sale_id JOIN products p ON p.id=i.product_id WHERE s.status='POSTED' AND s.transaction_date BETWEEN ? AND ?" + extra + ' GROUP BY i.product_id ORDER BY p.custom_name', args)
        returns = self.db.rows("SELECT i.product_id,p.custom_name,SUM(i.quantity) quantity,SUM(i.line_total) amount,SUM(i.cogs_reversed) cogs FROM return_items i JOIN returns r ON r.id=i.return_id JOIN products p ON p.id=i.product_id WHERE r.status='POSTED' AND r.transaction_date BETWEEN ? AND ?" + extra.replace('s.date_basis','r.date_basis') + ' GROUP BY i.product_id', args)
        by_product = {r['product_id']: r for r in sales}
        for ret in returns:
            r = by_product.setdefault(ret['product_id'], dict(product_id=ret['product_id'], custom_name=ret['custom_name'], quantity=0, sales=0, cogs=0))
            r.update(returned_quantity=ret['quantity'], return_amount=ret['amount'], return_cogs=ret['cogs'])
        for r in by_product.values():
            r['average_rate'] = int((Decimal(r['sales'])/r['quantity']).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if r['quantity'] else None
            r['returned_quantity'] = r.get('returned_quantity', 0)
            r['return_amount'] = r.get('return_amount', 0)
            r['net_quantity'] = r['quantity']-r['returned_quantity']
            r['net_sales'] = r['sales']-r['return_amount']
            r['net_cogs'] = r['cogs']-r.get('return_cogs', 0)
            r['gross_profit'] = r['net_sales']-r['net_cogs']
        unknown = {x['product_id'] for x in self.db.rows("SELECT DISTINCT i.product_id FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE i.cogs_known=0 AND s.status='POSTED' AND s.transaction_date BETWEEN ? AND ?"+sale_date+" UNION SELECT DISTINCT i.product_id FROM return_items i JOIN returns r ON r.id=i.return_id WHERE i.cogs_known=0 AND r.status='POSTED' AND r.transaction_date BETWEEN ? AND ?"+sale_date.replace('s.date_basis','r.date_basis'),(start,end,start,end))}
        for identity in unknown:
            if identity in by_product:
                by_product[identity].update(net_cogs=None,gross_profit=None)
        return list(by_product.values())

    def outstanding(self, end='9999-12-31'):
        return self.db.rows('SELECT p.id,p.name,p.phone,p.balance_basis,COALESCE(SUM(l.amount),0) balance FROM parties p LEFT JOIN party_ledger l ON l.party_id=p.id AND l.transaction_date<=? WHERE p.is_customer=1 GROUP BY p.id HAVING balance!=0 ORDER BY balance DESC', (end,))

    def supplier_outstanding(self,end='9999-12-31'):
        return self.db.rows('SELECT p.id,p.name,p.phone,COALESCE(SUM(l.amount),0) balance FROM parties p LEFT JOIN supplier_ledger l ON l.party_id=p.id AND l.transaction_date<=? WHERE p.is_supplier=1 GROUP BY p.id HAVING balance!=0 ORDER BY balance DESC',(end,))

    def cash_summary(self, start, end):
        return self.db.rows('SELECT a.id,a.name,COALESCE(SUM(CASE WHEN m.transaction_date<? THEN m.amount ELSE 0 END),0) opening,COALESCE(SUM(CASE WHEN m.transaction_date BETWEEN ? AND ? AND m.amount>0 THEN m.amount ELSE 0 END),0) received,COALESCE(SUM(CASE WHEN m.transaction_date BETWEEN ? AND ? AND m.amount<0 THEN -m.amount ELSE 0 END),0) paid_out,COALESCE(SUM(CASE WHEN m.transaction_date<=? THEN m.amount ELSE 0 END),0) closing FROM accounts a LEFT JOIN money_ledger m ON m.account_id=a.id GROUP BY a.id', (start, start, end, start, end, end))

    def daily_money(self, start, end):
        return self.db.rows('SELECT m.transaction_date,a.name,SUM(CASE WHEN m.amount>0 THEN m.amount ELSE 0 END) received,SUM(CASE WHEN m.amount<0 THEN -m.amount ELSE 0 END) paid_out,SUM(m.amount) net_change FROM money_ledger m JOIN accounts a ON a.id=m.account_id WHERE m.transaction_date BETWEEN ? AND ? GROUP BY m.transaction_date,a.id ORDER BY m.transaction_date,a.name', (start, end))

    def purchase_history(self, start, end, china=False):
        rows = self.db.rows("SELECT CASE WHEN b.date_label!='' THEN b.date_label ELSE b.transaction_date END transaction_date,b.reference,b.supplier_snapshot,b.purchase_type,b.shipment_status,i.id cost_lot_id,i.stack_id,COALESCE(s.carry_basis,'PER_UNIT') carry_basis,s.carry_input,i.product_description_snapshot,i.quantity,i.foreign_unit_price,i.total_foreign_cost,i.exchange_rate_snapshot,i.pkr_unit_purchase_cost,i.additional_cost_per_unit,i.carry_currency,i.foreign_carry_per_unit,i.landed_unit_cost,i.line_total_cost,l.remaining_quantity,i.inventory_status,COALESCE(r.returned_quantity,0) returned_quantity,COALESCE(r.returned_stock_cost,0) returned_stock_cost,COALESCE(r.supplier_credit,0) supplier_credit FROM purchase_items i JOIN purchase_batches b ON b.id=i.purchase_batch_id JOIN lot_stock l ON l.id=i.id LEFT JOIN purchase_stacks s ON s.id=i.stack_id LEFT JOIN (SELECT purchase_item_id,SUM(quantity) returned_quantity,SUM(stock_cost) returned_stock_cost,SUM(supplier_credit) supplier_credit FROM purchase_return_items GROUP BY purchase_item_id) r ON r.purchase_item_id=i.id WHERE b.status='POSTED' AND b.transaction_date BETWEEN ? AND ?" + (" AND b.purchase_type='CHINA_IMPORT'" if china else '') + ' ORDER BY b.transaction_date,b.id,i.id', (start, end))
        # Keep each entered stack together when exact carry allocation creates
        # two internal cost lots differing by one paisa.
        grouped={}
        fields=('quantity','line_total_cost','remaining_quantity','returned_quantity','returned_stock_cost','supplier_credit')
        for row in rows:
            key=('stack',row['stack_id']) if row['stack_id'] else ('lot',row['cost_lot_id'])
            if key not in grouped:
                grouped[key]={**row,**{field:0 for field in fields},'total_carry_cost':0}
            group=grouped[key]
            for field in fields:
                group[field]+=row[field]
            group['total_carry_cost']+=row['quantity']*row['additional_cost_per_unit']
        rows=list(grouped.values())
        for row in rows:
            row['additional_cost_per_unit']=int((Decimal(row['total_carry_cost'])/row['quantity']).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            row['landed_unit_cost']=int((Decimal(row['line_total_cost'])/row['quantity']).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            row['net_quantity'] = row['quantity']-row['returned_quantity']
            row['net_stock_cost'] = row['line_total_cost']-row['returned_stock_cost']
        return rows

    def returns(self, start, end, customer_id=None):
        return self.db.rows("SELECT r.id,CASE WHEN r.date_label!='' THEN r.date_label ELSE r.transaction_date END transaction_date,COALESCE(s.invoice_number,'Historical / unlinked') invoice_number,r.customer_snapshot,r.total,CASE WHEN EXISTS(SELECT 1 FROM return_items i WHERE i.return_id=r.id AND cogs_known=0) THEN NULL ELSE r.cogs_reversed END cogs_reversed,r.status,r.notes FROM returns r LEFT JOIN sales s ON s.id=r.original_sale_id WHERE r.transaction_date BETWEEN ? AND ?"+(' AND r.customer_id=?' if customer_id else '')+" ORDER BY r.transaction_date DESC,r.id DESC", (start, end,*((customer_id,) if customer_id else ())))

    def dashboard(self, day=None):
        day = day or today()
        daily = next(iter(self.sales_summary(day, day)), dict(sales=0, quantity=0, receipts=0, collections=0, credit_sales=0, returns=0, net_sales=0))
        balances = self.outstanding()
        return dict(today=daily, month=self.period_profit(day[:8]+'01', day), stock=StockService(self.db).totals(), receivable=sum(max(r['balance'], 0) for r in balances),customer_credit=sum(max(-r['balance'],0) for r in balances),payable=sum(max(r['balance'],0) for r in self.supplier_outstanding()))

    def recent(self):
        return self.db.rows("SELECT * FROM (SELECT 'Sale' kind,transaction_date,invoice_number reference,customer_snapshot description,total amount,created_at FROM sales WHERE status='POSTED' UNION ALL SELECT 'Purchase',transaction_date,reference,supplier_snapshot,total,created_at FROM purchase_batches WHERE status='POSTED' UNION ALL SELECT 'Collection',transaction_date,'PAY-'||id,party_snapshot,amount,created_at FROM payments WHERE purpose='CUSTOMER_PAYMENT' AND voided_at IS NULL UNION ALL SELECT 'Return',transaction_date,'R-'||id,customer_snapshot,total,created_at FROM returns WHERE status='POSTED' UNION ALL SELECT CASE WHEN r.kind='CANCELLATION' THEN 'Purchase cancellation' ELSE 'Stock return' END,r.transaction_date,'PR-'||r.id,b.reference||' · '||b.supplier_snapshot,r.supplier_credit,r.created_at FROM purchase_returns r JOIN purchase_batches b ON b.id=r.purchase_batch_id UNION ALL SELECT CASE WHEN f.payer_kind='SUPPLIER' THEN 'Supplier refund' ELSE 'Carry refund' END,f.transaction_date,COALESCE(NULLIF(f.reference,''),'PREF-'||f.id),b.reference||' · '||b.supplier_snapshot,f.amount,f.created_at FROM purchase_refunds f JOIN purchase_returns r ON r.id=f.purchase_return_id JOIN purchase_batches b ON b.id=r.purchase_batch_id) ORDER BY created_at DESC LIMIT 12")
