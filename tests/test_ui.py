import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import QDate,Qt
from PySide6.QtTest import QTest
from mobile_desk.ui.common import STYLE
from mobile_desk.ui.transactions import TransactionDialog,ReturnDialog
from mobile_desk.ui.products import ProductDialog
from mobile_desk.ui.people_money import PaymentDialog,PartyDialog,PartyChooser
from mobile_desk.ui.main_window import MainWindow
from mobile_desk.ui.report_page import ReportPage,REPORTS
from mobile_desk.values import money


@pytest.fixture(scope='session')
def app():
    app=QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLE)
    yield app


def test_ui_manual_product_and_purchase_sale_payment_return(app,shop):
    d=ProductDialog(None,shop)
    d.manual()
    d.name.setText('Unlisted used phone 12/256')
    QTest.mouseClick(d.save_button,Qt.MouseButton.LeftButton)
    assert d.result()==QDialog.DialogCode.Accepted
    product=shop.products.get(d.result_id)
    purchase=TransactionDialog(None,shop,True)
    purchase.date.setDate(QDate(2026,9,1))
    purchase.party.setCurrentIndex(purchase.party.findData(shop.supplier))
    purchase.add_product(product)
    purchase.entries[0]['qty'].setValue(5)
    purchase.entries[0]['price'].setText('40000')
    QTest.mouseClick(purchase.save_button,Qt.MouseButton.LeftButton)
    assert purchase.result()==QDialog.DialogCode.Accepted,purchase.error.text()
    sale=TransactionDialog(None,shop)
    sale.date.setDate(QDate(2026,9,2))
    sale.party.setCurrentIndex(sale.party.findData(shop.customer))
    sale.add_product(product)
    sale.entries[0]['qty'].setValue(2)
    sale.entries[0]['price'].setText('50000')
    sale.payment_mode.setCurrentIndex(1)
    sale.payments[0][0].setText('30000')
    QTest.mouseClick(sale.save_button,Qt.MouseButton.LeftButton)
    assert sale.result()==QDialog.DialogCode.Accepted,sale.error.text()
    assert shop.parties.balance(shop.customer)==money('70000')
    payment=PaymentDialog(None,shop,shop.customer)
    payment.date.setDate(QDate(2026,9,3))
    payment.amount.setText('20000')
    payment.commit()
    assert payment.result()==QDialog.DialogCode.Accepted,payment.error.text()
    ret=ReturnDialog(None,shop,sale.result_id)
    ret.date.setDate(QDate(2026,9,4))
    ret.quantities[0].setValue(1)
    ret.commit()
    assert ret.result()==QDialog.DialogCode.Accepted,ret.error.text()
    assert shop.parties.balance(shop.customer)==0
    assert shop.stock.totals()['quantity']==4


def test_ui_china_line_override(app,shop):
    d=TransactionDialog(None,shop,True)
    d.date.setDate(QDate(2026,9,1))
    d.type.setCurrentIndex(1)
    d.carry_currency.setCurrentIndex(d.carry_currency.findData('PKR'))
    d.party.setCurrentIndex(d.party.findData(shop.supplier))
    d.extra_costs.setChecked(True)
    d.rate.setText('40.3')
    d.carry.setText('4000')
    d.add_product(shop.products.get(shop.product))
    d.entries[0]['price'].setText('1000')
    d.entries[0]['rate'].setText('41.066')
    d.commit()
    assert d.result()==QDialog.DialogCode.Accepted,d.error.text()
    assert shop.stock.totals()['value']==money('45066')


def test_ui_invalid_sale_stays_open_no_mutation(app,shop):
    d=TransactionDialog(None,shop)
    d.payment_mode.setCurrentIndex(2)
    d.add_product(shop.products.get(shop.product))
    d.entries[0]['price'].setText('50000')
    d.commit()
    assert d.result()!=QDialog.DialogCode.Accepted
    assert 'customer' in d.error.text().lower()
    assert not shop.sales.list()


