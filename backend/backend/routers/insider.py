"""Insider Trading Aggregator router — Phase 27.

🟡 Compute tier — aggregates the SEC's quarterly insider transactions data set over the S&P 500.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ..services import insider_aggregator

router = APIRouter(prefix="/api/insider", tags=["insider"])


@router.get("/aggregate")
async def insider_aggregate():
    """🟡 Aggregate open-market insider trades across the S&P 500 for the
    newest quarter the SEC has published. The first run downloads ~11 MB.
    """
    try:
        # A worker thread: the download and reduce are synchronous and would
        # otherwise freeze the event loop.
        result = await asyncio.to_thread(insider_aggregator.get_insider_aggregate)
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
