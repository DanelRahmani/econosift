# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Axiom Finance backend.
Produces `axiom-backend` (or .exe) that Tauri bundles as a sidecar.

Usage:
    pip install -r requirements-build.txt
    pyinstaller build.spec
"""
block_cipher = None

a = Analysis(
    ['backend/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'sqlalchemy.ext.declarative',
        'sqlalchemy.orm',
        'sqlalchemy.sql.default_comparator',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.strptime',
        'pandas._libs.tslibs.offsets',
        'pandas._libs.tslibs.parsing',
        'scipy.special.cython_special',
        'scipy.sparse.csgraph._validation',
        'scipy.spatial.ckdtree',
        'scipy.spatial.qhull',
        'yfinance',
        'arch.univariate',
        'arch.univariate.distribution',
        'cachetools',
        'sqlalchemy.dialects.sqlite',
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
    ],
    hookspath=['./pyinstaller-hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'PIL', 'cv2',
        'curses', 'readline', 'IPython', 'jupyter',
        'notebook', 'test', 'unittest',
    ],
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
    name='axiom-backend',
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
