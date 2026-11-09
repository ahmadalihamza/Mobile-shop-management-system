from decimal import Decimal
from pathlib import Path
import sqlite3
import pytest
from mobile_desk.context import Context
from mobile_desk.database import Database,MIGRATIONS,APPLICATION_ID
from mobile_desk.services.purchases import price_line
from mobile_desk.values import money,BusinessError


def test_rmb_carry_converts_at_each_saved_line_rate_and_does_not_recost(shop):
    batch=shop.purchases.post('2026-10-01',[
        dict(product_id=shop.product,quantity=20,unit_price='1000',carry='25',exchange_rate='40'),
        dict(product_id=shop.product,quantity=30,unit_price='900',carry='30',exchange_rate='41')],
        purchase_type='CHINA_IMPORT',supplier_id=shop.supplier,default_rate='40',carry_currency='CNY')
    header,lots=shop.purchases.details(batch)
    assert lots[0]['additional_cost_per_unit']==money('1000')
    assert lots[1]['additional_cost_per_unit']==money('1230')
    assert lots[0]['landed_unit_cost']==money('41000')
    assert lots[1]['landed_unit_cost']==money('38130')
    assert lots[0]['foreign_carry_per_unit']=='25' and lots[1]['foreign_carry_per_unit']=='30'
    assert header['total']==money('1963900') and header['supplier_total']==money('1907000')
    assert shop.stock.current()[0]['average_purchase_price']==money('39278')
    shop.money.add_rate('2026-10-02','50')
    restarted=Context(shop.root,install_catalogue=False)
    assert restarted.purchases.details(batch)[1][1]['exchange_rate_snapshot']=='41'
    assert restarted.stock.current()[0]['value']==money('1963900')


def test_local_carry_currency_and_legacy_china_carry_remain_pkr():
    assert price_line(dict(quantity=1,unit_price='1000',carry='50'),'LOCAL')['landed_unit_cost']==money('1050')
    assert price_line(dict(quantity=1,unit_price='1000',carry='50'),'CHINA_IMPORT','40')['landed_unit_cost']==money('40050')
    with pytest.raises(BusinessError,match='only available for China'):
        price_line(dict(quantity=1,unit_price='1000',carry='50',carry_currency='CNY'),'LOCAL')
    line=price_line(dict(quantity=3,unit_price='1000',carry='0.123456',exchange_rate='40.123456',carry_currency='CNY'),'CHINA_IMPORT')
    assert line['additional_cost_per_unit']==495
    assert line['line_total_cost']==3*line['landed_unit_cost']


def test_pending_stock_unavailable_arrival_is_atomic_and_cannot_repeat(shop):
    purchase=shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=3,unit_price='100')],supplier_id=shop.supplier,received=False)
    assert shop.stock.totals()==dict(quantity=0,value=0)
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('300')
    with pytest.raises(BusinessError,match='Not enough stock'):
        shop.sales.post('2026-10-02',[dict(product_id=shop.product,quantity=1,selling_rate='150')],customer_id=shop.customer)
    shop.purchases.receive(purchase,'2026-10-03')
    assert shop.stock.totals()==dict(quantity=3,value=money('300'))
    with pytest.raises(BusinessError,match='awaiting arrival'):
        shop.purchases.receive(purchase,'2026-10-04')
    assert shop.stock.totals()['quantity']==3
    assert shop.purchases.details(purchase)[0]['received_date']=='2026-10-03'


def test_purchase_undo_requires_owner_and_preserves_history(shop,owner_credentials):
    purchase=shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=2,unit_price='100')],supplier_id=shop.supplier)
    with pytest.raises(BusinessError,match='Incorrect owner'):
        shop.purchases.void(purchase,'Wrong entry')
    assert shop.stock.totals()['quantity']==2
    shop.purchases.void(purchase,'Mistaken entry',**owner_credentials)
    assert shop.stock.totals()['quantity']==0
    assert shop.purchases.details(purchase)[0]['status']=='VOID'
    assert 'test-owner' in shop.db.one("SELECT reason FROM audit_log WHERE action='VOID' AND entity='purchase'")['reason']


