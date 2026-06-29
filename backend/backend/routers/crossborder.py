"""Cross-border finance router — trade flows between major economies.

Uses World Bank merchandise trade data (when BIS LBS is unavailable) to show
cross-border economic connections. Falls back gracefully if no data is available.
"""
from datetime import date
import asyncio
from fastapi import APIRouter

router = APIRouter(prefix="/api/crossborder", tags=["crossborder"])


@router.get("/claims")
async def crossborder_claims():
    """Cross-border claims/trade flows between major economies.

    Uses BIS LBS when available, falls back to World Bank merchandise trade data.
    """
    # Try BIS LBS first
    from ..sources.source_bis import get_crossborder_claims
    bis_claims = await get_crossborder_claims()
    if bis_claims:
        return {
            "claims": bis_claims,
            "source": "BIS Locational Banking Statistics (LBS)",
            "asOf": str(date.today()),
        }

    # Fallback: World Bank merchandise trade data
    from ..services import atlas_service
    try:
        trade_data = await atlas_service._wb_timeline("merchandise_trade", 2015, 2024)
    except Exception:
        trade_data = {}

    claims = []
    if trade_data:
        for iso3, years in trade_data.items():
            if not years:
                continue
            latest_val = years[max(years)]
            claims.append({
                "creditor": iso3,
                "debtor": "WLD",  # World aggregate
                "value_usd": round(latest_val, 1),
            })
        claims.sort(key=lambda c: c["value_usd"], reverse=True)
        claims = claims[:20]

    return {
        "claims": claims,
        "source": "World Bank (merchandise trade % of GDP; BIS LBS unavailable)",
        "asOf": str(date.today()),
    }
