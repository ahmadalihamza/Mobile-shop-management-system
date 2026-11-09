"""Checksummed snapshots, staged restore and recovery across directory swaps."""
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from contextlib import closing
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import zipfile
from mobile_desk.database import APPLICATION_ID, SCHEMA_VERSION, Database, audit
from mobile_desk.catalogue import CATALOGUE_ID
from mobile_desk.values import BusinessError, timestamp
from mobile_desk.services.security import SecurityService

FILES = ('mobile_desk.db', 'mobile_catalogue.db')


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_database(path: Path, catalogue=False):
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as c:
            c.execute('PRAGMA trusted_schema=OFF')
            application = c.execute('PRAGMA application_id').fetchone()[0]
            version = c.execute('PRAGMA user_version').fetchone()[0]
            expected = CATALOGUE_ID if catalogue else APPLICATION_ID
            if application != expected or not 1 <= version <= (1 if catalogue else SCHEMA_VERSION):
                raise BusinessError('Backup contains an incompatible database.')
            if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or c.execute('PRAGMA foreign_key_check').fetchone():
                raise BusinessError('Backup database integrity check failed.')
            if not catalogue:
                required = {'products','sales','sale_items','purchase_items','payments','stock_movements','settings','accounts','parties','returns','audit_log'}
                if version>=5:
                    required.update(('purchase_returns','purchase_return_items','purchase_refunds','purchase_stacks'))
                actual = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not required <= actual:
                    raise BusinessError('Backup is missing required business tables.')
                if c.execute('SELECT purchase_item_id FROM stock_movements GROUP BY purchase_item_id HAVING SUM(quantity)<0 LIMIT 1').fetchone():
                    raise BusinessError('Backup has invalid negative stock.')
    except sqlite3.DatabaseError:
        raise BusinessError('The backup does not contain readable SQLite databases.') from None


def reject_imported_history(path):
    """Old Excel migration archives must never become production records again."""
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        for table in ('products','parties','purchase_batches','sales','payments','returns','party_adjustments','expenses','account_transfers'):
            columns={row[1] for row in c.execute('PRAGMA table_info('+table+')')}
            if 'data_origin' in columns and c.execute('SELECT 1 FROM '+table+" WHERE data_origin='EXCEL_MIGRATION' LIMIT 1").fetchone():
                raise BusinessError('This backup contains retired Excel-imported history. It is an archive only and cannot be restored into the clean application.')


def recover_interrupted_restore(root: Path):
    marker, old, current, pending = root/'.restore-pending', root/'.restore-old', root/'data', root/'.restore-new'
    if not marker.exists():
        return
    # These paths are fixed children of the supplied data root, never paths from a package.
    if old.exists():
        if current.exists():
            abandoned = root/('.restore-abandoned-'+datetime.now().strftime('%Y%m%d%H%M%S%f'))
            current.rename(abandoned)
        old.rename(current)
    marker.unlink()
    if pending.exists():
        pending.rename(root/('.restore-unused-'+datetime.now().strftime('%Y%m%d%H%M%S%f')))
    logging.warning('Recovered interrupted backup restore')


