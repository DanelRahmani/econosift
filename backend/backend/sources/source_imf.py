"""IMF World Economic Outlook source via imfp."""
from __future__ import annotations

import asyncio
import pandas as pd

from ..cache import async_cached
from ..config import COUNTRY_NAMES
from ..models import SeriesResult, make_series

SOURCE_LABEL = "IMF (World Economic Outlook)"

INDICATOR_MAP = {
    "gdp_growth": "NGDP_RPCH",
    "inflation": "PCPIPCH",
    "unemployment": "LUR",
    "debt_gdp": "GGXWDG_NGDP",
    "current_account": "BCA_NGDPD",
    "gdp_per_capita": "NGDPDPC",
}


def _fetch_sync(indicator: str, countries: list[str], start: int, end: int) -> pd.DataFrame:
    import imfp
    return imfp.imf_dataset(
        "WEO", indicator=[indicator], country=list(countries),
        start_year=start, end_year=end,
    )


def _parse(df: pd.DataFrame, countries: tuple[str, ...]) -> dict[str, list[tuple[int, float]]]:
    out: dict[str, list[tuple[int, float]]] = {}
    if df is None or not hasattr(df, "empty") or df.empty:
        return out
    cols = {c.lower(): c for c in df.columns}
    country_col = cols.get("ref_area") or cols.get("country") or cols.get("reference_area")
    year_col = cols.get("time_period") or cols.get("year") or cols.get("date")
    value_col = cols.get("obs_value") or cols.get("value")
    if not (country_col and year_col and value_col):
        return out
    for _, row in df.iterrows():
        c = str(row[country_col]).upper()[:2]
        try:
            y = int(str(row[year_col])[:4])
            v = float(row[value_col])
        except (ValueError, TypeError):
            continue
        out.setdefault(c, []).append((y, v))
    for c in out:
        out[c] = sorted(out[c])
    return out


@async_cached("imf_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
    indicator = INDICATOR_MAP.get(indicator_key)
    if not indicator:
        return []

    # Try bulk data first
    try:
        from ..services.bulk_data_service import load_imf
        bulk = await asyncio.to_thread(load_imf, indicator_key, list(countries), start, end)
        if bulk is not None and not bulk.empty:
            out: dict[str, list[tuple[int, float]]] = {}
            for _, row in bulk.iterrows():
                iso3 = str(row["iso3"])
                # Convert ISO3 to ISO2
                from ..config import ISO2_TO_ISO3
                iso3_to_iso2 = {v: k for k, v in ISO2_TO_ISO3.items()}
                iso2 = iso3_to_iso2.get(iso3, iso3[:2])
                try:
                    out.setdefault(iso2, []).append((int(row["year"]), float(row["value"])))
                except (ValueError, TypeError):
                    continue
            parsed = {k: sorted(v) for k, v in out.items()}
        else:
            raise Exception("bulk data not available")
    except Exception:
        try:
            df = await asyncio.to_thread(_fetch_sync, indicator, list(countries), start, end)
            parsed = _parse(df, countries)
        except Exception:
            return []

    results: list[SeriesResult] = []
    for iso2, points in parsed.items():
        if iso2 not in countries:
            continue
        results.append(make_series(
            iso2, COUNTRY_NAMES.get(iso2, iso2), points, SOURCE_LABEL))
    return results
