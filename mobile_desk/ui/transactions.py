from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QWidget,QLineEdit,QComboBox,QHBoxLayout,QVBoxLayout,QGridLayout,QSpinBox,QTableWidget,QTableWidgetItem,QHeaderView,QGroupBox,QCheckBox)
from mobile_desk.ui.common import EntryDialog,AmountEdit,button,label,combo,date_edit,day,DataTable,party_combo,select_saved_party
from mobile_desk.ui.products import ProductPicker
from mobile_desk.values import BusinessError,money,currency,amount_text
from mobile_desk.services.purchases import price_line


class TransactionDialog(EntryDialog):
    def __init__(self,parent,ctx,purchase=False):
        super().__init__(parent,'New Purchase' if purchase else 'New Sale',1120)
        self.ctx=ctx
        self.purchase=purchase
        self.entries=[]
        self.resize(1120,780)
        self.save_button.setText('Save Purchase' if purchase else 'Save Sale')
        header=QGridLayout()
        self.body.addLayout(header)
        self.date=date_edit()
        header.addWidget(label('Date'),0,0)
        header.addWidget(self.date,0,1)
        self.party=party_combo(ctx,'is_supplier' if purchase else 'is_customer','Choose supplier for unpaid balance' if purchase else 'Walk-in / select customer for credit')
        party_row=QHBoxLayout()
        party_row.addWidget(self.party,1)
        self.choose_party_button=button('Choose / add supplier' if purchase else 'Choose / add customer',self.add_party)
        party_row.addWidget(self.choose_party_button)
        header.addWidget(label('Supplier' if purchase else 'Customer'),0,2)
        header.addLayout(party_row,0,3)
        header.setColumnStretch(3,1)
        self.type=None
        if purchase:
            self.type=QComboBox()
            header.addWidget(label('Type'),1,0)
            header.addWidget(self.type,1,1)
            self.type.addItem('Local purchase','LOCAL')
            self.type.addItem('China import (RMB)','CHINA_IMPORT')
            self.type.addItem('Opening stock (PKR cost)','OPENING')
            last=ctx.db.one("SELECT purchase_type,supplier_id FROM purchase_batches WHERE status='POSTED' AND purchase_type!='OPENING' ORDER BY id DESC LIMIT 1") or {}
            remembered=ctx.db.setting('last_purchase_type',last.get('purchase_type','LOCAL'))
            self.type.setCurrentIndex(max(0,self.type.findData(remembered)))
            supplier=ctx.db.setting('last_purchase_supplier',str(last.get('supplier_id') or ''))
            if supplier.isdigit():
                self.party.setCurrentIndex(max(0,self.party.findData(int(supplier))))
            self.reference=QLineEdit()
            header.addWidget(label('Batch reference'),1,2)
            header.addWidget(self.reference,1,3)
            self.reference.setPlaceholderText('Leave blank for an automatic reference')
            self.arrival=QComboBox()
            self.arrival.addItem('Stock has arrived','RECEIVED')
            self.arrival.addItem('Awaiting arrival — unavailable for sale','IN_TRANSIT')
            header.addWidget(label('Shipment'),2,0)
            header.addWidget(self.arrival,2,1,1,3)
            self.defaults=QWidget()
            defaults=QHBoxLayout(self.defaults)
            defaults.setContentsMargins(0,0,0,0)
            defaults.addWidget(label('Default RMB → PKR'))
            rates=ctx.money.rates()
            self.rate=AmountEdit(rates[0]['rate'] if rates else '40.3',6)
            defaults.addWidget(self.rate)
            self.carry_label=label('Default carry / stack')
            defaults.addWidget(self.carry_label)
            self.carry=AmountEdit('0',6)
            defaults.addWidget(self.carry)
            self.carry_currency=QComboBox()
            self.carry_currency.addItem('RMB','CNY')
            self.carry_currency.addItem('PKR','PKR')
            self.carry_currency.setToolTip('China carry is the total charge for the whole stack, entered once. Choose PKR only when the carrier actually charges PKR. Each line uses its saved exchange rate.')
            defaults.addWidget(self.carry_currency)
            self.body.addWidget(self.defaults)
            self.rate_hint=label('Each product row is one stack. Enter the whole stack’s carry once; add the same product again for another stack. The saved rate converts the charge and never changes old costs.','subtitle',True)
            self.body.addWidget(self.rate_hint)
        line_bar=QHBoxLayout()
        self.add_button=button('+ Add product  (Alt+A)',self.pick_product,True)
        self.add_button.setShortcut('Alt+A')
        line_bar.addWidget(self.add_button)
        line_bar.addWidget(button('Remove selected line',self.remove_line))
        line_bar.addStretch()
        self.body.addLayout(line_bar)
        headers=['Product','Qty','Price / unit (PKR)','Rate','Carry / unit','PKR / unit','Landed / unit','Line total'] if purchase else ['Product','Qty','Selling price / unit','Line total']
        self.table=QTableWidget(0,len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setMinimumHeight(180)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.body.addWidget(self.table,1)
        self.totals=label('Total PKR 0.00','section',True)
        self.layout.insertWidget(2,self.totals)
        self.payments=[]
        self.payment_mode=None
        if not purchase:
            self.payment_mode=QComboBox()
            self.payment_mode.addItems(['Paid in full','Part payment','Pay later / credit'])
            self.body.addWidget(self.payment_mode)
        group=QGroupBox('Payment now' if not purchase else 'Payment from Cash / Bank (optional)')
        self.payment_group=group
        grid=QGridLayout(group)
        self.second_payment=QWidget()
        second_layout=QHBoxLayout(self.second_payment)
        second_layout.setContentsMargins(0,0,0,0)
        for i in range(2):
            account=combo(ctx.money.accounts(True))
            amount=AmountEdit('0')
            amount.textChanged.connect(self.calculate)
            if i==0:
                grid.addWidget(label('Amount (PKR)'),0,0)
                grid.addWidget(amount,0,1)
                grid.addWidget(account,0,2)
            else:
                second_layout.addWidget(label('Second amount (PKR)'))
                second_layout.addWidget(amount)
                second_layout.addWidget(account)
            self.payments.append((amount,account))
        grid.addWidget(button('Pay full total',self.pay_full),0,3)
        split=QCheckBox('Split between two accounts')
        split.toggled.connect(self.second_payment.setVisible)
        split.toggled.connect(lambda checked:self.payments[1][0].setText(self.payments[1][0].text() if checked else '0'))
        grid.addWidget(split,1,0,1,4)
        grid.addWidget(self.second_payment,2,0,1,4)
        self.second_payment.hide()
        if purchase:
            self.record_payment=QCheckBox('Record a payment from Cash / Bank now')
            self.record_payment.toggled.connect(group.setVisible)
            self.record_payment.toggled.connect(self.calculate)
            self.body.addWidget(self.record_payment)
            group.setVisible(False)
        self.body.addWidget(group)
        self.carry_billed=QCheckBox('Additional costs are included in the supplier bill')
        self.extra_costs=QCheckBox('Add transport / carry costs')
        self.extra_costs.toggled.connect(self.costs_changed)
        if purchase:
            self.body.addWidget(self.extra_costs)
            self.body.addWidget(self.carry_billed)
            self.carry_billed.toggled.connect(self.calculate)
            self.carry_billed.hide()
            self.transport_payment=QWidget()
            transport_layout=QHBoxLayout(self.transport_payment)
            transport_layout.setContentsMargins(0,0,0,0)
            self.carry_paid=AmountEdit('0')
            self.carry_account=combo(ctx.money.accounts(True))
            transport_layout.addWidget(label('Transport / carry paid now (PKR)'))
            transport_layout.addWidget(self.carry_paid)
            transport_layout.addWidget(self.carry_account)
            self.body.addWidget(self.transport_payment)
            self.transport_payment.hide()
        self.balance=label('','subtitle',True)
        self.layout.insertWidget(3,self.balance)
        advanced=QWidget()
        advanced_layout=QHBoxLayout(advanced)
        advanced_layout.setContentsMargins(0,0,0,0)
        self.notes=QLineEdit()
        self.notes.setPlaceholderText('Optional')
        self.legacy=QLineEdit()
        self.legacy.hide()
        advanced_layout.addWidget(label('Notes'))
        advanced_layout.addWidget(self.notes,2)
        extra=QCheckBox('Add notes')
        extra.toggled.connect(advanced.setVisible)
        self.body.addWidget(extra)
        self.body.addWidget(advanced)
        advanced.hide()
        self.save_handler=self.save
        if self.payment_mode:
            self.payment_mode.currentIndexChanged.connect(self.mode_changed)
        if self.type:
            self.type.currentIndexChanged.connect(self.type_changed)
            self.carry_currency.currentIndexChanged.connect(self.carry_currency_changed)
            self.type_changed()
        self.calculate()
        self.add_button.setFocus()

    def add_party(self):
        from mobile_desk.ui.people_money import PartyChooser
        d=PartyChooser(self,self.ctx,supplier=self.purchase,allow_new=True,selected=self.party.currentData())
        if d.exec():
            select_saved_party(self.party,self.ctx,d.result_id)

    def selected_party(self):
        index=self.party.currentIndex()
        if index>=0 and self.party.currentText()==self.party.itemText(index):
            return self.party.itemData(index)
        if self.party.currentText().strip():
            raise BusinessError('Choose a customer or supplier from the list, or use Add to create one.')
        return None

    def type_changed(self):
        foreign=self.type.currentData()=='CHINA_IMPORT'
        self.defaults.setVisible(foreign)
        self.rate_hint.setVisible(foreign)
        self.table.setColumnHidden(3,not foreign)
        self.table.horizontalHeaderItem(2).setText('Price / unit (RMB)' if foreign else 'Price / unit (PKR)')
        opening=self.type.currentData()=='OPENING'
        self.arrival.setEnabled(not opening)
        if opening:
            self.arrival.setCurrentIndex(0)
        self.carry_currency.setCurrentIndex(0 if foreign else 1)
        self.carry_currency_changed()
        self.record_payment.setVisible(not opening)
        if opening:
            self.record_payment.setChecked(False)
        self.costs_changed()
        self.calculate()

    def carry_currency_changed(self):
        unit='RMB' if self.type.currentData()=='CHINA_IMPORT' and self.carry_currency.currentData()=='CNY' else 'PKR'
        basis='stack total' if self.type.currentData()=='CHINA_IMPORT' else 'piece'
        self.carry_label.setText('Default carry / '+basis)
        self.table.horizontalHeaderItem(4).setText('Carry / '+basis+' ('+unit+')')
        self.calculate()

    def costs_changed(self,*args):
        if not self.purchase:
            return
        show=self.extra_costs.isChecked()
        self.table.setColumnHidden(4,not show)
        self.table.setColumnHidden(5,True)
        self.table.setColumnHidden(6,not show)
        self.carry_billed.setVisible(show and self.type.currentData()!='OPENING')
        self.transport_payment.setVisible(show and self.type.currentData()!='OPENING' and not self.carry_billed.isChecked())
        self.calculate()

    def mode_changed(self,*args):
        mode=self.payment_mode.currentIndex()
        self.payments[0][0].setReadOnly(mode==0)
        self.payment_group.setVisible(mode!=2)
        if mode==2:
            for amount,_ in self.payments:
                amount.setText('0')
        elif mode==0:
            self.pay_full()
        self.calculate()

    def pick_product(self):
        picker=ProductPicker(self,self.ctx)
        if picker.exec():
            self.add_product(picker.product)

    def add_product(self,product):
        row=self.table.rowCount()
        self.table.insertRow(row)
        entry=dict(product_id=product['id'],name=product['custom_name'])
        title=QTableWidgetItem(product['custom_name'])
        title.setFlags(title.flags()&~Qt.ItemFlag.ItemIsEditable)
        title.setToolTip(product['custom_name'])
        self.table.setItem(row,0,title)
        qty=QSpinBox()
        qty.setRange(1,1000000)
        qty.setValue(1)
        qty.valueChanged.connect(self.calculate)
        price=AmountEdit('0',6 if self.purchase else 2)
        price.textChanged.connect(self.calculate)
        entry.update(qty=qty,price=price)
        self.table.setCellWidget(row,1,qty)
        self.table.setCellWidget(row,2,price)
        if self.purchase:
            rate=AmountEdit(self.rate.value(),6)
            carry=AmountEdit(self.carry.value(),6 if self.carry_currency.currentData()=='CNY' else 2)
            rate.textChanged.connect(self.calculate)
            carry.textChanged.connect(self.calculate)
            entry.update(rate=rate,carry=carry)
            self.table.setCellWidget(row,3,rate)
            self.table.setCellWidget(row,4,carry)
        self.entries.append(entry)
        if self.type:
            self.type.setEnabled(False)
            self.carry_currency.setEnabled(False)
            self.type.setToolTip('Remove all product lines before changing purchase currency.')
        self.table.selectRow(row)
        self.calculate()
        qty.setFocus()
        qty.selectAll()

    def remove_line(self):
        row=self.table.currentRow()
        if 0<=row<len(self.entries):
            self.entries.pop(row)
            self.table.removeRow(row)
            if self.type and not self.entries:
                self.type.setEnabled(True)
                self.carry_currency.setEnabled(True)
            self.calculate()

    def lines(self):
        result=[]
        for e in self.entries:
            row=dict(product_id=e['product_id'],quantity=e['qty'].value())
            if self.purchase:
                row.update(unit_price=e['price'].value(),exchange_rate=e['rate'].value(),carry=e['carry'].value() if self.extra_costs.isChecked() else '0',carry_currency=self.carry_currency.currentData(),carry_basis='STACK_TOTAL' if self.type.currentData()=='CHINA_IMPORT' else 'PER_UNIT')
            else:
                row['selling_rate']=e['price'].value()
            result.append(row)
        return result

    def total(self):
        if self.purchase:
            return sum(price_line(r,self.type.currentData())['line_total_cost'] for r in self.lines())
        return sum(r['quantity']*money(r['selling_rate']) for r in self.lines())

    def bill_total(self):
        if not self.purchase:
            return self.total()
        if self.type.currentData()=='OPENING':
            return 0
        return sum(p['line_total_cost']-(0 if self.carry_billed.isChecked() else p['additional_cost_total']) for r in self.lines() for p in [price_line(r,self.type.currentData())])

    def calculate(self,*args):
        if not hasattr(self,'balance'):
            return
        try:
            total=0
            foreign=Decimal(0)
            foreign_carry=Decimal(0)
            for i,row in enumerate(self.lines()):
                if self.purchase:
                    priced=price_line(row,self.type.currentData())
                    line_total=priced['line_total_cost']
                    if priced['foreign_unit_price'] is not None:
                        foreign+=Decimal(priced['foreign_unit_price'])*row['quantity']
                    if priced['carry_currency']=='CNY':
                        foreign_carry+=Decimal(priced['carry_input'])*(1 if priced['carry_basis']=='STACK_TOTAL' else row['quantity'])
                    self.output(i,5,currency(priced['pkr_unit_purchase_cost']))
                    self.output(i,6,currency(priced['landed_unit_cost']))
                    self.output(i,7,currency(line_total))
                else:
                    line_total=row['quantity']*money(row['selling_rate'])
                    self.output(i,3,currency(line_total))
                total+=line_total
            bill=self.bill_total()
            if self.purchase:
                self.transport_payment.setVisible(self.extra_costs.isChecked() and self.type.currentData()!='OPENING' and not self.carry_billed.isChecked())
            if self.payment_mode and self.payment_mode.currentIndex()==0:
                amount=self.payments[0][0]
                amount.setReadOnly(True)
                amount.blockSignals(True)
                amount.setText(amount_text(max(0,bill-money(self.payments[1][0].value()))))
                amount.blockSignals(False)
            paid=sum(money(p['amount']) for p in self.payment_lines())
            self.totals.setText((f'Supplier bill PKR {currency(bill)}     Stock cost PKR {currency(total)}' if self.purchase else f'Total PKR {currency(total)}')+(f'\nPhones RMB {foreign:,.2f} · Stack carry RMB {foreign_carry:,.2f}' if self.purchase and self.type.currentData()=='CHINA_IMPORT' else ''))
            self.balance.setText(f'Paid now: PKR {currency(paid)}     '+('Supplier remaining: ' if self.purchase else 'Customer remaining: ')+f'PKR {currency(bill-paid)}')
            self.error.clear()
        except (BusinessError,ValueError):
            self.totals.setText('Complete the quantity, price and applicable exchange rate.')

    def output(self,row,col,value):
        item=QTableWidgetItem(value)
        item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row,col,item)

    def pay_full(self):
        try:
            self.payments[1][0].setText('0')
            self.payments[0][0].setText(amount_text(self.bill_total()))
        except BusinessError as e:
            self.error.setText(str(e))

    def save(self):
        if any(Decimal(e['price'].value())<=0 for e in self.entries):
            raise BusinessError('Enter a price for every product before saving.')
        payments=self.payment_lines()
        common=dict(payments=payments,notes=self.notes.text(),legacy_reference=self.legacy.text(),key=self.key)
        if self.purchase:
            supplier=self.selected_party()
            if self.bill_total()>sum(money(p['amount']) for p in payments) and not supplier:
                raise BusinessError('Choose a supplier to keep the unpaid purchase balance.')
            return self.ctx.purchases.post(day(self.date),self.lines(),purchase_type=self.type.currentData(),supplier_id=supplier,reference=self.reference.text(),default_rate=self.rate.value(),default_carry=self.carry.value(),carry_currency=self.carry_currency.currentData(),received=self.arrival.currentData()=='RECEIVED',carry_billed_to_supplier=self.extra_costs.isChecked() and self.carry_billed.isChecked(),carry_payment=self.carry_paid.value() if self.transport_payment.isVisibleTo(self) else '0',carry_account_id=self.carry_account.currentData(),**common)
        return self.ctx.sales.post(day(self.date),self.lines(),customer_id=self.selected_party(),**common)

    def payment_lines(self):
        if self.purchase and not self.record_payment.isChecked():
            return []
        return [dict(account_id=a.currentData(),amount=w.value()) for w,a in self.payments if money(w.value())>0]


