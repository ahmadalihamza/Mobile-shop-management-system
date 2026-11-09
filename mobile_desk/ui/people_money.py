from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit,QCheckBox,QComboBox,QHBoxLayout,QWidget,QVBoxLayout,QFormLayout,QTabWidget
from mobile_desk.ui.common import EntryDialog,AmountEdit,combo,date_edit,day,label,button,DataTable,party_combo,party_selection_name,select_saved_party
from mobile_desk.values import amount_text,currency,BusinessError


class PartyFields(QWidget):
    def __init__(self,ctx,party=None,supplier=False):
        super().__init__()
        self.ctx,self.party=ctx,party
        self.body=QVBoxLayout(self)
        self.body.setContentsMargins(0,0,0,0)
        self.form=QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setSpacing(10)
        self.body.addLayout(self.form)
        self.name=self.field('Name',QLineEdit(party['name'] if party else ''))
        self.customer=self.field('Customer',QCheckBox('Buys from the shop'))
        self.supplier=self.field('Supplier',QCheckBox('Supplies phones to the shop'))
        self.customer.setChecked(bool(party['is_customer']) if party else not supplier)
        self.supplier.setChecked(bool(party['is_supplier']) if party else supplier)
        self.phone=self.field('Phone',QLineEdit(party.get('phone','') if party else ''))
        self.address=self.field('Address',QLineEdit(party.get('address','') if party else ''))
        self.notes=self.field('Notes',QLineEdit(party.get('notes','') if party else ''))
        self.active=self.field('Available for new entries',QCheckBox('Active'))
        self.active.setChecked(bool(party['active']) if party else True)
        extra=QCheckBox('Contact details, roles and availability')
        extra.setChecked(bool(party))
        self.body.addWidget(extra)
        def reveal(visible):
            for w in (self.customer,self.supplier,self.address,self.notes,self.active):
                self.form.setRowVisible(w,visible)
        extra.toggled.connect(reveal)
        reveal(bool(party))
        self.body.addStretch()

    def field(self,title,widget):
        self.form.addRow(title,widget)
        return widget

    def save(self):
        return self.ctx.parties.save(self.name.text(),party_id=self.party['id'] if self.party else None,is_customer=self.customer.isChecked(),is_supplier=self.supplier.isChecked(),phone=self.phone.text(),address=self.address.text(),notes=self.notes.text(),active=self.active.isChecked())


class PartyDialog(EntryDialog):
    def __init__(self,parent,ctx,party=None,supplier=False):
        super().__init__(parent,'Edit Contact' if party else 'Add Supplier' if supplier else 'Add Customer',650)
        self.fields=PartyFields(ctx,party,supplier)
        self.body.addWidget(self.fields)
        for name in ('name','customer','supplier','phone','address','notes','active'):
            setattr(self,name,getattr(self.fields,name))
        self.save_handler=self.fields.save
        self.name.setFocus()


class PartyChooser(EntryDialog):
    """Search existing accounts by identity; create only through the explicit new tab."""
    def __init__(self,parent,ctx,supplier=False,allow_new=False,selected=None):
        kind='supplier' if supplier else 'customer'
        super().__init__(parent,'Choose '+kind.title(),860)
        self.ctx,self.supplier=ctx,supplier
        self.role='is_supplier' if supplier else 'is_customer'
        self.offset,self.limit=0,100
        self.selected_id=selected
        self.tabs=QTabWidget()
        self.body.addWidget(self.tabs,1)
        existing=QWidget()
        layout=QVBoxLayout(existing)
        layout.addWidget(label('Select the saved account to keep all its bills and payments together.','subtitle',True))
        self.search=QLineEdit()
        self.search.setPlaceholderText('Search saved '+kind+'s by name or phone…')
        layout.addWidget(self.search)
        self.table=DataTable([('selection_name','Name / account'),('phone','Phone'),('address','Address'),('supplier_balance' if supplier else 'balance','Payable PKR' if supplier else 'Receivable PKR',currency)])
        layout.addWidget(self.table,1)
        paging=QHBoxLayout()
        self.count=label('')
        self.previous=button('Previous',lambda:self.move(-self.limit))
        self.next=button('Next',lambda:self.move(self.limit))
        paging.addWidget(self.count)
        paging.addStretch()
        paging.addWidget(self.previous)
        paging.addWidget(self.next)
        layout.addLayout(paging)
        self.tabs.addTab(existing,'Existing '+kind+'s')
        self.new_fields=None
        if allow_new:
            new=QWidget()
            new_layout=QVBoxLayout(new)
            new_layout.addWidget(label('Create a contact only when this is a different person or business. For another purchase from the same supplier, select its existing account.','subtitle',True))
            self.new_fields=PartyFields(ctx,supplier=supplier)
            new_layout.addWidget(self.new_fields,1)
            self.tabs.addTab(new,'New '+kind)
        if selected:
            current=ctx.db.one('SELECT name FROM parties WHERE id=?',(selected,))
            if current:
                self.search.setText(current['name'])
        self.search.textChanged.connect(self.reset_search)
        self.table.cellDoubleClicked.connect(lambda:self.commit())
        self.tabs.currentChanged.connect(self.mode_changed)
        self.save_handler=self.choose
        self.refresh()
        self.mode_changed()

    def refresh(self):
        rows=self.ctx.parties.search(self.search.text(),role=self.role,limit=self.limit+1,offset=self.offset,active_only=True)
        for row in rows:
            row['selection_name']=party_selection_name(row)
        self.table.populate(rows[:self.limit])
        for index,row in enumerate(self.table.data_rows):
            if row['id']==self.selected_id:
                self.table.selectRow(index)
                break
        self.previous.setEnabled(self.offset>0)
        self.next.setEnabled(len(rows)>self.limit)
        self.count.setText(f'{self.offset+1}–{self.offset+self.table.rowCount()}' if rows else 'No saved contacts found')

    def reset_search(self):
        self.offset=0
        self.refresh()

    def move(self,step):
        self.offset=max(0,self.offset+step)
        self.refresh()

    def mode_changed(self):
        self.error.clear()
        new=self.tabs.currentIndex()==1
        self.save_button.setText('Save New '+('Supplier' if self.supplier else 'Customer') if new else 'Use Selected '+('Supplier' if self.supplier else 'Customer'))
        (self.new_fields.name if new else self.search).setFocus()

    def choose(self):
        if self.tabs.currentIndex()==1:
            return self.new_fields.save()
        row=self.table.selected()
        if not row:
            raise BusinessError('Select a saved supplier.' if self.supplier else 'Select a saved customer.')
        if not self.ctx.db.one('SELECT id FROM parties WHERE id=? AND active=1 AND '+self.role+'=1',(row['id'],)):
            raise BusinessError('This contact is no longer available. Choose another saved contact.')
        return row['id']


