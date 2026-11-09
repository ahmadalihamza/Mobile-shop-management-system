import csv
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QFileDialog,QMessageBox,QLineEdit,QHeaderView
from mobile_desk.ui.common import label,button,date_edit,day,combo,DataTable,show_print,printable_table,refresh_party_combo,trading_label,confirm
from mobile_desk.values import currency,today,amount_text,normalize

REPORTS=['Daily Sales','Monthly Sales','Product Sales / Profit','Customer Outstanding','Customer Statement','Supplier Outstanding','Supplier Statement','Current Stock / Stock Value','Purchase History','China Batch / Landed Cost','Period Profit','Returns','Cash / Bank Period Summary']


def purchase_average(value):
    return '—' if value is None else currency(value)


class ReportPage(QWidget):
    def __init__(self,parent,ctx):
        super().__init__()
        self.host=parent
        self.ctx=ctx
        self.layout=QVBoxLayout(self)
        self.layout.setContentsMargins(26,22,26,20)
        self.layout.setSpacing(14)
        self.layout.addWidget(label('Reports','title'))
        self.layout.addWidget(label('Figures come from posted transactions. Amounts are in PKR unless a column is marked RMB.','subtitle',True))
        bar=QHBoxLayout()
        self.kind=QComboBox()
        self.kind.addItems(REPORTS)
        bar.addWidget(self.kind,1)
        self.start=date_edit(today()[:8]+'01')
        self.end=date_edit()
        bar.addWidget(label('From'))
        bar.addWidget(self.start)
        bar.addWidget(label('To'))
        bar.addWidget(self.end)
        bar.addWidget(button('Run report',self.refresh,True))
        self.layout.addLayout(bar)
        actions=QHBoxLayout()
        self.party=combo(ctx.parties.search(role='is_customer',limit=10000),optional='Choose customer')
        self.party.setEditable(True)
        self.party.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.party.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        actions.addWidget(self.party,1)
        self.search=QLineEdit()
        self.search.setPlaceholderText('Search product, contact or batch…')
        self.search.setClearButtonEnabled(True)
        actions.addWidget(self.search,1)
        self.search_timer=QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda:self.search_timer.start())
        actions.addWidget(button('Export CSV',self.export))
        actions.addWidget(button('Print / PDF',self.print_report))
        self.void_button=button('Undo selected return',self.void_return)
        actions.addWidget(self.void_button)
        self.layout.addLayout(actions)
        self.note=label('','subtitle',True)
        self.layout.addWidget(self.note)
        self.table=DataTable([])
        self.layout.addWidget(self.table,1)
        self.kind.currentTextChanged.connect(self.refresh)
        self.party.currentIndexChanged.connect(self.refresh)
        self.rows=[]
        self.columns=[]
        self.refresh()

    def refresh(self,*args):
        name=self.kind.currentText()
        supplier=name=='Supplier Statement'
        refresh_party_combo(self.party,self.ctx,'is_supplier' if supplier else 'is_customer','Choose supplier' if supplier else 'Choose customer')
        start,end=day(self.start),day(self.end)
        if end<start:
            self.note.setText('The end date must be on or after the start date.')
            return
        r=self.ctx.reports
        self.party.setVisible(name in ('Customer Statement','Supplier Statement'))
        searchable=name in ('Product Sales / Profit','Customer Outstanding','Supplier Outstanding','Current Stock / Stock Value','Purchase History','China Batch / Landed Cost','Returns')
        self.search.setVisible(searchable)
        self.void_button.setVisible(name=='Returns')
        self.start.setEnabled(name not in ('Customer Outstanding','Supplier Outstanding','Current Stock / Stock Value'))
        self.end.setEnabled(name!='Current Stock / Stock Value')
        self.note.setText('')
        if name in ('Daily Sales','Monthly Sales'):
            rows=r.sales_summary(start,end,name=='Monthly Sales')
            columns=[('period','Period'),('quantity','Pieces sold'),('sales','Sales',currency),('receipts','Paid at sale',currency),('credit_sales','Credit at sale',currency),('collections','Later collections',currency),('returns','Returns',currency),('net_sales','Net sales',currency)]
        elif name=='Product Sales / Profit':
            rows=r.product_sales(start,end)
            columns=[('custom_name','Product'),('quantity','Sold'),('sales','Sales',currency),('average_rate','Weighted rate',currency),('returned_quantity','Returned'),('net_sales','Net sales',currency),('net_cogs','Net cost',currency),('gross_profit','Gross profit',currency)]
            self.note.setText('Weighted selling rate = sale value ÷ sold pieces. Profit uses the original purchase costs allocated when each sale was saved.')
        elif name in ('Customer Outstanding','Supplier Outstanding'):
            rows=r.supplier_outstanding(end) if name=='Supplier Outstanding' else r.outstanding(end)
            columns=[('name','Supplier' if name=='Supplier Outstanding' else 'Customer'),('phone','Phone'),('balance','Balance PKR',currency)]
            self.note.setText('As of '+end+'. Positive balances are unpaid. Negative balances are advances / credit held.')
        elif name in ('Customer Statement','Supplier Statement'):
            selected=self.party.currentData() and self.party.currentText()==self.party.itemText(self.party.currentIndex())
            rows=self.ctx.parties.statement(self.party.currentData(),start,end,role='SUPPLIER' if supplier else 'CUSTOMER') if selected else []
            if not selected:
                self.note.setText('Search and choose a supplier from the list.' if supplier else 'Search and choose a customer from the list.')
            columns=[('transaction_date','Date'),('reference','Reference'),('description','Description'),('added','Added to balance',currency),('reduction','Payment / reduction',currency),('balance','Running balance',currency)]
        elif name=='Current Stock / Stock Value':
            rows=self.ctx.stock.current(limit=100000)
            columns=[('custom_name','Product'),('quantity','Pieces available'),('value','Stock cost PKR',currency),('average_purchase_price','Average Purchase Price (PKR)',purchase_average)]
            self.note.setText('Average Purchase Price = total landed purchase cost ÷ net purchased pieces across batches, including stock awaiting arrival and excluding supplier returns / cancellations. Sales do not change this purchase average. Available stock retains its actual remaining FIFO lot costs.')
        elif name in ('Purchase History','China Batch / Landed Cost'):
            rows=r.purchase_history(start,end,name=='China Batch / Landed Cost')
            columns=[('transaction_date','Date'),('reference','Batch'),('supplier_snapshot','Supplier'),('shipment_status','Shipment',trading_label),('product_description_snapshot','Product'),('quantity','Bought'),('returned_quantity','Returned / cancelled'),('net_quantity','Net purchased'),('foreign_unit_price','RMB / unit'),('exchange_rate_snapshot','PKR per RMB'),('pkr_unit_purchase_cost','PKR / unit',currency),('carry_currency','Carry currency',lambda v:'RMB' if v=='CNY' else v),('foreign_carry_per_unit','RMB carry / unit'),('additional_cost_per_unit','PKR carry / unit',currency),('landed_unit_cost','Landed / unit PKR',currency),('line_total_cost','Original cost PKR',currency),('net_stock_cost','Net purchase cost PKR',currency),('remaining_quantity','Available')]
            columns.insert(12,('carry_basis','Carry charged for',lambda v:'Whole stack' if v=='STACK_TOTAL' else 'Per piece (saved)'))
            columns.insert(13,('carry_input','Original carry charge'))
            columns.insert(14,('total_carry_cost','Total carry PKR',currency))
            self.note.setText('Each row is one recorded stack. Original carry charge uses Carry currency and Carry charged for; China entry uses the whole stack total. The converted total is allocated once across its pieces, with exact line totals. Per-piece costs are rounded for display. Net quantities exclude supplier returns / cancellations. Awaiting arrival is unavailable for sale.')
        elif name=='Period Profit':
            values=r.period_profit(start,end)
            rows=[dict(metric=k.replace('_',' ').title(),amount=v) for k,v in values.items() if k not in ('sales_with_unresolved_cost','returns_with_unresolved_cost')]
            columns=[('metric','Measure'),('amount','PKR',currency)]
            self.note.setText('Gross profit = net sales − original allocated cost. Profit after expenses deducts expenses, customer discounts and stock-return costs not credited by the supplier, then adds confirmed carry refunds. Supplier refunds settle the supplier account and are not sales or profit. Transfers are excluded.')
        elif name=='Returns':
            rows=r.returns(start,end)
            columns=[('id','Return'),('transaction_date','Date'),('invoice_number','Invoice'),('customer_snapshot','Customer'),('total','Returned value',currency),('cogs_reversed','Cost reversed',currency),('status','Status',trading_label)]
        else:
            rows=r.cash_summary(start,end)
            columns=[('name','Account'),('opening','Opening',currency),('received','Money in',currency),('paid_out','Money out',currency),('closing','Closing',currency)]
        query=normalize(self.search.text()) if searchable else ''
        if query:
            keys=('custom_name','supplier_snapshot','product_description_snapshot','name','phone','customer_snapshot','invoice_number','reference')
            tokens=query.split()
            rows=[row for row in rows if all(token in normalize(' '.join(str(row.get(key,'')) for key in keys)).replace(' ','') for token in tokens)]
            self.note.setText(self.note.text()+f'  Showing {len(rows)} matching rows.')
        self.rows,self.columns=rows,columns
        old=self.table
        self.table=DataTable(columns)
        self.layout.replaceWidget(old,self.table)
        old.hide()
        old.deleteLater()
        self.table.populate(rows)
        if name=='Current Stock / Stock Value':
            self.table.horizontalHeaderItem(3).setToolTip(self.note.text())
            self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(3,240)
            for index,row in enumerate(rows):
                if row.get('average_purchase_price') is None:
                    self.table.item(index,3).setText('—')
                    self.table.item(index,3).setToolTip('No net purchase history for this product.')

    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Export report',self.kind.currentText().replace('/','-')+'.csv','CSV (*.csv)')
        if not path:
            return
        try:
            with open(path,'w',encoding='utf-8-sig',newline='') as out:
                writer=csv.writer(out)
                writer.writerow([c[1] for c in self.columns])
                for row in self.rows:
                    values=[]
                    for col in self.columns:
                        value=row.get(col[0],'')
                        if len(col)>2 and col[2] in (currency,purchase_average) and value is not None:
                            value=amount_text(value)
                        elif isinstance(value,str) and value[:1] in ('=','+','-','@'):
                            value="'"+value
                        values.append(value)
                    writer.writerow(values)
            self.note.setText('CSV saved: '+path)
        except OSError:
            QMessageBox.warning(self,'Export failed','Could not write the file. Choose a writable folder or close the file if it is open.')

    def void_return(self):
        row=self.table.selected()
        if row:
            if confirm(self,'Undo customer return',f"Undo customer return R-{row['id']}? The original stays in history as Voided."):
                self.host.safe(lambda:self.ctx.returns.void(row['id']))
                self.refresh()

    def print_report(self):
        subtitle=self.ctx.db.setting('shop_name')+'\n'+day(self.start)+' to '+day(self.end)
        if self.kind.currentText() in ('Customer Statement','Supplier Statement'):
            subtitle+='\n'+self.party.currentText()
        show_print(self,self.kind.currentText(),printable_table(self.kind.currentText(),self.columns,self.rows,subtitle))