def test_navigation_and_all_reports(app,shop):
    window=MainWindow(shop)
    # Any navigation exception opens a modal; fail immediately instead.
    window.safe=lambda action:action()
    for i in range(9):
        window.navigate(i)
        app.processEvents()
        assert window.stack.currentWidget() is window.pages[i]
    reports=window.pages[7]
    for name in REPORTS:
        reports.kind.setCurrentText(name)
        reports.refresh()
        assert reports.columns
    window.close()


def test_local_purchase_hides_exchange_fields(app,shop):
    d=TransactionDialog(None,shop,True)
    assert d.table.isColumnHidden(3)
    d.type.setCurrentIndex(1)
    assert not d.table.isColumnHidden(3)
    assert not any('imei' in w.text().lower() for w in d.findChildren(type(d.error)))


def test_purchase_unchecked_payment_and_currency_guard(app,shop):
    d=TransactionDialog(None,shop,True)
    d.party.setCurrentIndex(d.party.findData(shop.supplier))
    d.add_product(shop.products.get(shop.product))
    d.entries[0]['price'].setText('50000')
    assert not d.type.isEnabled()
    d.record_payment.setChecked(True)
    d.pay_full()
    d.record_payment.setChecked(False)
    d.commit()
    assert d.result()==QDialog.DialogCode.Accepted,d.error.text()
    assert not shop.db.rows('SELECT * FROM payments')
    assert shop.money.accounts()[0]['balance']==0
    other=TransactionDialog(None,shop,True)
    other.add_product(shop.products.get(shop.product))
    other.remove_line()
    assert other.type.isEnabled()


def test_cached_page_party_filters_refresh(app,shop):
    window=MainWindow(shop)
    window.safe=lambda action:action()
    for page in (1,2,7):
        window.navigate(page)
    identity=shop.parties.save('New dealer',is_supplier=True)
    for page,attribute in ((1,'customer'),(2,'supplier'),(7,'party')):
        window.navigate(page)
        assert getattr(window.pages[page],attribute).findData(identity)>0
    window.close()


def test_ui_cash_walkin_defaults_and_supplier_partial_later(app,shop):
    purchase=TransactionDialog(None,shop,True)
    purchase.date.setDate(QDate(2026,9,1))
    purchase.party.setCurrentIndex(purchase.party.findData(shop.supplier))
    purchase.add_product(shop.products.get(shop.product))
    purchase.entries[0]['qty'].setValue(10)
    purchase.entries[0]['price'].setText('50000')
    purchase.record_payment.setChecked(True)
    purchase.payments[0][0].setText('300000')
    purchase.commit()
    assert purchase.result()==QDialog.DialogCode.Accepted,purchase.error.text()
    supplier=PaymentDialog(None,shop,shop.supplier,supplier=True)
    supplier.date.setDate(QDate(2026,9,2))
    supplier.amount.setText('100000')
    supplier.commit()
    assert supplier.result()==QDialog.DialogCode.Accepted,supplier.error.text()
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('100000')
    sale=TransactionDialog(None,shop)
    sale.date.setDate(QDate(2026,9,3))
    sale.add_product(shop.products.get(shop.product))
    sale.entries[0]['price'].setText('60000')
    assert sale.payments[0][0].value()=='60000.00'
    sale.commit()
    assert sale.result()==QDialog.DialogCode.Accepted,sale.error.text()
    assert shop.sales.details(sale.result_id)[0]['customer_id'] is None


def test_ui_purchase_carry_payment_and_bill_cost_difference(app,shop):
    d=TransactionDialog(None,shop,True)
    d.date.setDate(QDate(2026,9,1))
    d.party.setCurrentIndex(d.party.findData(shop.supplier))
    d.extra_costs.setChecked(True)
    d.add_product(shop.products.get(shop.product))
    d.entries[0]['price'].setText('40000')
    d.entries[0]['carry'].setText('1000')
    d.carry_paid.setText('1000')
    d.commit()
    assert d.result()==QDialog.DialogCode.Accepted,d.error.text()
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('40000')
    assert shop.money.accounts()[0]['balance']==-money('1000')
    assert shop.stock.totals()['value']==money('41000')


