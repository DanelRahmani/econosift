"""Sector performance router — Phase 10."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from .. import provenance as pv
from ..services import sector_service

router = APIRouter(prefix="/api/sector", tags=["sector"])


def _snapshot_time(sector: str) -> str | None:
    """Build time of the stored screener rows behind a sector drill (oldest ``updated_at``), as ``fetchedAt``."""
    from ..services import screener_cache

    try:
        row = screener_cache._get_conn().execute(
            "SELECT MIN(updated_at) FROM fundamentals WHERE sector = ?", (sector,)).fetchone()
        built = datetime.fromisoformat(row[0]).astimezone(timezone.utc) if row and row[0] else None
    except Exception:
        return None
    return built.strftime("%Y-%m-%dT%H:%M:%SZ") if built else None


@router.get("/returns")
async def get_sector_returns():
    try:
        return await asyncio.to_thread(sector_service.get_sector_returns)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/fundamentals")
async def get_sector_fundamentals():
    try:
        rows = await asyncio.to_thread(sector_service.get_sector_fundamentals)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    info = pv.ref("yahoo", None, "Quote and fund statistics of the 11 sector SPDR ETFs (Ticker.info)")
    closes = pv.ref("yahoo", None, "Daily adjusted close of the 11 sector SPDR ETFs, last 1 year", frequency="daily",
                    units="price, split- and dividend-adjusted")
    return pv.attach({"sectors": rows}, {
        "*": info,
        "sectors.price": pv.yahoo(None, "info.regularMarketPrice, else currentPrice, of each sector ETF", units="price"),
        "sectors.aum": pv.yahoo(None, "info.totalAssets of each sector ETF", units="USD"),
        "sectors.trailingPE": pv.yahoo(None, "info.trailingPE of each sector ETF"),
        "sectors.priceToBook": pv.yahoo(None, "info.priceToBook of each sector ETF"),
        "sectors.dividendYield": pv.derived("info.yield of each sector ETF × 100", [info], title="Dividend yield",
                                            note="Yahoo's fund yield, not a trailing-dividend calculation."),
        "sectors.beta": pv.yahoo(None, "info.beta of each sector ETF"),
        "sectors.vol30d": pv.derived("sample std of the last 30 daily simple returns × √252 × 100", [closes],
                                     title="30-day volatility"),
        "sectors.maxDrawdown": pv.derived("worst (close ÷ running peak − 1) × 100 over the 1-year window", [closes],
                                          title="Max drawdown, 1 year"),
        "sectors.return1m": pv.derived("(last close ÷ close 21 trading days earlier − 1) × 100", [closes],
                                       title="1-month return"),
        "sectors.return3m": pv.derived("(last close ÷ close 63 trading days earlier − 1) × 100", [closes],
                                       title="3-month return"),
        "sectors.return6m": pv.derived("(last close ÷ close 126 trading days earlier − 1) × 100", [closes],
                                       title="6-month return"),
        "sectors.return1y": pv.derived("(last close ÷ first close of the 1-year window − 1) × 100", [closes],
                                       title="1-year return"),
    })


@router.get("/rotation")
async def get_sector_rotation():
    try:
        return await asyncio.to_thread(sector_service.get_sector_rotation)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/drill")
async def get_sector_drill(sector: str = Query(..., description="Sector name, e.g. Technology")):
    if not sector:
        raise HTTPException(status_code=400, detail="sector is required")
    try:
        rows = await asyncio.to_thread(sector_service.get_sector_industry_drill, sector)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    stored = pv.ref("econosift", "screener_cache", "Screener universe cache: Yahoo fundamentals for the Dow 30, "
                    "Nasdaq-100 and S&P 500, refreshed nightly")
    ref = pv.derived(
        f"screener-cache stocks in the {sector} sector, grouped by industry, the three largest by market cap in "
        "each; change1d is the cached one-day price change", [stored], title="Industry drill-down")
    snapshot = await asyncio.to_thread(_snapshot_time, sector)
    if snapshot:
        # A stored snapshot: fetched when it was built, not at request time.
        ref["fetchedAt"] = snapshot
    return pv.attach({"sector": sector, "industries": rows}, {"*": ref})
