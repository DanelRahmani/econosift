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

# When frozen with console=False, stdout/stderr are None.
# Redirect to devnull so uvicorn's logging doesn't crash on .isatty().
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import uvicorn

# Import the FastAPI app object directly — avoids PyInstaller import-string issues.
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
