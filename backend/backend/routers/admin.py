"""Backend health dashboard: cache stats and data-source availability."""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from fastapi import APIRouter

from .. import cache
from ..config import FRED_API_KEY, FINNHUB_API_KEY

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
        from ..db_models import DailyPrice, DailyQuote, DailyMacro, DailyFX, JobExecution, CacheEntry
        with SessionLocal() as session:
            db_health = {
                "daily_price": session.query(DailyPrice).count(),
                "daily_quote": session.query(DailyQuote).count(),
                "daily_macro": session.query(DailyMacro).count(),
                "daily_fx":    session.query(DailyFX).count(),
                "job_execution": session.query(JobExecution).count(),
                "cache_entries": session.query(CacheEntry).count(),
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
    """Return download status for each bulk dataset."""
    from ..services.bulk_data_service import get_bulk_status
    return {"datasets": get_bulk_status()}


@router.post("/bulk-data/refresh")
async def bulk_data_refresh():
    """Trigger a bulk data download in the background. Returns immediately."""
    import asyncio as _asyncio
    from ..services.bulk_data_service import refresh_all_bulk_data
    _asyncio.create_task(_asyncio.to_thread(refresh_all_bulk_data))
    return {"status": "started", "note": "Bulk data download running in background. Check GET /bulk-data/status for progress."}
