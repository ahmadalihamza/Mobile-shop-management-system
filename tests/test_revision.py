from pathlib import Path
import sqlite3
import pytest
from mobile_desk.context import Context
from mobile_desk.clean_start import clean_start,BUSINESS_TABLES
from mobile_desk.services.backup import digest
from mobile_desk.values import BusinessError,money


def buy(shop,amount='50000',qty=10,paid='300000',**kwargs):
    return shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=qty,unit_price=amount)],supplier_id=shop.supplier,payments=[dict(account_id=shop.cash,amount=paid)] if paid!='0' else [],**kwargs)


def test_supplier_partial_later_payment_and_document_balance(shop):
    buy(shop)
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('200000')
    assert shop.parties.balance(shop.supplier)==0
    pid=shop.money.pay_supplier(shop.supplier,'2026-09-02',shop.bank,'100000',key='supplier-later')
    assert shop.money.pay_supplier(shop.supplier,'2026-09-02',shop.bank,'100000',key='supplier-later')==pid
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('100000')
    doc=shop.parties.documents(shop.supplier,role='SUPPLIER')[0]
    assert (doc['original_amount'],doc['settled'],doc['outstanding'])==tuple(map(money,('500000','400000','100000')))
    assert shop.reports.supplier_outstanding('2026-09-02')[0]['balance']==money('100000')
    assert shop.reports.dashboard('2026-09-02')['payable']==money('100000')
    assert shop.parties.statement(shop.supplier,role='SUPPLIER')[-1]['balance']==money('100000')
    assert sum(a['balance'] for a in shop.money.accounts())==-money('400000')
    assert shop.stock.totals()['quantity']==10
    shop.money.void('payment',pid,'Payment was entered twice')
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('200000')
    assert shop.parties.documents(shop.supplier,role='SUPPLIER')[0]['outstanding']==money('200000')


def test_china_cost_supplier_bill_and_external_carry_no_double_count(shop):
    pid=shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=10,unit_price='1000',carry='4000')],purchase_type='CHINA_IMPORT',default_rate='39.50',supplier_id=shop.supplier,payments=[dict(account_id=shop.cash,amount='300000')],carry_payment='40000',carry_account_id=shop.bank)
    header,lines=shop.purchases.details(pid)
    assert header['supplier_total']==money('395000')
    assert header['total']==money('435000')
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('95000')
    assert sum(a['balance'] for a in shop.money.accounts())==-money('340000')
    shop.money.add_rate('2026-09-02','41.10')
    shop.purchases.post('2026-09-02',[dict(product_id=shop.product,quantity=1,unit_price='1000')],purchase_type='CHINA_IMPORT',default_rate='41.10',supplier_id=shop.supplier)
    assert shop.purchases.details(pid)[1][0]['exchange_rate_snapshot']=='39.50'
    assert shop.purchases.details(pid)[1][0]['landed_unit_cost']==money('43500')
    shop.sales.post('2026-09-03',[dict(product_id=shop.product,quantity=2,selling_rate='50000')],payments=[dict(account_id=shop.cash,amount='100000')])
    assert shop.reports.period_profit('2026-09-01','2026-09-30')['profit_after_expenses']==money('13000')
    assert shop.stock.totals()['value']==money('389100')


def test_carry_billed_by_supplier_and_opening_stock(shop,owner_credentials):
    pid=shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=2,unit_price='40000',carry='1000')],supplier_id=shop.supplier,carry_billed_to_supplier=True,payments=[dict(account_id=shop.cash,amount='50000')])
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('32000')
    shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=1,unit_price='40000')],purchase_type='OPENING',supplier_id=shop.supplier)
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('32000')
    shop.purchases.void(pid,'Wrong quantity; replace purchase',**owner_credentials)
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==0
    assert shop.stock.totals()['quantity']==1
    assert shop.money.accounts()[0]['balance']==0


