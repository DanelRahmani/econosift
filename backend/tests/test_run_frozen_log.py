"""DESK-01-V: the frozen desktop backend writes uvicorn's INFO lines to backend.log.

run.py redirects stdout/stderr to <data dir>/backend.log when frozen, then starts
uvicorn with log_config=None. Without a logging handler of its own, uvicorn's
"Uvicorn running on ..." INFO lines had nowhere to go and the log stayed empty
(seen on a real 2026-10-07 build: health OK, backend.log 0 bytes).
"""
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

_PROBE = r"""
import sys, logging, runpy
sys.frozen = True                     # take run.py's frozen branch
runpy.run_path("run.py", run_name="not_main")   # redirect + imports, no uvicorn.run
logging.getLogger("uvicorn.error").info("Uvicorn running on http://127.0.0.1:8000")
sys.stderr.flush()
"""


def test_frozen_run_writes_uvicorn_info_lines_to_backend_log(tmp_path):
    env = {**os.environ, "ECONOSIFT_DATA_DIR": str(tmp_path)}
    subprocess.run([sys.executable, "-c", _PROBE], cwd=BACKEND, env=env, check=True, timeout=300)
    log = (tmp_path / "backend.log").read_text(encoding="utf-8")
    assert "Uvicorn running on http://127.0.0.1:8000" in log
