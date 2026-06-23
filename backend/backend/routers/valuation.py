"""CAPM + DCF valuation."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from ..services import yfinance_service as yfs
from ..services import metrics

router = APIRouter(prefix="/api/valuation", tags=["valuation"])


def _signal(spot, target, expected_return) -> str:
    if spot is None or target is None:
        return "INCOMPLETE"
    upside = (target - spot) / spot
    if upside > 0.10:
        return "BUY"
    if upside < -0.10:
        return "OVERVALUED"
    return "FAIR VALUE"


@router.get("/capm-dcf")
async def capm_dcf(
    tickers: str = Query(...),
    period: str = "1y",
    risk_free: float = 0.04,
    market_premium: float = 0.055,
    fcf_growth: float = 0.08,
    terminal_growth: float = 0.025,
):
    syms = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    benchmarks = sorted({yfs.benchmark_for(s) for s in syms})
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)

    valuations = []
    for sym in syms:
        bench = yfs.benchmark_for(sym)
        beta = None
        if frame is not None and not frame.empty and sym in frame.columns:
            bench_series = frame[bench] if bench in frame.columns else None
            m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
            beta = m.get("beta")

        bundle = await asyncio.to_thread(yfs.get_info, sym)
        info = bundle.get("info", {}) or {}

        expected_return = metrics.capm_expected_return(beta, risk_free, market_premium)
        discount = expected_return if expected_return else risk_free + market_premium
        target = metrics.dcf_target(info, fcf_growth, terminal_growth, discount)

        spot = info.get("currentPrice") or info.get("regularMarketPrice")
        spot = float(spot) if spot else None

        valuations.append({
            "ticker": sym,
            "benchmark": bench,
            "beta": beta,
            "expectedReturn": expected_return,
            "trailingPE": info.get("trailingPE"),
            "spotPrice": spot,
            "dcfTarget": target,
            "currency": info.get("currency") or "USD",
            "signal": _signal(spot, target, expected_return),
        })

    return {"valuations": valuations}
