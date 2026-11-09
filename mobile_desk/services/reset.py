"""Owner-approved fresh start, with a verified snapshot before replacement."""
from pathlib import Path
from mobile_desk.database import Database
from mobile_desk.services.backup import BackupService, check_database, recover_interrupted_restore
from mobile_desk.services.security import SecurityService
from mobile_desk.values import BusinessError


class ResetService:
    def __init__(self, root, db):
        self.root, self.db = Path(root), db

    def preview(self):
        return {title: self.db.one('SELECT COUNT(*) n FROM '+table)['n'] for title, table in
                (('Sales', 'sales'), ('Purchase batches', 'purchase_batches'),
                 ('Shop products', 'products'), ('Customers / suppliers', 'parties'),
                 ('Payments', 'payments'),('Purchase returns / cancellations','purchase_returns'),
                 ('Confirmed purchase refunds','purchase_refunds'))}

    def reset(self, username, password, confirmation):
        SecurityService(self.root).authorize(username, password)
        if confirmation != 'RESET':
            raise BusinessError('Type RESET exactly to confirm clearing all business records.')
        recover_interrupted_restore(self.root)
        backups = BackupService(self.root)
        pending = self.root/'.restore-new'
        if pending.exists() or (self.root/'.restore-old').exists():
            raise BusinessError('A previous replacement folder needs review. No records were cleared.')
        # Do not proceed at all if snapshot creation or verification fails.
        safety = backups.create()
        pending.mkdir()
        try:
            backups.inspect(safety, pending)
            snapshot = Database(pending/'mobile_desk.db')
            with snapshot.connect() as c:
                settings = dict(c.execute('SELECT key,value FROM settings'))
                accounts = list(c.execute('SELECT name,account_type,active FROM accounts ORDER BY id'))
            # Work only on the staged copy, never delete live business rows.
            for suffix in ('', '-wal', '-shm'):
                path = Path(str(snapshot.path)+suffix)
                if path.exists():
                    path.unlink()
            fresh = Database(pending/'mobile_desk.db')
            with fresh.connect(write=True) as c:
                for key in ('shop_name','shop_phone','shop_address','invoice_prefix','backup_folder','setup_complete'):
                    if key in settings:
                        c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, settings[key]))
                for name, kind, active in accounts:
                    c.execute('INSERT INTO accounts(name,account_type,opening_balance,opening_date,active) VALUES(?,?,0,?,?)',
                              (name,kind,'1900-01-01',active))
                if not accounts:
                    c.execute("INSERT INTO accounts(name,account_type,opening_date) VALUES('Cash','CASH','1900-01-01')")
            check_database(fresh.path)
            backups.replace_staged(safety, action='RESET', reason='Authorized by '+username)
        except BaseException:
            backups.abandon_staged()
            raise
        return safety
