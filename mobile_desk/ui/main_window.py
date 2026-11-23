from html import escape
from pathlib import Path
import logging
from PySide6.QtCore import Qt,QTimer,QUrl
from PySide6.QtGui import QDesktopServices,QIcon,QTextDocument
from PySide6.QtWidgets import (QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QGridLayout,QFrame,QScrollArea,QStackedWidget,QButtonGroup,QDialog,QTabWidget,QMessageBox,QCheckBox,QComboBox,QLineEdit,QHeaderView,QMenu)
from mobile_desk.context import Context
from mobile_desk.paths import resource_path
from mobile_desk.values import BusinessError,currency,today,weighted_average
from mobile_desk.ui.common import label,button,DataTable,ListPage,day,date_edit,show_print,printable_table,EntryDialog,refresh_party_combo,trading_label,confirm,fit_window
from mobile_desk.ui.products import ProductDialog
from mobile_desk.ui.transactions import TransactionDialog,ReturnDialog,SalePicker
from mobile_desk.ui.people_money import PartyDialog,PaymentDialog,AdjustmentDialog,AccountDialog,ExpenseDialog,TransferDialog,CarryPaymentDialog
from mobile_desk.ui.report_page import ReportPage
from mobile_desk.ui.settings import SettingsPage
from mobile_desk.ui.security import UndoDialog,password_field
from mobile_desk.ui.purchase_returns import PurchaseReturnDialog,PurchaseRefundDialog,ReceivePurchaseDialog


