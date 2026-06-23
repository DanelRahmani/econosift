"""pandas-datareader source. FRED fallback (no key) + Fama-French factors."""
from __future__ import annotations

import asyncio
from datetime import datetime
import pandas as pd

from ..cache import async_cached, cached
from ..config import COUNTRY_NAMES
from ..models import SeriesResult, make_series

SOURCE_LABEL = "pandas-datareader"

# Same FRED series IDs as source_fred (US only).
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
    import pandas_datareader.data as web
    df = web.DataReader(series_id, "fred",
                        start=datetime(start, 1, 1), end=datetime.today())
    return df[series_id] if series_id in df.columns else df.iloc[:, 0]


def _to_annual(s: pd.Series, method: str, start: int, end: int) -> list[tuple[int, float]]:
    if s is None or len(s) == 0:
        return []
    s = s.dropna()
    s.index = pd.to_datetime(s.index)
    if method == "yoy":
        annual = s.resample("YE").mean().pct_change() * 100.0
    elif method == "sum":
        annual = s.resample("YE").sum()
    else:
        annual = s.resample("YE").mean()
    return sorted(
        (ts.year, float(v)) for ts, v in annual.dropna().items()
        if start <= ts.year <= end
    )


@async_cached("dr_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
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


@cached("famafrench")
def fama_french() -> list[dict]:
    """Annual means of Fama-French research factors."""
    import pandas_datareader.data as web
    try:
        data = web.DataReader("F-F_Research_Data_Factors", "famafrench",
                              start=datetime(2000, 1, 1))
    except Exception:
        return []
    annual = data.get(1)
    if annual is None or annual.empty:
        annual = data.get(0)
    if annual is None or annual.empty:
        return []
    out: list[dict] = []
    for idx, row in annual.iterrows():
        try:
            year = int(str(idx))
        except (ValueError, TypeError):
            try:
                year = int(idx.year)
            except Exception:
                continue
        out.append({
            "year": year,
            "mkt_rf": float(row.get("Mkt-RF")),
            "smb": float(row.get("SMB")),
            "hml": float(row.get("HML")),
            "rf": float(row.get("RF")),
        })
    return out
