"""Multi-factor stock screener — legacy endpoint + Phase 5 cached-universe endpoints."""
from __future__ import annotations

import asyncio
import json
import threading
from fastapi import APIRouter, HTTPException, Query

from .. import provenance as pv
from ..services import yfinance_service as yfs
from ..services import metrics
from ..services import screener_service
from ..services import screener_cache
from ..services import constituents as _constituents

router = APIRouter(prefix="/api/screener", tags=["screener"])

_VALID_INDICES = {"dow", "ndx", "sp500"}

# Metrics exposed to the screener, with the path to pull them from.
# group None means it lives at the top level of the row.
FIELDS = {
    "peRatio": ("valuation", "peRatio"),
    "forwardPE": ("valuation", "forwardPE"),
    "pbRatio": ("valuation", "pbRatio"),
    "dividendYield": ("valuation", "dividendYield"),
    "debtToEquity": ("leverage", "debtToEquity"),
    "currentRatio": ("liquidity", "currentRatio"),
    "roe": ("profitability", "roe"),
    "netMargin": ("profitability", "netMargin"),
    "grossMargin": ("profitability", "grossMargin"),
    "sharpe": (None, "sharpe"),
    "beta": (None, "beta"),
    "zScore": (None, "zScore"),
}


async def _row_for(sym: str, period: str, risk_free: float) -> dict:
    bench = yfs.benchmark_for(sym)
    bundle = await asyncio.to_thread(yfs.get_info, sym)
    payload = metrics.compute_ratios(bundle)

    frame = await asyncio.to_thread(
        yfs.get_close_frame, tuple(dict.fromkeys([sym, bench])), period)
    sharpe = beta = None
    if frame is not None and not frame.empty and sym in frame.columns:
        bench_series = frame[bench] if bench in frame.columns else None
        m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
        sharpe, beta = m.get("sharpe"), m.get("beta")

    info = bundle.get("info", {}) or {}
    row = {
        "ticker": sym,
        "name": info.get("shortName") or info.get("longName") or sym,
        "sector": info.get("sector"),
        "sharpe": sharpe,
        "beta": beta,
        "zScore": payload["zScore"],
    }
    for group in ("valuation", "leverage", "liquidity", "profitability"):
        row[group] = payload[group]
    return row


def _value(row: dict, field: str):
    group, key = FIELDS[field]
    src = row if group is None else row.get(group, {})
    return src.get(key)


def _passes(row: dict, filters: list[dict]) -> bool:
    for f in filters:
        field, op, target = f["field"], f["op"], f["value"]
        v = _value(row, field)
        if v is None:
            return False
        if op == "lt" and not (v < target):
            return False
        if op == "gt" and not (v > target):
            return False
    return True


@router.get("")
async def screen(
    universe: str = Query(..., description="Comma-separated tickers"),
    filters: str = Query("", description="field:op:value,... e.g. peRatio:lt:15,roe:gt:0.1"),
    sort: str = Query("sharpe", description="field to rank by, descending"),
    period: str = "1y",
    risk_free: float = 0.04,
):
    syms = list(dict.fromkeys(t.strip().upper() for t in universe.split(",") if t.strip()))[:30]

    parsed_filters = []
    for clause in filters.split(","):
        clause = clause.strip()
        if not clause:
            continue
        parts = clause.split(":")
        if len(parts) != 3 or parts[0] not in FIELDS or parts[1] not in ("lt", "gt"):
            continue
        try:
            parsed_filters.append({"field": parts[0], "op": parts[1], "value": float(parts[2])})
        except ValueError:
            continue

    rows = await asyncio.gather(*[_row_for(s, period, risk_free) for s in syms],
                                return_exceptions=True)
    rows = [r for r in rows if isinstance(r, dict)]

    matched = [r for r in rows if _passes(r, parsed_filters)]
    sort_field = sort if sort in FIELDS else "sharpe"
    matched.sort(key=lambda r: (_value(r, sort_field) is None, -(_value(r, sort_field) or 0)))

    info = pv.ref("yahoo", None, "Quote snapshot and latest annual statements of each ticker")
    prices = pv.ref("yahoo", None, f"Daily adjusted close of each ticker and its benchmark index, {period}",
                    frequency="daily")
    return pv.attach({
        "fields": list(FIELDS.keys()),
        "filters": parsed_filters,
        "sort": sort_field,
        "count": len(matched),
        "screened": len(rows),
        "results": matched,
    }, {
        "*": info,
        "results": pv.derived("financial ratios from the statements and quote snapshot (see the Ratios tab for "
                              "each formula)", [info], title="Screener ratios"),
        "results.sharpe": pv.derived(
            f"(annualised mean log return − risk-free) / annualised volatility; risk-free = {risk_free:g} "
            "(request parameter)", [prices], title="Sharpe ratio"),
        "results.beta": pv.derived("cov(ticker, benchmark daily log returns) / var(benchmark)", [prices],
                                   title="Beta vs benchmark index"),
        "results.zScore": pv.derived("Altman Z = 1.2·WC/TA + 1.4·RE/TA + 3.3·EBIT/TA + 0.6·MV/TL + 1.0·Sales/TA",
                                     [info], title="Altman Z-Score"),
    })


