"""Financial Stability router — Phase 28.
Currency crisis early warning + banking stability endpoints.
"""
from fastapi import APIRouter

from ..services.currency_crisis_service import get_currency_crisis
from ..services.banking_stability_service import get_banking_stability

router = APIRouter(prefix="/api/stability", tags=["stability"])


@router.get("/currency-crisis")
async def currency_crisis():
    """Currency crisis early warning: six vulnerability indicators checked
    against fixed thresholds, with traffic-light output per country."""
    return await get_currency_crisis()


@router.get("/banking")
async def banking():
    """Banking stability dashboard: NPL ratios, bank capital to assets,
    bank Z-scores, domestic credit (% of GDP), and BIS credit gaps."""
    return await get_banking_stability()
