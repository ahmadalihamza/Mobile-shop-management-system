"""Short-lived SQLite connections; migrations and writes are atomic."""
from contextlib import contextmanager, closing
from pathlib import Path
import logging
import sqlite3
from mobile_desk.values import BusinessError, timestamp

APPLICATION_ID = 1296319025
SCHEMA_VERSION = 5

SCHEMA = '''
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO settings VALUES ('shop_name','Mobile Desk'),('shop_phone',''),('shop_address',''),('invoice_prefix','S-'),('next_invoice','1'),('setup_complete','0');
CREATE TABLE parties(id INTEGER PRIMARY KEY, name TEXT NOT NULL, normalized_name TEXT NOT NULL, is_customer INTEGER NOT NULL DEFAULT 1 CHECK(is_customer IN(0,1)), is_supplier INTEGER NOT NULL DEFAULT 0 CHECK(is_supplier IN(0,1)), phone TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, CHECK(is_customer=1 OR is_supplier=1));
CREATE INDEX party_search ON parties(normalized_name);
CREATE TABLE products(id INTEGER PRIMARY KEY, catalogue_model_id TEXT, brand TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', ram TEXT NOT NULL DEFAULT '', storage TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT '', variant TEXT NOT NULL DEFAULT '', custom_name TEXT NOT NULL, normalized_search_name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX product_search ON products(normalized_search_name);
CREATE TABLE product_aliases(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), alias TEXT NOT NULL, normalized_alias TEXT NOT NULL, UNIQUE(product_id,normalized_alias));
CREATE INDEX alias_search ON product_aliases(normalized_alias);
CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, account_type TEXT NOT NULL CHECK(account_type IN('CASH','BANK')), opening_balance INTEGER NOT NULL DEFAULT 0, opening_date TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE purchase_batches(id INTEGER PRIMARY KEY, reference TEXT NOT NULL UNIQUE, transaction_date TEXT NOT NULL, purchase_type TEXT NOT NULL CHECK(purchase_type IN('LOCAL','CHINA_IMPORT','OPENING')), supplier_id INTEGER REFERENCES parties(id), supplier_snapshot TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency IN('PKR','CNY')), default_exchange_rate TEXT, default_additional_cost INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL CHECK(total>=0), notes TEXT NOT NULL, legacy_reference TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'POSTED' CHECK(status IN('POSTED','VOID')), created_at TEXT NOT NULL, voided_at TEXT, void_reason TEXT);
CREATE INDEX purchase_date ON purchase_batches(transaction_date,status);
CREATE TABLE purchase_items(id INTEGER PRIMARY KEY, purchase_batch_id INTEGER NOT NULL REFERENCES purchase_batches(id), product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL CHECK(quantity>0), original_currency TEXT NOT NULL, foreign_unit_price TEXT, exchange_rate_snapshot TEXT, pkr_unit_purchase_cost INTEGER NOT NULL CHECK(pkr_unit_purchase_cost>=0), additional_cost_per_unit INTEGER NOT NULL CHECK(additional_cost_per_unit>=0), landed_unit_cost INTEGER NOT NULL CHECK(landed_unit_cost>=0), line_total_cost INTEGER NOT NULL CHECK(line_total_cost=quantity*landed_unit_cost), product_description_snapshot TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX lots_product ON purchase_items(product_id,purchase_batch_id);
CREATE TABLE sales(id INTEGER PRIMARY KEY, invoice_number TEXT NOT NULL UNIQUE, transaction_date TEXT NOT NULL, customer_id INTEGER REFERENCES parties(id), customer_snapshot TEXT NOT NULL, subtotal INTEGER NOT NULL CHECK(subtotal>=0), total INTEGER NOT NULL CHECK(total>=0), notes TEXT NOT NULL, legacy_reference TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'POSTED' CHECK(status IN('POSTED','VOID')), created_at TEXT NOT NULL, voided_at TEXT, void_reason TEXT);
CREATE INDEX sales_date ON sales(transaction_date,status);
CREATE INDEX sales_party ON sales(customer_id,transaction_date);
CREATE TABLE sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id), product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL CHECK(quantity>0), selling_rate INTEGER NOT NULL CHECK(selling_rate>=0), line_total INTEGER NOT NULL CHECK(line_total=quantity*selling_rate), cogs INTEGER NOT NULL CHECK(cogs>=0), gross_profit INTEGER NOT NULL, product_description_snapshot TEXT NOT NULL);
CREATE INDEX sale_items_product ON sale_items(product_id,sale_id);
CREATE TABLE stock_allocations(id INTEGER PRIMARY KEY, sale_item_id INTEGER NOT NULL REFERENCES sale_items(id), purchase_item_id INTEGER NOT NULL REFERENCES purchase_items(id), quantity INTEGER NOT NULL CHECK(quantity>0), unit_cost INTEGER NOT NULL CHECK(unit_cost>=0));
CREATE INDEX allocation_lot ON stock_allocations(purchase_item_id);
CREATE INDEX allocation_sale ON stock_allocations(sale_item_id);
CREATE TABLE returns(id INTEGER PRIMARY KEY, transaction_date TEXT NOT NULL, customer_id INTEGER REFERENCES parties(id), customer_snapshot TEXT NOT NULL, original_sale_id INTEGER NOT NULL REFERENCES sales(id), total INTEGER NOT NULL, cogs_reversed INTEGER NOT NULL, notes TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'POSTED' CHECK(status IN('POSTED','VOID')), created_at TEXT NOT NULL, voided_at TEXT, void_reason TEXT);
CREATE INDEX returns_date ON returns(transaction_date,status);
CREATE TABLE return_items(id INTEGER PRIMARY KEY, return_id INTEGER NOT NULL REFERENCES returns(id), product_id INTEGER NOT NULL REFERENCES products(id), original_sale_item_id INTEGER NOT NULL REFERENCES sale_items(id), quantity INTEGER NOT NULL CHECK(quantity>0), return_rate INTEGER NOT NULL CHECK(return_rate>=0), line_total INTEGER NOT NULL, cogs_reversed INTEGER NOT NULL, product_description_snapshot TEXT NOT NULL);
CREATE INDEX return_sale_item ON return_items(original_sale_item_id);
CREATE TABLE return_allocations(id INTEGER PRIMARY KEY, return_item_id INTEGER NOT NULL REFERENCES return_items(id), stock_allocation_id INTEGER NOT NULL REFERENCES stock_allocations(id), quantity INTEGER NOT NULL CHECK(quantity>0), unit_cost INTEGER NOT NULL);
CREATE INDEX return_allocation_original ON return_allocations(stock_allocation_id);
CREATE TABLE stock_movements(id INTEGER PRIMARY KEY, purchase_item_id INTEGER NOT NULL REFERENCES purchase_items(id), transaction_date TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity!=0), kind TEXT NOT NULL, reference_id INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX stock_lot ON stock_movements(purchase_item_id,transaction_date);
CREATE TABLE payments(id INTEGER PRIMARY KEY, transaction_date TEXT NOT NULL, party_id INTEGER REFERENCES parties(id), party_snapshot TEXT NOT NULL DEFAULT '', sale_id INTEGER REFERENCES sales(id), purchase_batch_id INTEGER REFERENCES purchase_batches(id), return_id INTEGER REFERENCES returns(id), account_id INTEGER NOT NULL REFERENCES accounts(id), direction TEXT NOT NULL CHECK(direction IN('IN','OUT')), purpose TEXT NOT NULL CHECK(purpose IN('SALE_RECEIPT','CUSTOMER_PAYMENT','RETURN_REFUND','PURCHASE_PAYMENT')), amount INTEGER NOT NULL CHECK(amount>0), reference TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, voided_at TEXT, void_reason TEXT);
CREATE INDEX payment_party ON payments(party_id,transaction_date);
CREATE INDEX payment_sale ON payments(sale_id,purpose);
CREATE INDEX payment_account ON payments(account_id,transaction_date);
CREATE TABLE party_adjustments(id INTEGER PRIMARY KEY, party_id INTEGER NOT NULL REFERENCES parties(id), transaction_date TEXT NOT NULL, adjustment_type TEXT NOT NULL CHECK(adjustment_type IN('OPENING_BALANCE','DISCOUNT','MANUAL_CREDIT','MANUAL_DEBIT')), amount INTEGER NOT NULL CHECK(amount!=0), reason TEXT NOT NULL, created_at TEXT NOT NULL, voided_at TEXT, void_reason TEXT);
CREATE INDEX adjustments_party ON party_adjustments(party_id,transaction_date);
CREATE TABLE expenses(id INTEGER PRIMARY KEY, transaction_date TEXT NOT NULL, description TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), account_id INTEGER NOT NULL REFERENCES accounts(id), category TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, voided_at TEXT, void_reason TEXT);
CREATE INDEX expenses_date ON expenses(transaction_date);
CREATE TABLE account_transfers(id INTEGER PRIMARY KEY, transaction_date TEXT NOT NULL, from_account INTEGER NOT NULL REFERENCES accounts(id), to_account INTEGER NOT NULL REFERENCES accounts(id), amount INTEGER NOT NULL CHECK(amount>0), reference TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL, voided_at TEXT, void_reason TEXT, CHECK(from_account!=to_account));
CREATE TABLE exchange_rate_history(id INTEGER PRIMARY KEY, transaction_date TEXT NOT NULL, from_currency TEXT NOT NULL DEFAULT 'CNY', to_currency TEXT NOT NULL DEFAULT 'PKR', rate TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '');
CREATE TABLE audit_log(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '');
CREATE TABLE operation_keys(key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result_id INTEGER NOT NULL);
CREATE TABLE import_sources(source_key TEXT PRIMARY KEY, source_file TEXT NOT NULL, source_sheet TEXT NOT NULL, source_row INTEGER NOT NULL, entity TEXT NOT NULL, entity_id INTEGER NOT NULL, imported_at TEXT NOT NULL);
CREATE VIEW lot_stock AS SELECT pi.*,b.transaction_date,b.reference,b.status,COALESCE((SELECT SUM(m.quantity) FROM stock_movements m WHERE m.purchase_item_id=pi.id),0) AS remaining_quantity FROM purchase_items pi JOIN purchase_batches b ON b.id=pi.purchase_batch_id;
CREATE VIEW party_ledger AS
 SELECT customer_id AS party_id,transaction_date,invoice_number AS reference,'Sale' AS description,total AS amount,'SALE' AS kind,id AS source_id,created_at FROM sales WHERE status='POSTED' AND customer_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,COALESCE(NULLIF(reference,''),'PAY-'||id),purpose,CASE WHEN direction='IN' THEN -amount ELSE amount END,'PAYMENT',id,created_at FROM payments WHERE voided_at IS NULL AND party_id IS NOT NULL AND purpose IN('SALE_RECEIPT','CUSTOMER_PAYMENT','RETURN_REFUND')
 UNION ALL SELECT customer_id,transaction_date,'R-'||id,'Sale return',-total,'RETURN',id,created_at FROM returns WHERE status='POSTED' AND customer_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,'ADJ-'||id,reason,amount,'ADJUSTMENT',id,created_at FROM party_adjustments WHERE voided_at IS NULL;
CREATE VIEW money_ledger AS
 SELECT id AS account_id,opening_date AS transaction_date,'OPENING' AS reference,'Opening balance' AS description,opening_balance AS amount,'OPENING' AS kind,id AS source_id,'' AS created_at FROM accounts
 UNION ALL SELECT account_id,transaction_date,COALESCE(NULLIF(reference,''),'PAY-'||id),purpose,CASE WHEN direction='IN' THEN amount ELSE -amount END,'PAYMENT',id,created_at FROM payments WHERE voided_at IS NULL
 UNION ALL SELECT account_id,transaction_date,'EXP-'||id,description,-amount,'EXPENSE',id,created_at FROM expenses WHERE voided_at IS NULL
 UNION ALL SELECT from_account,transaction_date,'TR-'||id,'Transfer out',-amount,'TRANSFER',id,created_at FROM account_transfers WHERE voided_at IS NULL
 UNION ALL SELECT to_account,transaction_date,'TR-'||id,'Transfer in',amount,'TRANSFER',id,created_at FROM account_transfers WHERE voided_at IS NULL;
'''