def test_catalogue_browsing_loads_and_statement_rejects_unselected_text(app,shop):
    from mobile_desk.catalogue import models_checksum
    models=[dict(id='a55',brand='Samsung',model='Galaxy A55',aliases=['a55'])]
    shop.catalogue.import_package(dict(format='mobile-desk-catalogue',schema_version=1,version='1.0',source='test fixture',licence='test',models=models,sha256=models_checksum(models)))
    window=MainWindow(shop)
    catalogue=window.catalogue_page()
    assert catalogue.table.rowCount()==1
    assert catalogue.table.selected()['model_name']=='Galaxy A55'
    report=ReportPage(window,shop)
    report.kind.setCurrentText('Supplier Statement')
    report.party.setCurrentIndex(report.party.findData(shop.supplier))
    report.party.setEditText('Unselected supplier')
    report.refresh()
    assert not report.rows and 'choose a supplier' in report.note.text()
    window.close()


def test_missing_price_cannot_post_free_stock_by_accident(app,shop):
    d=TransactionDialog(None,shop,True)
    d.party.setCurrentIndex(d.party.findData(shop.supplier))
    d.add_product(shop.products.get(shop.product))
    d.commit()
    assert 'price for every product' in d.error.text()
    assert not shop.purchases.list()


def test_reports_partial_product_and_supplier_search(app,shop):
    shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=3,unit_price='40000')],supplier_id=shop.supplier)
    other=shop.products.save(custom_name='Samsung Galaxy A55 8/256')
    shop.purchases.post('2026-09-01',[dict(product_id=other,quantity=1,unit_price='30000')])
    report=ReportPage(MainWindow(shop),shop)
    report.start.setDate(QDate(2026,9,1))
    report.end.setDate(QDate(2026,9,30))
    report.kind.setCurrentText('Purchase History')
    report.search.setText('11 ultra')
    report.refresh()
    assert len(report.rows)==1 and '11 Ultra' in report.rows[0]['product_description_snapshot']
    report.kind.setCurrentText('Supplier Outstanding')
    report.search.setText('supplier one')
    report.refresh()
    assert len(report.rows)==1 and report.rows[0]['balance']==money('120000')
    report.search.setText('missing supplier')
    report.refresh()
    assert not report.rows


def test_owner_reset_and_undo_dialog_guards(app,shop):
    from mobile_desk.ui.security import OwnerSetupDialog,ResetDialog,UndoDialog
    from mobile_desk.ui.settings import SettingsPage
    from PySide6.QtWidgets import QLineEdit
    owner=OwnerSetupDialog(None,shop)
    owner.password.setText('Learning password 26!')
    owner.confirmation.setText('different password')
    owner.commit()
    assert not shop.security.configured and 'do not match' in owner.error.text()
    owner.confirmation.setText(owner.password.text())
    owner.commit()
    assert owner.result()==QDialog.DialogCode.Accepted
    assert owner.password.echoMode()==QLineEdit.EchoMode.Password
    shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=1,unit_price='100')])
    undo=UndoDialog(None,shop,shop.corrections.latest())
    undo.password.setText('Learning password 26!')
    assert not hasattr(undo,'reason')
    undo.commit()
    assert undo.result()==QDialog.DialogCode.Accepted and shop.stock.totals()['quantity']==0
    reset=ResetDialog(None,shop)
    reset.password.setText('wrong password')
    reset.confirmation.setText('RESET')
    reset.commit()
    assert reset.result()!=QDialog.DialogCode.Accepted and 'Incorrect' in reset.error.text()
    reset.reject()
    assert shop.products.search()
    success=ResetDialog(None,shop)
    success.password.setText('Learning password 26!')
    success.confirmation.setText('RESET')
    success.commit()
    assert success.result()==QDialog.DialogCode.Accepted and success.result_id.exists()
    assert not shop.products.search()
    window=MainWindow(shop)
    settings=SettingsPage(window,shop)
    assert settings.reset_button.isEnabled()
    window.close()


