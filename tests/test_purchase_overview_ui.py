"""Operator workflows for acquisition averages, shipment history and refunds."""
import csv
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton, QTabWidget

from mobile_desk.ui.common import STYLE
from mobile_desk.ui.main_window import MainWindow
from mobile_desk.ui.report_page import ReportPage
from mobile_desk.values import money


@pytest.fixture(scope='session')
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setStyleSheet(STYLE)
    return instance


def owner(shop):
    credentials = dict(username='owner', password='Shipment owner 26!')
    shop.security.set_password(credentials['username'], credentials['password'], credentials['password'])
    return credentials


def purchase(shop, qty=2, price='100', **kwargs):
    return shop.purchases.post('2026-10-01', [dict(product_id=shop.product,
        quantity=qty, unit_price=price)], supplier_id=shop.supplier, **kwargs)


def returned(shop, batch, qty, day, credentials, **kwargs):
    lot = shop.purchases.details(batch)[1][0]['id']
    return shop.purchase_returns.post(batch, day,
        [dict(purchase_item_id=lot, quantity=qty)], reason='Cargo returned to China',
        **credentials, **kwargs)


def test_stock_page_shows_weighted_purchase_average_and_explains_valuation(app, shop):
    purchase(shop, 1, '12000')
    purchase(shop, 15, '25000')
    window = MainWindow(shop)
    page = window.stock_page()
    page.refresh()
    assert page.table.horizontalHeaderItem(3).text() == 'Purchase average PKR'
    assert page.table.item(0, 3).text() == '24,187.50'
    assert 'awaiting arrival' in page.table.horizontalHeaderItem(3).toolTip()
    captured = {}
    window.details = lambda title, subtitle, tables, *args, **kwargs: captured.update(subtitle=subtitle, tables=tables)
    window.product_details(page)
    assert 'Purchase average PKR 24,187.50' in captured['subtitle']
    assert 'Available average PKR 24,187.50' in captured['subtitle']
    window.close()


def test_empty_product_has_no_average_and_dashboard_shows_available_stock(app, shop, monkeypatch):
    import mobile_desk.ui.main_window as module
    monkeypatch.setattr(module, 'today', lambda: '2026-10-15')
    credentials = owner(shop)
    window = MainWindow(shop)
    stock = window.stock_page()
    stock.refresh()
    assert stock.table.item(0, 3).text() == '—'
    assert stock.table.columnWidth(3) >= 150
    batch = purchase(shop)
    returned(shop, batch, 1, '2026-10-02', credentials)
    dashboard = window.dashboard()
    dashboard.refresh()
    labels = dashboard.findChildren(QLabel)
    assert any(widget.text() == 'Available stock value (PKR)' for widget in labels)
    assert dashboard.dashboard_data['stock']['value'] == money('100')
    window.close()


def test_purchase_page_routes_selected_shipment_to_return_and_arrival_dialogs(app, shop, monkeypatch):
    import mobile_desk.ui.main_window as module
    batch = purchase(shop, received=False)
    window = MainWindow(shop)
    page = window.purchase_page()
    page.start.setDate(QDate(2026, 10, 1))
    page.end.setDate(QDate(2026, 10, 31))
    page.refresh()
    assert page.table.selected()['id'] == batch
    assert page.table.selected()['shipment_status'] == 'IN_TRANSIT'
    assert any(column[0] == 'shipment_status' for column in page.table.columns)
    labels = [widget.text() for widget in page.findChildren(QPushButton)]
    assert {'Open purchase', 'Undo Purchase', 'Return / Cancel', 'Returns / refunds'} <= set(labels)
    details_actions = {}
    window.details = lambda title, subtitle, tables, actions: details_actions.update(actions)
    window.batch_selected(page)
    assert {'Return / Cancel', 'Mark received', 'Returns / refunds'} <= details_actions.keys()
    monkeypatch.setattr(module, 'PurchaseReturnDialog', lambda parent, ctx, identity: ('return', identity))
    monkeypatch.setattr(module, 'ReceivePurchaseDialog', lambda parent, ctx, identity: ('receive', identity))
    captured = []
    window.entry = captured.append
    details_actions['Return / Cancel']()
    details_actions['Mark received']()
    assert captured == [('return', batch), ('receive', batch)]
    window.close()


