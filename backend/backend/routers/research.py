"""Research Hub router — Phase 14.

Three quantitative-research tools backed by existing data infrastructure:
- Risk Parity (inverse-vol / ERC weights + monthly-rebalanced backtest vs 60/40)
- FX Carry (G10 carry table + long-top3/short-bottom3 backtest)
- Cross-Sectional Momentum (decile sort over an index universe)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services import risk_parity_service as rp
from ..services import carry_service
from ..services import momentum_service

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
            return rp.risk_parity_backtest(tickers, req.period, req.mode)
        if req.mode == "invvol":
            return rp.inverse_vol_weights(tickers, req.period)
        return rp.erc_weights(tickers, req.period)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/carry")
async def get_carry(
    period: str = Query("3y"),
    backtest: bool = Query(False),
):
    try:
        if backtest:
            return carry_service.get_carry_backtest(period)
        return carry_service.get_carry_table(period)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/momentum")
async def get_momentum(
    universe: str = Query("dow", pattern="^(dow|ndx|sp500)$"),
    signal: str = Query("12m1m", pattern="^(1m|3m|6m|12m1m)$"),
):
    try:
        return momentum_service.get_momentum(universe, signal)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc
