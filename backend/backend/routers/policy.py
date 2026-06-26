"""Policy router — CB divergence, stance classification, carry differentials.

Phase 18A Task 3.
"""
from fastapi import APIRouter

from ..services.policy_service import get_policy_tracker

router = APIRouter(prefix="/api/policy", tags=["policy"])


@router.get("/tracker")
async def policy_tracker():
    return await get_policy_tracker()