MIGRATIONS = {
    1: SCHEMA,
    2: '''
CREATE INDEX returns_original_sale ON returns(original_sale_id,status);
CREATE INDEX purchase_supplier ON purchase_batches(supplier_id,transaction_date);
CREATE INDEX stock_date ON stock_movements(transaction_date,purchase_item_id);
CREATE INDEX audit_date ON audit_log(created_at);
CREATE INDEX sale_items_invoice ON sale_items(sale_id);
CREATE INDEX purchase_items_batch ON purchase_items(purchase_batch_id);
CREATE INDEX return_items_header ON return_items(return_id);
CREATE TABLE schema_history(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL);
INSERT INTO schema_history VALUES(1,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
INSERT INTO schema_history VALUES(2,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
CREATE TRIGGER preserve_lot_cost BEFORE UPDATE ON purchase_items BEGIN SELECT RAISE(ABORT,'Finalized purchase item snapshots cannot be edited'); END;
CREATE TRIGGER preserve_lot_history BEFORE DELETE ON purchase_items BEGIN SELECT RAISE(ABORT,'Finalized purchase items cannot be deleted'); END;
CREATE TRIGGER preserve_sale_history BEFORE DELETE ON sales BEGIN SELECT RAISE(ABORT,'Posted invoices cannot be deleted'); END;
CREATE TRIGGER preserve_stock_history BEFORE DELETE ON stock_movements BEGIN SELECT RAISE(ABORT,'Stock history cannot be deleted'); END;
CREATE TRIGGER preserve_stock_values BEFORE UPDATE ON stock_movements BEGIN SELECT RAISE(ABORT,'Stock history cannot be edited'); END;
''',
}

