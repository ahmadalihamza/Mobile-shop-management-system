from contextlib import closing
import os
import sqlite3

import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication,QDialog

from mobile_desk.database import APPLICATION_ID, MIGRATIONS
from mobile_desk.context import Context
from mobile_desk.values import BusinessError, money


def test_parcels_fifo_estimate_actual_and_historical_averages(shop):
    for pieces, price, reference in [(10,'40000','Parcel A'),(5,'45000','Parcel B')]:
        shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=pieces,
            unit_price=price,carry='1000')],supplier_id=shop.supplier,reference=reference)
    rows = shop.stock.current()
    assert len(shop.purchases.list())==2
    assert (rows[0]['quantity'],rows[0]['value'],rows[0]['average_purchase_price']) == (
        15,money('640000'),money('42666.67'))
    lines=[dict(product_id=shop.product,quantity=6,selling_rate='50000')]*2
    assert shop.stock.estimate_fifo('2026-10-02',lines)==money('502000')
    assert not shop.sales.list()
    assert shop.stock.estimate_fifo('2026-10-02',lines+[dict(product_id=shop.product,quantity=4)]) is None
    identity=shop.sales.post('2026-10-02',lines,customer_id=shop.customer)
    report=shop.reports.model_sales('2026-10-01','2026-10-31')[0]
    assert report['net_sales']==money('600000')
    assert report['gross_profit']==money('98000')
    assert report['selling_average']==money('50000')
    stock=shop.stock.current()[0]
    assert (stock['quantity'],stock['value'],stock['available_average'],stock['average_purchase_price'])==(
        3,money('138000'),money('46000'),money('42666.67'))
    assert sum(row['cogs'] for row in shop.sales.details(identity)[1])==money('502000')


def test_bill_book_number_idempotency_dues_and_search(shop):
    shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=4,unit_price='100000')],
                        supplier_id=shop.supplier)
    lines=[dict(product_id=shop.product,quantity=1,selling_rate='300000')]
    args=dict(customer_id=shop.customer,payments=[dict(account_id=shop.cash,amount='200000')],
              bill_book_number='  BB-218  ',key='saved-form')
    identity=shop.sales.post('2026-10-02',lines,**args)
    assert shop.sales.post('2026-10-02',lines,**args)==identity
    with pytest.raises(BusinessError,match='already recorded'):
        shop.sales.post('2026-10-02',lines,**dict(args,bill_book_number='bb-218',key='new-form'))
    shop.money.collect(shop.customer,'2026-10-03',shop.bank,'40000')
    row=shop.sales.list(query='BB-218')[0]
    assert row['bill_book_number']=='BB-218' and row['legacy_reference']==''
    assert row['id']==identity and len(shop.sales.list())==1
    assert shop.parties.documents(shop.customer)[0]['outstanding']==money('60000')
    assert shop.reports.model_sales('2026-10-01','2026-10-31')[0]['net_sales']==money('300000')
    assert shop.reports.receipt_totals('2026-10-01','2026-10-31')==dict(at_sale=money('200000'),later=money('40000'),refunds=0)


def test_selling_average_uses_weighted_net_activity_and_return_date(shop):
    shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=10,unit_price='100')],
                        supplier_id=shop.supplier)
    first=shop.sales.post('2026-10-02',[dict(product_id=shop.product,quantity=3,selling_rate='200')],
                          customer_id=shop.customer)
    shop.sales.post('2026-10-03',[dict(product_id=shop.product,quantity=1,selling_rate='400')],customer_id=shop.customer)
    item=shop.sales.details(first)[1][0]['id']
    shop.returns.post('2026-10-04',first,[dict(sale_item_id=item,quantity=1)])
    rows=shop.reports.model_sales('2026-10-01','2026-10-31')
    assert rows[0]['selling_average']==money('266.67')
    daily=shop.reports.model_sales('2026-10-01','2026-10-31',daily=True)
    assert daily[0]['net_quantity']==-1 and daily[0]['selling_average'] is None
    assert daily[0]['net_sales']==-money('200') and daily[0]['net_cogs']==-money('100')
    with shop.db.connect(write=True) as connection:
        connection.execute('UPDATE sale_items SET cogs_known=0 WHERE sale_id=?',(first,))
    assert shop.reports.model_sales('2026-10-01','2026-10-31')[0]['gross_profit'] is None
    assert shop.reports.model_sales('2026-11-01','2026-11-30')==[]


