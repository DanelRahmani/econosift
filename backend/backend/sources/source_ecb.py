"""ECB Data Portal source via ecbdata. Eurozone/EU coverage."""
from __future__ import annotations

import asyncio
import pandas as pd

from ..cache import async_cached
from ..config import EUROZONE, COUNTRY_NAMES
from ..models import SeriesResult, make_series
from ._annual import to_annual

SOURCE_LABEL = "ECB (European Central Bank)"

# ECB HICP country codes (mostly ISO2).
ECB_COUNTRY = {
    "DE": "DE", "FR": "FR", "IT": "IT", "ES": "ES", "NL": "NL",
    "AT": "AT", "BE": "BE", "PT": "PT", "IE": "IE", "FI": "FI",
    "GR": "GR",
}

# Euro-area aggregate policy rate (main refinancing operations / FR rate proxy).
POLICY_RATE_KEY = "FM.B.U2.EUR.4F.KR.MRR_FR.LEV"


def _annual(df: pd.DataFrame, start: int, end: int) -> list[tuple[int, float]]:
    if df is None or df.empty:
        return []
    if "TIME_PERIOD" in df.columns and "OBS_VALUE" in df.columns:
        s = pd.Series(
            pd.to_numeric(df["OBS_VALUE"], errors="coerce").values,
            index=pd.to_datetime(df["TIME_PERIOD"], errors="coerce"),
        ).dropna()
    else:
        return []
    return to_annual(s, "mean", start, end)


def _fetch_series(key: str) -> pd.DataFrame:
    from ecbdata import ecbdata
    return ecbdata.get_series(key)


@async_cached("ecb_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
    euro_countries = [c for c in countries if c in EUROZONE]
    results: list[SeriesResult] = []

    try:
        if indicator_key == "inflation":
            for c in euro_countries:
                cc = ECB_COUNTRY.get(c)
                if not cc:
                    continue
                key = f"ICP.M.{cc}.N.000000.4.ANR"
                df = await asyncio.to_thread(_fetch_series, key)
                points = _annual(df, start, end)
                if points:
                    results.append(make_series(
                        c, COUNTRY_NAMES.get(c, c), points, SOURCE_LABEL))
        elif indicator_key == "interest_rate" and euro_countries:
            df = await asyncio.to_thread(_fetch_series, POLICY_RATE_KEY)
            points = _annual(df, start, end)
            # One euro-area rate: label it as such rather than implying each
            # member sets its own policy rate (audit D-13).
            for c in euro_countries:
                if points:
                    results.append(make_series(
                        c, COUNTRY_NAMES.get(c, c), points,
                        "ECB — euro-area main refinancing rate (common to all members)"))
    except Exception:
        return results
    return results