def test_schema_four_upgrade_preserves_old_costs_and_creates_safety_copy(tmp_path):
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as c:
        c.executescript('\n'.join(MIGRATIONS[v] for v in range(1,5)))
        c.execute(f'PRAGMA application_id={APPLICATION_ID}')
        c.execute('PRAGMA user_version=4')
        c.execute("INSERT INTO products(custom_name,normalized_search_name,created_at,updated_at) VALUES('Legacy phone','legacy phone','old','old')")
        c.execute("INSERT INTO purchase_batches(reference,transaction_date,purchase_type,supplier_snapshot,currency,total,notes,created_at) VALUES('OLD-1','2026-10-01','CHINA_IMPORT','Supplier','CNY',4010000,'old','old')")
        c.execute("INSERT INTO purchase_items(purchase_batch_id,product_id,quantity,original_currency,foreign_unit_price,exchange_rate_snapshot,pkr_unit_purchase_cost,additional_cost_per_unit,landed_unit_cost,line_total_cost,product_description_snapshot,created_at) VALUES(1,1,1,'CNY','1000','40',4000000,10000,4010000,4010000,'Legacy phone','old')")
    db=Database(path)
    lot=db.one('SELECT * FROM purchase_items')
    assert lot['carry_currency']=='PKR' and lot['foreign_carry_per_unit'] is None
    assert lot['landed_unit_cost']==money('40100')
    assert db.one('SELECT * FROM purchase_batches')['shipment_status']=='RECEIVED'
    assert db.one('PRAGMA user_version')['user_version']==5
    assert list(tmp_path.glob('legacy.before-v5-*.db'))
    assert db.one('PRAGMA integrity_check')['integrity_check']=='ok'


def test_carry_is_charged_once_for_each_stack_and_average_is_weighted(shop):
    batch=shop.purchases.post('2026-10-01',[
        dict(product_id=shop.product,quantity=6,unit_price='500',carry='150'),
        dict(product_id=shop.product,quantity=10,unit_price='600',carry='525')],
        purchase_type='CHINA_IMPORT',default_rate='40',carry_currency='CNY',carry_basis='STACK_TOTAL',supplier_id=shop.supplier,carry_billed_to_supplier=True)
    header,lots=shop.purchases.details(batch)
    assert header['total']==money('387000') and header['supplier_total']==money('387000')
    assert shop.stock.current()[0]['average_purchase_price']==money('24187.50')
    stacks=shop.purchases.stacks(batch)
    assert [(s['quantity'],s['carry_input']) for s in stacks]==[(6,'150'),(10,'525')]
    assert sum(s['total_carry_cost'] for s in stacks)==money('27000')


def test_stack_carry_rounding_keeps_exact_charge_in_fifo_lots_and_report(shop):
    line=dict(product_id=shop.product,quantity=6,unit_price='1000',carry='1')
    batch=shop.purchases.post('2026-10-01',[line],purchase_type='CHINA_IMPORT',default_rate='40',carry_currency='CNY',carry_basis='STACK_TOTAL',supplier_id=shop.supplier)
    header,lots=shop.purchases.details(batch)
    assert sum(lot['quantity'] for lot in lots)==6 and len(lots)==2
    assert sum(lot['quantity']*lot['additional_cost_per_unit'] for lot in lots)==money('40')
    assert header['total']==shop.stock.totals()['value']==money('240040')
    assert max(lot['landed_unit_cost'] for lot in lots)-min(lot['landed_unit_cost'] for lot in lots)==1
    history=shop.reports.purchase_history('2026-10-01','2026-10-31',True)
    assert len(history)==1 and history[0]['quantity']==6
    assert history[0]['carry_input']=='1' and history[0]['carry_basis']=='STACK_TOTAL'
    assert history[0]['total_carry_cost']==money('40') and history[0]['line_total_cost']==money('240040')
    shop.sales.post('2026-10-02',[dict(product_id=shop.product,quantity=6,selling_rate='50000')],customer_id=shop.customer)
    assert shop.reports.period_profit('2026-10-01','2026-10-31')['cogs']==money('240040')
