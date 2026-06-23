"""Portfolio builder: aggregate performance & risk for a basket of holdings."""
from __future__ import annotations

import asyncio
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import yfinance_service as yfs
from ..services import portfolio as port

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class Holding(BaseModel):
    ticker: str
    weight: float = Field(default=1.0, ge=0.0)


class PortfolioRequest(BaseModel):
    holdings: list[Holding]
    period: str = "1y"
    risk_free: float = 0.04


@router.post("/analyze")
async def analyze(req: PortfolioRequest):
    holdings = [{"ticker": h.ticker.strip().upper(), "weight": h.weight}
                for h in req.holdings if h.ticker.strip()]
    if not holdings:
        return {"holdings": [], "series": [], "metrics": {}, "missing": []}

    syms = list(dict.fromkeys(h["ticker"] for h in holdings))
    # Use the most common benchmark across holdings for the portfolio beta.
    bench = yfs.benchmark_for(syms[0])
    all_syms = tuple(dict.fromkeys(syms + [bench]))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, req.period)
    if frame is None or frame.empty:
        return {"holdings": [], "series": [], "metrics": {}, "missing": syms}

    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index)
    bench_series = frame[bench] if bench in frame.columns else None

    result = port.analyze(frame, holdings, bench_series, req.risk_free)
    result["benchmark"] = bench
    return result
