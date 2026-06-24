"""Snowflake Composite Score router — Phase 9."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import snowflake_service

router = APIRouter(prefix="/api/snowflake", tags=["snowflake"])


@router.get("")
async def get_snowflake(ticker: str = Query(..., description="Stock ticker symbol")):
    """Full Snowflake score for a single ticker (5 axes, 0–10 each)."""
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        return snowflake_service.compute_snowflake(ticker.upper().strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/batch")
async def get_snowflake_batch(
    tickers: str = Query(..., description="Comma-separated ticker symbols"),
):
    """Lightweight Snowflake scores for multiple tickers (cache-only)."""
    if not tickers:
        raise HTTPException(status_code=400, detail="tickers is required")
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No valid tickers provided")
    # Stable cache key: sorted, joined
    tickers_key = ",".join(sorted(set(ticker_list)))
    try:
        return snowflake_service.compute_snowflake_batch(tickers_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
