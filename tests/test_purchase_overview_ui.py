"""Operator workflows for acquisition averages, shipment history and refunds."""
import csv
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton

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
    assert page.table.horizontalHeaderItem(3).text() == 'Average Purchase Price (PKR)'
    assert page.table.item(0, 3).text() == '24,187.50'
    assert 'awaiting arrival' in page.table.horizontalHeaderItem(3).toolTip()
    captured = {}
    window.details = lambda title, subtitle, tables: captured.update(subtitle=subtitle, tables=tables)
    window.product_details(page)
    assert 'Average Purchase Price PKR 24,187.50' in captured['subtitle']
    assert 'original FIFO costs' in captured['subtitle']
    window.close()


def test_empty_product_has_no_average_and_dashboard_shows_net_purchases(app, shop, monkeypatch):
    import mobile_desk.ui.main_window as module
    monkeypatch.setattr(module, 'today', lambda: '2026-10-15')
    credentials = owner(shop)
    window = MainWindow(shop)
    stock = window.stock_page()
    stock.refresh()
    assert stock.table.item(0, 3).text() == '—'
    assert stock.table.columnWidth(3) >= 220
    batch = purchase(shop)
    returned(shop, batch, 1, '2026-10-02', credentials)
    dashboard = window.dashboard()
    dashboard.refresh()
    labels = dashboard.findChildren(QLabel)
    assert any(widget.text() == 'Net purchases this month' for widget in labels)
    metrics = [widget.text() for widget in labels if widget.objectName() == 'metric']
    assert metrics[2] == '100.00'
    window.close()


def test_purchase_page_routes_selected_shipment_to_return_and_arrival_dialogs(app, shop, monkeypatch):
    import mobile_desk.ui.main_window as module
    batch = purchase(shop, received=False)
    window = MainWindow(shop)
    page = window.purchase_page()
    page.refresh()
    assert page.table.selected()['id'] == batch
    assert page.table.selected()['shipment_status'] == 'IN_TRANSIT'
    assert any(column[0] == 'shipment_status' for column in page.table.columns)
    labels = [widget.text() for widget in page.findChildren(QPushButton)]
    assert {'Return / Cancel', 'Mark received', 'Returns / refunds'} <= set(labels)
    monkeypatch.setattr(module, 'PurchaseReturnDialog', lambda parent, ctx, identity: ('return', identity))
    monkeypatch.setattr(module, 'ReceivePurchaseDialog', lambda parent, ctx, identity: ('receive', identity))
    captured = []
    window.entry = captured.append
    window.purchase_return_selected(page)
    window.receive_purchase_selected(page)
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
    batch = purchase(shop)
    window = MainWindow(shop)
    row = shop.purchases.details(batch)[0]
    dialog = window.purchase_undo_dialog(row)
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