def test_choose_existing_supplier_reuses_account_in_purchase(app,shop,monkeypatch):
    def choose(dialog):
        assert dialog.tabs.count()==2 and dialog.tabs.currentIndex()==0
        dialog.search.setText('supplier one')
        QTest.mouseClick(dialog.save_button,Qt.MouseButton.LeftButton)
        return dialog.result()
    monkeypatch.setattr(PartyChooser,'exec',choose)
    purchase=TransactionDialog(None,shop,True)
    count=purchase.party.count()
    assert not purchase.party.isEditable()
    QTest.mouseClick(purchase.choose_party_button,Qt.MouseButton.LeftButton)
    assert purchase.party.currentData()==shop.supplier
    QTest.mouseClick(purchase.choose_party_button,Qt.MouseButton.LeftButton)
    assert purchase.party.count()==count
    assert len(shop.parties.search(role='is_supplier'))==1
    assert not shop.purchases.list()


def test_choose_new_supplier_and_duplicate_recovery(app,shop,monkeypatch):
    def create(dialog):
        dialog.tabs.setCurrentIndex(1)
        dialog.new_fields.name.setText('Lahore Supply')
        dialog.new_fields.phone.setText('0300-1234567')
        QTest.mouseClick(dialog.save_button,Qt.MouseButton.LeftButton)
        return dialog.result()
    monkeypatch.setattr(PartyChooser,'exec',create)
    purchase=TransactionDialog(None,shop,True)
    purchase.add_party()
    row=shop.db.one('SELECT * FROM parties WHERE id=?',(purchase.party.currentData(),))
    assert row['name']=='Lahore Supply' and row['phone']=='0300-1234567'
    assert row['is_supplier']==1 and row['is_customer']==0
    assert not shop.purchases.list()
    chooser=PartyChooser(None,shop,supplier=True,allow_new=True)
    chooser.tabs.setCurrentIndex(1)
    chooser.new_fields.name.setText('supplier ONE')
    chooser.commit()
    assert chooser.result()!=QDialog.DialogCode.Accepted and 'already exists' in chooser.error.text()
    chooser.tabs.setCurrentIndex(0)
    chooser.search.setText('supplier one')
    chooser.commit()
    assert chooser.result_id==shop.supplier
    assert len(shop.parties.search(role='is_supplier'))==2


def test_payment_only_selects_saved_contact_and_does_not_create_purchase(app,shop,monkeypatch):
    def choose(dialog):
        assert dialog.tabs.count()==1 and dialog.new_fields is None
        dialog.search.setText('supplier one')
        dialog.commit()
        return dialog.result()
    monkeypatch.setattr(PartyChooser,'exec',choose)
    payment=PaymentDialog(None,shop,supplier=True)
    assert not payment.party.isEditable()
    payment.party.setEditText('Unexpected invented supplier')
    payment.amount.setText('1000')
    payment.commit()
    assert payment.result()!=QDialog.DialogCode.Accepted
    assert 'Choose a supplier' in payment.error.text()
    assert not shop.db.rows('SELECT * FROM payments')
    QTest.mouseClick(payment.choose_button,Qt.MouseButton.LeftButton)
    assert payment.party.currentData()==shop.supplier
    payment.commit()
    assert payment.result()==QDialog.DialogCode.Accepted,payment.error.text()
    assert len(shop.db.rows('SELECT * FROM payments'))==1
    assert not shop.purchases.list() and not shop.sales.list()
    assert len(shop.parties.search(role='is_supplier'))==1


def test_contact_picker_cancellation_and_empty_search_do_not_create_records(app,shop,monkeypatch):
    def cancel(dialog):
        dialog.tabs.setCurrentIndex(1)
        dialog.new_fields.name.setText('Never saved supplier')
        dialog.reject()
        return dialog.result()
    monkeypatch.setattr(PartyChooser,'exec',cancel)
    purchase=TransactionDialog(None,shop,True)
    purchase.add_party()
    assert purchase.party.currentData() is None
    assert not shop.parties.search('never saved')
    chooser=PartyChooser(None,shop,supplier=True)
    chooser.search.setText('no matching supplier')
    chooser.commit()
    assert chooser.result()!=QDialog.DialogCode.Accepted and 'Select a saved supplier' in chooser.error.text()


