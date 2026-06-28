"""Dividend Analysis router — Phase 27."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import dividend_service

router = APIRouter(prefix="/api/dividend", tags=["dividend"])


@router.get("/analysis")
async def dividend_analysis(ticker: str = Query(..., description="Ticker symbol, e.g. KO, AAPL")):
    """Dividend yield, growth rates, payout ratio, sustainability, and DDM fair value."""
    try:
        ticker = ticker.strip().upper()
        if not ticker or len(ticker) > 12:
            raise HTTPException(status_code=400, detail="Invalid ticker")
        result = dividend_service.get_dividend_analysis(ticker)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
