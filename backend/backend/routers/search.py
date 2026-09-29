"""Ticker search via Yahoo Finance autocomplete."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Query

from ..cache import async_cached

router = APIRouter(prefix="/api/search", tags=["search"])

_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EconoSift/1.0)"}


@async_cached("search")
async def _search(q: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS) as c:
            r = await c.get(_URL, params={"q": q, "quotesCount": 10, "newsCount": 0})
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []
    results = []
    for item in data.get("quotes", []):
        symbol = item.get("symbol")
        if not symbol:
            continue
        results.append({
            "symbol": symbol,
            "name": item.get("shortname") or item.get("longname") or symbol,
            "exchange": item.get("exchDisp") or item.get("exchange") or "",
        })
    return results


@router.get("")
async def search(q: str = Query(..., min_length=1)):
    return {"results": await _search(q.strip())}