class MainWindow(QMainWindow):
    def __init__(self,ctx):
        super().__init__()
        self.ctx=ctx
        self.setWindowTitle(ctx.db.setting('shop_name')+' — Mobile Desk')
        self.setWindowIcon(QIcon(str(resource_path('app.ico'))))
        self.setMinimumSize(960,520)
        fit_window(self,1360,850)
        root=QWidget()
        self.setCentralWidget(root)
        layout=QHBoxLayout(root)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        sidebar=QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(210)
        side=QVBoxLayout(sidebar)
        side.setContentsMargins(12,10,12,10)
        side.setSpacing(4)
        side.addWidget(label('Mobile Desk','brand'))
        self.nav_group=QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav=[]
        titles=['Dashboard','Sales','Purchases','Stock','Accounts','Reports']
        for i,title in enumerate(titles):
            b=button(title,lambda checked=False,index=i:self.navigate(index))
            b.setObjectName('nav')
            b.setCheckable(True)
            self.nav_group.addButton(b,i)
            self.nav.append(b)
            side.addWidget(b)
        side.addStretch()
        side.addWidget(button('New Sale',self.new_sale,True))
        side.addWidget(button('New Purchase',self.new_purchase))
        side.addWidget(button('Receive Payment',lambda:self.payment()))
        self.settings_button=button('Settings',lambda:self.navigate(6))
        self.settings_button.setCheckable(True)
        self.settings_button.setObjectName('nav')
        self.nav_group.addButton(self.settings_button,6)
        side.addWidget(self.settings_button)
        layout.addWidget(sidebar)
        self.stack=QStackedWidget()
        layout.addWidget(self.stack,1)
        self.pages={}
        self.current_index=0
        self.navigate(0)

    def safe(self,action):
        try:
            return action()
        except BusinessError as e:
            QMessageBox.warning(self,'Could not complete',str(e))
        except Exception:
            logging.exception('UI action failed')
            QMessageBox.warning(self,'Could not complete','The operation could not be completed. Check the application log for details.')

    def navigate(self,index):
        def action():
            self.current_index=index
            if index not in self.pages:
                builders=[self.dashboard,self.sales_page,self.purchase_page,self.stock_page,self.accounts_page,
                          lambda:ReportPage(self,self.ctx),lambda:SettingsPage(self,self.ctx)]
                page=builders[index]()
                self.pages[index]=page
                self.stack.addWidget(page)
            page=self.pages[index]
            self.stack.setCurrentWidget(page)
            self.nav_group.button(index).setChecked(True)
            if getattr(page,'seen_revision',None)!=(self.ctx.db.revision,today()):
                self.refresh()
        self.safe(action)

    def refresh(self):
        page=self.pages.get(self.current_index)
        if hasattr(page,'refresh'):
            page.refresh()
            page.seen_revision=(self.ctx.db.revision,today())

    def reload_context(self):
        self.ctx=Context(self.ctx.root)
        self.setWindowTitle(self.ctx.db.setting('shop_name')+' — Mobile Desk')
        for page in self.pages.values():
            self.stack.removeWidget(page)
            page.deleteLater()
        self.pages={}
        self.navigate(0)

    def entry(self,dialog):
        if dialog.exec():
            self.refresh()
            self.statusBar().showMessage('Saved successfully.',6000)
            return dialog.result_id
        return None

    def new_sale(self):
        identity=self.entry(TransactionDialog(self,self.ctx))
        if identity:
            number=self.ctx.sales.details(identity)[0]['invoice_number']
            self.statusBar().showMessage(f'Invoice {number} saved.',10000)
        return identity

    def new_purchase(self):
        return self.entry(TransactionDialog(self,self.ctx,purchase=True))

    def payment(self,party_id=None,supplier=False):
        return self.entry(PaymentDialog(self,self.ctx,party_id,supplier=supplier))

    def new_return(self,sale_id=None):
        if sale_id is None:
            picker=SalePicker(self,self.ctx)
            if not picker.exec():
                return
            sale_id=picker.sale['id']
        return self.entry(ReturnDialog(self,self.ctx,sale_id))

    def new_product(self,product=None,catalogue=None):
        return self.entry(ProductDialog(self,self.ctx,product,catalogue))

    def selected(self,page):
        row=page.table.selected()
        if not row:
            QMessageBox.information(self,'Select a record','Select a row first.')
        return row

    def void(self,page,handler):
        row=self.selected(page)
        if row:
            if getattr(handler,'__self__',None) is self.ctx.purchases:
                self.entry(self.purchase_undo_dialog(row,handler))
                page.refresh()
                return
            reference=row.get('invoice_number') or row.get('reference') or str(row['id'])
            if confirm(self,'Undo selected entry',f'Undo {reference}? The original stays marked Voided.\nAttached stock/payments are reversed; later on-account payments remain.'):
                self.safe(lambda:handler(row['id'],''))
                page.refresh()

    def purchase_undo_dialog(self,row,handler=None):
        d=EntryDialog(self,'Undo mistaken purchase entry',700)
        d.setObjectName('purchaseUndoDialog')
        reference=row.get('reference') or str(row['id'])
        d.body.insertWidget(0,label(reference+' · '+row['transaction_date']+'\nSupplier bill PKR '+currency(row['supplier_total']),'section',True))
        d.body.insertWidget(1,label('Use this to correct an entry mistake. Its stock and attached payments are reversed; the original remains Voided. For a real shipment cancellation or returned goods, use Return / Cancel and confirm any refund actually received.','notice',True))
        d.username=d.field('Owner username',QLineEdit(self.ctx.security.username))
        d.password=d.field('Owner password',password_field())
        d.save_button.setText('Authorize and undo purchase')
        action=handler or self.ctx.purchases.void
        d.save_handler=lambda:action(row['id'],username=d.username.text(),password=d.password.text())
        return d

    def undo_latest(self):
        def action():
            entry=self.ctx.corrections.latest()
            if not entry:
                QMessageBox.information(self,'Nothing to undo','There are no saved business entries to undo. Unsaved forms can be cancelled.')
                return
            if UndoDialog(self,self.ctx,entry).exec():
                self.refresh()
                self.statusBar().showMessage('Entry undone. The original remains in history as Voided.',8000)
        self.safe(action)

    def dashboard(self):
        page = QWidget()
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22,16,22,14)
        layout.setSpacing(9)
        layout.addWidget(label('Dashboard','title'))
        layout.addWidget(label(self.ctx.db.setting('shop_name')+' · '+today(),'subtitle'))
        if self.ctx.catalogue_warning:
            layout.addWidget(label(self.ctx.catalogue_warning,'notice',True))
        actions = QHBoxLayout()
        for title, action in [('New Sale',self.new_sale),('New Purchase',self.new_purchase),
                              ('Receive Payment',lambda:self.payment()),('View Stock',lambda:self.navigate(3)),
                              ('Undo Last Entry',self.undo_latest)]:
            actions.addWidget(button(title,action,title=='New Sale'))
        layout.addLayout(actions)
        grid = QGridLayout()
        metrics = {}
        titles = [('sales','Today’s net sales (PKR)'),('sold','Phones sold today'),
                  ('month_sales','This month’s net sales (PKR)'),('gross','This month’s gross profit (PKR)'),
                  ('stock','Available pieces'),('value','Available stock value (PKR)'),
                  ('receivable','Customers owe (PKR)'),('payable','We owe suppliers (PKR)')]
        for index,(key,title) in enumerate(titles):
            card = QFrame()
            card.setObjectName('card')
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12,8,12,8)
            card_layout.addWidget(label(title,'subtitle',True))
            value = label('—','metric')
            value.setWordWrap(True)
            card_layout.addWidget(value)
            grid.addWidget(card,index//4,index%4)
            metrics[key] = value
        layout.addLayout(grid)
        summary = label('','subtitle',True)
        layout.addWidget(summary)
        lower = QTabWidget()
        phones = ('phone_names','Phone names')
        sales = DataTable([('transaction_date','Date'),('invoice_number','Invoice'),
            ('customer_snapshot','Customer'),('quantity','Pieces'),phones,
            ('average_prices','Sale avg. (PKR)'),('total','Total PKR',currency)])
        purchases = DataTable([('transaction_date','Date'),('reference','Batch'),
            ('supplier_snapshot','Supplier'),('quantity','Pieces'),phones,
            ('average_prices','Purchase avg. (PKR)'),('total','Total PKR',currency)])
        sales.horizontalHeaderItem(5).setToolTip('Selling value divided by pieces for each model in this invoice.')
        purchases.horizontalHeaderItem(5).setToolTip('Landed cost, including saved cargo charges, divided by pieces for each model in this batch.')
        for table,title in ((sales,'Recent sales'),(purchases,'Recent purchases')):
            header = table.horizontalHeader()
            header.setStretchLastSection(False)
            for column,width in ((1,115),(2,110),(3,55)):
                header.setSectionResizeMode(column,QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(column,width)
            header.setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().setMinimumSectionSize(42)
            table.setWordWrap(False)
            lower.addTab(table,title)
        lower.setMinimumHeight(260)
        empty = label('','subtitle')
        layout.addWidget(lower,1)
        layout.addWidget(empty)
        sales.cellDoubleClicked.connect(lambda:self.sale_details(sales.selected()['id']))
        purchases.cellDoubleClicked.connect(lambda:self.show_purchase(purchases.selected()['id']))

        def refresh_panel():
            current = lower.currentWidget()
            if current is sales:
                rows = self.ctx.sales.list(limit=5,posted_only=True)
            else:
                rows = self.ctx.purchases.list(limit=5,posted_only=True)
            models = self.ctx.reports.transaction_model_prices(
                [row['id'] for row in rows], purchase=current is purchases)
            for row in rows:
                phone_prices = models.get(row['id'], [])
                row['phone_names'] = '\n'.join(name for name, _ in phone_prices)
                row['average_prices'] = '\n'.join(currency(price) for _, price in phone_prices) or '—'
            current.populate(rows)
            for index in range(current.rowCount()):
                current.item(index,5).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            current.resizeRowsToContents()
            empty.setText('' if rows else 'No transactions yet')

        timer = QTimer(page)
        timer.setSingleShot(True)
        timer.timeout.connect(refresh_panel)
        lower.currentChanged.connect(lambda:timer.start(0))

        def refresh():
            date = today()
            d = self.ctx.reports.dashboard(date)
            page.dashboard_data = d
            receipts = self.ctx.reports.receipt_totals(date,date)
            values = dict(sales=d['today'].get('net_sales',0), sold=d['today']['quantity'],
                          month_sales=d['month']['net_sales'],gross=d['month']['gross_profit'],
                          stock=d['stock']['quantity'],value=d['stock']['value'],
                          receivable=d['receivable'],payable=d['payable'])
            for key,value in values.items():
                display = f'{value:,}' if key in ('sold','stock') else currency(value)
                metrics[key].setText('Cost not verified' if value is None else display)
            month = d['month']
            metrics['month_sales'].setToolTip(f"{month['net_quantity']:,} net pieces · {month['invoice_count']:,} invoices")
            summary.setText(f"Received today PKR {currency(receipts['at_sale']+receipts['later'])} "
                f"(later collections {currency(receipts['later'])}) · Refunds PKR {currency(receipts['refunds'])} "
                f"· Incoming pieces {self.ctx.stock.incoming():,}")
            timer.start(0)

        page.refresh = refresh
        return page

    def sales_page(self):
        page=ListPage('Sales','',[('transaction_date','Date'),('sale_reference','Invoice / bill book'),
            ('customer_snapshot','Customer'),('model_summary','Models / pieces'),('total','Total PKR',currency),
            ('paid','Paid at sale PKR',currency),('remaining','Remaining PKR',currency),('payment_status','Payment')],
            self.sales_rows,date_filter=True)
        header=page.table.horizontalHeader()
        header.setStretchLastSection(False)
        for column,width in ((0,108),(1,145),(2,140),(4,118),(5,128),(6,128),(7,90)):
            header.setSectionResizeMode(column,QHeaderView.ResizeMode.Interactive)
            page.table.setColumnWidth(column,width)
        header.setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        for title,fn in [('New Sale',self.new_sale),('Open invoice',lambda:self.invoice_selected(page)),
                         ('Undo Sale',lambda:self.void(page,self.ctx.sales.void))]:
            page.actions.insertWidget(page.actions.count()-1,button(title,fn,title=='New Sale'))
        page.customer=QComboBox()
        page.customer.addItem('All customers',None)
        for r in self.ctx.parties.search(role='is_customer',limit=10000,include_balances=False):
            page.customer.addItem(r['name'],r['id'])
        page.filters.addWidget(page.customer)
        page.customer.currentIndexChanged.connect(page.reset)
        page.table.cellDoubleClicked.connect(lambda:self.invoice_selected(page))
        return page

    def sales_rows(self,p):
        refresh_party_combo(p.customer,self.ctx,'is_customer','All customers')
        rows=self.ctx.sales.list(day(p.start),day(p.end),p.search.text(),p.customer.currentData(),p.limit+1,p.offset)
        customer_bills = {}
        for r in rows:
            r['credit']=(r['total']-r['paid'] if r['status']=='POSTED' else 0) if r['settlement_status']=='KNOWN' else None
            if r['date_label']:
                r['transaction_date']=r['date_label']
            if r['settlement_status']!='KNOWN':
                r['paid']=None
            r['sale_reference'] = r['invoice_number']
            if r['bill_book_number']:
                r['sale_reference'] += ' / '+r['bill_book_number']
            r['model_summary'] = f"{r['product_names']} · {r['quantity']} pcs"
            r['remaining'] = r['credit']
            customer = r['customer_id']
            if r['status']=='POSTED' and r['credit'] and customer:
                if customer not in customer_bills:
                    customer_bills[customer] = {doc['source_id']:doc['outstanding']
                        for doc in self.ctx.parties.documents(customer) if doc.get('kind')=='SALE'}
                r['remaining'] = customer_bills[customer].get(r['id'],0)
            r['payment_status'] = ('Voided' if r['status']=='VOID' else 'Unknown' if r['remaining'] is None
                else 'Settled' if r['remaining']==0 else 'Part due' if r['remaining'] < r['total'] else 'Due')
        return rows

    def invoice_selected(self,page):
        row=self.selected(page)
        if row:
            self.sale_details(row['id'])

    def sale_details(self, identity):
        header, items, payments = self.ctx.sales.details(identity)
        name = header['invoice_number']
        subtitle = f"{header['transaction_date']} · {header['customer_snapshot']} · PKR {currency(header['total'])}"
        if header['bill_book_number']:
            subtitle += f" · Bill book {header['bill_book_number']}"
        actions = [('Print / PDF',lambda:self.invoice(identity))]
        if header['status']=='POSTED':
            def undo():
                if confirm(self,'Undo sale',f'Undo {name}? The original stays in history as Voided.'):
                    self.safe(lambda:self.ctx.sales.void(identity))
                    self.refresh()
            actions += [('Return phones',lambda:self.new_return(identity)),('Undo sale',undo)]
        self.details(name,subtitle,[('Items',[('product_description_snapshot','Product'),('quantity','Sold'),
            ('returned_quantity','Returned'),('selling_rate','Selling price PKR',currency),
            ('line_total','Total PKR',currency)],items),
            ('Payments',[('transaction_date','Date'),('account','Account'),('amount','PKR',currency),
                         ('voided_at','Voided')],payments)],actions)

    def return_selected(self,page):
        row=self.selected(page)
        if row:
            self.new_return(row['id'])

    def invoice(self,identity):
        header=self.ctx.db.one('SELECT invoice_number FROM sales WHERE id=?',(identity,))
        show_print(self,header['invoice_number'],self.invoice_html(identity))

    def invoice_html(self,identity):
        h,items,payments=self.ctx.sales.details(identity)
        paid=sum(p['amount'] for p in payments if p['purpose']=='SALE_RECEIPT')
        subtitle=self.ctx.db.setting('shop_name')+'\n'+self.ctx.db.setting('shop_address')+'\n'+self.ctx.db.setting('shop_phone')+'\nDate: '+(h['date_label'] or h['transaction_date'])+'\nCustomer: '+h['customer_snapshot']+'\nStatus: '+h['status']
        if h['bill_book_number']:
            subtitle += '\nBill book: '+h['bill_book_number']
        columns=[('product_description_snapshot','Product'),('quantity','Qty'),('selling_rate','Price PKR',currency),('line_total','Amount PKR',currency),('returned_quantity','Returned')]
        content=printable_table(h['invoice_number'],columns,items,subtitle)
        settlement=('Paid at sale: '+currency(paid)+'\nCredit at sale: '+currency(h['total']-paid)) if h['settlement_status']=='KNOWN' else 'Historical payment/customer allocation unresolved.'
        extra='<h2>Total PKR '+currency(h['total'])+'</h2><p>'+settlement+'\n'+escape(h['notes'])+'</p>'
        if h['void_reason']:
            extra+='<p>Correction: '+escape(h['void_reason'])+'</p>'
        content=content.replace('</body>',extra+'</body>')
        return content

    def purchase_page(self):
        page=ListPage('Purchases','Each purchase has its own row. Track arrival, return or cancel a shipment, and confirm refunds against the same supplier account.',[('reference','Batch'),('transaction_date','Date'),('product_names','Products / phones'),('purchase_type','Type',trading_label),('supplier_snapshot','Supplier'),('shipment_status','Shipment',trading_label),('supplier_total','Supplier bill PKR',currency),('total','Stock cost PKR',currency),('status','Status',trading_label)],self.purchase_rows,date_filter=True)
        page.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Interactive)
        page.table.setColumnWidth(2,230)
        page.table.verticalHeader().setMinimumSectionSize(42)
        page.table.verticalHeader().setMaximumSectionSize(126)
        refresh_list=page.refresh
        def refresh():
            refresh_list()
            for index,row in enumerate(page.table.data_rows):
                page.table.item(index,2).setText(row['product_names'].replace('; ','\n'))
            page.table.resizeRowsToContents()
        page.refresh=refresh
        for title,fn in [('New Purchase',self.new_purchase),('Open purchase',lambda:self.batch_selected(page)),
                         ('Undo Purchase',lambda:self.void(page,self.ctx.purchases.void)),
                         ('Return / Cancel',lambda:self.purchase_return_selected(page)),
                         ('Returns / refunds',lambda:self.purchase_return_history(page))]:
            page.actions.insertWidget(page.actions.count()-1,button(title,fn,title=='New Purchase'))
        page.kind=QComboBox()
        for title,value in [('All types',''),('Local','LOCAL'),('China import','CHINA_IMPORT'),('Opening stock','OPENING')]:
            page.kind.addItem(title,value)
        page.supplier=QComboBox()
        page.supplier.addItem('All suppliers',None)
        for r in self.ctx.parties.search(role='is_supplier',limit=10000,include_balances=False):
            page.supplier.addItem(r['name'],r['id'])
        for widget in (page.kind,page.supplier):
            page.filters.addWidget(widget)
            widget.currentIndexChanged.connect(page.reset)
        page.table.cellDoubleClicked.connect(lambda:self.batch_selected(page))
        return page

    def purchase_rows(self,page):
        refresh_party_combo(page.supplier,self.ctx,'is_supplier','All suppliers')
        rows=self.ctx.purchases.list(day(page.start),day(page.end),page.search.text(),page.kind.currentData(),page.supplier.currentData(),page.limit+1,page.offset)
        for row in rows:
            if row['date_label']:
                row['transaction_date']=row['date_label']
        return rows

    def purchase_return_selected(self,page):
        row=self.selected(page)
        if row:
            def open_return():
                dialog = PurchaseReturnDialog(self,self.ctx,row['id'])
                if not dialog.preview['returnable_quantity']:
                    raise BusinessError('This purchase has no pieces available to return or cancel.')
                return self.entry(dialog)
            self.safe(open_return)

    def receive_purchase_selected(self,page):
        row=self.selected(page)
        if row:
            if row['status']!='POSTED' or row['shipment_status']!='IN_TRANSIT':
                QMessageBox.information(self,'Shipment arrival','Choose a saved shipment that is still in transit.')
                return
            self.safe(lambda:self.entry(ReceivePurchaseDialog(self,self.ctx,row['id'])))

    def purchase_return_history(self,page):
        row=self.selected(page)
        if row:
            self.safe(lambda:self.purchase_return_history_dialog(row['id']).exec())

    def purchase_return_history_dialog(self,purchase_id):
        preview=self.ctx.purchase_returns.preview(purchase_id)
        header=preview['header']
        d=QDialog(self)
        d.setWindowTitle('Returns / refunds · '+header['reference'])
        d.resize(1160,740)
        layout=QVBoxLayout(d)
        layout.addWidget(label(header['reference']+' · Returns / refunds','section'))
        layout.addWidget(label(header['supplier_snapshot']+' · '+trading_label(header['shipment_status'])+'\nReturning stock reduces the supplier bill. Cash / Bank increases only when an actual refund is confirmed. Original purchases and payments remain in history.','subtitle',True))
        tabs=QTabWidget()
        d.returns_table=DataTable([('id','Return'),('transaction_date','Date'),('kind','Action',trading_label),('quantity','Pieces'),('stock_cost','Stock cost reversed PKR',currency),('supplier_credit','Supplier credit PKR',currency),('refunded_amount','Refunds received PKR',currency),('owner_username','Authorized by'),('reason','Action details')])
        d.returns_table.setObjectName('purchaseReturnsTable')
        d.refunds_table=DataTable([('purchase_return_id','Return'),('transaction_date','Date'),('payer_kind','Refund from',trading_label),('account_name','Received into'),('amount','Refund PKR',currency),('owner_username','Authorized by'),('reference','Reference'),('notes','Notes')])
        d.refunds_table.setObjectName('purchaseRefundsTable')
        tabs.addTab(d.returns_table,'Returns / cancellations')
        tabs.addTab(d.refunds_table,'Confirmed refunds')
        layout.addWidget(tabs,1)
        bar=QHBoxLayout()
        def reload():
            current=d.returns_table.selected()
            selected_id=current['id'] if current else None
            history=self.ctx.purchase_returns.preview(purchase_id)
            d.returns_table.populate(history['returns'])
            d.refunds_table.populate(history['refunds'])
            for index,row in enumerate(d.returns_table.data_rows):
                if row['id']==selected_id:
                    d.returns_table.selectRow(index)
                    break
            d.confirm_refund_button.setEnabled(bool(history['returns']))
        def confirm_refund():
            selected=d.returns_table.selected()
            if selected:
                if self.entry(PurchaseRefundDialog(d,self.ctx,selected['id'])):
                    reload()
        d.confirm_refund_button=button('Confirm refund for selected return',lambda:self.safe(confirm_refund),True)
        d.confirm_refund_button.setObjectName('confirmPurchaseRefundButton')
        bar.addWidget(d.confirm_refund_button)
        bar.addWidget(button('Refresh',lambda:self.safe(reload)))
        bar.addStretch()
        bar.addWidget(button('Close',d.accept))
        layout.addLayout(bar)
        tabs.currentChanged.connect(lambda index:d.confirm_refund_button.setVisible(index==0))
        reload()
        return d

    def batch_selected(self,page):
        row=self.selected(page)
        if not row:
            return
        self.show_purchase(row['id'])

    def show_purchase(self,identity):
        preview=self.ctx.purchase_returns.preview(identity)
        header,lines=preview['header'],preview['lines']
        columns=[('product_description_snapshot','Product'),('quantity','Bought'),('returned_quantity','Returned / cancelled'),('foreign_unit_price','RMB / unit'),('exchange_rate_snapshot','PKR per RMB'),('pkr_unit_purchase_cost','PKR / unit',currency),('carry_currency','Carry currency',lambda v:'RMB' if v=='CNY' else v),('foreign_carry_per_unit','RMB carry / unit'),('additional_cost_per_unit','PKR carry / unit',currency),('landed_unit_cost','Landed / unit PKR',currency),('line_total_cost','Original line cost PKR',currency),('remaining_quantity','Available')]
        payments=self.ctx.db.rows('SELECT p.*,a.name account FROM payments p JOIN accounts a ON a.id=p.account_id WHERE purchase_batch_id=? ORDER BY transaction_date,id',(header['id'],))
        actions=[('Print / PDF',lambda:show_print(self,header['reference'],printable_table(header['reference'],columns,lines,self.ctx.db.setting('shop_name')+'\n'+header['supplier_snapshot']+'\nSupplier bill PKR '+currency(header['supplier_total']))))]
        if self.ctx.money.carry_remaining(header['id'])>0:
            actions.append(('Pay transport / carry',lambda:self.entry(CarryPaymentDialog(self,self.ctx,header))))
        if preview['returnable_quantity']:
            actions.append(('Return / Cancel',lambda:self.safe(lambda:self.entry(PurchaseReturnDialog(self,self.ctx,header['id'])))))
        if header['status']=='POSTED' and header['shipment_status']=='IN_TRANSIT':
            actions.append(('Mark received',lambda:self.safe(lambda:self.entry(ReceivePurchaseDialog(self,self.ctx,header['id'])))))
        actions.append(('Returns / refunds',lambda:self.safe(lambda:self.purchase_return_history_dialog(header['id']).exec())))
        if header['status']=='POSTED' and not preview['returns']:
            actions.append(('Undo purchase',lambda:self.entry(self.purchase_undo_dialog(header))))
        stacks=self.ctx.purchases.stacks(header['id'])
        stack_tables=[('Stacks / shipment charges',[('product_description_snapshot','Product'),('quantity','Pieces in stack'),('carry_basis','Carry charged for',lambda v:'Whole stack' if v=='STACK_TOTAL' else 'Per piece (saved)'),('carry_currency','Charge currency',lambda v:'RMB' if v=='CNY' else v),('carry_input','Original carry charge'),('total_carry_cost','Total carry PKR',currency),('line_total_cost','Stack landed total PKR',currency)],stacks)] if stacks else []
        pieces=sum(line['quantity'] for line in lines)
        cargo=sum(line['quantity']*line['additional_cost_per_unit'] for line in lines)
        subtitle=(f"{header['transaction_date']} · {header['supplier_snapshot']} · "
                  f"{trading_label(header['status'])} · {trading_label(header['shipment_status'])}\n"
                  f"{pieces:,} pieces · Original supplier bill PKR {currency(header['supplier_total'])} · "
                  f"Cargo PKR {currency(cargo)} · Original stock cost PKR {currency(header['total'])}")
        self.details(header['reference'],subtitle,stack_tables+[('Cost breakdown',columns,lines),('Purchase / transport payments',[('transaction_date','Date'),('account','Account'),('amount','Paid PKR',currency),('notes','Notes'),('voided_at','Voided')],payments),('Returns / cancellations',[('transaction_date','Date'),('kind','Action',trading_label),('quantity','Pieces'),('stock_cost','Stock cost reversed PKR',currency),('supplier_credit','Supplier credit PKR',currency),('refunded_amount','Refunds received PKR',currency),('owner_username','Authorized by'),('reason','Action details')],preview['returns']),('Confirmed refunds',[('transaction_date','Date'),('payer_kind','Refund from',trading_label),('account_name','Received into'),('amount','Refund PKR',currency),('owner_username','Authorized by')],preview['refunds'])],actions)

    def stock_page(self):
        average_note='Average Purchase Price = total landed purchase cost ÷ purchased pieces across batches, after supplier returns / cancellations. Includes stock awaiting arrival. Available stock is valued at its actual remaining lot costs (FIFO).'
        page=ListPage('Stock','',[('custom_name','Model'),('quantity','Available pieces'),('value','Stock value PKR',currency),
            ('average_purchase_price','Purchase average PKR',currency),('available_average','Available avg. PKR',currency),
            ('selling_average','Selling avg. PKR',currency)],self.stock_rows)
        page.start=date_edit(today()[:8]+'01')
        page.end=date_edit()
        for widget in (label('Selling average from'),page.start,label('To'),page.end):
            page.filters.addWidget(widget)
        page.start.dateChanged.connect(page.reset)
        page.end.dateChanged.connect(page.reset)
        page.table.horizontalHeaderItem(4).setToolTip('Available stock value divided by available pieces.')
        page.table.horizontalHeaderItem(5).setToolTip('Net sales divided by net pieces in the shown dates. Returns use their posting dates.')
        page.table.horizontalHeaderItem(3).setToolTip(average_note)
        page.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Interactive)
        page.table.setColumnWidth(3,175)
        original_refresh=page.refresh
        def refresh():
            original_refresh()
            for index,row in enumerate(page.table.data_rows):
                for column,key in ((3,'average_purchase_price'),(4,'available_average'),(5,'selling_average')):
                    if row.get(key) is None:
                        page.table.item(index,column).setText('—')
        page.refresh=refresh
        for title,fn in [('Add Product',self.new_product),('Edit Product',lambda:self.edit_product(page)),('Product details',lambda:self.product_details(page))]:
            page.actions.insertWidget(page.actions.count()-1,button(title,lambda checked=False,f=fn:f(),title=='Add Product'))
        page.table.cellDoubleClicked.connect(lambda:self.product_details(page))
        return page

    def stock_rows(self,page):
        rows = self.ctx.stock.current(page.search.text(),page.limit+1,page.offset)
        start,end = day(page.start),day(page.end)
        averages = {row['product_id']:row['selling_average'] for row in
            self.ctx.reports.model_sales(start,end,product_ids=[row['id'] for row in rows])}
        for row in rows:
            row['selling_average'] = averages.get(row['id'])
        return rows

    def edit_product(self,page):
        row=self.selected(page)
        if row:
            self.new_product(self.ctx.products.get(row['id']))

    def product_details(self,page):
        row=self.selected(page)
        if not row:
            return
        self.show_product(row,day(page.start),day(page.end))

    def open_stock_product(self,identity,start,end):
        rows = self.ctx.stock.current(limit=1,product_id=identity)
        if rows:
            self.show_product(rows[0],start,end)

    def show_product(self,row,start_date,end_date):
        identity = row['id']
        lots = list(reversed(self.ctx.stock.lots(identity)))
        sales = self.ctx.activity.product_history(identity)
        pending = sum(lot['quantity']-lot['supplier_returned'] for lot in lots
                      if lot['status']=='POSTED' and lot['shipment_status']=='IN_TRANSIT')
        latest_purchase = next((lot for lot in lots if lot['status']=='POSTED' and
                               lot['shipment_status'] not in ('CANCELLED','RETURNED')),None)
        latest_sale = next((sale for sale in sales if sale['status']=='POSTED'),None)
        def price(value):
            return currency(value) if value is not None else '—'
        summary = (f"{row['quantity']} available · {pending} incoming · Stock value PKR {currency(row['value'])}\n"
                   f"Purchase average PKR {price(row['average_purchase_price'])} · "
                   f"Available average PKR {price(row['available_average'])}")
        if latest_purchase:
            summary += f"\nLast purchase {latest_purchase['transaction_date']} · PKR {currency(latest_purchase['landed_unit_cost'])} landed per piece"
        if latest_sale:
            summary += f"\nLast sale {latest_sale['transaction_date']} · PKR {currency(latest_sale['selling_rate'])} per piece"
        date_panel=QWidget()
        bar=QHBoxLayout(date_panel)
        bar.setContentsMargins(0,0,0,0)
        start=date_edit(start_date)
        end=date_edit(end_date)
        selling=label('','subtitle',True)
        for widget in (label('Sales from'),start,label('To'),end,selling):
            bar.addWidget(widget)
        def update_sales():
            rows=self.ctx.reports.model_sales(day(start),day(end),product_ids=[identity])
            if not rows:
                selling.setText('No model activity in these dates')
                return
            value=rows[0]
            selling.setText(f"Net pieces {value['net_quantity']} · Net sales PKR {price(value['net_sales'])}\n"
                f"Selling average PKR {price(value['selling_average'])} · FIFO gross profit PKR {price(value['gross_profit'])}")
        start.dateChanged.connect(update_sales)
        end.dateChanged.connect(update_sales)
        update_sales()
        stacks = {}
        for lot in lots:
            key=(lot['stack_id'],None) if lot['stack_id'] else (None,lot['id'])
            group=stacks.setdefault(key,dict(lot,quantity=0,sold=0,supplier_returned=0,remaining_quantity=0,line_total_cost=0))
            for field in ('quantity','sold','supplier_returned','remaining_quantity','line_total_cost'):
                group[field]+=lot[field]
        for stack in stacks.values():
            stack['landed_unit_cost']=weighted_average(stack['line_total_cost'],stack['quantity'])
        self.details(row['custom_name'],summary,[('View purchases',[
            ('reference','Parcel'),('transaction_date','Date'),('supplier_snapshot','Supplier'),
            ('shipment_status','Arrival',trading_label),('quantity','Bought'),('sold','Net sold'),
            ('supplier_returned','Returned to supplier'),('remaining_quantity','On hand'),('original_currency','Price currency'),
            ('foreign_unit_price','RMB / pc'),('exchange_rate_snapshot','FX'),('pkr_unit_purchase_cost','Cost PKR / pc',currency),
            ('carry_basis','Carry basis',trading_label),('cargo','Cargo PKR',currency),('landed_unit_cost','Landed PKR / pc',currency)
        ],list(stacks.values())),('View sales',[('transaction_date','Date'),('invoice_number','Invoice'),('customer_snapshot','Customer'),
            ('quantity','Pieces'),('selling_rate','Rate PKR',currency),('line_total','Total PKR',currency),('status','Status',trading_label)],sales)],
            [('Edit product',lambda:self.new_product(self.ctx.products.get(identity)))],header_widget=date_panel)

    def catalogue_page(self):
        page=ListPage('Mobile Catalogue','Offline reference names help you create shop products. Variants and condition remain optional.',[('brand','Brand'),('model_name','Model'),('release_year','Year'),('source_version','Catalogue version')],lambda p:self.ctx.catalogue.search(p.search.text(),p.limit+1,p.offset) if self.ctx.catalogue else [])
        page.search.setPlaceholderText('Search model, brand or alias… e.g. 15 pro, a55')
        page.actions.insertWidget(0,button('Create Shop Product',lambda:self.catalogue_product(page),True))
        page.actions.insertWidget(1,button('+ Add Product Manually',lambda:self.new_product()))
        page.table.cellDoubleClicked.connect(lambda:self.catalogue_product(page))
        page.refresh()
        return page

    def open_catalogue(self):
        d=QDialog(self)
        d.setWindowTitle('Offline Mobile Catalogue')
        d.resize(1100,720)
        layout=QVBoxLayout(d)
        layout.addWidget(self.catalogue_page())
        layout.addWidget(button('Close',d.accept))
        d.exec()

    def catalogue_product(self,page):
        row=self.selected(page)
        if row:
            self.new_product(catalogue=row)

    def parties_page(self,supplier=False):
        title='Suppliers' if supplier else 'Customers'
        role='is_supplier' if supplier else 'is_customer'
        subtitle='One account per supplier combines all its purchases and payments. Payable is what the shop owes; a negative balance is an advance.' if supplier else 'One account per customer combines all their sales and receipts. Receivable is what the customer owes; a negative balance is customer credit.'
        columns=[('selection_name','Name / account'),('phone','Phone'),('supplier_balance' if supplier else 'balance','We owe PKR' if supplier else 'Customer owes PKR',currency)]
        if not supplier:
            columns += [('last_purchase','Last purchase'),('bill_count','Bills')]
        page=ListPage(title,'',columns,lambda p:self.party_rows(p,role))
        page.supplier=supplier
        for text,fn in [('Add Supplier' if supplier else 'Add Customer',lambda:self.entry(PartyDialog(self,self.ctx,supplier=supplier))),('Open account',lambda:self.party_details(page)),('Edit',lambda:self.edit_party(page)),('Pay Supplier' if supplier else 'Receive Payment',lambda:self.pay_selected(page))]:
            page.actions.insertWidget(page.actions.count()-1,button(text,fn,text.startswith('Add')))
        page.table.cellDoubleClicked.connect(lambda:self.party_details(page))
        return page

    def party_rows(self,page,role):
        from mobile_desk.ui.common import party_selection_name
        rows=self.ctx.parties.search(page.search.text(),role,page.limit+1,page.offset)
        sales = {}
        if role=='is_customer' and rows:
            ids = [row['id'] for row in rows]
            sales = {row['customer_id']:row for row in self.ctx.db.rows(
                "SELECT customer_id,COUNT(*) bill_count,MAX(CASE WHEN date_basis!='UNKNOWN' THEN transaction_date END) last_purchase "
                "FROM sales WHERE status='POSTED' AND customer_id IN ("+','.join('?' for _ in ids)+") GROUP BY customer_id",ids)}
        for row in rows:
            row['selection_name']=party_selection_name(row)
            row.update(sales.get(row['id'],dict(bill_count=0,last_purchase='—')))
        return rows

    def edit_party(self,page):
        row=self.selected(page)
        if row:
            self.entry(PartyDialog(self,self.ctx,row))

    def pay_selected(self,page):
        row=self.selected(page)
        if row:
            self.payment(row['id'],supplier=page.supplier)

    def party_details(self,page):
        row=self.selected(page)
        if not row:
            return
        supplier=page.supplier
        role='SUPPLIER' if supplier else 'CUSTOMER'
        columns=[('transaction_date','Date'),('reference','Reference'),('description','Description'),('added','Bill / added PKR',currency),('reduction','Payment / reduction PKR',currency),('balance','Balance PKR',currency)]
        statement=self.ctx.parties.statement(row['id'],role=role)
        documents=self.ctx.parties.documents(row['id'],role=role)
        tabs=[('Statement',columns,statement),('Bills / balances',[('transaction_date','Date'),('reference','Bill'),('description','Description'),('original_amount','Original PKR',currency),('settled','Paid / credited PKR',currency),('outstanding','Remaining PKR',currency)],documents)]
        payments=[p for p in self.ctx.activity.payments('1900-01-01','9999-12-31',party_id=row['id'],limit=10000) if p['ledger_role']==role]
        tabs.append(('Payments (latest 10,000)',[('transaction_date','Date'),('purpose','Payment type',trading_label),('account','Account'),('amount','Amount',currency),('reference','Reference'),('voided_at','Voided')],payments))
        adjustments=self.ctx.db.rows('SELECT * FROM party_adjustments WHERE party_id=? AND ledger_role=? ORDER BY transaction_date,id',(row['id'],role))
        tabs.append(('Balance adjustments',[('transaction_date','Date'),('adjustment_type','Type',trading_label),('amount','Change PKR',currency),('reason','Action details'),('voided_at','Voided')],adjustments))
        if supplier:
            tabs.append(('Purchases (latest 500)',[('transaction_date','Date'),('reference','Batch'),('purchase_type','Type',trading_label),('supplier_total','Supplier bill',currency),('status','Status',trading_label)],self.ctx.purchases.list(supplier_id=row['id'],limit=500)))
        else:
            tabs.append(('Invoices (latest 500)',[('transaction_date','Date'),('invoice_number','Invoice'),('total','Total',currency),('status','Status',trading_label)],self.ctx.sales.list(customer_id=row['id'],limit=500)))
        actions=[('Pay Supplier' if supplier else 'Receive Payment',lambda:self.payment(row['id'],supplier=supplier)),('Opening / adjust balance',lambda:self.entry(AdjustmentDialog(self,self.ctx,row['id'],supplier=supplier))),('Print statement',lambda:show_print(self,row['name'],printable_table('Supplier Statement' if supplier else 'Customer Statement',columns,statement,self.ctx.db.setting('shop_name')+'\n'+row['name'])))]
        self.details(row['name'],('Supplier payable PKR ' if supplier else 'Customer receivable PKR ')+currency(self.ctx.parties.balance(row['id'],role=role))+'\nLater payments settle the oldest unpaid bills. Negative balance means an advance.',tabs,actions,corrections={2:'payment',3:'adjustment'})
        page.refresh()

    def money_page(self):
        tabs=QTabWidget()
        accounts=ListPage('Cash & Bank','Balances are calculated from receipts, purchases, expenses, refunds and transfers.',[('name','Account'),('account_type','Type',trading_label),('balance','Balance PKR',currency),('active','Active',lambda v:'Yes' if v else 'No')],lambda p:[r for r in self.ctx.money.accounts() if p.search.text().casefold() in r['name'].casefold()])
        accounts.actions.insertWidget(0,button('Add account',lambda:self.entry(AccountDialog(self,self.ctx)),True))
        accounts.actions.insertWidget(1,button('Edit account',lambda:self.edit_account(accounts)))
        accounts.actions.insertWidget(2,button('Account activity',lambda:self.account_details(accounts)))
        tabs.addTab(accounts,'Accounts')
        expenses=ListPage('Expenses','Record shop costs paid from cash or bank.',[('transaction_date','Date'),('description','Description'),('category','Category'),('account','Account'),('amount','PKR',currency),('voided_at','Voided')],lambda p:self.ctx.activity.expenses(day(p.start),day(p.end),p.search.text(),p.limit+1,p.offset),date_filter=True)
        expenses.actions.insertWidget(0,button('Record Expense',lambda:self.entry(ExpenseDialog(self,self.ctx)),True))
        expenses.actions.insertWidget(1,button('Void',lambda:self.void(expenses,lambda i,r:self.ctx.money.void('expense',i,r))))
        tabs.addTab(expenses,'Expenses')
        transfers=ListPage('Transfers','Move money between accounts without changing profit.',[('transaction_date','Date'),('source','From'),('destination','To'),('amount','PKR',currency),('reference','Reference'),('voided_at','Voided')],lambda p:self.ctx.activity.transfers(day(p.start),day(p.end),p.search.text(),p.limit+1,p.offset),date_filter=True)
        transfers.actions.insertWidget(0,button('New Transfer',lambda:self.entry(TransferDialog(self,self.ctx)),True))
        transfers.actions.insertWidget(1,button('Void',lambda:self.void(transfers,lambda i,r:self.ctx.money.void('transfer',i,r))))
        tabs.addTab(transfers,'Transfers')
        payments=ListPage('Payments','Sale receipts, customer collections, purchase payments and refunds.',[('transaction_date','Date'),('party_snapshot','Party'),('purpose','Purpose',trading_label),('account','Account'),('direction','Direction',trading_label),('amount','PKR',currency),('reference','Reference'),('voided_at','Voided')],lambda p:self.ctx.activity.payments(day(p.start),day(p.end),p.search.text(),p.limit+1,p.offset),date_filter=True)
        payments.actions.insertWidget(0,button('Receive Payment',self.payment,True))
        payments.actions.insertWidget(1,button('Pay Supplier',lambda:self.payment(supplier=True)))
        payments.actions.insertWidget(2,button('Correct payment',lambda:self.void(payments,lambda i,r:self.ctx.money.void('payment',i,r))))
        tabs.addTab(payments,'Payments')
        tabs.refresh=lambda:tabs.currentWidget().refresh()
        tabs.currentChanged.connect(lambda:tabs.refresh())
        return tabs

    def accounts_page(self):
        tabs = QTabWidget()
        tabs.addTab(self.parties_page(), 'Customers')
        tabs.addTab(self.parties_page(True), 'Suppliers')
        tabs.addTab(self.money_page(), 'Cash & Bank')
        tabs.refresh = lambda: tabs.currentWidget().refresh()
        tabs.currentChanged.connect(lambda: tabs.refresh())
        return tabs

    def audit_history(self):
        page = ListPage('Activity history','',
            [('created_at','Recorded at (UTC)'),('action','Action'),('entity','Record type'),
             ('entity_id','Record ID'),('reason','Details')],
            lambda p: self.ctx.db.rows("""
                SELECT * FROM audit_log WHERE action LIKE ? OR entity LIKE ? OR entity_id LIKE ?
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (*(['%'+p.search.text()+'%']*3),p.limit+1,p.offset)))
        dialog=QDialog(self)
        dialog.resize(980,620)
        dialog.setWindowTitle('Activity history')
        QVBoxLayout(dialog).addWidget(page)
        page.refresh()
        dialog.exec()

    def edit_account(self,page):
        row=self.selected(page)
        if row:
            self.entry(AccountDialog(self,self.ctx,row))

    def account_details(self,page):
        row=self.selected(page)
        if row:
            self.details(row['name'],'Current balance PKR '+currency(row['balance']),[('Latest 1,000 entries',[('transaction_date','Date'),('reference','Reference'),('description','Description'),('amount','Change PKR',currency)],self.ctx.activity.account_history(row['id']))])

    def details(self,title,subtitle,tables,actions=(),corrections=None,header_widget=None):
        d=QDialog(self)
        d.setWindowTitle(title)
        d.resize(1100,720)
        layout=QVBoxLayout(d)
        layout.addWidget(label(title,'section'))
        layout.addWidget(label(subtitle,'subtitle',True))
        if header_widget is not None:
            layout.addWidget(header_widget)
        tabs=QTabWidget()
        layout.addWidget(tabs,1)
        for name,columns,rows in tables:
            t=DataTable(columns)
            t.populate(rows)
            tabs.addTab(t,name)
        bar=QHBoxLayout()
        more = QMenu(d)
        for index,(title,action) in enumerate(actions):
            def wrapped(checked=False,fn=action):
                fn()
                d.accept()
            if index<3:
                bar.addWidget(button(title,wrapped))
            else:
                more.addAction(title,wrapped)
        if not more.isEmpty():
            more_button=button('More actions',lambda:None)
            more_button.setMenu(more)
            bar.addWidget(more_button)
        if corrections:
            def correct():
                current=tabs.currentIndex()
                if current not in corrections:
                    return
                selected=tabs.currentWidget().selected()
                if not selected:
                    return
                if confirm(d,'Correct entry','Undo this selected entry? The original stays in history as Voided.') and self.safe(lambda:(self.ctx.money.void(corrections[current],selected['id']),True)[1]):
                    d.accept()
                    self.refresh()
            correction=button('Correct selected entry',correct)
            bar.addWidget(correction)
            tabs.currentChanged.connect(lambda index:correction.setVisible(index in corrections))
            correction.setVisible(False)
        bar.addStretch()
        bar.addWidget(button('Close',d.accept))
        layout.addLayout(bar)
        d.exec()

    def first_run(self):
        if self.ctx.db.setting('setup_complete')=='1':
            return
        d=EntryDialog(self,'Welcome to Mobile Desk',650)
        name=d.field('Shop name',QLineEdit(self.ctx.db.setting('shop_name')))
        phone=d.field('Phone (optional)',QLineEdit())
        address=d.field('Address (optional)',QLineEdit())
        d.body.addWidget(label('The offline catalogue is ready. Start with your counted stock, agreed customer/supplier balances and actual Cash / Bank openings. Use Settings to open the shop guide.','subtitle',True))
        d.save_handler=lambda:self.ctx.money.save_settings(shop_name=name.text(),shop_phone=phone.text(),shop_address=address.text(),setup_complete='1')
        if d.exec():
            self.reload_context()

    def open_guide(self):
        path=resource_path('USER_GUIDE.md')
        if path.exists():
            text=path.read_text(encoding='utf-8')
            document=QTextDocument()
            document.setMarkdown(text)
            show_print(self,'Mobile Desk User Guide',document.toHtml())
