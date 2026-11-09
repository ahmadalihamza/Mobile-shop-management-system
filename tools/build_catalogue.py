"""Reproducibly normalize supplied/licensed reference names into an offline pack."""
from pathlib import Path
from collections import Counter
import hashlib
import html
import json
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mobile_desk.catalogue import Catalogue, models_checksum
from mobile_desk.values import normalize

ROOT = Path(__file__).resolve().parents[1]
old = json.loads((ROOT/'reference/Mobile-Desk-Windows/catalogue/catalogue.json').read_text(encoding='utf-8'))
android = json.loads((ROOT/'reference/catalogue-sources/devices.json').read_text(encoding='utf-8'))
brands = {normalize(x['brand']): x['brand'] for x in old}
brands.update({normalize(x): x for x in ['Nothing', 'CMF', 'Redmi', 'Poco', 'Itel', 'iQOO', 'Honor', 'Tecno', 'Infinix', 'Realme', 'OnePlus']})
skip = re.compile(r'\b(tab|tablet|pad|watch|tv|television|chromebook|smartwatch|shield|box|stick|projector)\b', re.I)
models = {}

def add(brand, name, source, alias='', year=None):
    brand, name = html.unescape(brand).strip(), html.unescape(name).strip()
    if name.casefold().startswith(brand.casefold()+' '):
        name = name[len(brand):].strip()
    if not name or skip.search(name):
        return
    key = normalize(brand)+'|'+normalize(name)
    identity = 'md-'+hashlib.sha256(key.encode()).hexdigest()[:24]
    entry = models.setdefault(key, dict(id=identity, brand=brand, model=name, source=source, aliases=[], release_year=year, device_type='Phone / reference name'))
    if alias and alias not in entry['aliases'] and len(entry['aliases'])<200:
        entry['aliases'].append(alias)
    if brand == 'Xiaomi' and name.lower().startswith('mi '):
        alternate = name.replace('Mi ', 'MI ')
        if alternate not in entry['aliases']:
            entry['aliases'].append(alternate)

for row in old:
    # The unlicensed direct Google extract is replaced by the Apache-licensed mapping.
    if 'github.com/ilyasozkurt' in row['source'] or row['brand'] == 'Apple':
        year = re.search(r'\b(19\d{2}|20\d{2})\b', row.get('release',''))
        add(row['brand'], row['name'], row['source'], year=int(year.group()) if year else None)
for code, row in sorted(android.items()):
    brand = brands.get(normalize(row.get('brand', '')))
    if brand:
        add(brand, row.get('name',''), 'https://github.com/bsthen/device-models', alias=code)
pack = dict(format='mobile-desk-catalogue', schema_version=1, version='2026.09.29.1', source='Supplied GPL historical catalogue; bsthen/device-models Apache-2.0 snapshot; supplied Apple factual model names', licence='GPL-3.0-or-later; Apache-2.0; manufacturer names are factual references, trademarks belong to their owners.', models=sorted(models.values(), key=lambda x: (x['brand'], x['model'])))
pack['sha256'] = models_checksum(pack['models'])
output = ROOT/'resources/mobile_catalogue.json'
output.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding='utf-8')
metadata = dict(version=pack['version'], records=len(models), brands=len({m['brand'] for m in models.values()}), sources=dict(Counter(m['source'] for m in models.values())), sha256=pack['sha256'], android_source_sha256=hashlib.sha256((ROOT/'reference/catalogue-sources/devices.json').read_bytes()).hexdigest())
(ROOT/'resources/catalogue_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata, indent=2))
