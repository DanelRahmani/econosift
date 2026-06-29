"""M&A / Corporate Actions router — Phase 30."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/mergers", tags=["mergers"])


@router.get("")
async def mergers():
    """M&A deal tracker: announced deals, monthly volume, sector heatmap."""
    from ..services.ma_service import get_ma_data
    return await get_ma_data()