def test_contact_picker_pages_and_distinguishes_legacy_duplicate_ids(app,shop):
    for index in range(103):
        shop.parties.save(f'Training Supplier {index:03}',is_customer=False,is_supplier=True)
    chooser=PartyChooser(None,shop,supplier=True)
    assert chooser.table.rowCount()==100 and chooser.next.isEnabled()
    QTest.mouseClick(chooser.next,Qt.MouseButton.LeftButton)
    assert chooser.offset==100 and chooser.table.rowCount()==4 and not chooser.next.isEnabled()
    chooser.search.setText('Supplier One')
    assert chooser.offset==0 and chooser.table.rowCount()==1
    with shop.db.connect(write=True) as c:
        duplicate=c.execute('INSERT INTO parties(name,normalized_name,is_customer,is_supplier,phone,address,notes,active,created_at) SELECT name,normalized_name,is_customer,is_supplier,phone,address,notes,active,created_at FROM parties WHERE id=?',(shop.supplier,)).lastrowid
    payment=PaymentDialog(None,shop,duplicate,supplier=True)
    first=payment.party.itemText(payment.party.findData(shop.supplier))
    second=payment.party.itemText(payment.party.findData(duplicate))
    assert first!=second and f'Account {duplicate}' in second
    chooser=PartyChooser(None,shop,supplier=True,selected=duplicate)
    chooser.search.setText('Supplier One')
    assert chooser.table.rowCount()==2 and chooser.table.selected()['id']==duplicate
    chooser.commit()
    assert chooser.result_id==duplicate


def test_purchase_remembers_saved_china_supplier_and_type_across_restart(app,shop):
    from mobile_desk.context import Context
    purchase=TransactionDialog(None,shop,True)
    purchase.type.setCurrentIndex(purchase.type.findData('CHINA_IMPORT'))
    purchase.party.setCurrentIndex(purchase.party.findData(shop.supplier))
    purchase.add_product(shop.products.get(shop.product))
    purchase.entries[0]['price'].setText('1000')
    purchase.commit()
    assert purchase.result()==QDialog.DialogCode.Accepted,purchase.error.text()
    next_purchase=TransactionDialog(None,Context(shop.root,install_catalogue=False),True)
    assert next_purchase.type.currentData()=='CHINA_IMPORT'
    assert next_purchase.party.currentData()==shop.supplier
    next_purchase.type.setCurrentIndex(next_purchase.type.findData('LOCAL'))
    next_purchase.reject()
    unchanged=TransactionDialog(None,shop,True)
    assert unchanged.type.currentData()=='CHINA_IMPORT'


def test_ui_china_rmb_carry_and_pending_stock(app,shop):
    dialog=TransactionDialog(None,shop,True)
    dialog.type.setCurrentIndex(dialog.type.findData('CHINA_IMPORT'))
    assert dialog.carry_currency.currentData()=='CNY'
    dialog.party.setCurrentIndex(dialog.party.findData(shop.supplier))
    dialog.date.setDate(QDate(2026,10,1))
    dialog.arrival.setCurrentIndex(dialog.arrival.findData('IN_TRANSIT'))
    dialog.extra_costs.setChecked(True)
    dialog.carry_billed.setChecked(True)
    dialog.rate.setText('40')
    dialog.carry.setText('500')
    dialog.add_product(shop.products.get(shop.product))
    dialog.entries[0]['qty'].setValue(20)
    dialog.entries[0]['price'].setText('1000')
    assert dialog.total()==money('820000')
    dialog.commit()
    assert dialog.result()==QDialog.DialogCode.Accepted,dialog.error.text()
    assert shop.stock.totals()['quantity']==0
    assert shop.purchases.stacks(dialog.result_id)[0]['carry_input']=='500'


