"""Advanced technicals router — Phase 12."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import technicals_service

router = APIRouter(prefix="/api/technicals", tags=["technicals"])

_VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}


@router.get("")
async def get_technicals(
    ticker: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    period: str = Query("1y", description="Period: 1mo, 3mo, 6mo, 1y, 2y, 5y"),
):
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    if period not in _VALID_PERIODS:
        period = "1y"
    try:
        return technicals_service.get_technicals(ticker.upper().strip(), period)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