def test_supplier_payment_rollback_and_role_safety(shop):
    buy(shop,paid='0')
    before=shop.db.one('SELECT COUNT(*) n FROM payments')['n']
    with pytest.raises(BusinessError):
        shop.money.pay_supplier(shop.supplier,'2026-09-02',99999,'100000')
    with pytest.raises(BusinessError):
        shop.money.pay_supplier(shop.customer,'2026-09-02',shop.cash,'100000')
    assert shop.db.one('SELECT COUNT(*) n FROM payments')['n']==before
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('500000')
    with pytest.raises(BusinessError):
        shop.parties.save('Supplier One',party_id=shop.supplier,is_customer=True,is_supplier=False)


def test_same_person_customer_supplier_ledgers_independent(shop):
    shop.parties.save('Both roles',party_id=shop.supplier,is_customer=True,is_supplier=True)
    buy(shop,paid='0')
    shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='60000')],customer_id=shop.supplier)
    shop.money.collect(shop.supplier,'2026-09-03',shop.cash,'10000')
    shop.money.pay_supplier(shop.supplier,'2026-09-03',shop.cash,'20000')
    assert shop.parties.balance(shop.supplier)==money('50000')
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('480000')


def test_oldest_bill_settlement_advances_asof_and_returns(shop):
    buy(shop,paid='0')
    shop.money.collect(shop.customer,'2026-09-01',shop.cash,'5000')
    first=shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=2,selling_rate='50000')],customer_id=shop.customer,payments=[dict(account_id=shop.cash,amount='30000')])
    shop.sales.post('2026-09-03',[dict(product_id=shop.product,quantity=1,selling_rate='60000')],customer_id=shop.customer)
    shop.money.collect(shop.customer,'2026-09-04',shop.cash,'75000')
    docs=shop.parties.documents(shop.customer)
    assert [d['outstanding'] for d in docs]==[0,money('50000')]
    assert [d['outstanding'] for d in shop.parties.documents(shop.customer,'2026-09-03')]==[money('65000'),money('60000')]
    item=shop.sales.details(first)[1][0]
    shop.returns.post('2026-09-05',first,[dict(sale_item_id=item['id'],quantity=1)],refund='10000',account_id=shop.cash)
    assert sum(d['outstanding'] for d in shop.parties.documents(shop.customer))==shop.parties.balance(shop.customer)==money('10000')


def test_supplier_opening_and_advance_after_void(shop,owner_credentials):
    shop.parties.adjustment(shop.supplier,'2026-08-31','OPENING_BALANCE','30000','Actual opening supplier balance',role='SUPPLIER')
    pid=buy(shop,qty=1,paid='0')
    shop.money.pay_supplier(shop.supplier,'2026-09-02',shop.cash,'40000')
    assert [d['outstanding'] for d in shop.parties.documents(shop.supplier,role='SUPPLIER')]==[0,money('40000')]
    shop.purchases.void(pid,'Wrong purchase; replace',**owner_credentials)
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==-money('10000')
    assert sum(d['outstanding'] for d in shop.parties.documents(shop.supplier,role='SUPPLIER'))==0


def test_clean_start_preserves_catalogue_config_archives_everything(shop):
    shop.catalogue.import_file(Path('resources/mobile_catalogue.json'))
    buy(shop)
    shop.money.save_settings(shop_name='Client shop',setup_complete='1')
    old_catalogue=digest(shop.root/'data/mobile_catalogue.db')
    result=clean_start(shop.root)
    assert result['before']['purchase_batches']==1 and not any(result['after'].values())
    assert Path(result['backup']).is_file()
    restarted=Context(shop.root)
    assert restarted.db.setting('shop_name')=='Client shop'
    assert restarted.db.setting('setup_complete')=='0'
    assert digest(shop.root/'data/mobile_catalogue.db')==old_catalogue
    assert restarted.catalogue.info()['count']>10000
    assert all(a['balance']==0 for a in restarted.money.accounts())
    assert not any(restarted.db.one('SELECT COUNT(*) n FROM '+t)['n'] for t in BUSINESS_TABLES)
    # Two further starts do not restore the old records.
    assert not Context(shop.root).sales.list() and not Context(shop.root).purchases.list()