def test_history_keeps_returns_and_confirmed_refunds_and_uses_selected_return(app, shop, monkeypatch):
    import mobile_desk.ui.main_window as module
    credentials = owner(shop)
    batch = purchase(shop, payments=[dict(account_id=shop.cash, amount='200')])
    first = returned(shop, batch, 1, '2026-10-02', credentials)
    second = returned(shop, batch, 1, '2026-10-03', credentials,
        refund_amount='50', refund_account_id=shop.bank)
    window = MainWindow(shop)
    history = window.purchase_return_history_dialog(batch)
    assert history.returns_table.rowCount() == 2
    assert history.refunds_table.rowCount() == 1
    assert history.refunds_table.selected()['account_name'] == 'MJ Bank'
    assert history.refunds_table.selected()['amount'] == money('50')
    assert {row['id'] for row in history.returns_table.data_rows} == {first, second}
    for index, row in enumerate(history.returns_table.data_rows):
        if row['id'] == first:
            history.returns_table.selectRow(index)
    monkeypatch.setattr(module, 'PurchaseRefundDialog', lambda parent, ctx, identity: identity)
    captured = []
    window.entry = captured.append
    history.confirm_refund_button.click()
    assert captured == [first]
    assert shop.purchases.details(batch)[0]['status'] == 'POSTED'
    history.close()
    window.close()


def test_mistaken_purchase_undo_requires_owner_and_retains_original_record(app, shop):
    credentials = owner(shop)
    batch = purchase(shop, payments=[dict(account_id=shop.cash, amount='200')])
    window = MainWindow(shop)
    page = window.purchase_page()
    page.start.setDate(QDate(2026, 10, 1))
    page.end.setDate(QDate(2026, 10, 31))
    captured = []
    window.entry = captured.append
    next(widget for widget in page.findChildren(QPushButton) if widget.text() == 'Undo Purchase').click()
    dialog, = captured
    assert shop.money.accounts()[0]['balance'] == -money('200')
    assert dialog.password.echoMode() == QLineEdit.EchoMode.Password
    assert not hasattr(dialog,'reason')
    dialog.password.setText('incorrect password')
    dialog.commit()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert 'Incorrect owner' in dialog.error.text()
    assert shop.stock.totals()['quantity'] == 2
    dialog.password.setText(credentials['password'])
    dialog.commit()
    assert dialog.result() == QDialog.DialogCode.Accepted, dialog.error.text()
    assert shop.stock.totals()['quantity'] == 0
    assert shop.purchases.details(batch)[0]['status'] == 'VOID'
    assert shop.money.accounts()[0]['balance'] == 0
    window.close()


def test_reports_show_rmb_carry_net_returns_and_export_average_as_pkr(app, shop, monkeypatch):
    credentials = owner(shop)
    batch = purchase(shop, purchase_type='CHINA_IMPORT', default_rate='40',
        default_carry='10', carry_currency='CNY')
    returned(shop, batch, 1, '2026-10-02', credentials)
    window = MainWindow(shop)
    report = ReportPage(window, shop)
    report.start.setDate(QDate(2026, 10, 1))
    report.end.setDate(QDate(2026, 10, 31))
    report.kind.setCurrentText('China Batch / Landed Cost')
    report.refresh()
    row = report.rows[0]
    assert (row['quantity'], row['returned_quantity'], row['net_quantity']) == (2, 1, 1)
    assert row['carry_currency'] == 'CNY' and row['foreign_carry_per_unit'] == '10'
    assert row['net_stock_cost'] == money('4400')
    keys = {column[0] for column in report.columns}
    assert {'carry_currency', 'foreign_carry_per_unit', 'net_quantity', 'net_stock_cost'} <= keys
    report.kind.setCurrentText('Current Stock / Stock Value')
    report.refresh()
    assert report.rows[0]['average_purchase_price'] == money('4400')
    exported = shop.root/'stock-report.csv'
    monkeypatch.setattr('mobile_desk.ui.report_page.QFileDialog.getSaveFileName',
        lambda *args: (str(exported), 'CSV (*.csv)'))
    report.export()
    with exported.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]['Average Purchase Price (PKR)'] == '4400.00'
    report.kind.setCurrentText('Period Profit')
    report.refresh()
    assert 'confirmed carry refunds' in report.note.text()
    assert 'not sales or profit' in report.note.text()
    window.close()



