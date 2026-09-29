"""Launcher entry point for the frozen PyInstaller binary.

PyInstaller freezes this as a raw script, but the app uses relative imports
(e.g. `from .routers import market`). This launcher adds the package directory
to sys.path and imports the FastAPI app object directly, which makes the package
structure visible at runtime.

When frozen with `console=False`, stdout/stderr are `None`, which crashes
uvicorn's logging on `.isatty()`. Rather than discard output to devnull (which
hides every startup error), we redirect stdout/stderr to a rotating log file in
the app data directory so crashes remain diagnosable in production.
"""
import os
import sys

# Add the directory containing this script to sys.path so that the inner
# `backend` package is importable as a top-level package.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)


def _log_path() -> str:
    """Resolve the app-data backend log path, matching config.py and Tauri."""
    data_dir = os.getenv("ECONOSIFT_DATA_DIR") or os.getenv("AXIOM_DATA_DIR")
    if not data_dir:
        if sys.platform == "win32":
            base = os.environ.get(
                "APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
            )
        elif sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        else:
            base = os.environ.get(
                "XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")
            )
        current = os.path.join(base, "EconoSift")
        legacy = os.path.join(base, "AxiomFinance")
        data_dir = current if os.path.isdir(current) or not os.path.isdir(legacy) else legacy
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "backend.log")


# When frozen without a console, stdout/stderr are None. Send them to a log file
# so uvicorn logging works and any import/startup crash is captured on disk.
# When frozen *with* piped streams (the Tauri desktop shell pipes the child's
# stdout/stderr but discards them on the Rust side), redirect unconditionally —
# `sys.stdout is None` never fires in that case, so relying on it alone silently
# drops all output. Non-frozen runs keep the original None-only check.
_frozen = getattr(sys, "frozen", False)
if _frozen or sys.stdout is None or sys.stderr is None:
    _log = open(_log_path(), "a", buffering=1, encoding="utf-8")
    if _frozen or sys.stdout is None:
        sys.stdout = _log
    if _frozen or sys.stderr is None:
        sys.stderr = _log

import uvicorn

# Import the FastAPI app object directly — avoids PyInstaller import-string issues.
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None, log_level="info")
