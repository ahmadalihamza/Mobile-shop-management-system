"""Fetch pinned upstream Qt attribution files; run only when refreshing release notices."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path,PurePosixPath
import posixpath
from urllib.request import urlopen
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
tree=json.loads((ROOT/'build/qtbase-tree.json').read_text())
base='https://raw.githubusercontent.com/qt/qtbase/v6.10.2/'
paths=[r['path'] for r in tree['tree'] if r['path'].startswith('src/') and r['path'].endswith('qt_attribution.json')]
out=ROOT/'resources/licences/Qt/third-party'


def read(path):
    with urlopen(base+quote(path),timeout=30) as response:
        return response.read()


def gather(path):
    data=read(path)
    parent=PurePosixPath(path).parent
    target=out/path
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    entries=json.loads(data,strict=False)
    if isinstance(entries,dict):
        entries=[entries]
    count=0
    for entry in entries:
        names=entry.get('LicenseFile',[])
        if isinstance(names,str):
            names=[names]
        for name in names:
            source=posixpath.normpath(str(parent/name))
            if source.startswith('../'):
                raise ValueError('Unexpected upstream licence path')
            content=read(source)
            dest=out/source
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(content)
            count+=1
    return count


with ThreadPoolExecutor(max_workers=6) as pool:
    counts=list(pool.map(gather,paths))
print(f'Preserved {len(paths)} Qt attribution files and {sum(counts)} referenced licences.')
