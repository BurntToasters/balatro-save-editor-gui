# PyInstaller spec - onedir build, bundles web/ assets.
import json
import os
import sys
import tempfile

APP_NAME = 'balatro-save-editor'
MAC_APP_NAME = 'Balatro Save Editor'
BUNDLE_ID = 'com.burnttoasters.balatrosaveeditor'

with open('package.json', encoding='utf-8') as _f:
    _pkg = json.load(_f)
APP_VERSION = _pkg.get('version', '0.0.0')

icon = None
target_arch = None
win_version_file = None

if sys.platform == 'win32':
    icon = 'icon/icon.ico'
    # Build a temporary Windows version-resource file so Explorer / About shows
    # the real version rather than the PyInstaller default.
    _parts = APP_VERSION.split('.')
    while len(_parts) < 4:
        _parts.append('0')
    _vt = ', '.join(_parts[:4])  # e.g. "0,2,0,0"
    _author = _pkg.get('author', 'BurntToasters').split('<')[0].strip()
    _vrc = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({_vt}), prodvers=({_vt}),
    mask=0x3f, flags=0x0, OS=0x4, fileType=0x1, subtype=0x0,
    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{_author}'),
      StringStruct('FileDescription', '{MAC_APP_NAME}'),
      StringStruct('FileVersion', '{APP_VERSION}'),
      StringStruct('InternalName', '{APP_NAME}'),
      StringStruct('ProductName', '{MAC_APP_NAME}'),
      StringStruct('ProductVersion', '{APP_VERSION}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""
    _tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    _tmp.write(_vrc)
    _tmp.close()
    win_version_file = _tmp.name

elif sys.platform == 'darwin':
    icon = 'icon/balatro-editor.icns'
    # Set BALATRO_MAC_ARCH=universal2 when building on a universal2 Python.
    target_arch = os.environ.get('BALATRO_MAC_ARCH') or None

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[('web', 'web')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    icon=icon,
    target_arch=target_arch,
    version=win_version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name=APP_NAME,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=f'{MAC_APP_NAME}.app',
        icon=icon,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            'CFBundleName': MAC_APP_NAME,
            'CFBundleDisplayName': MAC_APP_NAME,
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleVersion': APP_VERSION,
            'NSHighResolutionCapable': True,
        },
    )

# Clean up temp version file on Windows.
if win_version_file and os.path.exists(win_version_file):
    os.unlink(win_version_file)
