# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['photo_booth.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('layouts', 'layouts'), ('C:\\Users\\user\\AppData\\Roaming\\Python\\Python314\\site-packages\\cv2\\data\\haarcascade_frontalface_default.xml', 'cv2/data')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PHOTOBOOTH',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
