"""EDGAR data router: 13F institutional holders and Form 4 insider transactions."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import edgar_service

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/13f")
async def holders_13f(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Top 13F institutional holders from the most recent quarterly filing."""
    return await edgar_service.get_13f_holders(ticker.upper())


@router.get("/form4")
async def form4_insiders(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Recent Form 4 insider buy/sell transactions (last 90 days)."""
    return await edgar_service.get_form4_insiders(ticker.upper())