def test_ui_owner_return_and_later_refund_review(app,shop,owner_credentials):
    from mobile_desk.ui.purchase_returns import PurchaseReturnDialog,PurchaseRefundDialog
    purchase=shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=3,unit_price='100')],supplier_id=shop.supplier,payments=[dict(account_id=shop.cash,amount='300')])
    dialog=PurchaseReturnDialog(None,shop,purchase)
    dialog.date.setDate(QDate(2026,10,2))
    dialog.quantities[0].setValue(1)
    dialog.username.setText(owner_credentials['username'])
    dialog.password.setText(owner_credentials['password'])
    dialog.commit()
    assert dialog.result()!=QDialog.DialogCode.Accepted and 'confirmation' in dialog.error.text()
    dialog.confirmation.setChecked(True)
    dialog.commit()
    assert dialog.result()==QDialog.DialogCode.Accepted,dialog.error.text()
    assert shop.stock.totals()['quantity']==2 and shop.money.accounts()[0]['balance']==-money('300')
    refund=PurchaseRefundDialog(None,shop,dialog.result_id)
    refund.date.setDate(QDate(2026,10,3))
    refund.amount.setText('100')
    refund.username.setText(owner_credentials['username'])
    refund.password.setText('wrong password')
    refund.confirmation.setChecked(True)
    refund.commit()
    assert 'Incorrect owner' in refund.error.text()
    assert shop.money.accounts()[0]['balance']==-money('300')
    refund.password.setText(owner_credentials['password'])
    refund.commit()
    assert refund.result()==QDialog.DialogCode.Accepted,refund.error.text()
    assert shop.money.accounts()[0]['balance']==-money('200')
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==0


def test_ui_stack_charge_is_once_and_return_groups_rounding_lots(app,shop,owner_credentials):
    from mobile_desk.ui.purchase_returns import PurchaseReturnDialog
    purchase=TransactionDialog(None,shop,True)
    purchase.type.setCurrentIndex(purchase.type.findData('CHINA_IMPORT'))
    purchase.party.setCurrentIndex(purchase.party.findData(shop.supplier))
    purchase.date.setDate(QDate(2026,10,1))
    purchase.extra_costs.setChecked(True)
    purchase.carry_billed.setChecked(True)
    purchase.record_payment.setChecked(True)
    purchase.rate.setText('40')
    purchase.carry.setText('1')
    purchase.add_product(shop.products.get(shop.product))
    purchase.entries[0]['qty'].setValue(6)
    purchase.entries[0]['price'].setText('1000')
    purchase.pay_full()
    assert purchase.bill_total()==money('240040')
    assert 'stack total' in purchase.table.horizontalHeaderItem(4).text()
    purchase.commit()
    assert purchase.result()==QDialog.DialogCode.Accepted,purchase.error.text()
    assert len(shop.purchases.details(purchase.result_id)[1])==2
    returned=PurchaseReturnDialog(None,shop,purchase.result_id)
    assert returned.table.rowCount()==1 and len(returned.quantities)==1
    returned.date.setDate(QDate(2026,10,2))
    returned.quantities[0].setValue(3)
    returned.username.setText(owner_credentials['username'])
    returned.password.setText(owner_credentials['password'])
    returned.confirmation.setChecked(True)
    returned.commit()
    assert returned.result()==QDialog.DialogCode.Accepted,returned.error.text()
    assert shop.stock.totals()['quantity']==3
    assert shop.purchase_returns.details(returned.result_id)['header']['supplier_credit']==money('120019.99')
    assert shop.stock.totals()['value']==money('120020.01')


def test_carry_payment_ui_uses_net_remaining_after_partial_return(app,shop,owner_credentials):
    from mobile_desk.ui.people_money import CarryPaymentDialog
    batch=shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=4,unit_price='100',carry='10')],supplier_id=shop.supplier,carry_payment='10',carry_account_id=shop.cash)
    lot=shop.purchases.details(batch)[1][0]
    shop.purchase_returns.post(batch,'2026-10-02',[dict(purchase_item_id=lot['id'],quantity=2)],'Two pieces returned',**owner_credentials)
    dialog=CarryPaymentDialog(None,shop,shop.purchases.details(batch)[0])
    assert dialog.amount.value()=='10.00'
    dialog.date.setDate(QDate(2026,10,3))
    dialog.commit()
    assert dialog.result()==QDialog.DialogCode.Accepted,dialog.error.text()
    assert shop.money.carry_remaining(batch)==0
