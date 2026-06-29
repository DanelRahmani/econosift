"""Financial Stability router — Phase 28.
Currency crisis early warning + banking stability endpoints.
"""
from fastapi import APIRouter

from ..services.currency_crisis_service import get_currency_crisis
from ..services.banking_stability_service import get_banking_stability

router = APIRouter(prefix="/api/stability", tags=["stability"])


@router.get("/currency-crisis")
async def currency_crisis():
    """Currency crisis early warning system: KLR composite model
    with traffic-light output per country."""
    return await get_currency_crisis()


@router.get("/banking")
async def banking():
    """Banking stability dashboard: NPL ratios, capital adequacy,
    bank Z-scores, domestic credit growth, and BIS credit gaps."""
    return await get_banking_stability()
