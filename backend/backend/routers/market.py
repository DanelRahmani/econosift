"""Market data: prices, quote, risk metrics."""
from __future__ import annotations

import asyncio
import pandas as pd
from fastapi import APIRouter, Query

from ..services import yfinance_service as yfs
from ..services import metrics
from ..services import fx_service

router = APIRouter(prefix="/api/market", tags=["market"])


def _parse_tickers(tickers: str) -> list[str]:
    return [t.strip().upper() for t in tickers.split(",") if t.strip()]


# S&P 500 sector SPDR ETFs used as sector performance proxies.
SECTOR_ETFS = [
    ("XLK", "Technology"), ("XLF", "Financials"), ("XLV", "Health Care"),
    ("XLE", "Energy"), ("XLI", "Industrials"), ("XLY", "Consumer Discretionary"),
    ("XLP", "Consumer Staples"), ("XLU", "Utilities"), ("XLB", "Materials"),
    ("XLRE", "Real Estate"), ("XLC", "Communication Services"),
]


def _pct_change(series: pd.Series) -> float | None:
    s = series.dropna()
    if len(s) < 2 or s.iloc[0] == 0:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0, 2)


def _benchmarks_for(syms: list[str], override: str | None) -> tuple[list[str], dict[str, str]]:
    """Resolve a benchmark per symbol, honouring a manual override if given."""
    ov = override.strip().upper() if override and override.strip() else None
    mapping = {s: (ov or yfs.benchmark_for(s)) for s in syms}
    return sorted(set(mapping.values())), mapping


@router.get("/prices")
async def prices(tickers: str = Query(...), period: str = "1y",
                 benchmark: str | None = None):
    syms = _parse_tickers(tickers)
    benchmarks, _ = _benchmarks_for(syms, benchmark)
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


@router.get("/events/{ticker}")
async def events(ticker: str):
    """Upcoming earnings, recent dividends and splits for event overlays."""
    return await asyncio.to_thread(yfs.get_events, ticker.upper())


@router.get("/news/{ticker}")
async def news(ticker: str):
    """Recent headlines with keyword sentiment scoring."""
    return await asyncio.to_thread(yfs.get_news, ticker.upper())


@router.get("/sectors")
async def sectors(period: str = "1mo"):
    """Performance of the 11 S&P 500 sector SPDR ETFs over a period."""
    syms = tuple(e[0] for e in SECTOR_ETFS)
    frame = await asyncio.to_thread(yfs.get_close_frame, syms, period)
    rows = []
    for sym, name in SECTOR_ETFS:
        change = _pct_change(frame[sym]) if frame is not None and sym in frame.columns else None
        rows.append({"ticker": sym, "sector": name, "changePercent": change})
    rows.sort(key=lambda r: (r["changePercent"] is None, -(r["changePercent"] or 0)))
    return {"period": period, "sectors": rows}


@router.get("/relative-strength")
async def relative_strength(tickers: str = Query(...)):
    """Rank tickers by 1/3/6-month returns vs their benchmark."""
    syms = _parse_tickers(tickers)
    benchmarks = sorted({yfs.benchmark_for(s) for s in syms})
    all_syms = tuple(dict.fromkeys(syms + benchmarks))
    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, "1y")

    windows = {"ret1m": 21, "ret3m": 63, "ret6m": 126}
    rows = []
    if frame is not None and not frame.empty:
        for sym in syms:
            if sym not in frame.columns:
                continue
            s = frame[sym].dropna()
            bench = yfs.benchmark_for(sym)
            b = frame[bench].dropna() if bench in frame.columns else None
            row = {"ticker": sym, "benchmark": bench}
            for key, n in windows.items():
                row[key] = _trailing_return(s, n)
                bret = _trailing_return(b, n) if b is not None else None
                row[key + "Rel"] = (round(row[key] - bret, 2)
                                    if row[key] is not None and bret is not None else None)
            rows.append(row)
    rows.sort(key=lambda r: (r.get("ret3m") is None, -(r.get("ret3m") or 0)))
    return {"rankings": rows}


def _trailing_return(series: pd.Series, n: int) -> float | None:
    s = series.dropna()
    if len(s) <= n or s.iloc[-n - 1] == 0:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[-n - 1]) - 1.0) * 100.0, 2)


@router.get("/fx-rates")
async def fx_rates_endpoint(base: str = "USD"):
    """FX rates panel: 16 currency pairs vs base with changes and sparklines."""
    return await asyncio.to_thread(fx_service.fx_rates, base.upper())


@router.get("/risk")
async def risk(tickers: str = Query(...), period: str = "1y",
               risk_free: float = 0.04, benchmark: str | None = None):
    syms = _parse_tickers(tickers)
    benchmarks, bench_map = _benchmarks_for(syms, benchmark)
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)
    out_metrics = []
    if frame is not None and not frame.empty:
        for sym in syms:
            if sym not in frame.columns:
                continue
            bench = bench_map[sym]
            bench_series = frame[bench] if bench in frame.columns else None
            m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
            m["ticker"] = sym
            m["benchmark"] = bench
            out_metrics.append(m)

    return {"metrics": out_metrics}