# SQLite cannot drop NOT NULL in place. Rebuild only the two return tables,
# retaining their identities and every referencing allocation/payment.
def historical_schema():
    statements = ['DROP VIEW party_ledger;']
    for table in ('returns', 'return_items'):
        definition = next(s for s in SCHEMA.split(';') if s.strip().startswith('CREATE TABLE '+table+'('))
        definition = definition.replace('CREATE TABLE '+table+'(', 'CREATE TABLE '+table+'_new(')
        definition = definition.replace('original_sale_id INTEGER NOT NULL', 'original_sale_id INTEGER')
        definition = definition.replace('original_sale_item_id INTEGER NOT NULL', 'original_sale_item_id INTEGER')
        statements.extend((definition+';', f'INSERT INTO {table}_new SELECT * FROM {table};',
                           f'DROP TABLE {table};', f'ALTER TABLE {table}_new RENAME TO {table};'))
    statements.extend(('CREATE INDEX returns_date ON returns(transaction_date,status);',
                       'CREATE INDEX returns_original_sale ON returns(original_sale_id,status);',
                       'CREATE INDEX return_sale_item ON return_items(original_sale_item_id);',
                       'CREATE INDEX return_items_header ON return_items(return_id);'))
    statements.append(next(s for s in SCHEMA.split(';') if s.strip().startswith('CREATE VIEW party_ledger'))+';')
    for table in ('products','parties','purchase_batches','purchase_items','sales','sale_items',
                  'returns','return_items','payments','party_adjustments','expenses','account_transfers'):
        statements.append(f"ALTER TABLE {table} ADD COLUMN data_origin TEXT NOT NULL DEFAULT 'APPLICATION';")
    for table in ('sales','purchase_batches','returns','payments','party_adjustments','expenses','account_transfers'):
        statements.append(f"ALTER TABLE {table} ADD COLUMN date_basis TEXT NOT NULL DEFAULT 'EXACT';")
        statements.append(f"ALTER TABLE {table} ADD COLUMN date_label TEXT NOT NULL DEFAULT '';")
    statements.extend(('ALTER TABLE sale_items ADD COLUMN cogs_known INTEGER NOT NULL DEFAULT 1 CHECK(cogs_known IN(0,1));',
                       "ALTER TABLE sale_items ADD COLUMN reporting_model TEXT NOT NULL DEFAULT '';",
                       "ALTER TABLE parties ADD COLUMN balance_basis TEXT NOT NULL DEFAULT 'LEDGER';",
                       'ALTER TABLE return_items ADD COLUMN cogs_known INTEGER NOT NULL DEFAULT 1 CHECK(cogs_known IN(0,1));',
                       'ALTER TABLE return_items ADD COLUMN stock_lot_id INTEGER REFERENCES purchase_items(id);',
                       "ALTER TABLE party_adjustments ADD COLUMN legacy_reference TEXT NOT NULL DEFAULT '';",
                       "ALTER TABLE sales ADD COLUMN settlement_status TEXT NOT NULL DEFAULT 'KNOWN';",
                       "ALTER TABLE purchase_items ADD COLUMN inventory_status TEXT NOT NULL DEFAULT 'AVAILABLE';",
                       'ALTER TABLE purchase_items ADD COLUMN source_remaining_quantity INTEGER;',
                       'ALTER TABLE purchase_items ADD COLUMN total_foreign_cost TEXT;',
                       '''CREATE TABLE migration_runs(id INTEGER PRIMARY KEY,started_at TEXT NOT NULL,ended_at TEXT,
                          migration_version TEXT NOT NULL,source_manifest TEXT NOT NULL,plan_checksum TEXT NOT NULL,
                          imported_counts TEXT NOT NULL DEFAULT '{}',warnings TEXT NOT NULL DEFAULT '[]',
                          status TEXT NOT NULL);''',
                       '''CREATE TABLE historical_evidence(source_key TEXT PRIMARY KEY,run_id INTEGER NOT NULL REFERENCES migration_runs(id),
                          workbook TEXT NOT NULL,workbook_checksum TEXT NOT NULL,sheet TEXT NOT NULL,source_range TEXT NOT NULL,
                          source_reference TEXT NOT NULL,record_checksum TEXT NOT NULL,entity TEXT NOT NULL,entity_id INTEGER NOT NULL,
                          source_payload TEXT NOT NULL,decision TEXT NOT NULL);''',
                       'CREATE INDEX evidence_entity ON historical_evidence(entity,entity_id);',
                       '''CREATE TABLE inventory_confirmations(id INTEGER PRIMARY KEY,purchase_item_id INTEGER NOT NULL REFERENCES purchase_items(id),
                          transaction_date TEXT NOT NULL,counted_quantity INTEGER NOT NULL CHECK(counted_quantity>=0),
                          previous_quantity INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);''',
                       '''CREATE TABLE migration_issues(id INTEGER PRIMARY KEY,run_id INTEGER NOT NULL REFERENCES migration_runs(id),
                          source_key TEXT NOT NULL,workbook TEXT NOT NULL,sheet TEXT NOT NULL,source_range TEXT NOT NULL,
                          severity TEXT NOT NULL,reason TEXT NOT NULL,source_payload TEXT NOT NULL);''',
                       "INSERT INTO schema_history VALUES(3,strftime('%Y-%m-%dT%H:%M:%fZ','now'));"))
    statements.extend(('DROP VIEW party_ledger;', '''CREATE VIEW party_ledger AS
        SELECT customer_id party_id,transaction_date,COALESCE(NULLIF(legacy_reference,''),invoice_number) reference,
            'Sale' description,total amount,'SALE' kind,id source_id,created_at,date_basis,date_label FROM sales WHERE status='POSTED' AND customer_id IS NOT NULL
        UNION ALL SELECT party_id,transaction_date,COALESCE(NULLIF(reference,''),'PAY-'||id),purpose,
            CASE WHEN direction='IN' THEN -amount ELSE amount END,'PAYMENT',id,created_at,date_basis,date_label FROM payments
            WHERE voided_at IS NULL AND party_id IS NOT NULL AND purpose IN('SALE_RECEIPT','CUSTOMER_PAYMENT','RETURN_REFUND')
        UNION ALL SELECT customer_id,transaction_date,'R-'||id,'Sale return',-total,'RETURN',id,created_at,date_basis,date_label FROM returns WHERE status='POSTED' AND customer_id IS NOT NULL
        UNION ALL SELECT party_id,transaction_date,COALESCE(NULLIF(legacy_reference,''),'ADJ-'||id),reason,amount,'ADJUSTMENT',id,created_at,date_basis,date_label FROM party_adjustments WHERE voided_at IS NULL;'''))
    return '\n'.join(statements)


