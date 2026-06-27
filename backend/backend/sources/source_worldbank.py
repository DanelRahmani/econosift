"""World Bank source via wbgapi. Broad 200+ country coverage."""
from __future__ import annotations

import asyncio
import pandas as pd

from ..cache import async_cached
from ..config import ISO2_TO_ISO3, COUNTRY_NAMES
from ..models import SeriesResult, make_series

SOURCE_LABEL = "World Bank"

INDICATOR_MAP = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "inflation": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
    "debt_gdp": "GC.DOD.TOTL.GD.ZS",
    "trade_gdp": "NE.TRD.GNFS.ZS",
    "current_account": "BN.CAB.XOKA.GD.ZS",
    "gdp_per_capita": "NY.GDP.PCAP.KD",
    "population": "SP.POP.TOTL",
}


def _fetch_sync(series_id: str, iso3_list: list[str], start: int, end: int) -> dict:
    import wbgapi as wb
    df = wb.data.DataFrame(
        series_id, economy=iso3_list, time=range(start, end + 1),
        labels=False, skipBlanks=True,
    )
    return _parse(df)


def _parse(df: pd.DataFrame) -> dict[str, list[tuple[int, float]]]:
    """Return {iso3: [(year, value)]}."""
    out: dict[str, list[tuple[int, float]]] = {}
    if df is None or df.empty:
        return out
    # wbgapi: rows = economies, columns = 'YR2000'...
    for economy, row in df.iterrows():
        points: list[tuple[int, float]] = []
        for col, val in row.items():
            year = str(col).replace("YR", "")
            try:
                y = int(year)
                if pd.notna(val):
                    points.append((y, float(val)))
            except (ValueError, TypeError):
                continue
        if points:
            out[str(economy)] = sorted(points)
    return out


@async_cached("wb_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
    series_id = INDICATOR_MAP.get(indicator_key)
    if not series_id:
        return []
    iso3_to_iso2 = {ISO2_TO_ISO3.get(c, c): c for c in countries}
    iso3_list = list(iso3_to_iso2.keys())

    # Try bulk data first
    try:
        from ..services.bulk_data_service import load_worldbank
        bulk = await asyncio.to_thread(load_worldbank, indicator_key, iso3_list, start, end)
        if bulk is not None and not bulk.empty:
            out: dict[str, list[tuple[int, float]]] = {}
            for _, row in bulk.iterrows():
                iso3 = str(row["iso3"])
                try:
                    out.setdefault(iso3, []).append((int(row["year"]), float(row["value"])))
                except (ValueError, TypeError):
                    continue
            parsed = {k: sorted(v) for k, v in out.items()}
        else:
            raise Exception("bulk data not available")
    except Exception:
        try:
            parsed = await asyncio.to_thread(_fetch_sync, series_id, iso3_list, start, end)
        except Exception:
            return []

    results: list[SeriesResult] = []
    for iso3, points in parsed.items():
        iso2 = iso3_to_iso2.get(iso3, iso3)
        results.append(make_series(
            iso2, COUNTRY_NAMES.get(iso2, iso2), points, SOURCE_LABEL))
    return results
