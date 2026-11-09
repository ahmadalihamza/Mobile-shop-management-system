from pathlib import Path
import json
import pytest
from mobile_desk.context import Context
from mobile_desk.services.backup import BackupService
from mobile_desk.services.security import SecurityService
from mobile_desk.values import BusinessError, money

OWNER='shop-owner'
PASSWORD='Test shop owner 26!'


def protect(shop):
    shop.security.set_password(OWNER,PASSWORD,PASSWORD)


def transactions(shop):
    purchase=shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=3,unit_price='100')],
        supplier_id=shop.supplier,payments=[dict(account_id=shop.cash,amount='100')])
    sale=shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='150')],
        customer_id=shop.customer,payments=[dict(account_id=shop.bank,amount='50')])
    return purchase,sale


def test_password_setup_change_no_plaintext_and_persistent_attempt_limit(shop,monkeypatch):
    protect(shop)
    assert PASSWORD not in shop.security.path.read_text()
    security=SecurityService(shop.root)
    for _ in range(5):
        with pytest.raises(BusinessError,match='Incorrect'):
            security.authorize(OWNER,'wrong password')
    with pytest.raises(BusinessError,match='Wait one minute'):
        SecurityService(shop.root).authorize(OWNER,PASSWORD)
    import mobile_desk.services.security as module
    locked=json.loads(security.path.read_text())['locked_until']
    monkeypatch.setattr(module.time,'time',lambda:locked+1)
    security.authorize(OWNER,PASSWORD)
    with pytest.raises(BusinessError,match='Incorrect'):
        security.set_password(OWNER,'new correct password','new correct password',current_password='wrong')
    security.authorize(OWNER,PASSWORD)
    security.set_password(OWNER,'new correct password','new correct password',current_password=PASSWORD)
    with pytest.raises(BusinessError,match='Incorrect'):
        security.authorize(OWNER,PASSWORD)
    security.authorize(OWNER,'new correct password')


def test_reset_rejects_unconfigured_wrong_credentials_and_confirmation(shop):
    transactions(shop)
    with pytest.raises(BusinessError,match='set a password'):
        shop.reset.reset(OWNER,PASSWORD,'RESET')
    protect(shop)
    for user,password,confirmation in [(OWNER,'wrong','RESET'),('employee',PASSWORD,'RESET'),(OWNER,PASSWORD,''),(OWNER,PASSWORD,'reset')]:
        with pytest.raises(BusinessError):
            shop.reset.reset(user,password,confirmation)
    assert len(shop.sales.list())==len(shop.purchases.list())==1
    assert shop.stock.totals()['quantity']==2
    assert not list((shop.root/'backups').glob('*.mdbackup'))


def test_reset_zeroes_business_keeps_configuration_owner_catalogue_and_restores(shop):
    from mobile_desk.catalogue import models_checksum
    models=[dict(id='test-phone',brand='Test',model='Phone',aliases=['testphone'])]
    shop.catalogue.import_package(dict(format='mobile-desk-catalogue',schema_version=1,version='1.0',
        source='test fixture',licence='test',models=models,sha256=models_checksum(models)))
    shop.money.save_settings(shop_name='Client Shop',invoice_prefix='MJ-',setup_complete='1',backup_folder=str(shop.root/'usb'))
    shop.money.account('Owner Bank',opening='1000',day='2026-08-01')
    transactions(shop)
    shop.money.collect(shop.customer,'2026-09-03',shop.cash,'20')
    shop.money.pay_supplier(shop.supplier,'2026-09-03',shop.bank,'50')
    shop.money.expense('2026-09-03','Delivery','5',shop.cash)
    shop.money.transfer('2026-09-03',shop.cash,shop.bank,'10')
    shop.parties.adjustment(shop.customer,'2026-09-01','OPENING_BALANCE','30','Agreed opening')
    protect(shop)
    owner_before=shop.security.path.read_bytes()
    catalogue_before=shop.catalogue.search('testphone')
    backup=shop.reset.reset(OWNER,PASSWORD,'RESET')
    assert backup.exists()
    restarted=Context(shop.root,install_catalogue=False)
    for table in ('products','product_aliases','parties','purchase_batches','purchase_items','sales','sale_items',
        'stock_allocations','stock_movements','payments','returns','return_items','return_allocations',
        'expenses','account_transfers','party_adjustments','exchange_rate_history','operation_keys'):
        assert restarted.db.one('SELECT COUNT(*) n FROM '+table)['n']==0,table
    assert restarted.stock.totals()==dict(quantity=0,value=0)
    assert all(a['balance']==a['opening_balance']==0 for a in restarted.money.accounts())
    assert {a['name'] for a in restarted.money.accounts()}=={'Cash','MJ Bank','Owner Bank'}
    assert restarted.db.setting('shop_name')=='Client Shop'
    assert restarted.db.setting('next_invoice')=='1'
    assert restarted.db.setting('setup_complete')=='1'
    assert restarted.security.path.read_bytes()==owner_before
    assert restarted.catalogue.search('testphone')==catalogue_before
    assert restarted.db.one("SELECT COUNT(*) n FROM audit_log WHERE action='RESET'")['n']==1
    with pytest.raises(BusinessError,match='Incorrect'):
        restarted.backups.restore(backup)
    restarted.backups.restore(backup,username=OWNER,password=PASSWORD)
    recovered=Context(shop.root,install_catalogue=False)
    assert recovered.stock.totals()['quantity']==2
    assert recovered.parties.balance(shop.customer)==money('110')
    assert recovered.parties.balance(shop.supplier,role='SUPPLIER')==money('150')
    assert len(recovered.sales.list())==1 and len(recovered.purchases.list())==1
    assert recovered.security.path.read_bytes()==owner_before


