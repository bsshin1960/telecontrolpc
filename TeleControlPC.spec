# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'qasync',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'websockets.legacy.server',
        'mss',
        'PIL',
        'PIL.Image',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        'ctypes',
        'ctypes.wintypes',
        'asyncio',
        'logging',
        'socket',
        'json',
        'os',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TeleControlPC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # 콘솔 창 없이 GUI만 표시
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
