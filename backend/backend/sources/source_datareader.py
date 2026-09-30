"""pandas-datareader source. FRED fallback (no key) + Fama-French factors."""
from __future__ import annotations

import asyncio
from datetime import datetime
import pandas as pd

from ..cache import async_cached, cached
from ..config import COUNTRY_NAMES
from ..models import SeriesResult, make_series
from ._annual import to_annual

SOURCE_LABEL = "FRED (St. Louis Fed, via pandas-datareader)"

# Same FRED series IDs as source_fred (US only).
INDICATOR_MAP = {
    "gdp_growth": ("A191RL1A225NBEA", "mean"),
    "inflation": ("CPIAUCSL", "yoy"),
    "unemployment": ("UNRATE", "mean"),
    "interest_rate": ("FEDFUNDS", "mean"),
    "debt_gdp": ("GFDEGDQ188S", "mean"),
    "yield_10y": ("DGS10", "mean"),
}


def _fetch_sync(series_id: str, start: int) -> pd.Series:
    import pandas_datareader.data as web
    df = web.DataReader(series_id, "fred",
                        start=datetime(start, 1, 1), end=datetime.today())
    return df[series_id] if series_id in df.columns else df.iloc[:, 0]


def _to_annual(s: pd.Series, method: str, start: int, end: int) -> list[tuple[int, float]]:
    return to_annual(s, method, start, end)


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
        s = await asyncio.to_thread(_fetch_sync, series_id, start - 1)
        points = _to_annual(s, method, start, end)
    except Exception:
        return []
    if not points:
        return []
    return [make_series("US", COUNTRY_NAMES.get("US", "US"), points, SOURCE_LABEL)]


@cached("famafrench")
def fama_french() -> list[dict]:
    """Annual Fama-French factor returns, in percent.

    Both data paths return the same shape — ``{year, mkt_rf, smb, hml, rf}``
    in percent. (The bulk-parquet path used to return *monthly* rows keyed
    ``date`` in decimals while the live path returned annual rows keyed
    ``year`` in percent — audit D-31.)
    """
    # Try bulk data first: monthly decimals → compounded calendar-year %.
    # (Compounding the monthly spreads approximates Ken French's own annual
    # table, which is built from annual portfolio returns.)
    try:
        from ..services.bulk_data_service import load_famafrench
        df = load_famafrench(2000)
        if df is not None and not df.empty:
            m = df.copy()
            m["year"] = pd.to_datetime(m["date"].astype(str)).dt.year
            cols = ["mkt_rf", "smb", "hml", "rf"]
            full = m.groupby("year")[cols].count().min(axis=1) == 12  # complete years only
            annual = (1.0 + m.set_index("year")[cols]).groupby(level=0).prod() - 1.0
            return [
                {"year": int(y), **{c: round(float(r[c]) * 100.0, 4) for c in cols}}
                for y, r in annual[full].iterrows()
            ]
    except Exception:
        pass

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
