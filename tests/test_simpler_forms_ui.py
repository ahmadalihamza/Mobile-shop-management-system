import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication,QDialog,QLabel
from mobile_desk.ui.common import STYLE
from mobile_desk.ui.main_window import MainWindow
from mobile_desk.ui.people_money import AdjustmentDialog
from mobile_desk.ui.purchase_returns import PurchaseReturnDialog
from mobile_desk.ui.security import UndoDialog
from mobile_desk.ui.transactions import ReturnDialog
from mobile_desk.ui.report_page import ReportPage
from mobile_desk.values import money


@pytest.fixture(scope='session')
def app():
    instance=QApplication.instance() or QApplication([])
    instance.setStyleSheet(STYLE)
    return instance


def trade(shop):
    purchase=shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=4,unit_price='100')],supplier_id=shop.supplier)
    sale=shop.sales.post('2026-10-02',[dict(product_id=shop.product,quantity=1,selling_rate='150')],customer_id=shop.customer)
    return purchase,sale


def test_purchase_screen_displays_saved_phone_names(app,shop):
    purchase,_=trade(shop)
    window=MainWindow(shop)
    page=window.purchase_page()
    page.start.setDate(QDate(2026,10,1))
    page.end.setDate(QDate(2026,10,31))
    page.refresh()
    keys=[column[0] for column in page.table.columns]
    index=keys.index('product_names')
    assert page.table.horizontalHeaderItem(index).text()=='Products / phones'
    assert page.table.item(0,index).text()=='MI 11 Ultra 12/256 Shade'
    assert page.table.item(0,index).toolTip()=='MI 11 Ultra 12/256 Shade'
    assert page.table.selected()['id']==purchase
    other=shop.products.save(custom_name='Samsung Galaxy A55')
    shop.purchases.post('2026-10-03',[dict(product_id=shop.product,quantity=2,unit_price='100'),dict(product_id=other,quantity=2,unit_price='200')],supplier_id=shop.supplier)
    page.refresh()
    assert page.table.item(0,index).text()=='MI 11 Ultra 12/256 Shade\nSamsung Galaxy A55'
    assert 'Samsung Galaxy A55' in page.table.item(0,index).toolTip()
    assert page.table.rowHeight(0)>42
    window.close()


def test_entry_forms_have_no_reason_inputs_and_balance_saves_without_typing_one(app,shop):
    purchase,sale=trade(shop)
    window=MainWindow(shop)
    forms=[PurchaseReturnDialog(None,shop,purchase),ReturnDialog(None,shop,sale),
           AdjustmentDialog(None,shop,shop.customer),AdjustmentDialog(None,shop,shop.supplier,True),
           UndoDialog(None,shop,shop.corrections.latest()),window.purchase_undo_dialog(shop.purchases.details(purchase)[0])]
    for form in forms:
        assert not hasattr(form,'reason')
        assert not any('reason' in label.text().casefold() for label in form.findChildren(QLabel))
    assert not hasattr(forms[1],'notes')
    adjustment=forms[2]
    adjustment.date.setDate(QDate(2026,10,3))
    adjustment.amount.setText('20')
    adjustment.commit()
    assert adjustment.result()==QDialog.DialogCode.Accepted,adjustment.error.text()
    assert shop.parties.balance(shop.customer)==money('170')
    for form in forms:
        form.close()
    window.close()


def test_selected_sale_undo_uses_confirmation_without_text_entry(app,shop,monkeypatch):
    import mobile_desk.ui.main_window as module
    _,sale=trade(shop)
    window=MainWindow(shop)
    page=window.sales_page()
    page.start.setDate(QDate(2026,10,1))
    page.end.setDate(QDate(2026,10,31))
    page.refresh()
    monkeypatch.setattr(module,'confirm',lambda *args:False)
    window.void(page,shop.sales.void)
    assert shop.sales.details(sale)[0]['status']=='POSTED'
    monkeypatch.setattr(module,'confirm',lambda *args:True)
    window.void(page,shop.sales.void)
    assert shop.sales.details(sale)[0]['status']=='VOID'
    assert shop.stock.totals()['quantity']==4
    window.close()


def test_customer_return_undo_report_has_no_reason_prompt(app,shop,monkeypatch):
    import mobile_desk.ui.report_page as module
    _,sale=trade(shop)
    item=shop.sales.details(sale)[1][0]
    returned=shop.returns.post('2026-10-02',sale,[dict(sale_item_id=item['id'],quantity=1)])
    window=MainWindow(shop)
    report=ReportPage(window,shop)
    report.start.setDate(QDate(2026,10,1))
    report.end.setDate(QDate(2026,10,31))
    report.kind.setCurrentText('Returns')
    report.refresh()
    monkeypatch.setattr(module,'confirm',lambda *args:False)
    report.void_return()
    assert shop.db.one('SELECT status FROM returns WHERE id=?',(returned,))['status']=='POSTED'
    monkeypatch.setattr(module,'confirm',lambda *args:True)
    report.void_return()
    assert shop.db.one('SELECT status,void_reason FROM returns WHERE id=?',(returned,))==dict(status='VOID',void_reason='Customer return entry undone')
    window.close()
