"""Corporate Health router — Phase 27.

Altman Z-Score, Piotroski F-Score, and Beneish M-Score for any ticker.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from ..services import corporate_health_service

router = APIRouter(prefix="/api/corporate", tags=["corporate"])


@router.get("/health")
async def corporate_health(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Return Altman Z-Score, Piotroski F-Score, and Beneish M-Score for a ticker."""
    try:
        ticker = ticker.strip().upper()
        if not ticker or len(ticker) > 12:
            raise HTTPException(status_code=400, detail="Invalid ticker")
        result = corporate_health_service.get_corporate_health(ticker)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/earnings-quality")
async def earnings_quality(universe: str = Query("dow", pattern="^(dow|ndx|sp500)$")):
    """Sloan (1996) accruals-anomaly earnings quality monitor for an index universe."""
    try:
        return await asyncio.to_thread(corporate_health_service.get_earnings_quality, universe)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
