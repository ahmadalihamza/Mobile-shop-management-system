import hashlib
import json
import sqlite3
from mobile_desk.values import BusinessError, text, timestamp


def require(c, table: str, identity: int, role=None):
    if table not in {'products', 'parties', 'accounts', 'sales', 'purchase_batches', 'sale_items', 'returns', 'purchase_items'}:
        raise ValueError('Unsupported entity')
    r = c.execute(f'SELECT * FROM {table} WHERE id=?', (identity,)).fetchone()
    if not r or ('active' in r.keys() and not r['active']):
        raise BusinessError(f'The selected {table.replace("_", " ")} record is unavailable.')
    if role and not r[role]:
        raise BusinessError('Choose a party with the required customer/supplier role.')
    return r


def remember(c, key, payload, result_id=None):
    if not key:
        return None
    key = text(key, 'Operation key', True, 100)
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    row = c.execute('SELECT * FROM operation_keys WHERE key=?', (key,)).fetchone()
    if row:
        if row['fingerprint'] != fingerprint:
            raise BusinessError('This operation was already submitted with different details. Open a new form.')
        return row['result_id']
    if result_id is not None:
        c.execute('INSERT INTO operation_keys VALUES(?,?,?)', (key, fingerprint, result_id))
    return None


def payment(c, day, account_id, amount, purpose, *, party_id=None, sale_id=None, purchase_id=None, return_id=None, reference='', notes='', ledger_role=None) -> int:
    account = require(c, 'accounts', account_id)
    if day < account['opening_date']:
        raise BusinessError('The payment date is before this account’s opening date.')
    name = require(c, 'parties', party_id)['name'] if party_id else ''
    direction = 'OUT' if purpose in ('RETURN_REFUND', 'PURCHASE_PAYMENT') else 'IN'
    role = ledger_role or ('SUPPLIER' if purpose=='PURCHASE_PAYMENT' else 'CUSTOMER')
    return c.execute('INSERT INTO payments(transaction_date,party_id,party_snapshot,sale_id,purchase_batch_id,return_id,account_id,direction,purpose,amount,reference,notes,created_at,ledger_role) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (day, party_id, name, sale_id, purchase_id, return_id, account_id, direction, purpose, amount, text(reference), text(notes, 'Notes', limit=2000), timestamp(),role)).lastrowid


def check_line_total(value: int) -> None:
    if value > 1000000000000000:
        raise BusinessError('The transaction amount is too large.')
