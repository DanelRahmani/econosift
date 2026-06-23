"""Macro indicators, country data, FX, Fama-French."""
from __future__ import annotations

import asyncio
from datetime import date
from fastapi import APIRouter, Query

from ..config import COUNTRIES, INDICATORS
from ..services import macro_service
from ..services import yfinance_service as yfs
from ..sources import source_frankfurter, source_datareader, source_imf

router = APIRouter(prefix="/api/macro", tags=["macro"])

# CBOE Treasury yield indices — quoted directly as yield in percent, no API key.
YIELD_TENORS = [("^IRX", "3M", 0.25), ("^FVX", "5Y", 5.0),
                ("^TNX", "10Y", 10.0), ("^TYX", "30Y", 30.0)]


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


@router.get("/snapshot")
async def snapshot(countries: str = Query(...)):
    """Latest headline indicators per country for side-by-side comparison cards."""
    iso2_list = [c.strip().upper() for c in countries.split(",") if c.strip()][:4]
    return await macro_service.get_snapshot(iso2_list, date.today().year)


@router.get("/forecast")
async def forecast(
    countries: str = Query(...),
    indicator: str = Query(...),
    end: int = Query(default_factory=lambda: date.today().year + 5),
):
    """IMF World Economic Outlook projections for overlaying on historical charts."""
    iso2_list = tuple(c.strip().upper() for c in countries.split(",") if c.strip())
    start = date.today().year - 1
    series = await source_imf.fetch(indicator, iso2_list, start, end)
    return {
        "indicator": indicator,
        "unit": macro_service.get_unit(indicator),
        "source": source_imf.SOURCE_LABEL,
        "series": series or [],
    }


@router.get("/yield-curve")
async def yield_curve():
    """US Treasury yield curve with inversion detection (recession signal)."""
    syms = tuple(t[0] for t in YIELD_TENORS)
    frame = await asyncio.to_thread(yfs.get_close_frame, syms, "5d")

    points = []
    by_label: dict[str, float] = {}
    for sym, label, years in YIELD_TENORS:
        yld = None
        if frame is not None and sym in frame.columns:
            s = frame[sym].dropna()
            if len(s):
                yld = round(float(s.iloc[-1]), 3)
        points.append({"tenor": label, "years": years, "yield": yld})
        if yld is not None:
            by_label[label] = yld

    spread_10y_3m = (round(by_label["10Y"] - by_label["3M"], 3)
                     if "10Y" in by_label and "3M" in by_label else None)
    spread_10y_5y = (round(by_label["10Y"] - by_label["5Y"], 3)
                     if "10Y" in by_label and "5Y" in by_label else None)
    inverted = bool((spread_10y_3m is not None and spread_10y_3m < 0))

    return {
        "points": points,
        "spread10y3m": spread_10y_3m,
        "spread10y5y": spread_10y_5y,
        "inverted": inverted,
    }


@router.get("/fama-french")
async def fama_french():
    factors = await asyncio.to_thread(source_datareader.fama_french)
    return {"factors": factors}
