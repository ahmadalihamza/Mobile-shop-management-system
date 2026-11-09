from pathlib import Path
import json
import sqlite3
import zipfile
import pytest
from mobile_desk.catalogue import Catalogue,models_checksum
from mobile_desk.context import Context
from mobile_desk.values import BusinessError
from mobile_desk.services.backup import recover_interrupted_restore


def package(version='1.0',models=None):
    models=models or [dict(id='a55',brand='Samsung',model='Galaxy A55 5G',aliases=['a55']),dict(id='15p',brand='Apple',model='iPhone 15 Pro',aliases=['15 pro'])]
    return dict(format='mobile-desk-catalogue',schema_version=1,version=version,source='test fixture',licence='test',models=models,sha256=models_checksum(models))


def test_catalogue_search_and_snapshot_independence(shop):
    shop.catalogue.import_package(package())
    assert shop.catalogue.search(' A55 ')[0]['id']=='a55'
    assert shop.catalogue.search('15pro')[0]['id']=='15p'
    p=shop.products.save(custom_name='Samsung A55 Navy 8/256',catalogue_model_id='a55')
    shop.purchases.post('2026-09-01',[dict(product_id=p,quantity=1,unit_price='100')])
    s=shop.sales.post('2026-09-02',[dict(product_id=p,quantity=1,selling_rate='150')],customer_id=shop.customer)
    shop.catalogue.import_package(package('2.0',[dict(id='a55',brand='Samsung',model='Updated model name',aliases=['a55'])]))
    assert shop.sales.details(s)[1][0]['product_description_snapshot']=='Samsung A55 Navy 8/256'
    assert shop.products.get(p)['custom_name']=='Samsung A55 Navy 8/256'


def test_update_rollback_duplicate_and_version(shop):
    shop.catalogue.import_package(package())
    with pytest.raises(BusinessError):
        shop.catalogue.import_package(package())
    with pytest.raises(BusinessError):
        shop.catalogue.import_package(package('2.0',[dict(id='new',brand='Samsung',model='Galaxy A55 5G')]))
    bad=package('2.0')
    bad['sha256']='bad'
    with pytest.raises(BusinessError):
        shop.catalogue.import_package(bad)
    assert shop.catalogue.info()['version']=='1.0'
    assert shop.catalogue.info()['count']==2


def test_update_rollback_midway(shop):
    shop.catalogue.import_package(package())
    update=package('2.0',[dict(id='new',brand='New brand',model='New model'),dict(id='wrong-id',brand='Samsung',model='Galaxy A55 5G')])
    with pytest.raises(BusinessError):
        shop.catalogue.import_package(update)
    assert not shop.catalogue.search('New model')
    assert shop.catalogue.info()['brands']==2


def test_backup_restore_complete_and_safety(shop):
    shop.catalogue.import_package(package())
    backup=shop.backups.create()
    shop.products.save(custom_name='After backup')
    safety=shop.backups.restore(backup)
    assert safety.exists()
    assert len(shop.products.search())==1
    assert shop.catalogue.info()['version']=='1.0'
    assert shop.db.one("SELECT COUNT(*) n FROM audit_log WHERE action='RESTORE'")['n']==1


def test_tampered_backup_does_not_touch_data(shop,tmp_path):
    source=shop.backups.create()
    corrupt=tmp_path/'bad.mdbackup'
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(corrupt,'w') as dest:
        for name in original.namelist():
            dest.writestr(name,b'not sqlite' if name=='mobile_desk.db' else original.read(name))
    with pytest.raises(BusinessError):
        shop.backups.restore(corrupt)
    assert len(shop.products.search())==1


def test_zip_path_traversal_rejected(shop,tmp_path):
    corrupt=tmp_path/'bad.mdbackup'
    with zipfile.ZipFile(corrupt,'w') as z:
        z.writestr('../outside.db','bad')
        z.writestr('manifest.json','{}')
    with pytest.raises(BusinessError):
        shop.backups.inspect(corrupt)
    assert not (tmp_path.parent/'outside.db').exists()


def test_restore_failure_rolls_back_directory_swap(shop,monkeypatch):
    source=shop.backups.create()
    shop.products.save(custom_name='Keep me')
    import mobile_desk.services.backup as module
    real=module.check_database
    calls=0
    def fail(path,catalogue=False):
        nonlocal calls
        if Path(path)==shop.root/'data/mobile_desk.db':
            raise OSError('simulated post-swap failure')
        return real(path,catalogue)
    monkeypatch.setattr(module,'check_database',fail)
    with pytest.raises(OSError):
        shop.backups.restore(source)
    assert len(shop.products.search())==2
    assert not (shop.root/'.restore-pending').exists()


def test_interrupted_restore_recovery(shop):
    (shop.root/'data').rename(shop.root/'.restore-old')
    (shop.root/'data').mkdir()
    (shop.root/'.restore-pending').write_text('interrupted')
    recover_interrupted_restore(shop.root)
    assert len(shop.products.search())==1


def test_newer_schema_rejected(shop):
    from mobile_desk.database import Database
    with shop.db.connect() as c:
        c.execute('PRAGMA user_version=999')
    with pytest.raises(BusinessError):
        Database(shop.db.path)


def test_missing_catalogue_still_trades(shop):
    assert shop.catalogue.info()['count']==0
    shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=1,unit_price='100')])
    shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='150')],customer_id=shop.customer)
    assert shop.stock.totals()['quantity']==0
