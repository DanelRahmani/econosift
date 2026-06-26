from fastapi import APIRouter
from backend.services.sovereign_risk_service import get_sovereign_risk

router = APIRouter(prefix="/api/sovereign", tags=["sovereign"])


@router.get("/risk")
async def sovereign_risk():
    return await get_sovereign_risk()
