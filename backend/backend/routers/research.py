"""Research Hub router — Phase 14.

Three quantitative-research tools backed by existing data infrastructure:
- Risk Parity (inverse-vol / ERC weights + monthly-rebalanced backtest vs 60/40)
- FX Carry (G10 carry table + long-top3/short-bottom3 backtest)
- Cross-Sectional Momentum (decile sort over an index universe)
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import provenance as pv
from ..services import risk_parity_service as rp
from ..services import carry_service
from ..services import momentum_service
from ..services import realized_moments_service
from ..services import dupont_service
from ..services import cross_asset_service
from ..services import event_study_service
from ..services import fama_french as ff_service
from ..services import backtest_signals
from ..services.backtest_engine import LookaheadError, run_backtest

router = APIRouter(prefix="/api/research", tags=["research"])


class RiskParityRequest(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: ["SPY", "TLT", "GLD", "DJP"])
    period: str = "3y"
    mode: str = Field(default="erc", pattern="^(erc|invvol)$")
    backtest: bool = False


def _clean_tickers(raw: list[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for t in raw:
        s = t.strip().upper()
        if s and s not in seen:
            seen.append(s)
    return tuple(seen)


@router.post("/riskparity")
async def post_risk_parity(req: RiskParityRequest):
    tickers = _clean_tickers(req.tickers)
    if len(tickers) < 2:
        raise HTTPException(status_code=400, detail="at least 2 tickers required")
    try:
        if req.backtest:
            return await asyncio.to_thread(rp.risk_parity_backtest, tickers, req.period, req.mode)
        if req.mode == "invvol":
            return await asyncio.to_thread(rp.inverse_vol_weights, tickers, req.period)
        return await asyncio.to_thread(rp.erc_weights, tickers, req.period)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/carry")
async def get_carry(
    period: str = Query("3y"),
    backtest: bool = Query(False),
):
    try:
        if backtest:
            return await asyncio.to_thread(carry_service.get_carry_backtest, period)
        return await asyncio.to_thread(carry_service.get_carry_table, period)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/momentum")
async def get_momentum(
    universe: str = Query("dow", pattern="^(dow|ndx|sp500)$"),
    signal: str = Query("12m1m", pattern="^(1m|3m|6m|12m1m)$"),
):
    try:
        return await asyncio.to_thread(momentum_service.get_momentum, universe, signal)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/moments")
async def get_moments(
    ticker: str = Query(..., min_length=1, max_length=12),
    period: str = Query("3y", pattern=r"^(1y|2y|3y|5y|10y|max)$"),
):
    try:
        return await asyncio.to_thread(realized_moments_service.get_moments, ticker.strip().upper(), period)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/moments/crosssection")
async def get_moments_crosssection(
    universe: str = Query("dow", pattern="^(dow|ndx|sp500)$"),
    window: int = Query(21, ge=5, le=126),
):
    try:
        return await asyncio.to_thread(realized_moments_service.get_crosssection, universe, window)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dupont")
async def get_dupont():
    """Sector DuPont decomposition — median margin / turnover / leverage / ROE per GICS sector."""
    try:
        return await asyncio.to_thread(dupont_service.get_sector_dupont)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Phase 39: Cross-Asset & Factor Analytics ──────────────────────────

class CrossAssetRequest(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: ["SPY", "TLT", "GLD", "EURUSD=X"])
    period: str = Field(default="3y", pattern="^(1y|2y|3y|5y|max)$")


class MultiCountryHolding(BaseModel):
    ticker: str
    weight: float = Field(default=1.0, ge=0.0)
    currency: str = Field(default="USD")


class MultiCountryRequest(BaseModel):
    holdings: list[MultiCountryHolding]
    period: str = Field(default="3y", pattern="^(1y|2y|3y|5y|max)$")


# ── Phase 38b: Event Study Lab + Factor Regime ────────────────────────

class EventStudyRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=12)
    eventType: str = Field(default="earnings", pattern="^(earnings|fomc)$")
    window: int = Field(default=5, ge=1, le=10)


@router.post("/event-study")
async def post_event_study(req: EventStudyRequest):
    """CAR/AAR event study around earnings or FOMC dates (market model)."""
    try:
        return await asyncio.to_thread(
            event_study_service.run_event_study,
            req.ticker.strip().upper(), req.eventType, req.window,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/factor-regime")
async def get_factor_regime():
    """Fama-French factor regime: trailing returns, style leadership, cumulative growth."""
    try:
        return await asyncio.to_thread(ff_service.get_factor_regime)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/cross-asset-correlation")
async def cross_asset_correlation(req: CrossAssetRequest):
    """Cross-asset correlation matrix for mixed stocks/bonds/commodities/FX pairs."""
    try:
        return await cross_asset_service.get_cross_asset_correlations(req.tickers, req.period)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/fx-macro-link")
async def fx_macro_link():
    """FX / commodity / macro linkage — rolling correlations and lead/lag analysis."""
    try:
        return await cross_asset_service.get_fx_macro_link()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/multi-country-portfolio")
async def multi_country_portfolio(req: MultiCountryRequest):
    """Multi-country portfolio with FX-adjusted returns and currency exposure breakdown."""
    try:
        holdings = [{"ticker": h.ticker, "weight": h.weight, "currency": h.currency}
                     for h in req.holdings]
        return await cross_asset_service.get_multi_country_portfolio(holdings, req.period)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# --- Phase 43: signal backtester (compute tier: red / Run Analysis) ---

class BacktestRequest(BaseModel):
    signal: str = "momentum_12_1"
    universe: str = "sp500"
    period: str = "10y"
    rebalance: str = Field(default="M", pattern="^(W|M|Q)$")
    nQuantiles: int = Field(default=5, ge=2, le=10)
    costBps: float = Field(default=10.0, ge=0.0, le=500.0)
    longShort: bool = True
    pointInTimeUniverse: bool = True
    allowLookahead: bool = False


@router.get("/backtest/signals")
async def list_backtest_signals():
    """Registry of backtestable signals. All price-derived — see P3-14."""
    return {"signals": backtest_signals.available_signals()}


def _run_backtest_sync(req: "BacktestRequest") -> dict:
    signal, prices, meta = backtest_signals.build_signal(
        req.signal, universe=req.universe, period=req.period
    )

    universe_fn = None
    if req.pointInTimeUniverse:
        import datetime as _dt

        from ..services import constituents

        def universe_fn(d: _dt.date, _u=req.universe):
            return constituents.members_as_of(_u, d)["symbols"]

    result = run_backtest(
        signal,
        prices,
        rebalance=req.rebalance,
        n_quantiles=req.nQuantiles,
        long_short=req.longShort,
        cost_bps=req.costBps,
        universe_as_of=universe_fn,
        allow_lookahead=req.allowLookahead,
        is_fundamental=meta["isFundamental"],
    )
    result["meta"] = meta
    price_ref = pv.ref("yahoo", None, f"Daily adjusted close of each {req.universe} member",
                    frequency="daily", observed=pv.last_date(prices))
    members = pv.ref("wikipedia", None, f"{req.universe} constituents"
                     + (" as of each rebalance date (reconstructed from the change log)"
                        if req.pointInTimeUniverse else " (current members, so survivorship-biased)"))
    return pv.attach(result, {
        "*": pv.derived(
            f"each {req.rebalance} rebalance: rank members on the '{req.signal}' signal known at that date, "
            f"form {req.nQuantiles} equal-weight quantile portfolios, hold to the next rebalance; "
            f"{'top minus bottom quantile; ' if req.longShort else ''}costs {req.costBps} bps per unit turnover",
            [price_ref, members], title="Signal backtest"),
    })


@router.post("/backtest")
async def post_backtest(req: BacktestRequest):
    """Backtest a cross-sectional signal. Compute tier: red — never auto-fired.

    Downloads a price panel and runs a quantile sort, so it takes tens of
    seconds on a cold cache.
    """
    try:
        return await asyncio.to_thread(_run_backtest_sync, req)
    except LookaheadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc
