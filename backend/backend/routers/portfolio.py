"""Portfolio builder: aggregate performance & risk for a basket of holdings."""
from __future__ import annotations

import asyncio
from typing import Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import yfinance_service as yfs
from ..services import portfolio as port
from ..services.discount_rates import risk_free_rate

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class Holding(BaseModel):
    ticker: str
    weight: float = Field(default=1.0, ge=0.0)


class PortfolioRequest(BaseModel):
    holdings: list[Holding]
    period: str = "1y"
    risk_free: float = 0.04


class RollingRequest(PortfolioRequest):
    window: int = Field(default=60, ge=10, le=504)


class FFRequest(PortfolioRequest):
    model: str = Field(default="3", pattern="^[35]$")


class BLView(BaseModel):
    ticker: str
    expectedReturn: float


class BLRequest(PortfolioRequest):
    views: list[BLView] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_BENCH_COL = "^GSPC"
_AGG_COL = "AGG"


def _normalise(holdings_raw: list[Holding]) -> list[dict]:
    """Upper-case tickers, drop blanks."""
    return [
        {"ticker": h.ticker.strip().upper(), "weight": h.weight}
        for h in holdings_raw if h.ticker.strip()
    ]


async def _load_frame(holdings: list[dict], period: str,
                      extra: tuple[str, ...] = ()) -> pd.DataFrame | None:
    """Fetch close prices for holdings + any extra symbols."""
    syms = list(dict.fromkeys(h["ticker"] for h in holdings))
    all_syms = tuple(dict.fromkeys(syms + list(extra)))
    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)
    if frame is None or frame.empty:
        return None
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index)
    return frame


def _empty(msg: str = "no data") -> dict:
    return {"error": msg}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze(req: PortfolioRequest):
    """Full portfolio analysis: value series, metrics, drawdown, benchmarks."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"holdings": [], "series": [], "metrics": {}, "missing": []}

    syms = list(dict.fromkeys(h["ticker"] for h in holdings))
    bench = yfs.benchmark_for(syms[0])
    all_syms = tuple(dict.fromkeys(syms + [bench, _BENCH_COL, _AGG_COL]))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, req.period)
    if frame is None or frame.empty:
        return {"holdings": [], "series": [], "metrics": {}, "missing": syms}

    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index)
    bench_series = frame[bench] if bench in frame.columns else None

    result = port.analyze(frame, holdings, bench_series, req.risk_free)
    result["benchmark"] = bench

    # Add benchmark comparison series (base-100 ^GSPC / AGG)
    result["benchmarkSeries"] = port.benchmark_series(frame, req.period)

    return result


@router.post("/drawdown")
async def drawdown(req: PortfolioRequest):
    """Underwater drawdown curve for the portfolio."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"drawdownSeries": []}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present:
        return {"drawdownSeries": []}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}
    cols = list(weights.keys())

    px = frame[cols].dropna(how="all").ffill()
    rets = px.pct_change().dropna(how="all").fillna(0.0)
    import numpy as np
    w_vec = np.array([weights[c] for c in cols])
    port_ret = pd.Series(rets[cols].to_numpy() @ w_vec, index=rets.index)

    return {"drawdownSeries": port.drawdown_series(port_ret)}


@router.post("/benchmarks")
async def benchmarks(req: PortfolioRequest):
    """Base-100 cumulative return series for ^GSPC and AGG."""
    holdings = _normalise(req.holdings)
    frame = await _load_frame(holdings, req.period, extra=(_BENCH_COL, _AGG_COL))
    if frame is None:
        return {"gspc": [], "agg": []}
    return port.benchmark_series(frame, req.period)


@router.post("/correlation")
async def correlation(req: PortfolioRequest):
    """Pairwise Pearson correlation matrix for portfolio holdings."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"tickers": [], "matrix": []}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.correlation_matrix(holdings, frame)


@router.post("/risk-contribution")
async def risk_contribution(req: PortfolioRequest):
    """Marginal and percentage risk contribution per holding."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.risk_contribution(holdings, frame)


@router.post("/capm")
async def capm(req: PortfolioRequest):
    """CAPM attribution: alpha, beta, R², systematic/idiosyncratic variance."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return _empty("no holdings")

    syms = [h["ticker"] for h in holdings]
    bench = yfs.benchmark_for(syms[0])
    frame = await _load_frame(holdings, req.period, extra=(bench,))
    if frame is None:
        return _empty()

    return port.capm_attribution(holdings, frame, bench, req.risk_free)


@router.post("/rolling")
async def rolling(req: RollingRequest):
    """Rolling Sharpe, volatility, and beta (window parameter in body)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"window": req.window, "sharpe": [], "volatility": [], "beta": []}

    syms = [h["ticker"] for h in holdings]
    bench = yfs.benchmark_for(syms[0])
    frame = await _load_frame(holdings, req.period, extra=(bench,))
    if frame is None:
        return _empty()

    return port.rolling_portfolio_metrics(holdings, frame, bench, req.risk_free, req.window)


@router.post("/kelly")
async def kelly(req: PortfolioRequest):
    """Kelly criterion fractions for each holding (on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.kelly_criterion(holdings, frame)


@router.post("/ff")
async def fama_french(req: FFRequest):
    """Fama-French factor attribution for the portfolio (on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return _empty("no holdings")

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.ff_attribution_portfolio(holdings, frame, req.model, req.risk_free)


@router.post("/frontier")
async def frontier(req: PortfolioRequest):
    """Mean-variance efficient frontier (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"frontier": [], "error": "no holdings"}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.efficient_frontier(holdings, frame)


@router.post("/montecarlo")
async def montecarlo(req: PortfolioRequest):
    """Monte Carlo random weight simulation — risk/return cloud (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"points": [], "maxSharpe": {}}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.monte_carlo_weights(holdings, frame)


@router.post("/blacklitterman")
async def black_litterman(req: BLRequest):
    """Black-Litterman posterior + optimal weights (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return _empty("no holdings")

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    views = [{"ticker": v.ticker.strip().upper(), "expectedReturn": v.expectedReturn}
             for v in req.views]
    return port.black_litterman(holdings, frame, views, req.risk_free)


@router.post("/stress")
async def stress(req: PortfolioRequest):
    """Historical stress test across GFC / COVID / rate-shock / dot-com (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    syms = [h["ticker"] for h in holdings]
    bench = yfs.benchmark_for(syms[0])
    # Stress periods go back to 2000, so override period to max
    frame = await _load_frame(holdings, "max", extra=(bench,))
    if frame is None:
        return _empty()

    return port.stress_test_portfolio(holdings, frame, bench)
