"""Market data: prices, quote, risk metrics."""
from __future__ import annotations

import asyncio
import pandas as pd
from fastapi import APIRouter, Query

from ..services import yfinance_service as yfs
from ..services import metrics

router = APIRouter(prefix="/api/market", tags=["market"])


def _parse_tickers(tickers: str) -> list[str]:
    return [t.strip().upper() for t in tickers.split(",") if t.strip()]


@router.get("/prices")
async def prices(tickers: str = Query(...), period: str = "1y"):
    syms = _parse_tickers(tickers)
    benchmarks = sorted({yfs.benchmark_for(s) for s in syms})
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)
    if frame is None or frame.empty:
        return {"prices": [], "benchmarks": benchmarks, "missing": syms}

    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index).strftime("%Y-%m-%d")

    present = [c for c in all_syms if c in frame.columns]
    missing = [s for s in syms if s not in frame.columns]

    records = []
    for date, row in frame[present].iterrows():
        rec = {"Date": str(date)}
        for col in present:
            val = row[col]
            rec[col] = None if pd.isna(val) else round(float(val), 4)
        records.append(rec)

    return {
        "prices": records,
        "benchmarks": [b for b in benchmarks if b in present],
        "missing": missing,
    }


@router.get("/quote/{ticker}")
async def quote(ticker: str):
    return await asyncio.to_thread(yfs.get_quote, ticker.upper())


@router.get("/risk")
async def risk(tickers: str = Query(...), period: str = "1y",
               risk_free: float = 0.04):
    syms = _parse_tickers(tickers)
    benchmarks = sorted({yfs.benchmark_for(s) for s in syms})
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)
    out_metrics = []
    if frame is not None and not frame.empty:
        for sym in syms:
            if sym not in frame.columns:
                continue
            bench = yfs.benchmark_for(sym)
            bench_series = frame[bench] if bench in frame.columns else None
            m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
            m["ticker"] = sym
            m["benchmark"] = bench
            out_metrics.append(m)

    return {"metrics": out_metrics}
