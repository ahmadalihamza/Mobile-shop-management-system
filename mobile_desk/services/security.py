"""Local owner authorization, independent of replaceable business backups."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from mobile_desk.values import BusinessError, text


class SecurityService:
    def __init__(self, root):
        self.path = Path(root)/'owner-security.json'

    @property
    def configured(self):
        return self.path.exists()

    def _read(self):
        if not self.configured:
            raise BusinessError('The owner must set a password in Settings → Owner & Reset first.')
        try:
            if self.path.stat().st_size > 10000:
                raise ValueError
            record = json.loads(self.path.read_text(encoding='utf-8'))
            if (record['version'] != 1 or record['algorithm'] != 'scrypt-32768-8-1'
                    or not isinstance(record['username'], str) or not record['username']
                    or len(bytes.fromhex(record['salt'])) != 16
                    or len(bytes.fromhex(record['hash'])) != 32
                    or not isinstance(record['failed_attempts'], int)
                    or not 0 <= record['failed_attempts'] < 5
                    or not isinstance(record['locked_until'], (int, float))):
                raise ValueError
            return record
        except (ValueError, KeyError, TypeError, OSError):
            raise BusinessError('Owner security could not be read. Reset and restore are blocked. Keep the security file intact and contact support.') from None

    @property
    def username(self):
        return self._read()['username'] if self.configured else ''

    @staticmethod
    def _hash(password, salt):
        if not isinstance(password, str) or len(password.encode('utf-8')) > 1024:
            raise BusinessError('Password is too long.')
        return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=32768, r=8, p=1,
                              dklen=32, maxmem=128*1024*1024).hex()

    def _write(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name+'.'+secrets.token_hex(8)+'.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                json.dump(record, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def set_password(self, username, password, confirmation, *, current_password=None):
        username = text(username, 'Owner username', True, 80)
        if not isinstance(password, str) or len(password) < 8 or not password.strip():
            raise BusinessError('Use a password of at least 8 characters.')
        if password != confirmation:
            raise BusinessError('The new passwords do not match.')
        if self.configured:
            self.authorize(username, current_password or '')
        salt = secrets.token_bytes(16)
        record = dict(version=1, username=username, algorithm='scrypt-32768-8-1',
                      salt=salt.hex(), hash=self._hash(password, salt), failed_attempts=0, locked_until=0)
        self._write(record)

    def authorize(self, username, password):
        record = self._read()
        if time.time() < record['locked_until']:
            raise BusinessError('Too many incorrect attempts. Wait one minute before trying again.')
        candidate = self._hash(password, bytes.fromhex(record['salt']))
        valid_password = hmac.compare_digest(candidate, record['hash'])
        valid_username = hmac.compare_digest(str(username).strip().encode('utf-8'), record['username'].encode('utf-8'))
        if not (valid_username and valid_password):
            record['failed_attempts'] += 1
            if record['failed_attempts'] >= 5:
                record['failed_attempts'] = 0
                record['locked_until'] = time.time()+60
            self._write(record)
            raise BusinessError('Incorrect owner username or password.')
        if record['failed_attempts'] or record['locked_until']:
            record.update(failed_attempts=0, locked_until=0)
            self._write(record)