def test_dashboard_shows_original_names_and_weighted_prices_for_each_model(app, shop):
    other = shop.products.save(custom_name='Huawei P30 Pro; 256 GB')
    shop.purchases.post('2026-10-01', [
        dict(product_id=shop.product, quantity=2, unit_price='100', carry='3'),
        dict(product_id=other, quantity=2, unit_price='200', carry='5'),
        dict(product_id=shop.product, quantity=3, unit_price='130', carry='1.01'),
    ], supplier_id=shop.supplier, purchase_type='CHINA_IMPORT', default_rate='40',
       carry_currency='CNY', carry_basis='STACK_TOTAL')
    shop.sales.post('2026-10-02', [
        dict(product_id=shop.product, quantity=1, selling_rate='150'),
        dict(product_id=other, quantity=1, selling_rate='250'),
        dict(product_id=shop.product, quantity=2, selling_rate='160'),
    ], customer_id=shop.customer)
    shop.products.save(product_id=other, custom_name='Renamed Huawei')
    window = MainWindow(shop)
    tabs = window.pages[0].findChild(QTabWidget)
    assert [tabs.tabText(i) for i in range(tabs.count())] == ['Recent sales', 'Recent purchases']
    for index in range(2):
        tabs.setCurrentIndex(index)
        app.processEvents()
        table = tabs.currentWidget()
        assert table.horizontalHeaderItem(4).text() == 'Phone names'
        expected = 'MI 11 Ultra 12/256 Shade\nHuawei P30 Pro; 256 GB'
        assert table.item(0, 4).text() == expected
        assert table.item(0, 4).toolTip() == expected
        price_header = ('Sale avg. (PKR)', 'Purchase avg. (PKR)')[index]
        prices = ('156.67\n250.00', '4,752.08\n8,100.00')[index]
        assert table.horizontalHeaderItem(5).text() == price_header
        assert table.item(0, 5).text() == prices
    window.close()


@pytest.mark.parametrize('refund_received', [False, True])
def test_cancel_shipment_from_list_posts_only_a_confirmed_refund(app, shop, refund_received):
    credentials = owner(shop)
    batch = purchase(shop, received=False, payments=[dict(account_id=shop.cash, amount='120')])
    assert shop.stock.totals()['quantity'] == 0
    window = MainWindow(shop)
    page = window.purchase_page()
    page.start.setDate(QDate(2026, 10, 1))
    page.end.setDate(QDate(2026, 10, 31))
    opened = []
    window.entry = opened.append
    next(widget for widget in page.findChildren(QPushButton) if widget.text() == 'Return / Cancel').click()
    dialog, = opened
    assert dialog.table.horizontalHeaderItem(4).text() == 'Cancel now'
    assert dialog.quantities[0].value() == 2
    dialog.date.setDate(QDate(2026, 10, 2))
    dialog.password.setText(credentials['password'])
    if refund_received:
        dialog.refund_confirmed.setChecked(True)
        dialog.refund.setText('120')
        dialog.account.setCurrentIndex(dialog.account.findData(shop.bank))
    dialog.confirmation.setChecked(True)
    dialog.commit()
    assert dialog.result() == QDialog.DialogCode.Accepted, dialog.error.text()
    assert shop.purchases.details(batch)[0]['shipment_status'] == 'CANCELLED'
    assert shop.stock.totals()['quantity'] == 0
    balances = {account['id']: account['balance'] for account in shop.money.accounts()}
    assert balances[shop.cash] == -money('120')
    assert balances[shop.bank] == (money('120') if refund_received else 0)
    assert shop.parties.balance(shop.supplier, role='SUPPLIER') == (0 if refund_received else -money('120'))
    window.close()
