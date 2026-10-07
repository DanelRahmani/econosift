"""EDGAR data router: 13F institutional holders and Form 4 insider transactions."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from .. import provenance as pv
from ..services import edgar_service, thirteenf_service
from ..services import yfinance_service as yfs

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/13f")
async def holders_13f(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Top 13F institutional holders from the most recent quarterly filing."""
    return await thirteenf_service.get_13f_holders(ticker.upper())


@router.post("/13f/previous")
async def load_previous_13f():
    """🟡 Download and reduce the previous quarter's 13F data set (~100 MB), on request only,
    so holders show their quarter-on-quarter change (P2-37)."""
    return await asyncio.to_thread(thirteenf_service.load_previous)


@router.get("/form4")
async def form4_insiders(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Recent Form 4 insider buy/sell transactions (last 90 days)."""
    return await edgar_service.get_form4_insiders(ticker.upper())


@router.get("/composite")
async def market_composite(
    tickers: str = Query(..., description="Comma-separated tickers e.g. AAPL,MSFT"),
    period: str = Query("1y"),
    benchmark: str | None = Query(None),
):
    """
    Return prices + quotes in a single request.
    A single OHLCV fetch is shared so the round-trip count stays at
    1 (prices) + N (parallel quotes) instead of 2N separate calls.
    Risk metrics are omitted here; use /api/risk for per-ticker risk.
    """
    syms = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not syms:
        raise HTTPException(status_code=422, detail="No tickers provided")

    all_syms = tuple(syms + ([benchmark.upper()] if benchmark else []))

    # Single OHLCV fetch for all symbols + optional benchmark
    close_frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)

    prices: list[dict] = []
    if not close_frame.empty:
        bench_sym = benchmark.upper() if benchmark else None
        for date_idx, row in close_frame.iterrows():
            point: dict = {"date": str(date_idx)[:10]}
            for sym in syms:
                if sym in close_frame.columns:
                    val = row.get(sym)
                    point[sym] = float(val) if val == val and val is not None else None  # noqa: PLR0124
            if bench_sym and bench_sym in close_frame.columns:
                val = row.get(bench_sym)
                point[bench_sym] = float(val) if val == val and val is not None else None  # noqa: PLR0124
            prices.append(point)

    # Parallel quote fetch — one yfinance call per ticker, run concurrently
    async def _get_quote(sym: str) -> dict | None:
        try:
            return await asyncio.to_thread(yfs.get_quote, sym)
        except Exception:
            return None

    quote_results = await asyncio.gather(*[_get_quote(s) for s in syms])
    quotes = [q for q in quote_results if q is not None]

    adj = "price, split- and dividend-adjusted"
    prov = {"*": pv.ref("yahoo", None, "Daily adjusted close", units=adj, frequency="daily",
                        observed=pv.last_date(close_frame))}
    for c in close_frame.columns:
        prov[f"prices.{c}"] = pv.yahoo(c, "Daily adjusted close", units=adj, frequency="daily",
                                       observed=pv.last_date(close_frame[c]))
    for q in quotes:
        prov[f"quotes.{q['symbol']}"] = pv.yahoo(q["symbol"], "Quote: last price and previous close",
                                                 note="Yahoo fast_info, falling back to the info snapshot; "
                                                      "Yahoo quotes can lag the exchange.")
    return pv.attach({"prices": prices, "risk": [], "quotes": quotes}, prov)


@router.get("/short-interest")
async def short_interest(
    ticker: str = Query(None, description="Single ticker, e.g. AAPL"),
    universe: str = Query(None, description="Universe: sp500"),
):
    """Short interest data from Finnhub: % of float short, days to cover,
    squeeze score, and sector aggregates."""
    from ..services.short_interest_service import get_short_interest
    return await get_short_interest(ticker=ticker, universe=universe)
