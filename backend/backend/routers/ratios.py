"""Financial ratios + risk scores."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter

from ..services import yfinance_service as yfs
from ..services import metrics

router = APIRouter(prefix="/api/ratios", tags=["ratios"])


@router.get("/{ticker}")
async def ratios(ticker: str, period: str = "1y", risk_free: float = 0.04):
    sym = ticker.upper()
    bench = yfs.benchmark_for(sym)

    bundle = await asyncio.to_thread(yfs.get_info, sym)
    payload = metrics.compute_ratios(bundle)

    frame = await asyncio.to_thread(
        yfs.get_close_frame, tuple(dict.fromkeys([sym, bench])), period)
    beta = sharpe = sortino = None
    if frame is not None and not frame.empty and sym in frame.columns:
        bench_series = frame[bench] if bench in frame.columns else None
        m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
        beta, sharpe, sortino = m.get("beta"), m.get("sharpe"), m.get("sortino")

    return {
        "ticker": sym,
        "benchmark": bench,
        "beta": beta,
        "sharpe": sharpe,
        "sortino": sortino,
        "zScore": payload["zScore"],
        "liquidity": payload["liquidity"],
        "leverage": payload["leverage"],
        "efficiency": payload["efficiency"],
        "profitability": payload["profitability"],
        "valuation": payload["valuation"],
    }