def test_schema5_backup_restore_and_migration_preserve_original_references(shop,tmp_path):
    # Create a genuine v5 schema and restore its packaged backup through v7.
    old=tmp_path/'old'
    (old/'data').mkdir(parents=True)
    with closing(sqlite3.connect(old/'data/mobile_desk.db')) as connection:
        connection.executescript('\n'.join(MIGRATIONS[i] for i in range(1,6)))
        connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
        connection.execute('PRAGMA user_version=5')
        connection.execute("""
            INSERT INTO sales(invoice_number,transaction_date,customer_snapshot,subtotal,total,notes,legacy_reference,created_at)
            VALUES('S-000001','2026-10-02','Walk-in',0,0,'','Historical reference','2026-10-02')
        """)
        connection.commit()
    from mobile_desk.catalogue import Catalogue
    from mobile_desk.services.backup import BackupService
    Catalogue(old/'data/mobile_catalogue.db')
    backup=BackupService(old).create()
    shop.security.set_password('Owner','test-password','test-password')
    shop.backups.restore(backup,username='Owner',password='test-password')
    reopened=Context(shop.root,install_catalogue=False)
    row=reopened.sales.list()[0]
    assert row['legacy_reference']=='Historical reference' and row['bill_book_number']==''
    assert reopened.db.one('PRAGMA user_version')['user_version']==6
    assert list(reopened.db.path.parent.glob('mobile_desk.before-v6-*.db'))
    assert reopened.db.one('PRAGMA integrity_check')['integrity_check']=='ok'
    assert reopened.db.rows('PRAGMA foreign_key_check')==[]
    reopened.security.authorize('Owner','test-password')


def test_simple_shop_sale_dialog_saves_manual_bill_and_shows_current_due(shop):
    from mobile_desk.ui.main_window import MainWindow
    from mobile_desk.ui.transactions import TransactionDialog
    app=QApplication.instance() or QApplication([])
    shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=4,unit_price='100')],
                        supplier_id=shop.supplier)
    window=MainWindow(shop)
    assert [button.text() for button in window.nav]==['Dashboard','Sales','Purchases','Stock','Accounts','Reports']
    window.navigate(4)
    assert [window.pages[4].tabText(i) for i in range(3)]==['Customers','Suppliers','Cash & Bank']
    dialog=TransactionDialog(window,shop)
    dialog.date.setDate(QDate(2026,10,2))
    dialog.party.setCurrentIndex(dialog.party.findData(shop.customer))
    dialog.add_product(shop.products.get(shop.product))
    dialog.entries[0]['price'].setText('200')
    dialog.payment_mode.setCurrentIndex(1)
    dialog.payments[0][0].setText('50')
    dialog.bill_book.setText('Notebook-1')
    dialog.preview_margin()
    assert '100.00' in dialog.estimate.text() and '4 available' in dialog.reference_prices.text()
    dialog.commit()
    assert dialog.result()==QDialog.DialogCode.Accepted,dialog.error.text()
    assert 'Notebook-1' in window.invoice_html(dialog.result_id)
    shop.money.collect(shop.customer,'2026-10-03',shop.cash,'40')
    window.navigate(1)
    page=window.pages[1]
    page.start.setDate(QDate(2026,10,1))
    page.end.setDate(QDate(2026,10,31))
    row=page.table.selected()
    assert row['remaining']==money('110') and row['payment_status']=='Part due'
    assert 'Notebook-1' in row['sale_reference']
    window.setFixedSize(1366, 749)
    window.show()
    app.processEvents()
    assert page.table.horizontalScrollBar().maximum()==0
    window.navigate(5)
    report=window.pages[5]
    report.start.setDate(QDate(2026,10,1))
    report.end.setDate(QDate(2026,10,31))
    report.refresh()
    assert report.table.selected()['net_sales']==money('200')
    assert '1 net pieces' in report.totals.text()
    window.close()
    app.processEvents()