MIGRATIONS[3] = historical_schema()

MIGRATIONS[4] = '''
ALTER TABLE purchase_batches ADD COLUMN supplier_total INTEGER NOT NULL DEFAULT 0 CHECK(supplier_total>=0);
ALTER TABLE purchase_batches ADD COLUMN carry_billed_to_supplier INTEGER NOT NULL DEFAULT 0;
UPDATE purchase_batches SET supplier_total=(SELECT COALESCE(SUM(quantity*pkr_unit_purchase_cost),0) FROM purchase_items WHERE purchase_batch_id=purchase_batches.id) WHERE purchase_type!='OPENING';
ALTER TABLE payments ADD COLUMN ledger_role TEXT NOT NULL DEFAULT 'CUSTOMER' CHECK(ledger_role IN('CUSTOMER','SUPPLIER','NONE'));
UPDATE payments SET ledger_role='SUPPLIER' WHERE purpose='PURCHASE_PAYMENT';
ALTER TABLE party_adjustments ADD COLUMN ledger_role TEXT NOT NULL DEFAULT 'CUSTOMER' CHECK(ledger_role IN('CUSTOMER','SUPPLIER'));
DROP VIEW party_ledger;
CREATE VIEW party_ledger AS
 SELECT customer_id party_id,transaction_date,invoice_number reference,'Sale' description,total amount,'SALE' kind,id source_id,created_at,date_basis,date_label FROM sales WHERE status='POSTED' AND customer_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,COALESCE(NULLIF(reference,''),'PAY-'||id),purpose,CASE WHEN direction='IN' THEN -amount ELSE amount END,'PAYMENT',id,created_at,date_basis,date_label FROM payments WHERE voided_at IS NULL AND party_id IS NOT NULL AND ledger_role='CUSTOMER'
 UNION ALL SELECT customer_id,transaction_date,'R-'||id,'Sale return',-total,'RETURN',id,created_at,date_basis,date_label FROM returns WHERE status='POSTED' AND customer_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,'ADJ-'||id,reason,amount,'ADJUSTMENT',id,created_at,date_basis,date_label FROM party_adjustments WHERE voided_at IS NULL AND ledger_role='CUSTOMER';
CREATE VIEW supplier_ledger AS
 SELECT supplier_id party_id,transaction_date,reference,'Purchase' description,supplier_total amount,'PURCHASE' kind,id source_id,created_at,date_basis,date_label FROM purchase_batches WHERE status='POSTED' AND purchase_type!='OPENING' AND supplier_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,COALESCE(NULLIF(reference,''),'PAY-'||id),'Supplier payment',-amount,'PAYMENT',id,created_at,date_basis,date_label FROM payments WHERE voided_at IS NULL AND ledger_role='SUPPLIER' AND party_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,'ADJ-'||id,reason,amount,'ADJUSTMENT',id,created_at,date_basis,date_label FROM party_adjustments WHERE voided_at IS NULL AND ledger_role='SUPPLIER';
CREATE TABLE entry_drafts(kind TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at TEXT NOT NULL);
INSERT INTO schema_history VALUES(4,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
'''


