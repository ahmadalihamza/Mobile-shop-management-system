"""Explicit one-time clean start; never runs automatically at application launch."""
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
from PySide6.QtCore import QLockFile
from mobile_desk.database import Database
from mobile_desk.services.backup import BackupService,digest,check_database
from mobile_desk.values import BusinessError
from mobile_desk.services.security import SecurityService

BUSINESS_TABLES=('products','product_aliases','parties','purchase_batches','purchase_items','purchase_stacks','purchase_returns','purchase_return_items','purchase_refunds','sales','sale_items','stock_allocations','returns','return_items','return_allocations','payments','party_adjustments','expenses','account_transfers','stock_movements','exchange_rate_history','migration_runs','historical_evidence','migration_issues','inventory_confirmations','entry_drafts')


def safe_account_names(c):
    """Keep actual application configuration, not import-only ledger buckets.
    The retired importer wrote account evidence but did not emit the normal
    SAVE/account audit created by application configuration.
    """
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    imported={int(r[0]) for r in c.execute("SELECT DISTINCT entity_id FROM historical_evidence WHERE entity='accounts'")} if 'historical_evidence' in tables else set()
    configured={int(r[0]) for r in c.execute("SELECT entity_id FROM audit_log WHERE action='SAVE' AND entity='account'")}
    return {name for identity,name in c.execute('SELECT id,name FROM accounts') if identity not in imported or identity in configured or name=='Cash'}


def clean_start(root, *, username=None, password=None):
    root=Path(root).resolve()
    security=SecurityService(root)
    if security.configured:
        security.authorize(username or '', password or '')
    source=root/'data/mobile_desk.db'
    if not source.is_file():
        raise BusinessError('No existing business database was found.')
    lock=QLockFile(str(root/'mobile_desk.lock'))
    if not lock.tryLock(100):
        raise BusinessError('Close Mobile Desk before starting with a clean database.')
    try:
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        archive=root/'archives'/('BeforeCleanStart_'+stamp)
        archive.mkdir(parents=True)
        backup=BackupService(root).create(archive)
        catalogue=root/'data/mobile_catalogue.db'
        catalogue_hash=digest(catalogue) if catalogue.exists() else None
        with closing(sqlite3.connect(source)) as c:
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            before={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in BUSINESS_TABLES if t in tables}
            settings=dict(c.execute('SELECT key,value FROM settings'))
            allowed=safe_account_names(c)
            accounts=[r for r in c.execute('SELECT name,account_type,active FROM accounts ORDER BY id') if r[0] in allowed]
            removed_accounts=[r[0] for r in c.execute('SELECT name FROM accounts') if r[0] not in allowed]
        staged=root/'data'/('clean-start-'+stamp+'.db')
        fresh=Database(staged)
        with fresh.connect(write=True) as c:
            for key in ('shop_name','shop_phone','shop_address','invoice_prefix','backup_folder'):
                if key in settings:
                    c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,settings[key]))
            # Names are configuration; old money balances are operational history.
            for name,kind,active in accounts:
                c.execute('INSERT INTO accounts(name,account_type,opening_balance,opening_date,active) VALUES(?,?,0,?,?)',(name,kind,'1900-01-01',active))
            if not accounts:
                c.execute("INSERT INTO accounts(name,account_type,opening_date) VALUES('Cash','CASH','1900-01-01')")
        with fresh.connect() as c:
            c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        check_database(staged)
        after={t:fresh.one('SELECT COUNT(*) n FROM '+t)['n'] for t in BUSINESS_TABLES}
        if any(after.values()):
            raise BusinessError('The new database is not clean; no records were replaced.')
        with closing(sqlite3.connect(source)) as c:
            c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        # Preserve the exact former files, including any checkpoint sidecars.
        source.rename(archive/'mobile_desk-original.db')
        for suffix in ('-wal','-shm'):
            path=Path(str(source)+suffix)
            if path.exists():
                path.rename(archive/path.name)
        try:
            os.replace(staged,source)
        except BaseException:
            (archive/'mobile_desk-original.db').rename(source)
            raise
        assert not catalogue_hash or digest(catalogue)==catalogue_hash
        report=dict(clean_start=True,backup=str(backup),archive=str(archive),before=before,after=after,catalogue_unchanged=True,catalogue_sha256=catalogue_hash,accounts_openings_reset=True,removed_import_only_accounts=removed_accounts)
        (archive/'CLEAN_START_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        return report
    finally:
        lock.unlock()
