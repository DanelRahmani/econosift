"""Backend health dashboard: cache stats and data-source availability."""
from __future__ import annotations

import time
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