MIGRATIONS[5] = '''
ALTER TABLE purchase_batches ADD COLUMN shipment_status TEXT NOT NULL DEFAULT 'RECEIVED' CHECK(shipment_status IN('IN_TRANSIT','RECEIVED','CANCELLED','RETURNED'));
ALTER TABLE purchase_batches ADD COLUMN received_date TEXT;
UPDATE purchase_batches SET received_date=transaction_date;
ALTER TABLE purchase_batches ADD COLUMN default_carry_currency TEXT NOT NULL DEFAULT 'PKR' CHECK(default_carry_currency IN('PKR','CNY'));
ALTER TABLE purchase_items ADD COLUMN carry_currency TEXT NOT NULL DEFAULT 'PKR' CHECK(carry_currency IN('PKR','CNY'));
ALTER TABLE purchase_items ADD COLUMN foreign_carry_per_unit TEXT;
CREATE TABLE purchase_stacks(id INTEGER PRIMARY KEY,purchase_batch_id INTEGER NOT NULL REFERENCES purchase_batches(id),product_id INTEGER NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL CHECK(quantity>0),carry_basis TEXT NOT NULL CHECK(carry_basis IN('PER_UNIT','STACK_TOTAL')),carry_currency TEXT NOT NULL CHECK(carry_currency IN('PKR','CNY')),carry_input TEXT NOT NULL,total_carry_cost INTEGER NOT NULL CHECK(total_carry_cost>=0),line_total_cost INTEGER NOT NULL CHECK(line_total_cost>=0),created_at TEXT NOT NULL);
ALTER TABLE purchase_items ADD COLUMN stack_id INTEGER REFERENCES purchase_stacks(id);
CREATE INDEX purchase_stack_batch ON purchase_stacks(purchase_batch_id);
CREATE TRIGGER preserve_purchase_stack BEFORE UPDATE ON purchase_stacks BEGIN SELECT RAISE(ABORT,'Original stack charges cannot be edited'); END;
CREATE TRIGGER retain_purchase_stack BEFORE DELETE ON purchase_stacks BEGIN SELECT RAISE(ABORT,'Original stack charges cannot be deleted'); END;
CREATE TABLE purchase_returns(id INTEGER PRIMARY KEY,purchase_batch_id INTEGER NOT NULL REFERENCES purchase_batches(id),transaction_date TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('RETURN','CANCELLATION')),reason TEXT NOT NULL,owner_username TEXT NOT NULL,supplier_credit INTEGER NOT NULL CHECK(supplier_credit>=0),stock_cost INTEGER NOT NULL CHECK(stock_cost>=0),created_at TEXT NOT NULL);
CREATE INDEX purchase_returns_batch ON purchase_returns(purchase_batch_id,transaction_date);
CREATE TABLE purchase_return_items(id INTEGER PRIMARY KEY,return_id INTEGER NOT NULL REFERENCES purchase_returns(id),purchase_item_id INTEGER NOT NULL REFERENCES purchase_items(id),quantity INTEGER NOT NULL CHECK(quantity>0),stock_cost INTEGER NOT NULL CHECK(stock_cost>=0),supplier_credit INTEGER NOT NULL CHECK(supplier_credit>=0),UNIQUE(return_id,purchase_item_id));
CREATE INDEX purchase_return_item_lot ON purchase_return_items(purchase_item_id);
CREATE TABLE purchase_refunds(id INTEGER PRIMARY KEY,purchase_return_id INTEGER NOT NULL REFERENCES purchase_returns(id),transaction_date TEXT NOT NULL,account_id INTEGER NOT NULL REFERENCES accounts(id),amount INTEGER NOT NULL CHECK(amount>0),payer_kind TEXT NOT NULL CHECK(payer_kind IN('SUPPLIER','CARRIER')),owner_username TEXT NOT NULL,reference TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
CREATE INDEX purchase_refunds_return ON purchase_refunds(purchase_return_id,transaction_date);
CREATE TRIGGER preserve_purchase_returns BEFORE UPDATE ON purchase_returns BEGIN SELECT RAISE(ABORT,'Purchase return history cannot be edited'); END;
CREATE TRIGGER preserve_purchase_return_items BEFORE UPDATE ON purchase_return_items BEGIN SELECT RAISE(ABORT,'Purchase return quantities cannot be edited'); END;
CREATE TRIGGER preserve_purchase_refunds BEFORE UPDATE ON purchase_refunds BEGIN SELECT RAISE(ABORT,'Confirmed purchase refunds cannot be edited'); END;
CREATE TRIGGER retain_purchase_returns BEFORE DELETE ON purchase_returns BEGIN SELECT RAISE(ABORT,'Purchase return history cannot be deleted'); END;
CREATE TRIGGER retain_purchase_return_items BEFORE DELETE ON purchase_return_items BEGIN SELECT RAISE(ABORT,'Purchase return quantities cannot be deleted'); END;
CREATE TRIGGER retain_purchase_refunds BEFORE DELETE ON purchase_refunds BEGIN SELECT RAISE(ABORT,'Confirmed purchase refunds cannot be deleted'); END;
DROP VIEW supplier_ledger;
CREATE VIEW supplier_ledger AS
 SELECT supplier_id party_id,transaction_date,reference,'Purchase' description,supplier_total amount,'PURCHASE' kind,id source_id,created_at,date_basis,date_label FROM purchase_batches WHERE status='POSTED' AND purchase_type!='OPENING' AND supplier_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,COALESCE(NULLIF(reference,''),'PAY-'||id),'Supplier payment',-amount,'PAYMENT',id,created_at,date_basis,date_label FROM payments WHERE voided_at IS NULL AND ledger_role='SUPPLIER' AND party_id IS NOT NULL
 UNION ALL SELECT party_id,transaction_date,'ADJ-'||id,reason,amount,'ADJUSTMENT',id,created_at,date_basis,date_label FROM party_adjustments WHERE voided_at IS NULL AND ledger_role='SUPPLIER'
 UNION ALL SELECT b.supplier_id,r.transaction_date,'PR-'||r.id,'Purchase return / cancellation',-r.supplier_credit,'PURCHASE_RETURN',r.id,r.created_at,'EXACT','' FROM purchase_returns r JOIN purchase_batches b ON b.id=r.purchase_batch_id WHERE b.supplier_id IS NOT NULL
 UNION ALL SELECT b.supplier_id,f.transaction_date,COALESCE(NULLIF(f.reference,''),'PREF-'||f.id),'Supplier refund received',f.amount,'PURCHASE_REFUND',f.id,f.created_at,'EXACT','' FROM purchase_refunds f JOIN purchase_returns r ON r.id=f.purchase_return_id JOIN purchase_batches b ON b.id=r.purchase_batch_id WHERE f.payer_kind='SUPPLIER' AND b.supplier_id IS NOT NULL;
DROP VIEW money_ledger;
CREATE VIEW money_ledger AS
 SELECT id account_id,opening_date transaction_date,'OPENING' reference,'Opening balance' description,opening_balance amount,'OPENING' kind,id source_id,'' created_at FROM accounts
 UNION ALL SELECT account_id,transaction_date,COALESCE(NULLIF(reference,''),'PAY-'||id),purpose,CASE WHEN direction='IN' THEN amount ELSE -amount END,'PAYMENT',id,created_at FROM payments WHERE voided_at IS NULL
 UNION ALL SELECT account_id,transaction_date,'EXP-'||id,description,-amount,'EXPENSE',id,created_at FROM expenses WHERE voided_at IS NULL
 UNION ALL SELECT from_account,transaction_date,'TR-'||id,'Transfer out',-amount,'TRANSFER',id,created_at FROM account_transfers WHERE voided_at IS NULL
 UNION ALL SELECT to_account,transaction_date,'TR-'||id,'Transfer in',amount,'TRANSFER',id,created_at FROM account_transfers WHERE voided_at IS NULL
 UNION ALL SELECT account_id,transaction_date,COALESCE(NULLIF(reference,''),'PREF-'||id),CASE WHEN payer_kind='SUPPLIER' THEN 'Supplier refund received' ELSE 'Carry refund received' END,amount,'PURCHASE_REFUND',id,created_at FROM purchase_refunds;
INSERT INTO schema_history VALUES(5,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
'''


