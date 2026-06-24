"""Sector performance router — Phase 10."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import sector_service

router = APIRouter(prefix="/api/sector", tags=["sector"])


@router.get("/returns")
async def get_sector_returns():
    try:
        return sector_service.get_sector_returns()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/fundamentals")
async def get_sector_fundamentals():
    try:
        return sector_service.get_sector_fundamentals()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/rotation")
async def get_sector_rotation():
    try:
        return sector_service.get_sector_rotation()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/drill")
async def get_sector_drill(sector: str = Query(..., description="Sector name, e.g. Technology")):
    if not sector:
        raise HTTPException(status_code=400, detail="sector is required")
    try:
        return sector_service.get_sector_industry_drill(sector)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