class BackupService:
    def __init__(self, root: Path):
        self.root = Path(root)

    def create(self, folder=None) -> Path:
        folder = Path(folder or self.root/'backups')
        folder.mkdir(parents=True, exist_ok=True)
        target = folder/('MobileDesk_Backup_'+datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')+'.mdbackup')
        manifest = dict(format='mobile-desk-backup', version=1, created_at=timestamp(), files={})
        with TemporaryDirectory(prefix='md-backup-') as tmp:
            tmp = Path(tmp)
            for name in FILES:
                source = self.root/'data'/name
                if not source.exists():
                    if name == 'mobile_catalogue.db':
                        continue
                    raise BusinessError('No business database is available to back up.')
                with closing(sqlite3.connect(source)) as c, closing(sqlite3.connect(tmp/name)) as dest:
                    c.backup(dest)
                check_database(tmp/name, name == 'mobile_catalogue.db')
                manifest['files'][name] = digest(tmp/name)
            if 'mobile_catalogue.db' in manifest['files']:
                with closing(sqlite3.connect(tmp/'mobile_catalogue.db')) as c:
                    row = c.execute('SELECT version FROM catalogue_versions ORDER BY imported_at DESC LIMIT 1').fetchone()
                    manifest['catalogue_version'] = row[0] if row else '0.0'
            partial = target.with_suffix('.partial')
            try:
                with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                    z.writestr('manifest.json', json.dumps(manifest, indent=2))
                    for name in manifest['files']:
                        z.write(tmp/name, name)
                os.replace(partial, target)
            except BaseException:
                if partial.exists():
                    partial.unlink()
                raise
        logging.info('Backup created')
        return target

    def inspect(self, path, destination=None) -> dict:
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if len(names) != len(set(names)) or set(names)-{'manifest.json', *FILES} or 'manifest.json' not in names:
                    raise BusinessError('Unexpected or duplicate files in the backup package.')
                if any(i.file_size > 2_000_000_000 for i in z.infolist()) or z.getinfo('manifest.json').file_size > 10000:
                    raise BusinessError('Backup package is too large.')
                manifest = json.loads(z.read('manifest.json'))
                if manifest.get('format') != 'mobile-desk-backup' or manifest.get('version') != 1:
                    raise BusinessError('Unsupported backup format.')
                checksums = manifest.get('files')
                if not isinstance(checksums, dict) or 'mobile_desk.db' not in checksums or set(names) != {'manifest.json', *checksums}:
                    raise BusinessError('Backup manifest does not match the package.')
                with TemporaryDirectory(prefix='md-verify-') as tmp:
                    directory = Path(destination or tmp)
                    directory.mkdir(parents=True, exist_ok=True)
                    for name, checksum in checksums.items():
                        target = directory/name
                        with z.open(name) as src, target.open('wb') as out:
                            shutil.copyfileobj(src, out)
                        if digest(target) != checksum:
                            raise BusinessError('Backup checksum failed. Current data was not changed.')
                        check_database(target, name == 'mobile_catalogue.db')
                        if name=='mobile_desk.db':
                            reject_imported_history(target)
                return manifest
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeError):
            raise BusinessError('This is not a valid Mobile Desk backup.') from None

    def restore(self, path, *, username=None, password=None):
        security = SecurityService(self.root)
        if security.configured:
            security.authorize(username or '', password or '')
        self.inspect(path)
        safety = self.create()
        root = self.root
        recover_interrupted_restore(root)
        pending, old = root/'.restore-new', root/'.restore-old'
        if pending.exists() or old.exists():
            raise BusinessError('A previous restore folder needs review. No data was replaced.')
        pending.mkdir()
        try:
            self.inspect(path, pending)
            self.replace_staged(safety, action='RESTORE')
        except BaseException:
            self.abandon_staged()
            raise
        logging.info('Backup restored with safety backup')
        return safety

    def abandon_staged(self):
        root = self.root
        if (root/'.restore-pending').exists():
            recover_interrupted_restore(root)
        elif (root/'.restore-new').exists():
            (root/'.restore-new').rename(root/('.restore-unused-'+datetime.now().strftime('%Y%m%d%H%M%S%f')))

    def replace_staged(self, safety, *, action, reason=''):
        """Commit a validated staging directory; restore old files on interruption."""
        if action not in ('RESTORE', 'RESET'):
            raise ValueError('Unsupported data replacement')
        root = self.root
        pending, old, current, marker = root/'.restore-new', root/'.restore-old', root/'data', root/'.restore-pending'
        check_database(pending/'mobile_desk.db')
        if (pending/'mobile_catalogue.db').exists():
            check_database(pending/'mobile_catalogue.db', True)
        if old.exists() or marker.exists():
            raise BusinessError('A previous replacement needs recovery. No records were replaced.')
        try:
            with marker.open('wb') as handle:
                handle.write(b'Rollback to .restore-old if present.\n')
                handle.flush()
                os.fsync(handle.fileno())
            current.rename(old)
            pending.rename(current)
            check_database(current/'mobile_desk.db')
            if (current/'mobile_catalogue.db').exists():
                check_database(current/'mobile_catalogue.db', True)
            db = Database(current/'mobile_desk.db')
            with db.connect(write=True) as c:
                audit(c, action, 'backup', 'package', (reason+'; ' if reason else '')+f'Safety backup: {safety.name}')
            marker.unlink()
        except BaseException:
            self.abandon_staged()
            raise
        # The replacement is committed. A file-lock/archive error must not report
        # failure after the business records have already changed successfully.
        try:
            prefix = 'BeforeReset_' if action=='RESET' else 'BeforeRestore_'
            old.rename(root/'backups'/(prefix+datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
        except OSError:
            logging.exception('Replacement completed; original files retained in .restore-old')
