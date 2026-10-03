"""Snowflake Composite Score router — Phase 9."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from .. import provenance as pv
from ..services import screener_cache, snowflake_service

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
        scores = snowflake_service.compute_snowflake_batch(tickers_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    peers = pv.ref("econosift", "screener_cache", "Screener universe cache: Yahoo fundamentals for the Dow 30, "
                   "Nasdaq-100 and S&P 500, refreshed nightly",
                   note="Only tickers present in the cache are scored; no live Yahoo call is made.")
    ref = pv.derived(
        "five 0-10 axis scores (value, growth, performance, health, dividend) from the screener cache, mostly "
        "percentile ranks against sector peers (share of peers with a strictly lower value x 10); a lighter "
        "calculation than /api/snowflake, using fewer components per axis", [peers], title="Snowflake scores")
    prov: dict = {"*": ref}
    prov["overallScore"] = pv.derived("mean of the available axis scores, equally weighted", [ref],
                                      title="Overall score")
    prov["axisScores"] = pv.derived(
            "value: weighted percentile ranks as in /api/snowflake; growth: revenue growth 35%, EPS growth 35%, "
            "trailing - forward P/E 30%; performance: ROE 40%, gross margin 30%, net margin 30%; health: Altman Z, "
            "ROIC, current ratio (capped at 4) and inverted debt-to-equity, 25% each; dividend: yield percentile "
            "among dividend-paying peers, 0 for non-payers", [peers], title="Axis scores")
    for t in scores:  # per-ticker keys alias the shared refs instead of repeating them
        prov[f"scores.{t}.overallScore"] = "overallScore"
        prov[f"scores.{t}.scores"] = "axisScores"
    # A stored snapshot: fetched when it was built, not at request time.
    try:
        built = datetime.fromisoformat(screener_cache.last_refresh(list(scores)) or "").astimezone(timezone.utc)
        ref["fetchedAt"] = built.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        pass
    return pv.attach({"scores": scores}, prov)
