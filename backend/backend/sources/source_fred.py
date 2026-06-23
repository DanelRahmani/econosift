"""FRED source via fredapi. US-only coverage."""
from __future__ import annotations

import asyncio
import pandas as pd

from ..cache import async_cached
from ..config import FRED_API_KEY, COUNTRY_NAMES
from ..models import SeriesResult, make_series

SOURCE_LABEL = "FRED (St. Louis Fed)"

# (series_id, resample_method)  method in {"mean","sum","yoy"}
INDICATOR_MAP = {
    "gdp_growth": ("A191RL1Q225SBEA", "mean"),
    "inflation": ("CPIAUCSL", "yoy"),
    "unemployment": ("UNRATE", "mean"),
    "interest_rate": ("FEDFUNDS", "mean"),
    "debt_gdp": ("GFDEGDQ188S", "mean"),
    "yield_10y": ("DGS10", "mean"),
    "current_account": ("BOPGSTB", "sum"),
}


def _fetch_sync(series_id: str, start: int) -> pd.Series:
    from fredapi import Fred
    fred = Fred(api_key=FRED_API_KEY)
    return fred.get_series(series_id, observation_start=f"{start}-01-01")


def _to_annual(s: pd.Series, method: str, start: int, end: int) -> list[tuple[int, float]]:
    if s is None or len(s) == 0:
        return []
    s = s.dropna()
    s.index = pd.to_datetime(s.index)
    if method == "yoy":
        annual = s.resample("YE").mean()
        annual = annual.pct_change() * 100.0
    elif method == "sum":
        annual = s.resample("YE").sum()
    else:
        annual = s.resample("YE").mean()
    points: list[tuple[int, float]] = []
    for ts, val in annual.dropna().items():
        y = ts.year
        if start <= y <= end:
            points.append((y, float(val)))
    return sorted(points)


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
        s = await asyncio.to_thread(_fetch_sync, series_id, start)
        points = _to_annual(s, method, start, end)
    except Exception:
        return []
    if not points:
        return []
    return [make_series("US", COUNTRY_NAMES.get("US", "US"), points, SOURCE_LABEL)]
