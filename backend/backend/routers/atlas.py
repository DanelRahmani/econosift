"""Global Macro Atlas router — Phase 13."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..services import atlas_service

router = APIRouter(prefix="/api/atlas", tags=["atlas"])


@router.get("/indicators")
async def get_indicators():
    try:
        return atlas_service.get_indicators()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/regions")
async def get_regions():
    try:
        return atlas_service.get_regions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/timeline")
async def get_timeline(
    indicator: str = Query(..., description="Indicator id, e.g. gdp_growth"),
    start: int = Query(2000, description="Start year"),
    end: int = Query(default_factory=lambda: date.today().year - 1, description="End year (default: last complete year)"),
):
    try:
        return await atlas_service.get_timeline(indicator, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/snapshot")
async def get_snapshot(
    indicator: str = Query(..., description="Indicator id, e.g. gdp_growth"),
    year: int = Query(..., description="Year, e.g. 2023"),
):
    try:
        return await atlas_service.get_snapshot(indicator, year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
