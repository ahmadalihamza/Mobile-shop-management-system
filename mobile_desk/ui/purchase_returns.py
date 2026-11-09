"""Review quantities, authenticate the owner, and confirm only money actually received."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit,QCheckBox,QComboBox,QSpinBox,QTableWidget,QTableWidgetItem,QHeaderView
from mobile_desk.ui.common import EntryDialog,AmountEdit,label,combo,date_edit,day,button
from mobile_desk.ui.security import password_field,OwnerSetupDialog
from mobile_desk.values import BusinessError,currency,money,amount_text


def owner_fields(dialog,ctx):
    if not ctx.security.configured:
        dialog.body.addWidget(label('The owner must set a password before a return, cancellation or refund can be finalized.','notice',True))
        dialog.body.addWidget(button('Set owner password',lambda:OwnerSetupDialog(dialog,ctx).exec()))
    dialog.username=dialog.field('Owner username',QLineEdit(ctx.security.username))
    dialog.password=dialog.field('Owner password',password_field())


class PurchaseReturnDialog(EntryDialog):
    def __init__(self,parent,ctx,purchase_id):
        self.ctx,self.purchase_id=ctx,purchase_id
        self.preview=ctx.purchase_returns.preview(purchase_id)
        self.batch=self.preview['header']
        cancelling=self.preview['kind']=='CANCELLATION'
        super().__init__(parent,'Purchase Cancellation' if cancelling else 'Stock Return to Supplier',1040)
        self.resize(1040,780)
        self.body.addWidget(label(self.batch['reference']+' · '+self.batch['supplier_snapshot']+'\n'+('Awaiting arrival: cancel selected ordered pieces.' if cancelling else 'Return only pieces still physically available from this purchase.'),'section',True))
        self.date=self.field('Cancellation / return date',date_edit())
        self.table=QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['Product','Bought','Already returned','Available to return','Return now'])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in range(1,5):
            self.table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(170)
        groups={}
        for lot in self.preview['lines']:
            key=('stack',lot['stack_id']) if lot.get('stack_id') else ('lot',lot['id'])
            if key not in groups:
                groups[key]=dict(product_description_snapshot=lot['product_description_snapshot'],quantity=0,returned_quantity=0,returnable_quantity=0,parts=[])
            group=groups[key]
            for field in ('quantity','returned_quantity','returnable_quantity'):
                group[field]+=lot[field]
            group['parts'].append(lot)
        self.return_groups=list(groups.values())
        self.quantities=[]
        for row,lot in enumerate(self.return_groups):
            self.table.insertRow(row)
            for column,value in enumerate((lot['product_description_snapshot'],lot['quantity'],lot['returned_quantity'],lot['returnable_quantity'])):
                item=QTableWidgetItem(str(value))
                item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row,column,item)
            qty=QSpinBox()
            qty.setRange(0,lot['returnable_quantity'])
            qty.setValue(lot['returnable_quantity'])
            self.quantities.append(qty)
            self.table.setCellWidget(row,4,qty)
        self.body.addWidget(self.table,1)
        self.body.addWidget(label('The original purchase and payments stay in history. The returned value reduces the supplier bill. Cash / Bank changes only for a confirmed refund below.','subtitle',True))
        self.refund_confirmed=self.field('Refund',QCheckBox('Money has actually been received back'))
        self.refund=self.field('Confirmed refund (PKR)',AmountEdit())
        self.account=self.field('Refund received into',combo(ctx.money.accounts(True)))
        self.payer=self.field('Refund from',QComboBox())
        self.payer.addItem('Supplier','SUPPLIER')
        self.payer.addItem('Transport / carrier','CARRIER')
        owner_fields(self,ctx)
        self.summary=label('','notice',True)
        self.layout.insertWidget(2,self.summary)
        self.confirmation=QCheckBox('I confirm the purchase, quantities and actual refund shown above')
        self.layout.insertWidget(3,self.confirmation)
        self.save_button.setText('Authorize and Finalize')
        self.save_button.setObjectName('danger')
        self.save_handler=self.save
        for qty in self.quantities:
            qty.valueChanged.connect(self.calculate)
        self.refund_confirmed.toggled.connect(self.calculate)
        self.refund.textChanged.connect(self.calculate)
        self.account.currentIndexChanged.connect(self.calculate)
        self.payer.currentIndexChanged.connect(self.calculate)
        self.calculate()

    def calculate(self):
        credit=cost=count=0
        for lot,qty in self.selected_parts():
            count+=qty
            cost+=qty*lot['landed_unit_cost']
            credit+=qty*lot['supplier_credit_per_unit']
        confirmed=self.refund_confirmed.isChecked()
        for field in (self.refund,self.account,self.payer):
            self.form.setRowVisible(field,confirmed)
        try:
            refund=money(self.refund.value()) if confirmed else 0
            value_label='Landed value cancelled' if self.preview['kind']=='CANCELLATION' else 'Landed stock cost removed'
            self.summary.setText(f"Review {self.batch['reference']} · {self.batch['supplier_snapshot']}\nPieces: {count} · {value_label}: PKR {currency(cost)}\nSupplier bill credit: PKR {currency(credit)}\nMoney received now: PKR {currency(refund)}"+(' into '+self.account.currentText() if confirmed else ' — no cash refund recorded yet.'))
        except BusinessError:
            self.summary.setText('Enter the actual refund amount in PKR.')
        self.confirmation.setChecked(False)

    def selected_parts(self):
        result=[]
        for group,widget in zip(self.return_groups,self.quantities):
            left=widget.value()
            for lot in group['parts']:
                take=min(left,lot['returnable_quantity'])
                if take:
                    result.append((lot,take))
                    left-=take
        return result

    def save(self):
        if not self.confirmation.isChecked():
            raise BusinessError('Review the purchase, quantities and refund, then tick the confirmation.')
        lines=[dict(purchase_item_id=lot['id'],quantity=qty) for lot,qty in self.selected_parts()]
        return self.ctx.purchase_returns.post(self.purchase_id,day(self.date),lines,username=self.username.text(),password=self.password.text(),refund_amount=self.refund.value() if self.refund_confirmed.isChecked() else '0',refund_account_id=self.account.currentData(),refund_payer=self.payer.currentData(),key=self.key)


class PurchaseRefundDialog(EntryDialog):
    def __init__(self,parent,ctx,return_id):
        super().__init__(parent,'Confirm Purchase Refund Received',740)
        self.ctx,self.return_id=ctx,return_id
        details=ctx.purchase_returns.details(return_id)
        self.purchase=details['purchase']
        self.body.addWidget(label(self.purchase['reference']+f' · Return / cancellation PR-{return_id}\n'+self.purchase['supplier_snapshot'],'section',True))
        self.body.addWidget(label('Record only money actually received. Supplier refunds settle supplier credit; transport refunds are tracked separately. The purchase and original payments remain in history.','subtitle',True))
        self.date=self.field('Refund received date',date_edit())
        self.payer=self.field('Refund from',QComboBox())
        self.payer.addItem('Supplier','SUPPLIER')
        self.payer.addItem('Transport / carrier','CARRIER')
        self.amount=self.field('Actual refund (PKR)',AmountEdit())
        self.account=self.field('Received into',combo(ctx.money.accounts(True)))
        self.reference=self.field('Refund reference',QLineEdit())
        self.notes=self.field('Notes',QLineEdit())
        owner_fields(self,ctx)
        self.summary=label('','notice',True)
        self.layout.insertWidget(2,self.summary)
        self.confirmation=QCheckBox('I confirm this money has been received into the account shown')
        self.layout.insertWidget(3,self.confirmation)
        self.save_button.setText('Authorize and Record Refund')
        self.save_handler=self.save
        self.payer.currentIndexChanged.connect(self.calculate)
        self.date.dateChanged.connect(self.calculate)
        self.amount.textChanged.connect(self.calculate)
        self.account.currentIndexChanged.connect(self.calculate)
        self.calculate()

    def calculate(self):
        limits=self.ctx.purchase_returns.refund_limits(self.return_id,day(self.date))
        limit=limits['carrier' if self.payer.currentData()=='CARRIER' else 'supplier']
        self.summary.setText(f"{self.purchase['reference']} · Available {self.payer.currentText().lower()} refund: PKR {currency(limit)}\nActual money received: PKR {self.amount.value()} into {self.account.currentText()}.\nNo money is added until this confirmed refund is saved.")
        self.confirmation.setChecked(False)

    def save(self):
        if not self.confirmation.isChecked():
            raise BusinessError('Review the actual refund and account, then tick the confirmation.')
        return self.ctx.purchase_returns.confirm_refund(self.return_id,day(self.date),self.account.currentData(),self.amount.value(),self.username.text(),self.password.text(),payer=self.payer.currentData(),reference=self.reference.text(),notes=self.notes.text(),key=self.key)


class ReceivePurchaseDialog(EntryDialog):
    def __init__(self,parent,ctx,purchase_id):
        super().__init__(parent,'Mark Shipment Received',690)
        preview=ctx.purchase_returns.preview(purchase_id)
        header=preview['header']
        remaining=sum(row['unreturned_quantity'] for row in preview['lines'])
        self.body.addWidget(label(header['reference']+' · '+header['supplier_snapshot']+f'\n{remaining} pieces will become available for sale. Cancelled pieces stay excluded.','section',True))
        self.date=self.field('Actual arrival date',date_edit())
        self.confirmation=QCheckBox('These remaining phones have physically arrived')
        self.body.addWidget(self.confirmation)
        self.save_button.setText('Confirm Stock Received')
        def save():
            if not self.confirmation.isChecked():
                raise BusinessError('Confirm that this shipment has physically arrived.')
            return ctx.purchases.receive(purchase_id,day(self.date))
        self.save_handler=save
