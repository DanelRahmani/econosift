"""Dashboard endpoints: breadth, global indices, Fear & Greed, top movers.

All are compute tier 🟢 (run on page load) and cached for 60 minutes. The
constituent universe is itself cached weekly inside ``constituents``.
"""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from .. import provenance as pv
from ..services import breadth_service, indices_service, feargreed_service, movers_service
from ..services import constituents

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_INDICES = {"sp500", "ndx", "dow"}


def _norm_index(index: str) -> str:
    key = constituents.ALIASES.get(index.strip().lower(), index.strip().lower())
    return key if key in _INDICES else "sp500"


@router.get("/breadth")
async def breadth(index: str = "sp500"):
    return await asyncio.to_thread(breadth_service.breadth, _norm_index(index))


@router.get("/indices")
async def indices():
    return await asyncio.to_thread(indices_service.global_indices)


@router.get("/fear-greed")
async def fear_greed():
    return await asyncio.to_thread(feargreed_service.fear_greed)


@router.get("/movers")
async def movers(index: str = "sp500", limit: int = Query(10, ge=1, le=50)):
    return await asyncio.to_thread(movers_service.top_movers, _norm_index(index), limit)


@router.get("/constituents")
async def constituents_endpoint(index: str = "sp500"):
    """Index membership (yfinance-ready symbols); cached weekly. Reused by the
    treemap and screener universes in later phases."""
    members = await asyncio.to_thread(constituents.get_constituents, _norm_index(index))
    return pv.attach(
        {"index": _norm_index(index), "count": len(members), "constituents": members},
        {"*": pv.ref("wikipedia", None, "Index constituents (MediaWiki API)")})
