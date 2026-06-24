"""Treemap router — exposes /api/treemap for the Phase 3 S&P 500 treemap.

NOTE: This router must be registered in ``backend/backend/main.py`` by the
orchestrator:
    from .routers import treemap as treemap_router
    app.include_router(treemap_router.router)
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from ..services import treemap_service
from ..services import constituents

router = APIRouter(prefix="/api/treemap", tags=["treemap"])

_INDICES = {"sp500", "ndx", "dow"}

# Valid periods accepted by the endpoint.
_VALID_PERIODS = treemap_service.VALID_PERIODS


def _norm_index(index: str) -> str:
    key = constituents.ALIASES.get(index.strip().lower(), index.strip().lower())
    return key if key in _INDICES else "sp500"


@router.get("")
async def treemap_endpoint(index: str = "sp500", period: str = "1d"):
    """Return treemap payload: per-stock price, return%, market cap, 52w range.

    Query params
    ------------
    index  : "sp500" | "ndx" | "dow"  (default "sp500"; aliases accepted)
    period : "1d" | "1w" | "1m" | "3m" | "ytd" | "1y"  (default "1d")
    """
    norm_index = _norm_index(index)
    norm_period = period if period in _VALID_PERIODS else "1d"
    return await asyncio.to_thread(treemap_service.treemap, norm_index, norm_period)