class SalePicker(QDialog):
    def __init__(self,parent,ctx):
        super().__init__(parent)
        self.setWindowTitle('Choose original invoice')
        self.resize(900,600)
        self.sale=None
        self.ctx=ctx
        layout=QVBoxLayout(self)
        layout.addWidget(label('Find the original invoice','section'))
        self.search=QLineEdit()
        self.search.setPlaceholderText('Invoice number or customer…')
        layout.addWidget(self.search)
        self.table=DataTable([('invoice_number','Invoice'),('transaction_date','Date'),('customer_snapshot','Customer'),('total','Total PKR',currency),('status','Status')])
        layout.addWidget(self.table,1)
        layout.addWidget(button('Return selected invoice',self.select,True))
        self.table.cellDoubleClicked.connect(self.select)
        self.search.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.table.populate(self.ctx.sales.list(query=self.search.text(),limit=100))

    def select(self,*args):
        self.sale=self.table.selected()
        if self.sale and self.sale['status']=='POSTED':
            self.accept()


class ReturnDialog(EntryDialog):
    def __init__(self,parent,ctx,sale_id):
        super().__init__(parent,'Return Sale',950)
        self.ctx=ctx
        self.sale_id=sale_id
        self.sale,self.items,_=ctx.sales.details(sale_id)
        self.resize(950,700)
        self.body.insertWidget(0,label(self.sale['invoice_number']+' · '+self.sale['customer_snapshot'],'subtitle'))
        self.date=self.field('Return date',date_edit())
        self.table=QTableWidget(len(self.items),5)
        self.table.setHorizontalHeaderLabels(['Product','Sold','Already returned','Return now','Selling price PKR'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setMinimumHeight(220)
        self.quantities=[]
        for i,item in enumerate(self.items):
            for j,key in ((0,'product_description_snapshot'),(1,'quantity'),(2,'returned_quantity'),(4,'selling_rate')):
                cell=QTableWidgetItem(currency(item[key]) if j==4 else str(item[key]))
                cell.setFlags(cell.flags()&~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i,j,cell)
            qty=QSpinBox()
            qty.setRange(0,item['quantity']-item['returned_quantity'])
            qty.valueChanged.connect(self.calculate)
            self.table.setCellWidget(i,3,qty)
            self.quantities.append(qty)
        self.body.addWidget(self.table,1)
        self.total_label=label('Return total PKR 0.00','section')
        self.body.addWidget(self.total_label)
        self.refund=self.field('Refund now (PKR)',AmountEdit())
        self.account=self.field('Refund from account',combo(ctx.money.accounts(True)))
        self.body.addWidget(label('The remaining returned value reduces the customer balance. Original purchase costs are restored automatically.','subtitle',True))
        self.body.addWidget(button('Refund full return value',self.full_refund))
        self.save_button.setText('Save Return')
        self.save_handler=self.save

    def calculate(self):
        if hasattr(self,'total_label'):
            value=sum(item['selling_rate']*w.value() for item,w in zip(self.items,self.quantities))
            self.total_label.setText('Return total PKR '+currency(value))
            if not self.sale['customer_id']:
                self.refund.setText(amount_text(value))

    def full_refund(self):
        value=sum(item['selling_rate']*w.value() for item,w in zip(self.items,self.quantities))
        self.refund.setText(amount_text(value))

    def save(self):
        lines=[dict(sale_item_id=item['id'],quantity=w.value()) for item,w in zip(self.items,self.quantities) if w.value()]
        return self.ctx.returns.post(day(self.date),self.sale_id,lines,refund=self.refund.value(),account_id=self.account.currentData(),notes='Customer return',key=self.key)