# ---------------------------------------------------------------------------
# Phase 5 — Cached-universe endpoints
# ---------------------------------------------------------------------------

@router.get("/presets")
async def get_presets():
    """Return the list of available preset signal definitions."""
    return {"presets": screener_service.PRESETS}


@router.get("/status")
async def get_status(index: str = Query("dow")):
    """Return cache freshness info for a given index universe."""
    if index not in _VALID_INDICES:
        raise HTTPException(status_code=422, detail=f"index must be one of {sorted(_VALID_INDICES)}")
    members = _constituents.get_constituents(index)
    symbols = [m["symbol"] for m in members]
    return {
        "index": index,
        "rowCount": screener_cache.row_count(symbols),
        "lastRefresh": screener_cache.last_refresh(symbols),
        "stale": screener_cache.is_stale(symbols),
    }


@router.post("/refresh")
async def trigger_refresh(index: str = Query("dow")):
    """Kick a background cache refresh for the given index. Returns immediately."""
    if index not in _VALID_INDICES:
        raise HTTPException(status_code=422, detail=f"index must be one of {sorted(_VALID_INDICES)}")
    t = threading.Thread(target=screener_service.refresh_universe, args=(index,), daemon=True)
    t.start()
    return {"index": index, "started": True}


@router.get("/universe")
async def get_universe(
    index: str = Query("dow"),
    presets: str = Query("", description="Comma-separated preset IDs"),
    filters: str = Query("", description="JSON array of {field,op,value} objects"),
    sort: str = Query("marketCap"),
    dir: str = Query("desc"),
    limit: int = Query(250),
):
    """Query the cached screener universe with optional preset/filter/sort."""
    if index not in _VALID_INDICES:
        raise HTTPException(status_code=422, detail=f"index must be one of {sorted(_VALID_INDICES)}")
    if dir not in ("asc", "desc"):
        dir = "desc"

    preset_ids: list[str] = [p.strip() for p in presets.split(",") if p.strip()] if presets else []

    parsed_filters: list[dict] = []
    if filters:
        try:
            parsed_filters = json.loads(filters)
            if not isinstance(parsed_filters, list):
                parsed_filters = []
        except (json.JSONDecodeError, ValueError):
            parsed_filters = []

    result = screener_service.query(
        index=index,
        preset_ids=preset_ids,
        filters=parsed_filters,
        sort_key=sort,
        direction=dir,
        limit=limit,
    )
    stale = bool(result.get("stale")) if isinstance(result, dict) else False
    return pv.attach(result, {
        "*": pv.derived(
            f"fundamentals, prices and technical indicators for each {index} member, filtered and sorted",
            [pv.ref("yahoo", None, "Quote snapshot, statements and daily prices of each member",
                    observed=result.get("asOf") if isinstance(result, dict) else None,
                    flags=("stale",) if stale else (),
                    note="Served from the overnight screener cache; refreshed in the background when stale."),
             pv.ref("wikipedia", None, f"Current {index} constituents")],
            title="Screener universe"),
    })