class PaymentDialog(EntryDialog):
    def __init__(self,parent,ctx,party_id=None,supplier=False):
        super().__init__(parent,'Pay Supplier' if supplier else 'Receive Customer Payment',680)
        self.ctx=ctx
        self.supplier=supplier
        self.role='SUPPLIER' if supplier else 'CUSTOMER'
        party_row=QWidget()
        row=QHBoxLayout(party_row)
        row.setContentsMargins(0,0,0,0)
        self.party=party_combo(ctx,'is_supplier' if supplier else 'is_customer','Choose supplier' if supplier else 'Choose customer',party_id)
        row.addWidget(self.party,1)
        self.choose_button=button('Choose from list',self.choose_party)
        row.addWidget(self.choose_button)
        self.field('Supplier' if supplier else 'Customer',party_row)
        self.balance=label('','section')
        self.body.addWidget(self.balance)
        self.date=self.field('Date',date_edit())
        self.amount=self.field('Amount paid (PKR)' if supplier else 'Amount received (PKR)',AmountEdit())
        self.account=self.field('Pay from' if supplier else 'Receive into',combo(ctx.money.accounts(True)))
        self.reference=self.field('Reference',QLineEdit())
        self.notes=self.field('Notes',QLineEdit())
        self.party.currentIndexChanged.connect(self.refresh)
        self.refresh()
        self.save_handler=self.save
        self.amount.setFocus()
        self.amount.selectAll()

    def choose_party(self):
        dialog=PartyChooser(self,self.ctx,supplier=self.supplier,selected=self.party.currentData())
        if dialog.exec():
            select_saved_party(self.party,self.ctx,dialog.result_id)

    def refresh(self):
        identity=self.party.currentData()
        self.balance.setText('Current balance: PKR '+currency(self.ctx.parties.balance(identity,role=self.role)) if identity else 'Choose a supplier' if self.supplier else 'Choose a customer')

    def save(self):
        if not self.party.currentData() or self.party.currentText()!=self.party.itemText(self.party.currentIndex()):
            raise BusinessError('Choose a supplier from the list.' if self.supplier else 'Choose a customer from the list.')
        handler=self.ctx.money.pay_supplier if self.supplier else self.ctx.money.collect
        return handler(self.party.currentData(),day(self.date),self.account.currentData(),self.amount.value(),self.reference.text(),self.notes.text(),key=self.key)


class AdjustmentDialog(EntryDialog):
    def __init__(self,parent,ctx,party_id,supplier=False):
        super().__init__(parent,'Supplier Balance Adjustment' if supplier else 'Customer Balance Adjustment',650)
        self.date=self.field('Date',date_edit())
        self.kind=self.field('Adjustment',QComboBox())
        choices=[('Opening balance','OPENING_BALANCE'),('Reduce balance','MANUAL_CREDIT'),('Add to balance','MANUAL_DEBIT')]
        if not supplier:
            choices.insert(1,('Agreed discount','DISCOUNT'))
        for name,key in choices:
            self.kind.addItem(name,key)
        self.amount=self.field('Amount (PKR)',AmountEdit())
        self.credit=self.field('Opening balance direction',QCheckBox('Supplier owes shop (advance held)' if supplier else 'Shop owes customer (customer has credit)'))
        self.body.addWidget(label('Opening balances bring earlier records into Mobile Desk. Later sales and payments calculate balances automatically.','subtitle',True))
        self.save_handler=lambda:ctx.parties.adjustment(party_id,day(self.date),self.kind.currentData(),self.amount.value(),opening_credit=self.credit.isChecked(),role='SUPPLIER' if supplier else 'CUSTOMER')


