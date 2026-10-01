"""Insider Trading Aggregator router — Phase 27.

🟡 Compute tier — triggers aggregation across S&P 500 EDGAR Form 4 filings.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import insider_aggregator

router = APIRouter(prefix="/api/insider", tags=["insider"])


@router.get("/aggregate")
async def insider_aggregate():
    """🟡 Aggregate Form 4 insider transactions across S&P 500.
    
    First run is slow (100+ seconds). Subsequent calls use cache (6h TTL).
    """
    try:
        result = insider_aggregator.get_insider_aggregate()
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
