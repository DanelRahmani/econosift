"""Macro indicators, country data, FX, Fama-French."""
from __future__ import annotations

import asyncio
from datetime import date
from fastapi import APIRouter, Query

from ..config import COUNTRIES, INDICATORS
from ..services import macro_service
from ..sources import source_frankfurter, source_datareader

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.get("/indicators")
async def indicators():
    return {"indicators": INDICATORS}


@router.get("/countries")
async def countries():
    return {"countries": COUNTRIES}


@router.get("/data")
async def data(
    countries: str = Query(...),
    indicator: str = Query(...),
    start: int = 2000,
    end: int = Query(default_factory=lambda: date.today().year),
):
    iso2_list = [c.strip().upper() for c in countries.split(",") if c.strip()]
    series = await macro_service.get_macro_data(indicator, iso2_list, start, end)
    return {
        "indicator": indicator,
        "unit": macro_service.get_unit(indicator),
        "series": series,
    }


@router.get("/fx")
async def fx(base: str = "USD", targets: str = "EUR,GBP,JPY"):
    tgt = tuple(t.strip().upper() for t in targets.split(",") if t.strip())
    return await source_frankfurter.latest(base.upper(), tgt)


@router.get("/fx/history")
async def fx_history(
    base: str = "USD",
    targets: str = "EUR,GBP,JPY",
    start: str = "2020-01-01",
    end: str = Query(default_factory=lambda: date.today().isoformat()),
):
    tgt = tuple(t.strip().upper() for t in targets.split(",") if t.strip())
    return await source_frankfurter.history(base.upper(), tgt, start, end)


@router.get("/fama-french")
async def fama_french():
    factors = await asyncio.to_thread(source_datareader.fama_french)
    return {"factors": factors}
