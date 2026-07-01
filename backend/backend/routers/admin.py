"""Backend health dashboard: cache stats and data-source availability."""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import cache
from ..config import DATA_DIR, FRED_API_KEY, FINNHUB_API_KEY, GEMINI_API_KEY

router = APIRouter(prefix="/api/admin", tags=["admin"])

_STARTED = time.time()


@router.get("/health")
async def health():
    cache_stats = cache.stats()
    total_hits = sum(s["hits"] for s in cache_stats.values())
    total_misses = sum(s["misses"] for s in cache_stats.values())
    total = total_hits + total_misses

    # Database health — table row counts + total cache size
    db_health: dict = {}
    try:
        from ..database import SessionLocal
        from ..db_models import DailyPrice, DailyQuote, DailyMacro, DailyFX, JobExecution, CacheEntry, AiSummary
        with SessionLocal() as session:
            db_health = {
                "daily_price": session.query(DailyPrice).count(),
                "daily_quote": session.query(DailyQuote).count(),
                "daily_macro": session.query(DailyMacro).count(),
                "daily_fx":    session.query(DailyFX).count(),
                "job_execution": session.query(JobExecution).count(),
                "cache_entries": session.query(CacheEntry).count(),
                "ai_summaries": session.query(AiSummary).count(),
            }
            # Add total cache size
            total_bytes = session.query(CacheEntry.value_json).all()
            db_health["cache_size_kb"] = round(sum(len(r[0]) for r in total_bytes if r[0]) / 1024, 1)
    except Exception as exc:
        db_health = {"error": str(exc)}

    return {
        "status": "ok",
        "uptimeSeconds": round(time.time() - _STARTED, 1),
        "cache": {
            "byName": cache_stats,
            "totalHits": total_hits,
            "totalMisses": total_misses,
            "overallHitRate": round(total_hits / total, 4) if total else None,
            "ttlSeconds": cache._CACHE_TTL,
        },
        "config": {
            "fredApiKey": bool(FRED_API_KEY),
            "finnhubApiKey": bool(FINNHUB_API_KEY),
            "geminiApiKey": bool(GEMINI_API_KEY),
        },
        "database": db_health,
    }


@router.get("/performance")
async def performance():
    """System performance stats: cache hit rates, recent job executions, DB info."""
    # Cache stats (uses the same cache.stats() as /health)
    cache_stats = cache.stats()

    # Recent job executions (last 24 h)
    job_stats: list[dict] = []
    try:
        from ..database import SessionLocal
        from ..db_models import JobExecution
        cutoff = datetime.utcnow() - timedelta(hours=24)
        with SessionLocal() as session:
            jobs = (
                session.query(JobExecution)
                .filter(JobExecution.started_at >= cutoff)
                .order_by(JobExecution.started_at.desc())
                .limit(50)
                .all()
            )
            job_stats = [
                {
                    "job_id": j.job_id,
                    "job_name": j.job_name,
                    "status": j.status,
                    "started_at": str(j.started_at),
                    "completed_at": str(j.completed_at) if j.completed_at else None,
                    "rows_affected": j.rows_affected,
                    "error_message": j.error_message,
                }
                for j in jobs
            ]
    except Exception as exc:
        job_stats = [{"error": str(exc)}]

    # DB connection info
    db_info: dict = {}
    try:
        from ..database import engine
        url = engine.url
        safe_url = str(url).replace(str(url.password or ""), "***") if url.password else str(url)
        pool = engine.pool
        db_info = {
            "url": safe_url,
            "pool_size": pool.size() if hasattr(pool, "size") else "N/A",
        }
    except Exception as exc:
        db_info = {"error": str(exc)}

    return {
        "cache": cache_stats,
        "jobs_last_24h": job_stats,
        "database": db_info,
    }


# ---------------------------------------------------------------------------
# Prefetch  — staggered background warming of cached data
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel


@router.post("/prefetch")
async def prefetch_start():
    """Start a staggered background prefetch of all slow-changing data sources.

    Returns immediately with the initial progress state.  The prefetch runs
    in the background and can be monitored via GET /api/admin/prefetch/status.
    """
    from ..services.prefetch_service import run_prefetch
    return await run_prefetch()


@router.get("/prefetch/status")
async def prefetch_status():
    """Return the current progress of the background prefetch job."""
    from ..services.prefetch_service import get_prefetch_status
    return get_prefetch_status()


# ---------------------------------------------------------------------------
# Bulk data — download World Bank / Fama-French / IMF WEO locally
# ---------------------------------------------------------------------------

@router.get("/bulk-data/status")
async def bulk_data_status():
    """Return download status for each bulk dataset, plus whether a refresh is running."""
    from ..services.bulk_data_service import get_bulk_status, is_bulk_running
    return {"datasets": get_bulk_status(), "running": is_bulk_running()}


@router.post("/bulk-data/refresh")
async def bulk_data_refresh():
    """Trigger a bulk data download in the background. Returns immediately."""
    import asyncio as _asyncio
    from ..services.bulk_data_service import refresh_all_bulk_data
    _asyncio.create_task(_asyncio.to_thread(refresh_all_bulk_data))
    return {"status": "started", "note": "Bulk data download running in background. Check GET /bulk-data/status for progress."}


# ---------------------------------------------------------------------------
# Config — view / update API keys in .env
# ---------------------------------------------------------------------------

