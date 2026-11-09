"""Local reference catalogue. Updates never open the business database."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import re
import sqlite3
from mobile_desk.values import BusinessError, normalize, text, timestamp

CATALOGUE_ID = 1296319026
CATALOGUE_SCHEMA = '''
CREATE TABLE catalogue_brands(id INTEGER PRIMARY KEY,name TEXT NOT NULL,normalized_name TEXT NOT NULL UNIQUE);
CREATE TABLE catalogue_models(id TEXT PRIMARY KEY,brand_id INTEGER NOT NULL REFERENCES catalogue_brands(id),model_name TEXT NOT NULL,normalized_name TEXT NOT NULL,series TEXT NOT NULL DEFAULT '',device_type TEXT NOT NULL DEFAULT '',release_year INTEGER,source TEXT NOT NULL,source_version TEXT NOT NULL,UNIQUE(brand_id,normalized_name));
CREATE TABLE catalogue_aliases(model_id TEXT NOT NULL REFERENCES catalogue_models(id),alias TEXT NOT NULL,UNIQUE(model_id,alias));
CREATE TABLE catalogue_variants(model_id TEXT NOT NULL REFERENCES catalogue_models(id),ram TEXT NOT NULL,storage TEXT NOT NULL,UNIQUE(model_id,ram,storage));
CREATE TABLE catalogue_versions(version TEXT PRIMARY KEY,imported_at TEXT NOT NULL,source TEXT NOT NULL,licence TEXT NOT NULL,record_count INTEGER NOT NULL,checksum TEXT NOT NULL);
CREATE VIRTUAL TABLE catalogue_search USING fts5(model_id UNINDEXED,search_name,compact,tokenize='unicode61',prefix='2 3 4');
'''


def version_key(version):
    if not isinstance(version, str) or not re.fullmatch(r'\d{1,8}(\.\d{1,8}){1,4}', version):
        raise BusinessError('Catalogue version must contain 2–5 numeric parts, such as 2026.09.29.1.')
    return tuple(int(p) for p in version.split('.'))


def models_checksum(models):
    return hashlib.sha256(json.dumps(models, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class Catalogue:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            version = c.execute('PRAGMA user_version').fetchone()[0]
            tables = c.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone()
            if tables and (c.execute('PRAGMA application_id').fetchone()[0] != CATALOGUE_ID or version != 1):
                raise BusinessError('The catalogue database is incompatible. Restore it or install a catalogue update into a fresh catalogue.')
            if not tables:
                c.executescript('BEGIN;'+CATALOGUE_SCHEMA+f'PRAGMA application_id={CATALOGUE_ID}; PRAGMA user_version=1; COMMIT;')
            if c.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise BusinessError('The catalogue failed its integrity check. Manual shop products are still available.')

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def info(self):
        with self.connect() as c:
            count = c.execute('SELECT COUNT(*) FROM catalogue_models').fetchone()[0]
            brands = c.execute('SELECT COUNT(*) FROM catalogue_brands').fetchone()[0]
            last = c.execute('SELECT * FROM catalogue_versions ORDER BY imported_at DESC LIMIT 1').fetchone()
            return dict(count=count, brands=brands, version=last['version'] if last else '0.0', source=last['source'] if last else '')

    def search(self, query='', limit=100, offset=0):
        with self.connect() as c:
            tokens = normalize(query).split()
            base = 'SELECT m.*,b.name AS brand FROM catalogue_models m JOIN catalogue_brands b ON b.id=m.brand_id'
            if not tokens:
                return [dict(r) for r in c.execute(base+' ORDER BY b.name,m.model_name LIMIT ? OFFSET ?', (limit, offset))]
            expression = ' AND '.join('"'+token+'"*' for token in tokens)
            matches = [dict(r) for r in c.execute(base+" JOIN catalogue_search f ON f.model_id=m.id WHERE catalogue_search MATCH ? ORDER BY CASE WHEN b.name IN('Apple','Samsung','Xiaomi','OnePlus','Google','Oppo','Vivo','Realme') THEN 0 ELSE 1 END,rank,b.name,m.model_name LIMIT ? OFFSET ?", (expression, limit, offset))]
            if not matches:
                clauses = ' AND '.join('instr(f.compact,?)>0' for _ in tokens)
                matches = [dict(r) for r in c.execute(base+' JOIN catalogue_search f ON f.model_id=m.id WHERE '+clauses+' ORDER BY b.name,m.model_name LIMIT ? OFFSET ?', (*tokens, limit, offset))]
            return matches

    def get(self, identity):
        with self.connect() as c:
            row = c.execute('SELECT m.*,b.name brand FROM catalogue_models m JOIN catalogue_brands b ON b.id=m.brand_id WHERE m.id=?', (identity,)).fetchone()
            return dict(row) if row else None

    def import_file(self, path):
        path = Path(path)
        if path.stat().st_size > 100_000_000:
            raise BusinessError('Catalogue update is too large.')
        try:
            package = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            raise BusinessError('Choose a valid Mobile Desk JSON catalogue update.') from None
        return self.import_package(package)

    def import_package(self, package):
        if not isinstance(package, dict) or package.get('format') != 'mobile-desk-catalogue' or package.get('schema_version') != 1:
            raise BusinessError('Unsupported catalogue package format.')
        version = package.get('version')
        version_key(version)
        source, licence = text(package.get('source'), 'Source', True, 2000), text(package.get('licence'), 'Licence', True, 2000)
        models = package.get('models')
        if not isinstance(models, list) or not 1 <= len(models) <= 100000:
            raise BusinessError('Catalogue package must contain 1–100,000 models.')
        checksum = models_checksum(models)
        if checksum != package.get('sha256'):
            raise BusinessError('Catalogue checksum does not match. Obtain an intact update package.')
        clean, ids, names = [], set(), set()
        for row in models:
            if not isinstance(row, dict):
                raise BusinessError('Invalid model record.')
            identity = text(row.get('id'), 'Model ID', True, 150)
            brand, model = text(row.get('brand'), 'Brand', True, 150), text(row.get('model'), 'Model', True, 250)
            pair = (normalize(brand), normalize(model))
            if identity in ids or pair in names:
                raise BusinessError('Duplicate model ID or brand/model in the update package.')
            ids.add(identity)
            names.add(pair)
            year = row.get('release_year')
            if year is not None and (type(year) is not int or not 1970 <= year <= 2100):
                raise BusinessError('Invalid catalogue release year.')
            aliases = row.get('aliases', [])
            variants = row.get('variants', [])
            if not isinstance(aliases, list) or len(aliases)>200 or not isinstance(variants, list) or len(variants)>100:
                raise BusinessError('Invalid catalogue aliases or variants.')
            aliases = [text(a, 'Alias', True, 250) for a in aliases]
            vs = []
            for v in variants:
                if not isinstance(v, dict):
                    raise BusinessError('Invalid variant record.')
                vs.append((text(v.get('ram'), limit=30), text(v.get('storage'), limit=30)))
            clean.append((identity, brand, model, text(row.get('series'), limit=150), text(row.get('device_type'), limit=50), year, text(row.get('source') or source, limit=2000), aliases, vs))
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            last = c.execute('SELECT version FROM catalogue_versions ORDER BY imported_at DESC LIMIT 1').fetchone()
            if last and version_key(version) <= version_key(last['version']):
                raise BusinessError('This catalogue version is already installed or older than the installed version.')
            for identity, brand, model, series, device_type, year, row_source, aliases, variants in clean:
                c.execute('INSERT OR IGNORE INTO catalogue_brands(name,normalized_name) VALUES(?,?)', (brand, normalize(brand)))
                brand_id = c.execute('SELECT id FROM catalogue_brands WHERE normalized_name=?', (normalize(brand),)).fetchone()[0]
                other = c.execute('SELECT id FROM catalogue_models WHERE brand_id=? AND normalized_name=?', (brand_id, normalize(model))).fetchone()
                if other and other['id'] != identity:
                    raise BusinessError('This brand/model already has a different stable ID. The whole update was cancelled.')
                c.execute('INSERT INTO catalogue_models(id,brand_id,model_name,normalized_name,series,device_type,release_year,source,source_version) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET brand_id=excluded.brand_id,model_name=excluded.model_name,normalized_name=excluded.normalized_name,series=excluded.series,device_type=excluded.device_type,release_year=excluded.release_year,source=excluded.source,source_version=excluded.source_version', (identity, brand_id, model, normalize(model), series, device_type, year, row_source, version))
                c.execute('DELETE FROM catalogue_aliases WHERE model_id=?', (identity,))
                c.execute('DELETE FROM catalogue_variants WHERE model_id=?', (identity,))
                c.executemany('INSERT OR IGNORE INTO catalogue_aliases VALUES(?,?)', [(identity, alias) for alias in aliases])
                c.executemany('INSERT OR IGNORE INTO catalogue_variants VALUES(?,?,?)', [(identity, *v) for v in variants])
                search = normalize(' '.join([brand, model, series, *aliases]))
                if last:
                    c.execute('DELETE FROM catalogue_search WHERE model_id=?', (identity,))
                c.execute('INSERT INTO catalogue_search(model_id,search_name,compact) VALUES(?,?,?)', (identity, search, search.replace(' ', '')))
            c.execute('INSERT INTO catalogue_versions VALUES(?,?,?,?,?,?)', (version, timestamp(), source, licence, len(clean), checksum))
        return len(clean)
