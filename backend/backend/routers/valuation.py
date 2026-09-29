"""CAPM + DCF valuation."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from ..services import yfinance_service as yfs
from ..services import metrics
from ..services.dcf_engine import two_stage_dcf
from ..services.valuation_engine import valuation_models
from ..services.fundamentals import extended_fundamentals
from ..services.analyst_service import analyst_data
from ..services import fama_french

router = APIRouter(prefix="/api/valuation", tags=["valuation"])


def _kpis(info: dict) -> dict:
    """Headline KPI + extended-fundamental fields straight from Ticker.info.

    Every access is guarded; short data is US-listed only and may be absent.
    """
    g = info.get
    mcap = g("marketCap")
    fcf = g("freeCashflow")
    ev = g("enterpriseValue")
    return {
        "price": g("currentPrice") or g("regularMarketPrice"),
        "marketCap": mcap,
        "trailingPE": g("trailingPE"),
        "forwardPE": g("forwardPE"),
        "trailingEps": g("trailingEps"),
        "forwardEps": g("forwardEps"),
        "dividendYield": g("dividendYield"),
        "fiftyTwoWeekHigh": g("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": g("fiftyTwoWeekLow"),
        "beta": g("beta"),
        "averageVolume": g("averageVolume") or g("averageDailyVolume10Day"),
        "bookValue": g("bookValue"),
        "evToFcf": (ev / fcf) if (ev and fcf) else None,
        "fcfYield": (fcf / mcap) if (fcf and mcap) else None,
        "shortPercentOfFloat": g("shortPercentOfFloat"),
        "shortRatio": g("shortRatio"),
        "sector": g("sector"),
        "industry": g("industry"),
        "currency": g("currency") or "USD",
    }


def _beta_for(sym: str) -> float | None:
    """Compute beta vs the symbol's benchmark over 2y of daily prices."""
    bench = yfs.benchmark_for(sym)
    frame = yfs.get_close_frame(tuple(dict.fromkeys([sym, bench])), "2y")
    if frame is None or frame.empty or sym not in frame.columns:
        return None
    bench_series = frame[bench] if bench in frame.columns else None
    m = metrics.risk_metrics(frame[sym], bench_series, 0.04)
    return m.get("beta")


def _signal(spot, target, expected_return) -> str:
    if spot is None or target is None:
        return "INCOMPLETE"
    upside = (target - spot) / spot
    if upside > 0.10:
        return "BUY"
    if upside < -0.10:
        return "OVERVALUED"
    return "FAIR VALUE"


@router.get("/capm-dcf")
async def capm_dcf(
    tickers: str = Query(...),
    period: str = "1y",
    risk_free: float = 0.04,
    market_premium: float = 0.055,
    fcf_growth: float = 0.08,
    terminal_growth: float = 0.025,
):
    syms = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    benchmarks = sorted({yfs.benchmark_for(s) for s in syms})
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)

    valuations = []
    for sym in syms:
        bench = yfs.benchmark_for(sym)
        beta = None
        if frame is not None and not frame.empty and sym in frame.columns:
            bench_series = frame[bench] if bench in frame.columns else None
            m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
            beta = m.get("beta")

        bundle = await asyncio.to_thread(yfs.get_info, sym)
        info = bundle.get("info", {}) or {}

        expected_return = metrics.capm_expected_return(beta, risk_free, market_premium)
        discount = expected_return if expected_return else risk_free + market_premium
        target = metrics.dcf_target(info, fcf_growth, terminal_growth, discount)

        spot = info.get("currentPrice") or info.get("regularMarketPrice")
        spot = float(spot) if spot else None

        valuations.append({
            "ticker": sym,
            "benchmark": bench,
            "beta": beta,
            "expectedReturn": expected_return,
            "trailingPE": info.get("trailingPE"),
            "spotPrice": spot,
            "dcfTarget": target,
            "currency": info.get("currency") or "USD",
            "signal": _signal(spot, target, expected_return),
        })

    return {"valuations": valuations}


@router.get("/risk-free-rates")
async def risk_free_rates():
    """Live country risk-free rates from FRED (cached nightly)."""
    from ..services.risk_free_service import get_risk_free_rates
    return {"rates": await get_risk_free_rates()}


@router.get("/dcf")
async def dcf(
    ticker: str,
    fcf_growth: float = 0.08,
    terminal_growth: float = 0.025,
    wacc: float = 0.09,
    stage1_years: int = 10,
):
    """Two-stage DCF valuation with scenario table and sensitivity heatmap."""
    bundle = await asyncio.to_thread(yfs.get_info, ticker.strip().upper())
    return two_stage_dcf(
        bundle,
        fcf_growth=fcf_growth,
        terminal_growth=terminal_growth,
        wacc=wacc,
        stage1_years=stage1_years,
    )


@router.get("/full")
async def full(ticker: str):
    """Full valuation bundle (compute tier: runs on page load).

    Combines the 8-model valuation engine + EconoSift composite, extended
    fundamentals (Piotroski / Beneish / Ohlson / DuPont / ROIC / CCC), and
    analyst data (price targets, consensus, surprises, estimates).
    """
    sym = ticker.strip().upper()
    bundle = await asyncio.to_thread(yfs.get_info, sym)
    beta = await asyncio.to_thread(_beta_for, sym)
    valuation = await asyncio.to_thread(valuation_models, bundle, beta)
    fundamentals = await asyncio.to_thread(extended_fundamentals, bundle)
    analyst = await asyncio.to_thread(analyst_data, sym)
    kpis = _kpis(bundle.get("info", {}) or {})
    # Fix 7: Inject computed beta when yfinance info.beta is null
    if kpis.get("beta") is None and beta is not None:
        kpis["beta"] = beta
    return {
        "ticker": sym,
        "kpis": kpis,
        "valuation": valuation,
        "fundamentals": fundamentals,
        "analyst": analyst,
    }


@router.get("/factors")
async def factors(ticker: str, model: str = "3", period: str = "2y"):
    """Fama-French 3F/5F per-ticker attribution (compute tier: on-demand)."""
    sym = ticker.strip().upper()
    return await asyncio.to_thread(
        fama_french.factor_regression, sym, model, period
    )
