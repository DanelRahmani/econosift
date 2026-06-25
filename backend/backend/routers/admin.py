"""Backend health dashboard: cache stats and data-source availability."""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from fastapi import APIRouter

from .. import cache
from ..config import FRED_API_KEY

router = APIRouter(prefix="/api/admin", tags=["admin"])

_STARTED = time.time()


@router.get("/health")
async def health():
    cache_stats = cache.stats()
    total_hits = sum(s["hits"] for s in cache_stats.values())
    total_misses = sum(s["misses"] for s in cache_stats.values())
    total = total_hits + total_misses

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
        },
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
