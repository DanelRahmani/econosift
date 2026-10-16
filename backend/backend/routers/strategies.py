"""Strategy plugins: upload, list, run (Phase 70, plan §5).

Uploading runs arbitrary Python on this machine, so it is **off by default**
(Admin toggle, stored in ``app_setting``) and every run, the bundled examples
included, goes through the sandboxed subprocess. Writes and runs also refuse
a browser request from any origin the CORS policy does not list (a page on
another site, or a DNS-rebinding page pointing at localhost). Compute tier
red: nothing here runs on page load.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import rate_limit, store
from ..services import strategy_engine as se
from ..services import strategy_sandbox

router = APIRouter(tags=["research"])

EXAMPLES = Path(__file__).resolve().parents[1] / "strategies"
UPLOADS_KEY = "strategy_uploads"
_run_lock = threading.Lock()  # one run at a time: each holds a price panel and a child process


def same_origin_only(request: Request) -> None:
    """Refuse a cross-site browser request (CSRF / DNS rebinding) to an endpoint that runs code."""
    origin = request.headers.get("origin")
    if origin and origin not in getattr(request.app.state, "allowed_origins", ()):
        raise HTTPException(status_code=403, detail=f"requests from {origin} are not allowed")


def uploads_enabled() -> bool:
    with store.connect() as conn:
        row = conn.execute("SELECT value FROM app_setting WHERE key = ?", (UPLOADS_KEY,)).fetchone()
    return bool(row and row[0] == "1")


def _examples() -> dict[str, dict]:
    out = {}
    for path in sorted(EXAMPLES.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        out[f"example:{path.stem}"] = dict(id=f"example:{path.stem}", name=path.name, builtIn=True,
                                           sha256=se.check_source(source), uploadedAt=None, source=source)
    return out


def _load(strategy_id: str) -> dict:
    examples = _examples()
    if strategy_id in examples:
        return examples[strategy_id]
    if not strategy_id.isdigit():
        raise HTTPException(status_code=404, detail="no such strategy")
    with store.connect() as conn:
        row = conn.execute("SELECT id, name, sha256, source, uploaded_at FROM strategy WHERE id = ?",
                           (int(strategy_id),)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="no such strategy")
    return dict(id=str(row[0]), name=row[1], sha256=row[2], source=row[3], uploadedAt=row[4], builtIn=False)


def _public(s: dict) -> dict:
    return {k: v for k, v in s.items() if k != "source"} | {"bytes": len(s["source"].encode("utf-8"))}


# -- Admin toggle -----------------------------------------------------------------

class UploadsToggle(BaseModel):
    enabled: bool


@router.get("/api/admin/strategy-uploads")
def get_strategy_uploads():
    return {"enabled": uploads_enabled(), "sandbox": strategy_sandbox.capabilities()}


@router.put("/api/admin/strategy-uploads", dependencies=[Depends(same_origin_only)])
def put_strategy_uploads(body: UploadsToggle):
    store.upsert("app_setting", [dict(key=UPLOADS_KEY, value="1" if body.enabled else "0")], ("key",))
    return {"enabled": body.enabled, "sandbox": strategy_sandbox.capabilities()}


# -- Strategies -----------------------------------------------------------------------

@router.get("/api/research/strategies")
def list_strategies():
    with store.connect() as conn:
        rows = conn.execute("SELECT id, name, sha256, source, uploaded_at FROM strategy ORDER BY id").fetchall()
    uploaded = [dict(id=str(r[0]), name=r[1], sha256=r[2], source=r[3], uploadedAt=r[4], builtIn=False)
                for r in rows]
    return {
        "uploadsEnabled": uploads_enabled(),
        "sandbox": strategy_sandbox.capabilities(),
        "limits": {"maxBytes": se.MAX_SOURCE_BYTES, "timeoutSeconds": strategy_sandbox.TIMEOUT_S,
                   "memoryMB": strategy_sandbox.MEMORY_MB, "maxGross": se.MAX_GROSS},
        "strategies": [_public(s) for s in [*_examples().values(), *uploaded]],
    }


@router.get("/api/research/strategies/{strategy_id}/source")
def strategy_source(strategy_id: str):
    s = _load(strategy_id)
    return {"id": s["id"], "name": s["name"], "sha256": s["sha256"], "source": s["source"]}


class StrategyUpload(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[\w .-]+\.py$")
    source: str = Field(min_length=1, max_length=se.MAX_SOURCE_BYTES)


@router.post("/api/research/strategies", dependencies=[Depends(same_origin_only)])
def upload_strategy(body: StrategyUpload):
    if not uploads_enabled():
        raise HTTPException(status_code=403, detail="strategy uploads are off; an admin can turn them on")
    try:
        digest = se.check_source(body.source)  # parsed, never run here
    except se.StrategyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with store.connect() as conn:
        conn.execute("INSERT INTO strategy (name, sha256, source, uploaded_at) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT (sha256) DO UPDATE SET name = excluded.name", (body.name, digest, body.source, now))
        row = conn.execute("SELECT id FROM strategy WHERE sha256 = ?", (digest,)).fetchone()
    return _public(_load(str(row[0])))


@router.delete("/api/research/strategies/{strategy_id}", dependencies=[Depends(same_origin_only)])
def delete_strategy(strategy_id: str):
    s = _load(strategy_id)
    if s["builtIn"]:
        raise HTTPException(status_code=400, detail="bundled examples cannot be deleted")
    with store.connect() as conn:
        conn.execute("DELETE FROM strategy WHERE id = ?", (int(s["id"]),))
    return {"deleted": s["id"]}


ParamValue = float | int | bool | str


class StrategyRun(BaseModel):
    strategyId: str
    index: str = Field(default="sp500", pattern="^(sp500|ndx|dow)$")
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    years: int = Field(default=10, ge=1, le=25)
    rebalance: str = Field(default="M", pattern="^(W|M|Q)$")
    costBps: float = Field(default=10.0, ge=0.0, le=500.0)
    params: dict[str, ParamValue] = Field(default_factory=dict, max_length=20)


def _window(req) -> tuple[str, str]:
    with store.connect() as conn:
        last = conn.execute("SELECT MAX(date) FROM price_daily").fetchone()[0]
    if not last:
        raise HTTPException(status_code=409, detail="no stored prices yet: the first backfill is still running")
    end = min(pd.Timestamp(req.end or last), pd.Timestamp(last))
    start = pd.Timestamp(req.start) if req.start else end - pd.DateOffset(years=req.years)
    return start.date().isoformat(), end.date().isoformat()


def _runnable(strategy_id: str) -> dict:
    s = _load(strategy_id)
    if not s["builtIn"] and not uploads_enabled():
        raise HTTPException(status_code=403, detail="strategy uploads are off, so uploaded strategies do not run")
    return s


def _requests() -> int:
    return sum(g["requests"] for g in rate_limit.status().values())


def _exclusive(fn):
    """Run ``fn`` alone and report the backend's external requests while it ran."""
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="another strategy run is in progress")
    try:
        before = _requests()
        result = fn()
        # Counts every source guard in this process, the fetcher thread's included: a
        # run itself only reads the store, and its child process has no network.
        result["externalRequestsDuringRun"] = _requests() - before
        return result
    except se.StrategyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        _run_lock.release()


@router.post("/api/research/strategies/run", dependencies=[Depends(same_origin_only)])
async def run_strategy(req: StrategyRun):
    """Backtest a strategy over the point-in-time universe, in the sandbox. Red tier."""
    s = _runnable(req.strategyId)
    start, end = _window(req)

    def go():
        return se.backtest(s["source"], s["name"], index=req.index, start=start, end=end,
                           rebalance=req.rebalance, cost_bps=req.costBps, params=req.params,
                           runner_factory=strategy_sandbox.SandboxRunner)

    return await asyncio.to_thread(_exclusive, go)