def test_old_backup_cannot_remove_owner_protection(shop):
    old=shop.backups.create()
    protect(shop)
    shop.products.save(custom_name='Preserve this')
    with pytest.raises(BusinessError):
        shop.backups.restore(old)
    assert len(shop.products.search())==2
    shop.backups.restore(old,username=OWNER,password=PASSWORD)
    assert SecurityService(shop.root).configured
    with pytest.raises(BusinessError):
        shop.reset.reset(OWNER,'wrong','RESET')


def test_corrupt_owner_record_blocks_reset_restore_and_password_replacement(shop):
    backup=shop.backups.create()
    protect(shop)
    shop.security.path.write_text('{}')
    for action in (lambda:shop.reset.reset(OWNER,PASSWORD,'RESET'),
                   lambda:shop.backups.restore(backup,username=OWNER,password=PASSWORD),
                   lambda:shop.security.set_password(OWNER,PASSWORD,PASSWORD,current_password=PASSWORD)):
        with pytest.raises(BusinessError,match='security could not be read'):
            action()
    assert len(shop.products.search())==1


def test_backup_failure_prevents_reset(shop,monkeypatch):
    transactions(shop)
    protect(shop)
    def fail(*args,**kwargs):
        raise OSError('Disk full')
    monkeypatch.setattr(BackupService,'create',fail)
    with pytest.raises(OSError,match='Disk full'):
        shop.reset.reset(OWNER,PASSWORD,'RESET')
    assert len(shop.sales.list())==1 and shop.stock.totals()['quantity']==2
    assert not (shop.root/'.restore-new').exists()


def test_reset_post_swap_failure_restores_original_records(shop,monkeypatch):
    transactions(shop)
    protect(shop)
    import mobile_desk.services.backup as module
    original=module.check_database
    def fail(path,catalogue=False):
        if Path(path)==shop.root/'data/mobile_desk.db':
            raise OSError('Simulated swap verification failure')
        return original(path,catalogue)
    monkeypatch.setattr(module,'check_database',fail)
    with pytest.raises(OSError,match='verification failure'):
        shop.reset.reset(OWNER,PASSWORD,'RESET')
    assert len(shop.sales.list())==1 and shop.stock.totals()['quantity']==2
    assert not (shop.root/'.restore-pending').exists()
    assert list((shop.root/'backups').glob('*.mdbackup'))


def test_undo_saved_order_reverses_sale_then_purchase_and_keeps_history(shop,owner_credentials):
    purchase,sale=transactions(shop)
    entry=shop.corrections.latest()
    assert entry['kind']=='sale' and entry['id']==sale
    shop.corrections.undo_latest(entry['audit_id'],'Wrong sale')
    assert shop.stock.totals()['quantity']==3
    assert shop.parties.balance(shop.customer)==0
    assert shop.money.accounts()[1]['balance']==0
    assert shop.sales.details(sale)[0]['status']=='VOID'
    entry=shop.corrections.latest()
    assert entry['kind']=='purchase' and entry['id']==purchase
    shop.corrections.undo_latest(entry['audit_id'],'Wrong purchase',**owner_credentials)
    assert shop.stock.totals()==dict(quantity=0,value=0)
    assert all(a['balance']==0 for a in shop.money.accounts())
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==0
    assert shop.corrections.latest() is None
    assert len(shop.sales.list())==len(shop.purchases.list())==1


def test_undo_blocks_used_purchase_and_changed_latest_without_mutation(shop,owner_credentials):
    purchase,sale=transactions(shop)
    with pytest.raises(BusinessError,match='dependent sale'):
        shop.corrections.undo('purchase',purchase,'Wrong purchase',**owner_credentials)
    entry=shop.corrections.latest()
    shop.money.collect(shop.customer,'2026-09-03',shop.cash,'20')
    with pytest.raises(BusinessError,match='latest saved entry has changed'):
        shop.corrections.undo_latest(entry['audit_id'],'Wrong sale')
    assert shop.sales.details(sale)[0]['status']=='POSTED'
    assert shop.stock.totals()['quantity']==2
    current=shop.corrections.latest()
    assert current['kind']=='payment'
    shop.corrections.undo_latest(current['audit_id'],'Wrong payment')
    assert shop.parties.balance(shop.customer)==money('100')


def test_undo_return_and_money_entries(shop):
    _,sale=transactions(shop)
    item=shop.sales.details(sale)[1][0]
    shop.returns.post('2026-09-03',sale,[dict(sale_item_id=item['id'],quantity=1)],refund='10',account_id=shop.cash)
    entry=shop.corrections.latest()
    assert entry['kind']=='return'
    shop.corrections.undo_latest(entry['audit_id'],'Wrong return')
    assert shop.stock.totals()['quantity']==2
    for expected,action in [
        ('payment',lambda:shop.money.pay_supplier(shop.supplier,'2026-09-03',shop.cash,'10')),
        ('expense',lambda:shop.money.expense('2026-09-03','Test expense','10',shop.cash)),
        ('transfer',lambda:shop.money.transfer('2026-09-03',shop.cash,shop.bank,'10')),
        ('adjustment',lambda:shop.parties.adjustment(shop.customer,'2026-09-03','OPENING_BALANCE','10','Test opening'))]:
        before=[a['balance'] for a in shop.money.accounts()]
        customer=shop.parties.balance(shop.customer)
        supplier=shop.parties.balance(shop.supplier,role='SUPPLIER')
        action()
        entry=shop.corrections.latest()
        assert entry['kind']==expected
        shop.corrections.undo_latest(entry['audit_id'],'Learning entry')
        assert [a['balance'] for a in shop.money.accounts()]==before
        assert shop.parties.balance(shop.customer)==customer
        assert shop.parties.balance(shop.supplier,role='SUPPLIER')==supplier
