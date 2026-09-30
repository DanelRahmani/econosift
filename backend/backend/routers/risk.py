"""Risk & Rolling Metrics endpoints — Phase 6."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from .. import provenance as pv
from ..services import yfinance_service as yfs
from ..services import advanced_risk as ar
from ..services.discount_rates import risk_free_rate, risk_free_rate_is_fallback
from ..cache import cached

router = APIRouter(prefix="/api/risk", tags=["risk"])


def _parse_tickers(tickers: str) -> list[str]:
    return [t.strip().upper() for t in tickers.split(",") if t.strip()]


def _benchmarks_for(syms: list[str], override: str | None) -> tuple[list[str], dict[str, str]]:
    ov = override.strip().upper() if override and override.strip() else None
    mapping = {s: (ov or yfs.benchmark_for(s)) for s in syms}
    return sorted(set(mapping.values())), mapping


def _px_ref(frame, sym: str) -> dict:
    return pv.yahoo(sym, "Daily adjusted close", units="price (split/dividend adjusted)",
                    frequency="daily", observed=pv.last_date(frame[sym]))


def _rf_ref() -> dict:
    """The risk-free rate these calculations use: FRED DGS10, or the 4% fallback."""
    if risk_free_rate_is_fallback():
        return pv.fred("DGS10", "10-year Treasury yield used as the risk-free rate", flags=("fallback",),
                       note="FRED was unreachable, so a hard-coded 4% stood in for the risk-free rate.")
    return pv.fred("DGS10", "10-year Treasury yield used as the risk-free rate", units="% p.a.",
                   frequency="daily")


_ROLLING_FORMULAS = {
    "volatility": "rolling {w}-day sample std of daily log returns × √252",
    "sharpe": "rolling {w}-day mean of (daily log return − rf/252) × 252 ÷ (rolling std of daily log return × √252)",
    "sortino": ("rolling {w}-day mean excess return × 252 ÷ (√mean(min(daily log return − rf/252, 0)²) "
                "over the window × √252)"),
    "maxDrawdown": "worst (price ÷ running peak − 1) inside each rolling {w}-day window of adjusted closes",
    "var95": "rolling {w}-day historical 5th percentile of daily log returns (a return, not a currency amount)",
    "var99": "rolling {w}-day historical 1st percentile of daily log returns (a return, not a currency amount)",
    "beta": "rolling {w}-day cov(daily log return, benchmark daily log return) ÷ var(benchmark)",
}

# metric -> (formula, inputs); "{s}" is the ticker's key, "{b}" its benchmark's.
_EXTENDED_FORMULAS = {
    "annReturn": ("mean daily log return × 252", ["prices.{s}"]),
    "annVolatility": ("sample std of daily log returns × √252", ["prices.{s}"]),
    "maxDrawdown": ("worst (adjusted close ÷ running peak − 1) over the whole period", ["prices.{s}"]),
    "calmar": ("annReturn ÷ |maxDrawdown|", ["prices.{s}"]),
    "omega": ("mean(max(r − rf/252, 0)) ÷ mean(max(rf/252 − r, 0)) of daily log returns", ["prices.{s}", "riskFree"]),
    "beta": ("cov(daily log return, benchmark daily log return) ÷ var(benchmark), on shared dates",
             ["prices.{s}", "prices.{b}"]),
    "alpha": ("Jensen's alpha: annReturn − (rf + beta × (benchmark annReturn − rf))",
              ["prices.{s}", "prices.{b}", "riskFree"]),
    "treynor": ("(annReturn − rf) ÷ beta", ["prices.{s}", "prices.{b}", "riskFree"]),
    "systematicVar": ("beta² × variance of the benchmark's daily log return (a daily variance)",
                      ["prices.{s}", "prices.{b}"]),
    "idiosyncraticVar": ("max(variance of daily log return − systematicVar, 0)", ["prices.{s}", "prices.{b}"]),
    "rSquared": ("systematicVar ÷ variance of daily log return", ["prices.{s}", "prices.{b}"]),
    "var95Historical": ("5th percentile of daily log returns (a return, not a currency amount)", ["prices.{s}"]),
    "var99Historical": ("1st percentile of daily log returns (a return, not a currency amount)", ["prices.{s}"]),
    "cvar95": ("mean of the daily log returns at or below var95Historical", ["prices.{s}"]),
    "cvar99": ("mean of the daily log returns at or below var99Historical", ["prices.{s}"]),
}


def _ticker_prices(prov: dict, frame, sym: str, bench: str | None) -> None:
    prov[f"prices.{sym}"] = _px_ref(frame, sym)
    if bench and bench in frame.columns:
        prov[f"prices.{bench}"] = _px_ref(frame, bench)


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

    prov: dict = {
        "*": pv.derived("Rolling-window risk statistics of daily log returns of adjusted closes",
                        [_px_ref(frame, r["ticker"]) for r in results], title="Rolling risk metrics"),
        "riskFree": _rf_ref(),
    }
    for r in results:
        sym, bench = r["ticker"], r["benchmark"]
        _ticker_prices(prov, frame, sym, bench)
        for metric, formula in _ROLLING_FORMULAS.items():
            inputs = [f"prices.{sym}"]
            if metric == "beta":
                inputs.append(f"prices.{bench}")
            if metric in ("sharpe", "sortino"):
                inputs.append("riskFree")
            prov[f"tickers.{sym}.{metric}"] = pv.derived(
                formula.format(w=window), inputs, title=f"Rolling {metric}",
                observed=pv.last_date(frame[sym]))
    return pv.attach({"tickers": results, "period": period, "window": window}, prov)


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

    prov: dict = {
        "*": pv.derived("Point-in-time risk statistics over the whole period, from daily log returns of adjusted closes",
                        [_px_ref(frame, r["ticker"]) for r in results], title="Extended risk metrics"),
        "riskFree": _rf_ref(),
    }
    for r in results:
        sym, bench = r["ticker"], r["benchmark"]
        _ticker_prices(prov, frame, sym, bench)
        for metric, (formula, inputs) in _EXTENDED_FORMULAS.items():
            prov[f"tickers.{sym}.{metric}"] = pv.derived(
                formula, [i.format(s=sym, b=bench) for i in inputs], title=metric,
                observed=pv.last_date(frame[sym]))
    return pv.attach({"tickers": results, "period": period}, prov)


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
    prov = {"*": pv.derived(
        f"Pearson correlation of daily log returns over trailing {window}-session windows, one snapshot every 21 sessions",
        [pv.ref("yahoo", None, "Daily adjusted close of the requested tickers", frequency="daily",
                observed=pv.last_date(frame))], title="Rolling correlation matrix")}
    return pv.attach({"snapshots": snapshots, "tickers": syms, "window": window}, prov)


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
        result = ar.garch_fit(ret)
        if "error" in result:
            return result
        px = _px_ref(frame, ticker.upper())
        fit = "GARCH(1,1) fitted by maximum likelihood (arch library, normal errors) to daily log returns × 100"
        return pv.attach(result, {
            "*": pv.derived(fit, [px], title="GARCH(1,1)"),
            "omega": pv.derived(fit + "; omega is in %² (squared percent) per day", [px], title="GARCH omega"),
            "forecastVol": pv.derived("√(1-step-ahead conditional variance) ÷ 100 — a daily volatility", [px],
                                      title="Forecast daily volatility"),
            "annForecastVol": pv.derived("forecastVol × √252", [px], title="Annualised forecast volatility"),
        })

    return await asyncio.to_thread(_run)


@router.post("/hurst")
async def hurst(ticker: str = Query(...), period: str = "3y"):
    def _run():
        syms = (ticker.upper(),)
        frame = yfs.get_close_frame(syms, period)
        if frame is None or frame.empty or ticker.upper() not in frame.columns:
            return {"error": "No price data"}
        result = ar.hurst_exponent(frame[ticker.upper()].dropna())
        return pv.attach(result, {
            "*": pv.derived(
                "Rescaled-range (R/S) analysis of daily log returns over lags 8 to min(n/2, 200); each R/S is divided "
                "by the Anis-Lloyd expected R/S for iid data and H = 0.5 + slope of log(R/S ÷ expected) on log(lag)",
                [_px_ref(frame, ticker.upper())], title="Hurst exponent"),
            "interpretation": pv.derived("H < 0.4 mean-reverting, 0.4 to 0.6 random walk, H > 0.6 trending",
                                         ["*"], title="Hurst interpretation"),
        })

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
        prov: dict = {"*": pv.derived(
            "Ornstein-Uhlenbeck fit by OLS of P(t+1) on P(t) over daily adjusted-close levels: b = slope, a = intercept",
            [pv.ref("yahoo", None, "Daily adjusted close of the requested tickers", frequency="daily",
                    observed=pv.last_date(frame))], title="Ornstein-Uhlenbeck fit")}
        for r in results:
            prov[f"results.{r['ticker']}.theta"] = pv.derived("theta = −ln(b) × 252", ["*"], title="Mean-reversion speed")
            prov[f"results.{r['ticker']}.mu"] = pv.derived("mu = a ÷ (1 − b), in price units", ["*"], title="Long-run mean")
            prov[f"results.{r['ticker']}.sigma"] = pv.derived(
                "sample std of the OLS residuals (ddof = 2) ÷ √(1/252)", ["*"], title="Volatility")
            prov[f"results.{r['ticker']}.halfLifeDays"] = pv.derived(
                "ln 2 ÷ theta × 252 (in trading days)", ["*"], title="Half-life")
        return pv.attach({"results": results}, prov)

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
        if "error" in result:
            return result
        px = pv.ref("yahoo", None, f"Daily adjusted close of {available[0]} and {available[1]}", frequency="daily",
                    observed=pv.last_date(frame[available[:2]].dropna()))
        return pv.attach(result, {
            "*": pv.derived("Engle-Granger cointegration test on the price levels of the first two tickers",
                            [px], title="Cointegration"),
            "pValue": pv.derived(
                "MacKinnon p-value of the Engle-Granger test (statsmodels coint, default settings) with ticker1 "
                "as the dependent series", [px], title="Engle-Granger p-value"),
            "isCointegrated": pv.derived("pValue < 0.05", ["pValue"], title="Cointegrated at 5%"),
            "hedgeRatio": pv.derived("OLS slope (with intercept) of ticker1's price on ticker2's price", [px],
                                     title="Hedge ratio"),
            "spread": pv.derived("ticker1 price − hedgeRatio × ticker2 price (the regression intercept is not removed)",
                                 ["hedgeRatio"], title="Spread"),
        })

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
        result = ar.monte_carlo_var(ret, sims=min(sims, 50_000), horizon=horizon)
        sim = (f"{min(sims, 50_000)} simulated {horizon}-day log returns, each the sum of {horizon} draws from "
               "Normal(mean, std) of the ticker's historical daily log returns (seed 42)")
        return pv.attach(result, {
            "*": pv.derived("Monte Carlo VaR: " + sim, [_px_ref(frame, ticker.upper())], title="Monte Carlo VaR"),
            "var95": pv.derived("5th percentile of the simulated returns (a return, not a currency amount)",
                                ["*"], title="VaR 95%"),
            "var99": pv.derived("1st percentile of the simulated returns (a return, not a currency amount)",
                                ["*"], title="VaR 99%"),
            "expected": pv.derived("mean of the simulated returns", ["*"], title="Expected return"),
            "worstCase": pv.derived("minimum of the simulated returns", ["*"], title="Worst simulated return"),
        })

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

        px = _px_ref(frame, sym)
        prov: dict = {"*": pv.derived(
            "Historical stress replay: the ticker's own price path inside fixed calendar windows (last 10 years "
            "of history only)", [px], title="Stress test")}
        for res in results:
            if "error" in res or "start" not in res:
                continue
            prov[f"scenarios.{res['scenario']}"] = pv.derived(
                f"totalReturn = exp(sum of daily log returns) − 1 from {res['start']} to {res['end']}; "
                "maxDrawdown = worst (price ÷ running peak − 1) inside the window; benchmark = the benchmark's "
                "cumulative return over the same window", [px], title=res.get("label"), observed=res["end"])
        return pv.attach({"ticker": sym, "benchmark": bench_sym, "scenarios": results}, prov)

    return await asyncio.to_thread(_run)
