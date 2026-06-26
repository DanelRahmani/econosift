"""Yield curve router — Phase 18A."""
from fastapi import APIRouter

from ..services.yield_curve_service import get_yield_curves

router = APIRouter(prefix="/api/yield", tags=["yield"])


@router.get("/curves")
async def yield_curves():
    return await get_yield_curves()
