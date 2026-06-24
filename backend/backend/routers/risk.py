"""Risk & Rolling Metrics endpoints — Phase 6."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from ..services import yfinance_service as yfs
from ..services import advanced_risk as ar
from ..services.discount_rates import risk_free_rate
from ..cache import cached

router = APIRouter(prefix="/api/risk", tags=["risk"])


def _parse_tickers(tickers: str) -> list[str]:
    return [t.strip().upper() for t in tickers.split(",") if t.strip()]


def _benchmarks_for(syms: list[str], override: str | None) -> tuple[list[str], dict[str, str]]:
    ov = override.strip().upper() if override and override.strip() else None
    mapping = {s: (ov or yfs.benchmark_for(s)) for s in syms}
    return sorted(set(mapping.values())), mapping


# ──────────────────────────────────────────────────────────────────────────────
# 🟢 Default tier — cached 60 min
# ──────────────────────────────────────────────────────────────────────────────

@cached("risk_rolling")
def _rolling_sync(tickers_key: str, period: str, window: int, benchmark: str | None) -> dict:
    syms = _parse_tickers(tickers_key)
    benchmarks, bench_map = _benchmarks_for(syms, benchmark)
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    import pandas as pd
    frame = yfs.get_close_frame(all_syms, period)
    if frame is None or frame.empty:
        return {"tickers": [], "period": period, "window": window}

    rf = risk_free_rate()
    results = []
    for sym in syms:
        if sym not in frame.columns:
            continue
        prices = frame[sym].dropna()
        bench = bench_map[sym]
        bench_prices = frame[bench] if bench in frame.columns else None
        payload = ar.rolling_metrics_for_ticker(prices, bench_prices, rf, window)
        payload["ticker"] = sym
        payload["benchmark"] = bench
        results.append(payload)

    return {"tickers": results, "period": period, "window": window}


@router.get("/rolling")
async def rolling_metrics(
    tickers: str = Query(...),
    period: str = "3y",
    window: int = 252,
    benchmark: str | None = None,
):
    return await asyncio.to_thread(_rolling_sync, tickers, period, window, benchmark)


@cached("risk_extended")
def _extended_sync(tickers_key: str, period: str, benchmark: str | None) -> dict:
    syms = _parse_tickers(tickers_key)
    benchmarks, bench_map = _benchmarks_for(syms, benchmark)
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    frame = yfs.get_close_frame(all_syms, period)
    if frame is None or frame.empty:
        return {"tickers": [], "period": period}

    rf = risk_free_rate()
    results = []
    for sym in syms:
        if sym not in frame.columns:
            continue
        prices = frame[sym].dropna()
        bench = bench_map[sym]
        bench_prices = frame[bench].dropna() if bench in frame.columns else None

        from ..services.metrics import log_returns
        ret = log_returns(prices)
        bench_ret = log_returns(bench_prices) if bench_prices is not None else None
        metrics = ar.extended_metrics(ret, bench_ret, rf, prices)
        metrics["ticker"] = sym
        metrics["benchmark"] = bench
        results.append(metrics)

    return {"tickers": results, "period": period}


@router.get("/extended")
async def extended_metrics(
    tickers: str = Query(...),
    period: str = "3y",
    benchmark: str | None = None,
):
    return await asyncio.to_thread(_extended_sync, tickers, period, benchmark)


@cached("risk_correlation")
def _correlation_sync(tickers_key: str, period: str, window: int) -> dict:
    syms = _parse_tickers(tickers_key)
    frame = yfs.get_close_frame(tuple(syms), period)
    if frame is None or frame.empty:
        return {"snapshots": [], "tickers": syms}

    from ..services.metrics import log_returns
    rets = frame[syms].apply(log_returns).dropna()
    snapshots = ar.rolling_correlation_matrix(rets, window)
    return {"snapshots": snapshots, "tickers": syms, "window": window}


@router.get("/correlation")
async def correlation(
    tickers: str = Query(...),
    period: str = "3y",
    window: int = 252,
):
    return await asyncio.to_thread(_correlation_sync, tickers, period, window)


# ──────────────────────────────────────────────────────────────────────────────
# 🟡 On-demand tier — uncached, POST
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/garch")
async def garch(ticker: str = Query(...), period: str = "2y"):
    def _run():
        syms = (ticker.upper(),)
        frame = yfs.get_close_frame(syms, period)
        if frame is None or frame.empty or ticker.upper() not in frame.columns:
            return {"error": "No price data"}
        from ..services.metrics import log_returns
        ret = log_returns(frame[ticker.upper()].dropna())
        return ar.garch_fit(ret)

    return await asyncio.to_thread(_run)


@router.post("/hurst")
async def hurst(ticker: str = Query(...), period: str = "3y"):
    def _run():
        syms = (ticker.upper(),)
        frame = yfs.get_close_frame(syms, period)
        if frame is None or frame.empty or ticker.upper() not in frame.columns:
            return {"error": "No price data"}
        return ar.hurst_exponent(frame[ticker.upper()].dropna())

    return await asyncio.to_thread(_run)


@router.post("/ou")
async def ornstein_uhlenbeck(tickers: str = Query(...), period: str = "2y"):
    def _run():
        syms = _parse_tickers(tickers)
        frame = yfs.get_close_frame(tuple(syms), period)
        if frame is None or frame.empty:
            return {"results": []}
        results = []
        for sym in syms:
            if sym not in frame.columns:
                continue
            fit = ar.ou_fit(frame[sym].dropna())
            fit["ticker"] = sym
            results.append(fit)
        return {"results": results}

    return await asyncio.to_thread(_run)


@router.post("/cointegration")
async def cointegration(tickers: str = Query(...), period: str = "3y"):
    def _run():
        syms = _parse_tickers(tickers)
        if len(syms) < 2:
            return {"error": "Provide at least 2 tickers"}
        frame = yfs.get_close_frame(tuple(syms), period)
        if frame is None or frame.empty:
            return {"error": "No price data"}
        available = [s for s in syms if s in frame.columns]
        if len(available) < 2:
            return {"error": "Not enough tickers with data"}
        result = ar.cointegration_test(frame[available[:2]].dropna())
        result["ticker1"] = available[0]
        result["ticker2"] = available[1]
        return result

    return await asyncio.to_thread(_run)


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 User-triggered tier — uncached, POST
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/montecarlo")
async def monte_carlo(
    ticker: str = Query(...),
    period: str = "2y",
    sims: int = 10_000,
    horizon: int = 1,
):
    def _run():
        syms = (ticker.upper(),)
        frame = yfs.get_close_frame(syms, period)
        if frame is None or frame.empty or ticker.upper() not in frame.columns:
            return {"error": "No price data"}
        from ..services.metrics import log_returns
        ret = log_returns(frame[ticker.upper()].dropna())
        return ar.monte_carlo_var(ret, sims=min(sims, 50_000), horizon=horizon)

    return await asyncio.to_thread(_run)


@router.post("/stress")
async def stress_test(
    ticker: str = Query(...),
    scenarios: str = Query(default="gfc,covid,rates,dotcom"),
    benchmark: str | None = None,
):
    def _run():
        sym = ticker.upper()
        scenario_list = [s.strip().lower() for s in scenarios.split(",") if s.strip()]
        bench_sym = (benchmark or yfs.benchmark_for(sym)).upper()

        # Fetch longest available history (10y)
        all_syms = tuple(dict.fromkeys([sym, bench_sym]))
        frame = yfs.get_close_frame(all_syms, "10y")
        if frame is None or frame.empty or sym not in frame.columns:
            return {"error": "No price data"}

        prices = frame[sym].dropna()
        bench_prices = frame[bench_sym].dropna() if bench_sym in frame.columns else None

        results = []
        for key in scenario_list:
            res = ar.stress_test_returns(prices, key, bench_prices)
            results.append(res)

        return {"ticker": sym, "benchmark": bench_sym, "scenarios": results}

    return await asyncio.to_thread(_run)
