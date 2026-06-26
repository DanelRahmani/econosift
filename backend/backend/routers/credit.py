"""Credit market router — Phase 18A."""
from fastapi import APIRouter

from ..services.credit_market import get_credit_pulse

router = APIRouter(prefix="/api/credit", tags=["credit"])


@router.get("/pulse")
async def credit_pulse():
    return await get_credit_pulse()