# In Docker, .env is mounted at /app/.env (docker-compose.yml). Elsewhere
# (local dev, desktop app) it lives at DATA_DIR/.env — must match config.py's
# load_dotenv() target, since the old project-root-relative fallback resolved
# to a path inside the frozen desktop exe's bundle, not the app-data dir the
# backend actually reads from.
_ENV_PATH = "/app/.env"
if not os.path.isfile(_ENV_PATH):
    _ENV_PATH = str(DATA_DIR / ".env")


class _ConfigUpdate(BaseModel):
    fredApiKey: str | None = None
    finnhubApiKey: str | None = None
    geminiApiKey: str | None = None


def _mask_key(key: str | None) -> str | None:
    """Return first 4 + ... + last 4 of a key, or None if key is None/empty."""
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return key[:4] + "..." + key[-4:]


def _read_env() -> str:
    """Read the .env file contents.  Returns empty string if the file doesn't exist."""
    try:
        with open(_ENV_PATH, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def _write_env(new_content: str) -> None:
    """Write new content to the .env file."""
    with open(_ENV_PATH, "w", encoding="utf-8") as fh:
        fh.write(new_content)


async def _validate_fred_key(key: str) -> bool:
    """Test a FRED API key with a lightweight GDP series call."""
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id=GDP&api_key={key}&file_type=json&limit=1"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return False
            data = resp.json()
            # Valid key → JSON with "observations" key; invalid key → {"error_message": ...}
            return "error_message" not in data and "error_code" not in data
    except Exception:
        return False


async def _validate_finnhub_key(key: str) -> bool:
    """Test a Finnhub API key with a lightweight AAPL quote call."""
    url = f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={key}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return False
            data = resp.json()
            # Valid key returns {"c":..., "h":..., ...}; invalid returns {"error":"..."}
            return "error" not in data
    except Exception:
        return False


async def _validate_gemini_key(key: str) -> bool:
    """Test a Gemini API key by listing available models."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return False
            data = resp.json()
            # Valid key returns {"models": [...]}; invalid returns {"error": {...}}
            return "models" in data and "error" not in data
    except Exception:
        return False


@router.get("/config")
async def get_config():
    """Return masked API keys."""
    return {
        "fredApiKey": _mask_key(FRED_API_KEY),
        "finnhubApiKey": _mask_key(FINNHUB_API_KEY),
        "geminiApiKey": _mask_key(GEMINI_API_KEY),
    }


@router.put("/config")
async def update_config(body: _ConfigUpdate):
    """Validate and update FRED / Finnhub API keys in .env.

    Only the provided keys are updated.  Each key is validated against its
    respective API before writing.  Returns the new masked values plus a
    `restartRequired` flag — the container must be recreated for changes to
    take effect.
    """
    updated_any = False
    errors: list[str] = []

    # --- Validate FRED key if provided ----------------------------------------
    if body.fredApiKey is not None:
        if not body.fredApiKey.strip():
            errors.append("FRED API key cannot be empty.")
        elif not await _validate_fred_key(body.fredApiKey):
            errors.append("FRED API key is invalid — check and try again.")

    # --- Validate Finnhub key if provided -------------------------------------
    if body.finnhubApiKey is not None:
        if not body.finnhubApiKey.strip():
            errors.append("Finnhub API key cannot be empty.")
        elif not await _validate_finnhub_key(body.finnhubApiKey):
            errors.append("Finnhub API key is invalid — check and try again.")

    # --- Validate Gemini key if provided --------------------------------------
    if body.geminiApiKey is not None:
        if not body.geminiApiKey.strip():
            errors.append("Gemini API key cannot be empty.")
        elif not await _validate_gemini_key(body.geminiApiKey):
            errors.append("Gemini API key is invalid — check and try again.")

    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # --- Write updated values to .env -----------------------------------------
    content = _read_env()

    if body.fredApiKey is not None:
        key = body.fredApiKey.strip()
        if re.search(r"^FRED_API_KEY=", content, flags=re.MULTILINE):
            content = re.sub(
                r"^FRED_API_KEY=.*$",
                f"FRED_API_KEY={key}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content = content.rstrip("\n") + f"\nFRED_API_KEY={key}\n"
        updated_any = True

    if body.finnhubApiKey is not None:
        key = body.finnhubApiKey.strip()
        if re.search(r"^FINNHUB_API_KEY=", content, flags=re.MULTILINE):
            content = re.sub(
                r"^FINNHUB_API_KEY=.*$",
                f"FINNHUB_API_KEY={key}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content = content.rstrip("\n") + f"\nFINNHUB_API_KEY={key}\n"
        updated_any = True

    if body.geminiApiKey is not None:
        key = body.geminiApiKey.strip()
        if re.search(r"^GEMINI_API_KEY=", content, flags=re.MULTILINE):
            content = re.sub(
                r"^GEMINI_API_KEY=.*$",
                f"GEMINI_API_KEY={key}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content = content.rstrip("\n") + f"\nGEMINI_API_KEY={key}\n"
        updated_any = True

    if updated_any:
        _write_env(content)

    return {
        "fredApiKey": _mask_key(body.fredApiKey if body.fredApiKey is not None else FRED_API_KEY),
        "finnhubApiKey": _mask_key(body.finnhubApiKey if body.finnhubApiKey is not None else FINNHUB_API_KEY),
        "geminiApiKey": _mask_key(body.geminiApiKey if body.geminiApiKey is not None else GEMINI_API_KEY),
        "restartRequired": updated_any,
    }
