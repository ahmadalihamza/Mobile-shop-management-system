# PyInstaller onedir recipe. Paths are anchored to this file, not the caller's cwd.
from pathlib import Path
import sys

if sys.platform != 'win32':
    raise RuntimeError('Build this release on Windows x64.')
root=Path(SPECPATH).parent
a=Analysis(
    [str(root/'run_mobile_desk.py')],pathex=[str(root)],binaries=[],
    datas=[(str(root/'resources'),'resources')],hiddenimports=[],hookspath=[],
    hooksconfig={},runtime_hooks=[],excludes=['tkinter','pytest','openpyxl'],
    noarchive=False,optimize=0,
)
# Qt 6.10 uses the unversioned Windows ICU API. Some Python distributions put
# ICU 78 on PATH; automatic collection then shadows the system DLL with a
# different ABI (ucnv_open_78 instead of ucnv_open). SQLite/CPython do not use it.
# Let Windows load its own ICU implementation rather than redistribute an OS DLL.
removed=[]
keep=[]
for entry in a.binaries:
    name=Path(entry[0]).name.casefold()
    if name in ('icuuc.dll','icuin.dll') or (name.startswith('icudt') and name.endswith('.dll')):
        removed.append(name)
    else:
        keep.append(entry)
a.binaries=keep
print('Using Windows system ICU; excluded collected copies:',removed)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='MobileDesk',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    disable_windowed_traceback=True,argv_emulation=False,target_arch=None,
    codesign_identity=None,entitlements_file=None,
    version=str(root/'installer/version_info.txt'),icon=[str(root/'resources/app.ico')])
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,upx_exclude=[],name='MobileDesk')
