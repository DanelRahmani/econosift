"""Yield curve router — Phase 18A."""
from fastapi import APIRouter

from ..services.yield_curve_service import get_yield_curves
from ..services.treasury_noise_service import get_treasury_noise

router = APIRouter(prefix="/api/yield", tags=["yield"])


@router.get("/curves")
async def yield_curves():
    return await get_yield_curves()


@router.get("/noise")
async def treasury_noise():
    """Nelson-Siegel curve-fit noise across the CMT tenors (HPW-style illiquidity gauge)."""
    return await get_treasury_noise()
