"""Launcher entry point for the frozen PyInstaller binary.

PyInstaller freezes `main.py` as a raw script, but the app uses
relative imports (e.g. `from .routers import market`).  This launcher
adds the package directory to sys.path and runs uvicorn with a dotted
import string, which makes the package structure visible at runtime.
"""
import sys
import os

# Add the directory containing this script to sys.path so that
# `backend` is importable as a top-level package.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)