class AccountDialog(EntryDialog):
    def __init__(self,parent,ctx,account=None):
        super().__init__(parent,'Edit Account' if account else 'Add Cash / Bank Account',650)
        self.name=self.field('Account name',QLineEdit(account['name'] if account else ''))
        self.kind=self.field('Type',QComboBox())
        self.kind.addItem('Bank','BANK')
        self.kind.addItem('Cash','CASH')
        if account:
            self.kind.setCurrentIndex(self.kind.findData(account['account_type']))
            self.kind.setEnabled(False)
        self.opening=self.field('Opening amount (PKR)',AmountEdit(amount_text(abs(account['opening_balance'])) if account else '0'))
        self.negative=self.field('Opening balance direction',QCheckBox('Negative opening balance'))
        self.negative.setChecked(bool(account and account['opening_balance']<0))
        self.date=self.field('Opening date',date_edit(account['opening_date'] if account else None))
        self.active=self.field('Available for new entries',QCheckBox('Active account'))
        self.active.setChecked(bool(account['active']) if account else True)
        if account and ctx.db.one("SELECT 1 FROM money_ledger WHERE account_id=? AND kind!='OPENING' LIMIT 1",(account['id'],)):
            self.opening.setEnabled(False)
            self.date.setEnabled(False)
            self.negative.setEnabled(False)
        self.save_handler=lambda:ctx.money.account(self.name.text(),self.kind.currentData(),self.opening.value(),day(self.date),account_id=account['id'] if account else None,active=self.active.isChecked(),negative_opening=self.negative.isChecked())


class ExpenseDialog(EntryDialog):
    def __init__(self,parent,ctx):
        super().__init__(parent,'Record Expense',650)
        self.date=self.field('Date',date_edit())
        self.description=self.field('Description',QLineEdit())
        self.amount=self.field('Amount (PKR)',AmountEdit())
        self.account=self.field('Paid from',combo(ctx.money.accounts(True)))
        self.category=self.field('Category (optional)',QLineEdit())
        self.notes=self.field('Notes',QLineEdit())
        self.save_handler=lambda:ctx.money.expense(day(self.date),self.description.text(),self.amount.value(),self.account.currentData(),self.category.text(),self.notes.text(),key=self.key)


class TransferDialog(EntryDialog):
    def __init__(self,parent,ctx):
        super().__init__(parent,'Transfer Between Accounts',650)
        self.date=self.field('Date',date_edit())
        self.source=self.field('From',combo(ctx.money.accounts(True)))
        self.dest=self.field('To',combo(ctx.money.accounts(True)))
        if self.dest.count()>1:
            self.dest.setCurrentIndex(1)
        self.amount=self.field('Amount (PKR)',AmountEdit())
        self.reference=self.field('Reference',QLineEdit())
        self.notes=self.field('Notes',QLineEdit())
        self.body.addWidget(label('Transfers move money between your accounts. They do not change sales or profit.','subtitle',True))
        self.save_handler=lambda:ctx.money.transfer(day(self.date),self.source.currentData(),self.dest.currentData(),self.amount.value(),self.reference.text(),self.notes.text(),key=self.key)


class RateDialog(EntryDialog):
    def __init__(self,parent,ctx):
        super().__init__(parent,'Remember RMB Exchange Rate',620)
        self.date=self.field('Date',date_edit())
        self.rate=self.field('PKR for 1 RMB',AmountEdit('40.3',6))
        self.notes=self.field('Notes',QLineEdit())
        self.body.addWidget(label('This rate will be suggested for new purchases. Saved purchase costs stay unchanged.','subtitle',True))
        self.save_handler=lambda:ctx.money.add_rate(day(self.date),self.rate.value(),self.notes.text())


class CarryPaymentDialog(EntryDialog):
    def __init__(self,parent,ctx,batch):
        super().__init__(parent,'Pay Transport / Carry',650)
        remaining=ctx.money.carry_remaining(batch['id'])
        self.body.addWidget(label(batch['reference']+' · Remaining PKR '+currency(remaining),'section',True))
        self.date=self.field('Payment date',date_edit())
        self.amount=self.field('Amount (PKR)',AmountEdit(amount_text(remaining)))
        self.account=self.field('Pay from',combo(ctx.money.accounts(True)))
        self.notes=self.field('Notes',QLineEdit())
        self.body.addWidget(label('This records money paid for costs already included in this stock. It does not deduct the cost from profit again.','subtitle',True))
        self.save_handler=lambda:ctx.money.pay_carry(batch['id'],day(self.date),self.account.currentData(),self.amount.value(),self.notes.text(),key=self.key)
