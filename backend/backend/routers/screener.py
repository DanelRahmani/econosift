"""Multi-factor stock screener over a user-defined ticker universe."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from ..services import yfinance_service as yfs
from ..services import metrics

router = APIRouter(prefix="/api/screener", tags=["screener"])

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

    return {
        "fields": list(FIELDS.keys()),
        "filters": parsed_filters,
        "sort": sort_field,
        "count": len(matched),
        "screened": len(rows),
        "results": matched,
    }