def audit(c, action: str, entity: str, identity, reason='') -> None:
    c.execute('INSERT INTO audit_log(created_at,action,entity,entity_id,reason) VALUES(?,?,?,?,?)', (timestamp(), action, entity, str(identity), reason))


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self, write=False):
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA busy_timeout=15000')
        c.execute('PRAGMA synchronous=FULL')
        try:
            if write:
                c.execute('BEGIN IMMEDIATE')
            yield c
            if write:
                c.commit()
        except BaseException:
            if write:
                c.rollback()
            raise
        finally:
            c.close()

    def initialize(self):
        with self.connect() as c:
            version = c.execute('PRAGMA user_version').fetchone()[0]
            app_id = c.execute('PRAGMA application_id').fetchone()[0]
            tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if tables and app_id != APPLICATION_ID:
                raise BusinessError('This is not a compatible Mobile Desk business database. Keep the existing file and choose a different data folder.')
            if version > SCHEMA_VERSION:
                raise BusinessError('This database needs a newer version of Mobile Desk.')
            if c.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise BusinessError('The business database failed its integrity check. Restore a verified backup.')
            if version < SCHEMA_VERSION:
                if tables:
                    backup = self.path.with_name(f'{self.path.stem}.before-v{SCHEMA_VERSION}-{timestamp().replace(":", "-")}.db')
                    with closing(sqlite3.connect(backup)) as dest:
                        c.backup(dest)
                logging.info('Initializing business schema %s', SCHEMA_VERSION)
                try:
                    # Required for the v3 return-table rebuild; verified before commit.
                    c.execute('PRAGMA foreign_keys=OFF')
                    steps='\n'.join(MIGRATIONS[v] for v in range(version+1,SCHEMA_VERSION+1))
                    c.executescript('BEGIN IMMEDIATE;\n' + steps + f'\nPRAGMA application_id={APPLICATION_ID}; PRAGMA user_version={SCHEMA_VERSION};')
                    if c.execute('PRAGMA foreign_key_check').fetchone():
                        raise BusinessError('Schema upgrade failed its foreign-key check.')
                    c.commit()
                except BaseException:
                    c.rollback()
                    raise
                finally:
                    c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA journal_mode=WAL')

    def rows(self, query: str, params=()) -> list[dict]:
        with self.connect() as c:
            return [dict(r) for r in c.execute(query, params)]

    def one(self, query: str, params=()) -> dict | None:
        with self.connect() as c:
            row = c.execute(query, params).fetchone()
            return dict(row) if row else None

    def setting(self, key: str, default='') -> str:
        row = self.one('SELECT value FROM settings WHERE key=?', (key,))
        return row['value'] if row else default
