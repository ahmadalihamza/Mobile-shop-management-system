import csv
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QFileDialog,QMessageBox,QLineEdit,QHeaderView,QMenu
from mobile_desk.ui.common import label,button,date_edit,day,combo,DataTable,show_print,printable_table,refresh_party_combo,trading_label,confirm
from mobile_desk.values import currency,today,amount_text,normalize,weighted_average

REPORTS=['Daily Sales','Monthly Sales','Product Sales / Profit','Customer Outstanding','Customer Statement','Supplier Outstanding','Supplier Statement','Current Stock / Stock Value','Purchase History','China Batch / Landed Cost','Period Profit','Returns','Cash / Bank Period Summary']
PRIMARY_REPORTS = [('Daily Sales','Daily Sales'),('Monthly Sales','Monthly Sales'),
                   ('Available Stock','Current Stock / Stock Value'),('Product Profit','Product Sales / Profit')]


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
        primary = QHBoxLayout()
        self.primary_buttons = []
        for title,report in PRIMARY_REPORTS:
            control=button(title,lambda checked=False,name=report:self.kind.setCurrentText(name))
            control.setCheckable(True)
            control.setObjectName('reportChoice')
            primary.addWidget(control)
            self.primary_buttons.append((report,control))
        self.layout.addLayout(primary)
        bar=QHBoxLayout()
        self.kind=QComboBox()
        self.kind.addItems(REPORTS)
        self.kind.setParent(self)
        self.kind.hide()
        menu=QMenu(self)
        for report in REPORTS:
            if report not in {name for _,name in PRIMARY_REPORTS}:
                menu.addAction(report,lambda checked=False,name=report:self.kind.setCurrentText(name))
        more=button('More Reports',lambda:None)
        more.setMenu(menu)
        primary.addWidget(more)
        self.report_name=label('','section')
        self.layout.addWidget(self.report_name)
        self.start=date_edit(today()[:8]+'01')
        self.end=date_edit()
        bar.addWidget(label('From'))
        bar.addWidget(self.start)
        bar.addWidget(label('To'))
        bar.addWidget(self.end)
        bar.addWidget(button('Run report',self.refresh,True))
        self.layout.addLayout(bar)
        actions=QHBoxLayout()
        self.party=combo(optional='Choose customer')
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
        self.offset=0
        self.limit=100
        self.totals=label('','subtitle',True)
        self.layout.addWidget(self.totals)
        pages=QHBoxLayout()
        self.page_label=label('','subtitle')
        self.previous=button('Previous',lambda:self.move_page(-1))
        self.next=button('Next',lambda:self.move_page(1))
        pages.addWidget(self.page_label,1)
        pages.addWidget(self.previous)
        pages.addWidget(self.next)
        self.layout.addLayout(pages)
        self.kind.currentTextChanged.connect(self.refresh)
        self.party.currentIndexChanged.connect(self.refresh)
        self.rows=[]
        self.columns=[]
        self.refresh()

    def refresh(self,*args,keep_page=False):
        if not keep_page:
            self.offset=0
        name=self.kind.currentText()
        self.report_name.setText(next((title for title,report in PRIMARY_REPORTS if report==name),name))
        supplier=name=='Supplier Statement'
        if name in ('Customer Statement','Supplier Statement'):
            refresh_party_combo(self.party,self.ctx,'is_supplier' if supplier else 'is_customer','Choose supplier' if supplier else 'Choose customer')
        for report,control in self.primary_buttons:
            control.setChecked(name==report)
        start,end=day(self.start),day(self.end)
        if end<start:
            self.note.setText('The end date must be on or after the start date.')
            self.rows=[]
            self.table.populate([])
            self.totals.clear()
            self.next.setEnabled(False)
            self.previous.setEnabled(False)
            self.page_label.clear()
            return
        r=self.ctx.reports
        self.party.setVisible(name in ('Customer Statement','Supplier Statement'))
        model_report=name in ('Daily Sales','Monthly Sales','Product Sales / Profit')
        stock_report=name=='Current Stock / Stock Value'
        searchable=model_report or name in ('Customer Outstanding','Supplier Outstanding','Current Stock / Stock Value','Purchase History','China Batch / Landed Cost','Returns')
        self.search.setVisible(searchable)
        self.void_button.setVisible(name=='Returns')
        self.start.setEnabled(name not in ('Customer Outstanding','Supplier Outstanding','Current Stock / Stock Value'))
        self.end.setEnabled(name!='Current Stock / Stock Value')
        self.note.setText('')
        self.totals.clear()
        if model_report:
            rows=r.model_sales(start,end,daily=name=='Daily Sales')
            columns=[('custom_name','Model'),('sold_pieces','Sold'),('returned_pieces','Returned'),
                ('net_quantity','Net pieces'),('net_sales','Net sales PKR',currency),
                ('selling_average','Selling average PKR',purchase_average)]
            if name=='Daily Sales':
                columns.insert(0,('day','Date'))
            if name=='Product Sales / Profit':
                columns += [('net_cogs','FIFO cost PKR',currency),('gross_profit','Gross profit PKR',currency),
                            ('margin','Margin',lambda value:f'{value:.1f}%')]
            self.note.setText('Selling average uses net pieces and net sales. Returns use their posting date.')
            if name!='Product Sales / Profit':
                receipts=r.receipt_totals(start,end)
                summary=r.sales_summary(start,end,monthly=True)
                credit=sum(row['credit_sales'] for row in summary if row['period']!='Date unknown')
                self.note.setText(self.note.text()+f" All models: paid at sale and later PKR "
                    f"{currency(receipts['at_sale']+receipts['later'])} · Credit at sale PKR {currency(credit)} "
                    f"· Cash refunds PKR {currency(receipts['refunds'])}.")
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
            rows=self.ctx.stock.current(self.search.text(),limit=self.limit+1,offset=self.offset)
            columns=[('custom_name','Model'),('quantity','Available pieces'),('value','Stock value PKR',currency),
                     ('average_purchase_price','Average Purchase Price (PKR)',purchase_average),
                     ('available_average','Available average PKR',purchase_average)]
            self.note.setText('Double-click a model for parcels and sales. Purchase average includes incoming purchases.')
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
        query=normalize(self.search.text()) if searchable and not stock_report else ''
        if query:
            keys=('custom_name','supplier_snapshot','product_description_snapshot','name','phone','customer_snapshot','invoice_number','reference')
            tokens=query.split()
            rows=[row for row in rows if all(token in normalize(' '.join(str(row.get(key,'')) for key in keys)).replace(' ','') for token in tokens)]
            self.note.setText(self.note.text()+f'  Showing {len(rows)} matching rows.')
        self.rows,self.columns=rows,columns
        shown = rows[:self.limit] if stock_report else rows[self.offset:self.offset+self.limit]
        has_next = len(rows)>self.limit if stock_report else len(rows)>self.offset+self.limit
        self.previous.setEnabled(self.offset>0)
        self.next.setEnabled(has_next)
        self.page_label.setText(f'{self.offset+1:,}–{self.offset+len(shown):,}' if shown else 'No matching transactions')
        if model_report:
            pieces=sum(row['net_quantity'] for row in rows)
            sales=sum(row['net_sales'] for row in rows)
            profit = ''
            if name=='Product Sales / Profit':
                values=[row['gross_profit'] for row in rows]
                profit=' · Gross profit PKR '+(currency(sum(values)) if all(v is not None for v in values) else 'Cost not verified')
            average=weighted_average(sales,pieces)
            self.totals.setText(f'Total · {pieces:,} net pieces · Net sales PKR {currency(sales)} · '
                f'Selling average PKR {purchase_average(average)}'+profit)
        elif stock_report:
            self.totals.setText(f"Page totals · {sum(row['quantity'] for row in shown):,} available pieces · "
                f"Stock value PKR {currency(sum(row['value'] for row in shown))}")
        old=self.table
        self.table=DataTable(columns)
        self.layout.replaceWidget(old,self.table)
        old.hide()
        old.deleteLater()
        self.table.populate(shown)
        if name=='Current Stock / Stock Value':
            self.table.horizontalHeaderItem(3).setToolTip(self.note.text())
            self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(3,240)
            for index,row in enumerate(shown):
                for column,key in ((3,'average_purchase_price'),(4,'available_average')):
                    if row.get(key) is None:
                        self.table.item(index,column).setText('—')
            self.table.cellDoubleClicked.connect(self.open_model)

    def move_page(self,step):
        self.offset=max(0,self.offset+step*self.limit)
        self.refresh(keep_page=True)

    def open_model(self,*args):
        row=self.table.selected()
        if row:
            self.host.open_stock_product(row['id'],day(self.start),day(self.end))

    def export_rows(self):
        if self.kind.currentText()!='Current Stock / Stock Value':
            yield from self.rows
            return
        offset=0
        while True:
            rows=self.ctx.stock.current(self.search.text(),limit=500,offset=offset)
            yield from rows
            if len(rows)<500:
                break
            offset+=500

    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Export report',self.kind.currentText().replace('/','-')+'.csv','CSV (*.csv)')
        if not path:
            return
        try:
            with open(path,'w',encoding='utf-8-sig',newline='') as out:
                writer=csv.writer(out)
                writer.writerow([c[1] for c in self.columns])
                for row in self.export_rows():
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
        show_print(self,self.kind.currentText(),printable_table(self.kind.currentText(),self.columns,list(self.export_rows()),subtitle))
