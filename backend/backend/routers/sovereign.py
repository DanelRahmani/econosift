from fastapi import APIRouter
from backend.services.sovereign_risk_service import get_sovereign_risk

router = APIRouter(prefix="/api/sovereign", tags=["sovereign"])


@router.get("/risk")
async def sovereign_risk():
    return await get_sovereign_risk()


@router.get("/default-prob")
async def sovereign_default_prob():
    """Sovereign default probability model (logistic regression, Reinhart & Rogoff)."""
    from backend.services.sovereign_default_service import get_default_probabilities
    return await get_default_probabilities()
