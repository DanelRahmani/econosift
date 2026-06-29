"""OpenFactbook country profiles router."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/countries", tags=["countries"])


@router.get("")
async def country_list():
    """List all ~260 countries with ISO codes and names."""
    from ..services.factbook_service import get_country_list
    return get_country_list()


@router.get("/{iso2}")
async def country_profile(iso2: str):
    """Get a single country profile with structured sections."""
    from ..services.factbook_service import get_country_profile
    profile = get_country_profile(iso2)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Country not found: {iso2}")
    return profile
