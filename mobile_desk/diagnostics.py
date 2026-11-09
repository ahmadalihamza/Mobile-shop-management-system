"""Explicit isolated release diagnostics; never called during normal operation."""
from pathlib import Path
from PySide6.QtCore import QDate
from PySide6.QtGui import QTextDocument,QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QDialog
from mobile_desk.context import Context
from mobile_desk.ui.products import ProductDialog
from mobile_desk.ui.transactions import TransactionDialog,ReturnDialog
from mobile_desk.ui.people_money import PaymentDialog
from mobile_desk.ui.main_window import MainWindow
from mobile_desk.values import money


def release_flow(root,output):
    """Exercise real Qt form submission and persistence in a fresh test root."""
    root=Path(root)
    if (root/'data/mobile_desk.db').exists():
        raise RuntimeError('Release flow requires a fresh data folder.')
    ctx=Context(root,install_catalogue=False)
    customer=ctx.parties.save('Practice QA customer')
    supplier=ctx.parties.save('Practice QA supplier',is_customer=False,is_supplier=True)
    cash=ctx.money.accounts()[0]['id']
    bank=ctx.money.account('Practice QA bank')

    def post(dialog):
        if hasattr(dialog,'date'):
            dialog.date.setDate(QDate(2026,9,30))
        dialog.save_button.click()
        if dialog.result()!=QDialog.DialogCode.Accepted:
            raise AssertionError(dialog.error.text())
        return dialog.result_id

    products=[]
    for name in ('Practice manual phone 8/256','Practice second phone'):
        d=ProductDialog(None,ctx)
        d.manual()
        d.name.setText(name)
        products.append(ctx.products.get(post(d)))
    local=TransactionDialog(None,ctx,True)
    local.party.setCurrentIndex(local.party.findData(supplier))
    for product,quantity,price in ((products[0],5,'40000'),(products[1],2,'10000')):
        local.add_product(product)
        local.entries[-1]['qty'].setValue(quantity)
        local.entries[-1]['price'].setText(price)
    post(local)
    china=TransactionDialog(None,ctx,True)
    china.type.setCurrentIndex(1)
    china.carry_currency.setCurrentIndex(china.carry_currency.findData('PKR'))
    china.party.setCurrentIndex(china.party.findData(supplier))
    china.extra_costs.setChecked(True)
    china.rate.setText('41')
    china.carry.setText('40000')
    china.add_product(products[0])
    china.entries[0]['qty'].setValue(10)
    china.entries[0]['price'].setText('1000')
    china_id=post(china)
    ctx.money.add_rate('2026-10-01','99','Release diagnostic')
    assert ctx.purchases.details(china_id)[1][0]['landed_unit_cost']==money('45000')
    sale=TransactionDialog(None,ctx)
    sale.party.setCurrentIndex(sale.party.findData(customer))
    for product,quantity,price in ((products[0],8,'50000'),(products[1],1,'15000')):
        sale.add_product(product)
        sale.entries[-1]['qty'].setValue(quantity)
        sale.entries[-1]['price'].setText(price)
    sale.payment_mode.setCurrentIndex(1)
    sale.payments[0][0].setText('30000')
    sale_id=post(sale)
    header,items,_=ctx.sales.details(sale_id)
    assert header['total']==money('415000')
    assert sum(i['cogs'] for i in items)==money('345000')
    assert ctx.parties.balance(customer)==money('385000')
    collection=PaymentDialog(None,ctx,customer)
    collection.amount.setText('20000')
    collection.account.setCurrentIndex(collection.account.findData(bank))
    post(collection)
    ret=ReturnDialog(None,ctx,sale_id)
    ret.quantities[0].setValue(2)
    ret.refund.setText('10000')
    ret.account.setCurrentIndex(ret.account.findData(cash))
    ret.show()
    from PySide6.QtWidgets import QApplication
    QApplication.instance().processEvents()
    ret.grab().save(str(output/'return_sale.png'))
    post(ret)
    assert ctx.stock.totals()==dict(quantity=10,value=money('405000'))
    assert ctx.parties.balance(customer)==money('275000')
    ctx.money.expense('2026-09-30','Practice delivery','1500',cash)
    ctx.money.transfer('2026-09-30',cash,bank,'5000')
    profit=ctx.reports.period_profit('2026-09-01','2026-09-30')
    assert profit['profit_after_expenses']==money('48500')
    balances={r['id']:r['balance'] for r in ctx.money.accounts()}
    assert balances=={cash:money('13500'),bank:money('25000')}
    payable=ctx.parties.balance(supplier,role='SUPPLIER')
    assert payable==money('630000')
    supplier_payment=PaymentDialog(None,ctx,supplier,supplier=True)
    supplier_payment.amount.setText('100000')
    supplier_payment.account.setCurrentIndex(supplier_payment.account.findData(bank))
    post(supplier_payment)
    assert ctx.parties.balance(supplier,role='SUPPLIER')==money('530000')
    assert ctx.parties.documents(supplier,role='SUPPLIER')[0]['outstanding']==money('120000')
    invoice_window=MainWindow(ctx)
    doc=QTextDocument()
    doc.setHtml(invoice_window.invoice_html(sale_id))
    printer=QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    pdf=output/'sample-invoice.pdf'
    printer.setOutputFileName(str(pdf))
    doc.print_(printer)
    assert pdf.read_bytes().startswith(b'%PDF-') and pdf.stat().st_size>1000
    invoice_window.close()
    backup=ctx.backups.create()
    ctx.products.save(custom_name='After-backup product')
    ctx.backups.restore(backup)
    restored=Context(root,install_catalogue=False)
    assert len(restored.products.search())==2
    assert restored.stock.totals()['value']==money('405000')
    assert restored.parties.balance(customer)==money('275000')
    assert restored.parties.balance(supplier,role='SUPPLIER')==money('530000')
    assert restored.db.one('PRAGMA integrity_check')['integrity_check']=='ok'
    from mobile_desk.ui.security import OwnerSetupDialog,UndoDialog,ResetDialog,OwnerAuthorizationDialog
    import secrets
    password=secrets.token_urlsafe(24)
    def capture(name,dialog):
        dialog.show()
        QApplication.instance().processEvents()
        dialog.grab().save(str(output/(name+'.png')))
    owner=OwnerSetupDialog(None,restored)
    owner.username.setText('release-owner')
    owner.password.setText(password)
    owner.confirmation.setText(password)
    capture('owner_password',owner)
    post(owner)
    before=[a['balance'] for a in restored.money.accounts()]
    restored.money.expense('2026-09-30','Learning entry to undo','1000',cash)
    undo=UndoDialog(None,restored,restored.corrections.latest())
    capture('undo_last_entry',undo)
    post(undo)
    assert [a['balance'] for a in restored.money.accounts()]==before
    reset=ResetDialog(None,restored)
    reset.password.setText('incorrect password')
    reset.confirmation.setText('RESET')
    reset.commit()
    assert 'Incorrect' in reset.error.text() and restored.stock.totals()['quantity']==10
    reset.error.clear()
    reset.password.setText(password)
    capture('reset_all_data',reset)
    safety=post(reset)
    clean=Context(root,install_catalogue=False)
    assert not clean.products.search() and not clean.sales.list() and not clean.purchases.list()
    assert clean.stock.totals()==dict(quantity=0,value=0)
    assert all(a['balance']==0 for a in clean.money.accounts()) and clean.security.configured
    authorization=OwnerAuthorizationDialog(None,clean,'Authorize backup restore')
    authorization.password.setText(password)
    capture('owner_restore',authorization)
    credentials=post(authorization)
    clean.backups.restore(safety,**credentials)
    recovered=Context(root,install_catalogue=False)
    assert recovered.stock.totals()['value']==money('405000')
    assert recovered.parties.balance(customer)==money('275000')
    assert recovered.parties.balance(supplier,role='SUPPLIER')==money('530000')
    assert recovered.security.configured
    return dict(status='passed',checks=['manual products','local multi-line purchase','China FX snapshot','multi-item sale','multi-lot FIFO','partial customer credit','supplier bill and later supplier payment','per-bill remaining balance','bank collection','linked return and refund','exact restored lot costs','expense','transfer','profit and balances','invoice PDF','backup and restore','SQLite integrity','owner password setup','undo latest expense','wrong reset password blocked','full reset to zero','owner credentials survive reset','owner authorized recovery of cleared entries'])
