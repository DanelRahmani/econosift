"""Market data: prices, quote, risk metrics."""
from __future__ import annotations

import asyncio
import pandas as pd
from fastapi import APIRouter, Query

from .. import provenance as pv
from ..services import yfinance_service as yfs
from ..services import metrics
from ..services import fx_service
from ..services import discount_rates

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
    if frame is None or not hasattr(frame, "empty") or frame.empty:
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

    adj = "price, split- and dividend-adjusted"
    prov = {"*": pv.ref("yahoo", None, "Daily adjusted close", units=adj, frequency="daily",
                        observed=pv.last_date(frame))}
    for c in present:
        prov[f"prices.{c}"] = pv.yahoo(c, "Daily adjusted close", units=adj, frequency="daily",
                                       observed=pv.last_date(frame[c]))
    return pv.attach({
        "prices": records,
        "benchmarks": [b for b in benchmarks if b in present],
        "missing": missing,
    }, prov)


@router.get("/quote/{ticker}")
async def quote(ticker: str):
    sym = ticker.upper()
    result = await asyncio.to_thread(yfs.get_quote, sym)
    prov = {
        "*": pv.yahoo(sym, "Quote: last price and previous close",
                      note="Yahoo fast_info (last price, previous close), falling back to the info snapshot "
                           "(currentPrice / regularMarketPrice); Yahoo quotes can lag the exchange."),
        "changePercent": pv.derived("(last price − previous close) / previous close × 100",
                                    [pv.yahoo(sym, "Last price and previous close")],
                                    title="Change vs previous close"),
    }
    return pv.attach(result, prov)


@router.get("/events/{ticker}")
async def events(ticker: str):
    """Upcoming earnings, recent dividends and splits for event overlays."""
    sym = ticker.upper()
    result = await asyncio.to_thread(yfs.get_events, sym)
    return pv.attach(result, {
        "*": pv.yahoo(sym, "Corporate events (earnings calendar, dividends, splits)"),
        "earnings": pv.yahoo(sym, "Next earnings date (calendar)"),
        "dividends": pv.yahoo(sym, "Dividend history, most recent 12 payments", units="currency per share"),
        "splits": pv.yahoo(sym, "Stock split history, most recent 8", units="split ratio"),
    })


@router.get("/news/{ticker}")
async def news(ticker: str):
    """Recent headlines with keyword sentiment scoring."""
    sym = ticker.upper()
    result = await asyncio.to_thread(yfs.get_news, sym)
    return pv.attach(result, {
        "*": pv.yahoo(sym, "Recent news headlines (up to 12)",
                      note="Headlines are syndicated by Yahoo Finance; each item's publisher is the originating outlet."),
        "news.sentiment": pv.derived(
            "positive if the headline has more positive than negative keywords, negative if more negative, else neutral",
            title="Headline keyword sentiment", note="A fixed keyword list applied to the title, not a model."),
    })


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
    formula = f"(last adjusted close / first adjusted close in the {period} window − 1) × 100"
    prov = {"*": pv.derived(formula, [pv.ref("yahoo", None, "Sector SPDR ETF daily adjusted close",
                                             frequency="daily", observed=pv.last_date(frame))],
                            title="Sector ETF performance")}
    names = dict(SECTOR_ETFS)
    for r in rows:
        sym = r["ticker"]
        if frame is not None and sym in frame.columns:
            prov[f"sectors.{sym}"] = pv.derived(
                formula, [pv.yahoo(sym, f"{names[sym]} sector SPDR ETF, daily adjusted close", frequency="daily",
                                   observed=pv.last_date(frame[sym]))],
                title=f"{names[sym]} ({sym}) performance")
    return pv.attach({"period": period, "sectors": rows}, prov)


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
    formula = ("retNm = (close / close 21/63/126 trading days earlier − 1) × 100; "
               "…Rel = ticker return − benchmark return over the same window")
    prov = {"*": pv.derived(formula, [pv.ref("yahoo", None, "Daily adjusted close, tickers and benchmarks",
                                             frequency="daily", observed=pv.last_date(frame))],
                            title="Relative strength vs benchmark")}
    for r in rows:
        sym, bench = r["ticker"], r["benchmark"]
        inputs = [pv.yahoo(sym, "Daily adjusted close", frequency="daily", observed=pv.last_date(frame[sym])),
                  pv.yahoo(bench, "Benchmark daily adjusted close", frequency="daily",
                           observed=pv.last_date(frame[bench]) if bench in frame.columns else None)]
        prov[f"rankings.{sym}"] = pv.derived(formula, inputs, title=f"{sym} relative strength vs {bench}")
    return pv.attach({"rankings": rows}, prov)


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
               risk_free: float | None = None, benchmark: str | None = None):
    syms = _parse_tickers(tickers)
    if risk_free is not None:
        rf_source = "request parameter"
    else:
        risk_free, rf_source = await asyncio.to_thread(discount_rates.short_risk_free_rate_with_source)
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

    return pv.attach({"metrics": out_metrics, "riskFree": risk_free, "riskFreeSource": rf_source},
                     _risk_provenance(out_metrics, frame, period, risk_free, rf_source))


def _risk_provenance(rows: list[dict], frame, period: str, risk_free: float, rf_source: str) -> dict:
    """``metrics.<ticker>`` and ``metrics.<ticker>.<field>`` for each risk row."""
    rf = f"rf = {risk_free:g} ({rf_source})"
    prov: dict = {"*": pv.derived(
        "annualised statistics of daily log returns of the adjusted close; beta is benchmark-relative",
        [pv.ref("yahoo", None, f"Daily adjusted close, {period}", frequency="daily",
                observed=pv.last_date(frame))],
        title="Risk metrics")}
    for row in rows:
        sym, bench = row["ticker"], row["benchmark"]
        inputs = [pv.yahoo(sym, f"Daily adjusted close, {period}", frequency="daily",
                           observed=pv.last_date(frame[sym])),
                  pv.yahoo(bench, f"Benchmark daily adjusted close, {period}", frequency="daily",
                           observed=pv.last_date(frame[bench]) if bench in frame.columns else None)]
        base = f"metrics.{sym}"
        prov[base] = pv.derived("statistics of daily log returns r = ln(close / previous close), 252 trading days a year",
                                inputs, title=f"{sym} risk metrics")
        for field, formula, title in (
            ("annVolatility", "stdev(r, ddof=1) × √252", "Annualised volatility"),
            ("dailyMeanReturn", "mean(r)", "Mean daily log return"),
            ("var95", "5th percentile of r (historical 1-day VaR)", "1-day 95% VaR"),
            ("cvar95", "mean of r over days where r ≤ VaR95", "1-day 95% CVaR (expected shortfall)"),
            ("sharpe", f"(mean(R) × 252 − rf) / (stdev(R, ddof=1) × √252) of simple returns R = close / previous close − 1; {rf}", "Sharpe ratio"),
            ("sortino", f"(mean(R) × 252 − rf) / (√mean(min(R − rf/252, 0)²) × √252) of simple returns R; {rf}", "Sortino ratio"),
            ("beta", f"cov(r, r_benchmark) / var(r_benchmark) over common days, benchmark {bench}", "Beta"),
        ):
            prov[f"{base}.{field}"] = pv.derived(formula, inputs, title=title)
    return prov
