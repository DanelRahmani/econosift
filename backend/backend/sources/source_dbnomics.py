"""DB.nomics source (OECD/BIS) via dbnomics."""
from __future__ import annotations

import asyncio
import pandas as pd

from ..cache import async_cached
from ..config import iso2_to_iso3, COUNTRY_NAMES
from ..models import SeriesResult, make_series
from ._annual import to_annual

SOURCE_LABEL = "DB.nomics (OECD/BIS)"


# How each DB.nomics series becomes the indicator: CPI and real GDP arrive as
# *levels* (an index, a volume) and must be turned into annual % changes —
# previously the raw index/volume was served as "inflation"/"GDP growth"
# (audit D-05).
_METHOD = {"inflation": "yoy", "gdp_growth": "yoy", "unemployment": "mean", "interest_rate": "mean"}


def _series_path(indicator_key: str, iso2: str) -> str | None:
    iso3 = iso2_to_iso3(iso2)
    if indicator_key == "unemployment" and iso3:
        return f"OECD/MEI/{iso3}.LRHUTTTT.STSA.M"
    if indicator_key == "inflation" and iso3:
        return f"OECD/MEI/{iso3}.CPALTT01.IXOBSAM.M"
    if indicator_key == "gdp_growth" and iso3:
        return f"OECD/QNA/{iso3}.B1_GE.VOBARSA.Q"
    if indicator_key == "interest_rate":
        return f"BIS/cbpol/{iso2}:PP:M"
    return None


def _fetch_sync(path: str) -> pd.DataFrame:
    from dbnomics import fetch_series
    return fetch_series(path)


def _annual(df: pd.DataFrame, start: int, end: int, method: str = "mean") -> list[tuple[int, float]]:
    if df is None or df.empty or "period" not in df.columns or "value" not in df.columns:
        return []
    s = pd.Series(
        pd.to_numeric(df["value"], errors="coerce").values,
        index=pd.to_datetime(df["period"], errors="coerce"),
    ).dropna()
    s = s[s.index.notna()]
    return to_annual(s, method, start, end)


@async_cached("dbnomics_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
    results: list[SeriesResult] = []
    for iso2 in countries:
        path = _series_path(indicator_key, iso2)
        if not path:
            continue
        try:
            df = await asyncio.to_thread(_fetch_sync, path)
            points = _annual(df, start, end, _METHOD.get(indicator_key, "mean"))
        except Exception:
            continue
        if points:
            results.append(make_series(
                iso2, COUNTRY_NAMES.get(iso2, iso2), points, SOURCE_LABEL))
    return results
