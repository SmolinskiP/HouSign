# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\HA_Gestures\\models', 'models'), ('C:\\HA_Gestures\\ha_gestures\\sound', 'ha_gestures\\sound'), ('C:\\HA_Gestures\\settings.json', '.'), ('C:\\HA_Gestures\\gestures.yaml', '.'), ('C:\\HA_Gestures\\gesture_bindings.json', '.'), ('C:\\HA_Gestures\\logo.png', '.'), ('C:\\HA_Gestures\\logo.ico', '.')]
binaries = []
hiddenimports = ['pystray', 'pyaudio', 'websockets.sync.client', 'PIL']
tmp_ret = collect_all('flet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('mediapipe')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\HA_Gestures\\ha_gestures\\app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='HouSign-Debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\HA_Gestures\\logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HouSign-Debug',
)
