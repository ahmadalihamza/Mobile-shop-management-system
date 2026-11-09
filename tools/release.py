"""Release manifest, source bundle, licences and portable ZIP from explicit allowlists."""
import argparse
from datetime import datetime,timezone
import hashlib
from importlib.metadata import distribution,version
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mobile_desk import __version__

DIST=ROOT/'dist'
APP=DIST/'MobileDesk'
DOCS=['README.md','USER_GUIDE.md','BUSINESS_RULES.md','DATABASE_SCHEMA.md','CATALOGUE.md','THIRD_PARTY_NOTICES.md','LICENSE']
GUIDES=['REVISION_ACCEPTANCE.md','RESET_UNDO_ACCEPTANCE.md','SUPPLIER_SELECTION_ACCEPTANCE.md','CHINA_PURCHASE_ACCEPTANCE.md','FORM_SIMPLICITY_REVIEW.md','SIMPLER_FORMS_ACCEPTANCE.md']
SOURCE_FILES=DOCS+['run_mobile_desk.py','pyproject.toml','requirements.txt','requirements-dev.txt','build_windows.ps1','.gitignore','.gitattributes']
SOURCE_FILES += ['practice/'+name for name in ('Practice-Guide.md','Practice-Guide.html','China-Imports-And-Returns.md','Start-Practice.cmd','Sample-Catalogue-Update.json','Verified-Results.json')]
SOURCE_FILES += ['tools/'+name for name in ('release.py','build_catalogue.py','gather_qt_notices.py','benchmark_business.py','clean_production.py','render_practice_guide.py','verify_practice_walkthrough.py')]


def files_in(directory):
    return sorted(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')


def prepare():
    if (ROOT/'resources/client_seed.zip').exists():
        raise RuntimeError('Retired client seed must not be packaged.')
    for name in DOCS:
        shutil.copy2(ROOT/name,APP/name)
    (APP/'docs').mkdir(exist_ok=True)
    for name in GUIDES:
        if (ROOT/'docs'/name).exists():
            shutil.copy2(ROOT/'docs'/name,APP/'docs'/name)
    licences=APP/'licences'
    shutil.copytree(ROOT/'resources/licences',licences,dirs_exist_ok=True)
    shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt',licences/'Python-LICENSE.txt')
    for name in ('PySide6-Essentials','shiboken6','pyinstaller'):
        dist=distribution(name)
        target=licences/name
        target.mkdir(exist_ok=True)
        (target/'METADATA.txt').write_text(dist.read_text('METADATA') or '',encoding='utf-8')
        for f in dist.files or []:
            if any(s in str(f).lower() for s in ('license','licence','copying','notice')):
                source=Path(dist.locate_file(f))
                if source.is_file():
                    dest=target/str(f).replace('..','_')
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,dest)
    metadata=dict(application='Mobile Desk',version=__version__,built_at=datetime.now(timezone.utc).isoformat(),python=sys.version,sqlite=sqlite3.sqlite_version,packages={name:version(name) for name in ('PySide6-Essentials','shiboken6','pyinstaller','pytest','openpyxl')},catalogue=json.loads((ROOT/'resources/catalogue_metadata.json').read_text()),data_included=False,clean_start=True)
    (APP/'release.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    source_zip=DIST/f'MobileDesk-{__version__}-Source.zip'
    included=[ROOT/name for name in SOURCE_FILES]
    for directory,patterns in {'mobile_desk':('*.py',),'tests':('*.py',),'installer':('*.iss','*.spec','*.txt')}.items():
        included.extend(p for p in files_in(ROOT/directory) if any(p.match(pattern) for pattern in patterns))
    included.extend(ROOT/'resources'/name for name in ('app.ico','dropdown.svg','catalogue_metadata.json','mobile_catalogue.json'))
    # Qt notices include extensionless LICENSE and COPYING files.
    included.extend(files_in(ROOT/'resources/licences'))
    included.extend(ROOT/'docs'/name for name in GUIDES if (ROOT/'docs'/name).exists())
    # Raw client data and extracted prototype never enter a public application package.
    with zipfile.ZipFile(source_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(set(included)):
            z.write(path,'MobileDesk-Source/'+path.relative_to(ROOT).as_posix())
    shutil.copy2(source_zip,APP/source_zip.name)
    print(json.dumps(dict(prepared=str(APP),source=str(source_zip)),indent=2))


def archive():
    portable=DIST/f'MobileDesk-{__version__}-Windows-x64.zip'
    with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in files_in(APP):
            if path.suffix.lower() in ('.db','.mdbackup','.xlsx'):
                raise RuntimeError('A data file was found in the application release: '+str(path))
            z.write(path,'MobileDesk/'+path.relative_to(APP).as_posix())
    targets=[portable,DIST/f'MobileDesk-{__version__}-Source.zip',APP/'MobileDesk.exe']
    setup=DIST/f'MobileDesk-{__version__}-Setup.exe'
    if setup.exists():
        targets.append(setup)
    checks=[]
    for path in targets:
        with path.open('rb') as stream:
            checks.append(hashlib.file_digest(stream,'sha256').hexdigest()+'  '+path.relative_to(DIST).as_posix())
    (DIST/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='ascii')
    print(json.dumps(dict(portable=str(portable),size_mb=round(portable.stat().st_size/1024**2,1)),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','archive'])
    args=parser.parse_args()
    prepare() if args.command=='prepare' else archive()
