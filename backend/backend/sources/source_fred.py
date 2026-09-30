"""FRED source via fredapi. US-only coverage."""
from __future__ import annotations

import asyncio
import pandas as pd

from ..cache import async_cached
from ..config import FRED_API_KEY, COUNTRY_NAMES
from ..models import SeriesResult, make_series
from ._annual import to_annual

SOURCE_LABEL = "FRED (St. Louis Fed)"

# (series_id, resample_method)  method in {"mean","sum","yoy"}
# Annual real GDP growth is BEA's own annual series, not an average of the
# quarterly SAAR prints. Current account is deliberately absent: FRED's
# BOPGSTB is the goods & services *trade balance* in $mn, not the current
# account in % of GDP that every other source supplies (audit D-04).
INDICATOR_MAP = {
    "gdp_growth": ("A191RL1A225NBEA", "mean"),
    "inflation": ("CPIAUCSL", "yoy"),
    "unemployment": ("UNRATE", "mean"),
    "interest_rate": ("FEDFUNDS", "mean"),
    "debt_gdp": ("GFDEGDQ188S", "mean"),
    "yield_10y": ("DGS10", "mean"),
}


def _fetch_sync(series_id: str, start: int) -> pd.Series:
    from fredapi import Fred
    fred = Fred(api_key=FRED_API_KEY)
    return fred.get_series(series_id, observation_start=f"{start}-01-01")


def _to_annual(s: pd.Series, method: str, start: int, end: int) -> list[tuple[int, float]]:
    return to_annual(s, method, start, end)


@async_cached("fred_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
    if not FRED_API_KEY:
        return []
    if "US" not in countries:
        return []
    mapping = INDICATOR_MAP.get(indicator_key)
    if not mapping:
        return []
    series_id, method = mapping
    try:
        s = await asyncio.to_thread(_fetch_sync, series_id, start - 1)
        points = _to_annual(s, method, start, end)
    except Exception:
        return []
    if not points:
        return []
    return [make_series("US", COUNTRY_NAMES.get("US", "US"), points, SOURCE_LABEL)]
