# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for EconoSift backend (Windows, onedir).

Produces `dist/econosift-backend/econosift-backend.exe` + `_internal/` folder that the
Tauri app bundles as a `resources` directory and spawns at startup.

Usage:
    pip install -r requirements.txt -r requirements-build.txt
    pyinstaller build.spec --noconfirm

Notes:
  * onedir (not onefile) — far more reliable for the heavy native stack
    (numpy/scipy/pyarrow MKL DLLs) and makes missing files obvious.
  * We use collect_all() for every third-party package so submodules, data
    files (pycountry ISO DBs, financedatabase/edgar CSVs, certifi cacert.pem …)
    and native binaries are all captured — the previous hand-listed
    hiddenimports missed most of these, which caused the module-import crashes.
  * console/UPX are debug-friendly for bring-up: console=True so startup errors
    are visible, upx=False to avoid corrupting native DLLs / AV false-positives.
    Flip console=False for the final windowless build once everything works.
"""
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas, binaries, hiddenimports = [], [], []

# Every third-party package the backend imports (grepped from backend/backend/).
# collect_all grabs submodules + data files + native libs in one shot.
_PACKAGES = [
    # Web stack
    "fastapi", "starlette", "uvicorn", "pydantic", "pydantic_core", "anyio",
    "sniffio", "click", "h11", "httptools", "websockets", "watchfiles",
    # Scientific / quant
    "numpy", "scipy", "pandas", "pyarrow", "arch", "statsmodels", "pandas_ta",
    # Data / finance sources
    "yfinance", "fredapi", "finnhub", "pandas_datareader", "wbgapi", "imfp",
    "dbnomics", "ecbdata", "eurostat", "wikitextparser", "edgar",
    "edgartools", "financedatabase", "pycountry",
    # Persistence / IO / net
    "sqlalchemy", "apscheduler", "openpyxl", "httpx", "httpcore", "requests",
    "certifi", "charset_normalizer", "urllib3", "idna", "dotenv", "tqdm",
    "dateutil", "pytz", "multitasking",
]

for pkg in _PACKAGES:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # pragma: no cover - package may be absent/renamed
        print(f"[build.spec] skip collect_all({pkg!r}): {exc}")

# Bundle the app's own package so `from backend.main import app` resolves at runtime.
datas += [("backend", "backend")]

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["./pyinstaller-hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # NOTE: do NOT exclude "unittest"/"test" — numpy.testing (pulled in by
        # scipy at import time) does `from unittest import TestCase`.
        "tkinter", "matplotlib", "PIL", "cv2",
        "IPython", "jupyter", "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir: binaries collected by COLLECT below
    name="econosift-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # UPX corrupts native DLLs / trips AV
    console=False,                  # windowless; run.py logs to backend.log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="econosift-backend",
)