def test_retired_excel_backup_cannot_be_restored(shop):
    buy(shop)
    with shop.db.connect(write=True) as c:
        c.execute("UPDATE purchase_batches SET data_origin='EXCEL_MIGRATION'")
    archived=shop.backups.create()
    clean_start(shop.root)
    restarted=Context(shop.root,install_catalogue=False)
    with pytest.raises(BusinessError,match='retired Excel'):
        restarted.backups.restore(archived)
    assert not restarted.purchases.list()


def test_supplier_payment_persists_backup_restore_and_restart(shop):
    buy(shop)
    shop.money.pay_supplier(shop.supplier,'2026-09-02',shop.cash,'100000')
    backup=shop.backups.create()
    shop.money.pay_supplier(shop.supplier,'2026-09-03',shop.cash,'50000')
    shop.backups.restore(backup)
    restarted=Context(shop.root,install_catalogue=False)
    assert restarted.parties.balance(shop.supplier,role='SUPPLIER')==money('100000')
    assert restarted.parties.documents(shop.supplier,role='SUPPLIER')[0]['outstanding']==money('100000')
    assert restarted.db.one('PRAGMA integrity_check')['integrity_check']=='ok'


def test_production_resources_contain_no_excel_seed():
    assert not Path('resources/client_seed.zip').exists()
    assert not Path('mobile_desk/client_seed.py').exists()
    assert 'install_client_seed' not in Path('mobile_desk/app.py').read_text()


def test_later_carry_payment_corrects_money_only_and_is_reversible(shop):
    pid=shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=2,unit_price='40000',carry='1000')],supplier_id=shop.supplier)
    before=shop.reports.period_profit('2026-09-01','2026-09-30')
    payment=shop.money.pay_carry(pid,'2026-09-02',shop.cash,'1500')
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('80000')
    assert shop.stock.totals()['value']==money('82000')
    assert shop.money.accounts()[0]['balance']==-money('1500')
    assert shop.reports.period_profit('2026-09-01','2026-09-30')==before
    with pytest.raises(BusinessError,match='remaining transport'):
        shop.money.pay_carry(pid,'2026-09-02',shop.cash,'501')
    shop.money.void('payment',payment,'Wrong transport amount')
    assert shop.money.accounts()[0]['balance']==0
    shop.money.pay_carry(pid,'2026-09-03',shop.cash,'2000')
    assert shop.money.accounts()[0]['balance']==-money('2000')


def test_partial_month_report_limits_invoice_credit_to_range(shop):
    buy(shop,paid='0')
    shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='50000')],customer_id=shop.customer)
    shop.sales.post('2026-09-20',[dict(product_id=shop.product,quantity=1,selling_rate='60000')],customer_id=shop.customer)
    summary=shop.reports.sales_summary('2026-09-01','2026-09-10',monthly=True)
    assert summary[0]['sales']==summary[0]['credit_sales']==money('50000')


def test_clean_start_removes_import_only_account_configuration(shop):
    with shop.db.connect(write=True) as c:
        imported=c.execute("INSERT INTO accounts(name,account_type,opening_date) VALUES('Historical bank unspecified','BANK','1900-01-01')").lastrowid
        c.execute("INSERT INTO migration_runs(id,started_at,migration_version,source_manifest,plan_checksum,status) VALUES(1,'2026-09-01','retired','{}','test','COMPLETED')")
        for identity in (imported,shop.cash,shop.bank):
            c.execute("INSERT INTO historical_evidence VALUES(?,1,'reference.xlsx','test','test','1','test','test','accounts',?,'{}','retired account reference')",('account-'+str(identity),identity))
    result=clean_start(shop.root)
    restarted=Context(shop.root,install_catalogue=False)
    assert {a['name'] for a in restarted.money.accounts()}=={'Cash','MJ Bank'}
    assert result['removed_import_only_accounts']==['Historical bank unspecified']
