# PyInstaller spec - onedir build, bundles web/ assets.
import os
import sys

APP_NAME = 'balatro-save-editor'
MAC_APP_NAME = 'Balatro Save Editor'
BUNDLE_ID = 'com.burnttoasters.balatrosaveeditor'

icon = None
target_arch = None
if sys.platform == 'win32':
    icon = 'icon/icon.ico'
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
            'NSHighResolutionCapable': True,
        },
    )
