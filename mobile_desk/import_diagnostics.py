"""Isolated native Windows acceptance flow for import, stack charges and refunds."""
from pathlib import Path
import json
import secrets
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication,QDialog
from mobile_desk.context import Context
from mobile_desk.ui.transactions import TransactionDialog
from mobile_desk.ui.purchase_returns import PurchaseReturnDialog,PurchaseRefundDialog,ReceivePurchaseDialog
from mobile_desk.ui.main_window import MainWindow
from mobile_desk.values import money


def import_release_flow(root,output):
    root,output=Path(root),Path(output)
    if (root/'data/mobile_desk.db').exists():
        raise RuntimeError('Import acceptance requires a fresh isolated folder.')
    ctx=Context(root,install_catalogue=False)
    user,password='import-qa-owner',secrets.token_urlsafe(24)
    ctx.security.set_password(user,password,password)
    ctx.money.save_settings(shop_name='Mobile Desk — Import practice',setup_complete='1')
    supplier=ctx.parties.save('China training supplier',is_customer=False,is_supplier=True)
    product=ctx.products.save(custom_name='Huawei P30 Pro')
    cash=ctx.money.accounts()[0]['id']
    bank=ctx.money.account('Import QA Bank')
    app=QApplication.instance()
    screens=[]
    window=MainWindow(ctx)
    window.resize(1366,768)

    def capture(widget,name):
        widget.show()
        app.processEvents()
        if not widget.grab().save(str(output/(name+'.png'))):
            raise AssertionError('Could not save '+name)
        screens.append(name)

    def post(dialog):
        dialog.commit()
        if dialog.result()!=QDialog.DialogCode.Accepted:
            raise AssertionError(dialog.error.text())
        return dialog.result_id

    def credentials(dialog):
        dialog.username.setText(user)
        dialog.password.setText(password)

    batches=[]
    for index,qty,price,carry,account,arrival in ((1,6,'500','150',cash,'RECEIVED'),(2,10,'600','525',bank,'IN_TRANSIT')):
        d=TransactionDialog(window,ctx,True)
        if index==1:
            d.type.setCurrentIndex(d.type.findData('CHINA_IMPORT'))
            d.party.setCurrentIndex(d.party.findData(supplier))
        else:
            assert d.type.currentData()=='CHINA_IMPORT' and d.party.currentData()==supplier
        d.date.setDate(QDate(2026,10,index))
        d.reference.setText('IMPORT-STACK-'+str(index))
        d.arrival.setCurrentIndex(d.arrival.findData(arrival))
        d.extra_costs.setChecked(True)
        d.carry_billed.setChecked(True)
        d.record_payment.setChecked(True)
        d.rate.setText('40')
        d.carry.setText(carry)
        d.add_product(ctx.products.get(product))
        d.entries[0]['qty'].setValue(qty)
        d.entries[0]['price'].setText(price)
        d.payments[0][1].setCurrentIndex(d.payments[0][1].findData(account))
        d.pay_full()
        if index==2:
            capture(d,'china_stack_total_carry')
        batches.append(post(d))
    assert ctx.stock.totals()==dict(quantity=6,value=money('126000'))
    assert ctx.products.get(product)['average_purchase_price']==money('24187.50')
    window.navigate(3)
    capture(window,'average_purchase_price')
    window.navigate(2)
    window.pages[2].start.setDate(QDate(2026,10,1))
    window.pages[2].end.setDate(QDate(2026,10,31))
    assert {row['id'] for row in window.pages[2].table.data_rows}==set(batches)
    capture(window,'purchase_shipments')
    cancel=PurchaseReturnDialog(window,ctx,batches[1])
    cancel.date.setDate(QDate(2026,10,3))
    cancel.quantities[0].setValue(4)
    credentials(cancel)
    cancel.confirmation.setChecked(True)
    capture(cancel,'owner_partial_cancellation')
    return_id=post(cancel)
    assert ctx.stock.totals()['quantity']==6
    assert ctx.purchase_returns.refund_limits(return_id)['supplier']==money('104400')
    assert sum(a['balance'] for a in ctx.money.accounts())==-money('387000')
    for index,amount in enumerate(('40000','64400')):
        refund=PurchaseRefundDialog(window,ctx,return_id)
        refund.date.setDate(QDate(2026,10,4+index))
        refund.amount.setText(amount)
        refund.account.setCurrentIndex(refund.account.findData(bank))
        credentials(refund)
        refund.confirmation.setChecked(True)
        if index==0:
            capture(refund,'owner_confirmed_refund')
        post(refund)
    received=ReceivePurchaseDialog(window,ctx,batches[1])
    received.date.setDate(QDate(2026,10,6))
    received.confirmation.setChecked(True)
    capture(received,'receive_uncancelled_shipment')
    post(received)
    assert ctx.stock.totals()==dict(quantity=12,value=money('282600'))
    returned=PurchaseReturnDialog(window,ctx,batches[0])
    returned.date.setDate(QDate(2026,10,7))
    returned.quantities[0].setValue(2)
    returned.refund_confirmed.setChecked(True)
    returned.refund.setText('42000')
    returned.account.setCurrentIndex(returned.account.findData(cash))
    credentials(returned)
    returned.confirmation.setChecked(True)
    capture(returned,'owner_received_stock_return')
    post(returned)
    history=window.purchase_return_history_dialog(batches[1])
    capture(history,'purchase_refund_history')
    history.close()
    window.navigate(3)
    capture(window,'average_after_returns')
    assert ctx.stock.totals()==dict(quantity=10,value=money('240600'))
    assert ctx.products.get(product)['average_purchase_price']==money('24060')
    assert sum(a['balance'] for a in ctx.money.accounts())==-money('240600')
    assert ctx.parties.balance(supplier,role='SUPPLIER')==0
    assert ctx.db.one('PRAGMA integrity_check')['integrity_check']=='ok'
    assert not ctx.db.rows('PRAGMA foreign_key_check')
    backup=ctx.backups.create()
    ctx.backups.restore(backup,username=user,password=password)
    restored=Context(root,install_catalogue=False)
    assert restored.stock.totals()==dict(quantity=10,value=money('240600'))
    assert len(restored.purchase_returns.list())==2
    result=dict(status='passed',screens=screens,weighted_average_16_phones='24187.50',
                stack_carry_rmb=['150','525'],final_stock_quantity=10,final_stock_value='240600.00',
                final_average='24060.00',net_money_paid='240600.00',supplier_balance='0.00',
                confirmed_refunds='146400.00',owner_authenticated=True,backup_restore='passed',
                records_created_only_in_isolated_test_folder=True)
    (output/'import-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    window.close()
    return result
