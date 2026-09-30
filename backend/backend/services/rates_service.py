"""Rates & Yields service: yield curve, Taylor Rule, ACM decomposition, credit spreads."""
from __future__ import annotations

import asyncio
import io
import logging
from datetime import date, timedelta

import pandas as pd
import requests

from ..cache import async_cached
from ..config import FRED_API_KEY

log = logging.getLogger(__name__)

YIELD_SERIES = [
    "FEDFUNDS",
    "DGS3MO",
    "DGS2",
    "DGS5",
    "DGS7",
    "DGS10",
    "DGS20",
    "DGS30",
    "T5YIE",
    "T10YIE",
    "DFII10",
    "MORTGAGE30US",
    "BAMLH0A0HYM2",
    "BAMLC0A0CM",
]

# NY Fed ACM term-structure decomposition (data file, not the paper — the
# previous URL pointed at the Staff Report 340 PDF, so this panel was always
# "unavailable"; audit D-18). Legacy .xls, read with xlrd.
ACM_URL = (
    "https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.xls"
)


def _fetch_many_fred_sync(series_ids: list[str], start: str) -> dict[str, pd.Series]:
    """Fetch multiple FRED series, return dict of raw pd.Series."""
    if not FRED_API_KEY:
        return {}
    from fredapi import Fred
    fred = Fred(api_key=FRED_API_KEY)
    out: dict[str, pd.Series] = {}
    for sid in series_ids:
        try:
            s = fred.get_series(sid, observation_start=start)
            if s is not None and not s.empty:
                out[sid] = s.sort_index()
        except Exception as exc:
            log.warning("FRED %s failed: %s", sid, exc)
    return out


def _series_to_records(s: pd.Series) -> list[dict]:
    records = []
    for idx, val in s.items():
        if pd.isna(val):
            continue
        d = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
        records.append({"date": d, "value": round(float(val), 6)})
    return records


def _latest(s: pd.Series | None) -> float | None:
    if s is None or s.empty:
        return None
    last = s.dropna()
    if last.empty:
        return None
    return round(float(last.iloc[-1]), 4)


def _download_acm_sync() -> dict:
    """NY Fed ACM 10y decomposition: risk-neutral expected yield + term premium.

    Monthly sheet; columns ACMRNY10 (expectations) and ACMTP10 (term premium),
    both in percent.
    """
    try:
        resp = requests.get(ACM_URL, timeout=30)
        resp.raise_for_status()
        df = pd.read_excel(io.BytesIO(resp.content), sheet_name="ACM Monthly")
        df["DATE"] = pd.to_datetime(df["DATE"], format="%d-%b-%Y", errors="coerce")
        df = df.dropna(subset=["DATE"]).sort_values("DATE")

        def _pts(col: str) -> list[dict]:
            return [{"date": str(d.date()), "value": round(float(v), 4)}
                    for d, v in zip(df["DATE"], df[col]) if pd.notna(v)]

        return {
            "expectations": _pts("ACMRNY10"),
            "term_premium": _pts("ACMTP10"),
            "source": "NY Fed (ACM)",
        }
    except Exception as exc:
        log.warning("ACM download failed: %s", exc)
        return {"expectations": [], "term_premium": [], "source": "unavailable"}


def _compute_taylor_rule(
    fred_data: dict[str, pd.Series],
) -> dict:
    """Compute Taylor Rule implied rate and actual FEDFUNDS monthly series."""
    try:
        cpi = fred_data.get("CPIAUCSL")
        gdpc1 = fred_data.get("GDPC1")
        gdppot = fred_data.get("GDPPOT")
        fedfunds = fred_data.get("FEDFUNDS")

        if cpi is None or gdpc1 is None or gdppot is None or fedfunds is None:
            return {"implied": [], "actual": [], "output_gap": []}

        # π = rolling 12-month YoY CPI
        cpi = cpi.resample("MS").last().ffill()
        pi = cpi.pct_change(12) * 100

        # Output gap = (GDPC1 - GDPPOT) / GDPPOT * 100, quarterly → monthly
        gdpc1_m = gdpc1.resample("MS").last().ffill()
        gdppot_m = gdppot.resample("MS").last().ffill()
        output_gap = (gdpc1_m - gdppot_m) / gdppot_m * 100

        # Align on common monthly index
        monthly_idx = pi.dropna().index.intersection(output_gap.dropna().index)
        pi_aligned = pi.reindex(monthly_idx).ffill()
        og_aligned = output_gap.reindex(monthly_idx).ffill()

        # Taylor Rule: r = 0.5 + π + 0.5*(π − 2.0) + 0.5*output_gap
        taylor = 0.5 + pi_aligned + 0.5 * (pi_aligned - 2.0) + 0.5 * og_aligned
        taylor = taylor.clip(-5, 25)

        # Actual fed funds resampled to monthly
        ff_m = fedfunds.resample("MS").last().ffill()
        ff_aligned = ff_m.reindex(monthly_idx).ffill()

        implied = [
            {"date": str(d.date()), "value": round(float(v), 4)}
            for d, v in taylor.dropna().items()
        ]
        actual = [
            {"date": str(d.date()), "value": round(float(v), 4)}
            for d, v in ff_aligned.dropna().items()
        ]
        outgap = [
            {"date": str(d.date()), "value": round(float(v), 4)}
            for d, v in og_aligned.dropna().items()
        ]
        return {"implied": implied, "actual": actual, "output_gap": outgap}
    except Exception as exc:
        log.warning("Taylor Rule computation failed: %s", exc)
        return {"implied": [], "actual": [], "output_gap": []}


def _get_rates_data_sync() -> dict:
    today = date.today()
    five_years_ago = (today - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
    twenty_years_ago = "2000-01-01"

    # Fetch 5Y history for all yield series + Taylor Rule inputs
    taylor_series = ["CPIAUCSL", "GDPC1", "GDPPOT"]
    all_series = YIELD_SERIES + taylor_series

    # 5Y history fetch
    fred_data = _fetch_many_fred_sync(all_series, five_years_ago)
    # Also fetch longer history for Taylor Rule (need 12-month lag for YoY)
    fred_long = _fetch_many_fred_sync(taylor_series, twenty_years_ago)

    # Latest values (most recent non-null)
    def latest_val(sid: str) -> float | None:
        s = fred_data.get(sid)
        if s is None:
            return None
        return _latest(s)

    yields = {sid: latest_val(sid) for sid in YIELD_SERIES}

    # Spreads
    dgs10 = yields.get("DGS10")
    dgs2 = yields.get("DGS2")
    dgs3mo = yields.get("DGS3MO")
    spread_2y10y = round(dgs10 - dgs2, 4) if dgs10 is not None and dgs2 is not None else None
    spread_3m10y = round(dgs10 - dgs3mo, 4) if dgs10 is not None and dgs3mo is not None else None
    inverted = bool(spread_3m10y is not None and spread_3m10y < 0)

    # Build history dicts
    history: dict[str, list[dict]] = {}
    for sid in YIELD_SERIES:
        s = fred_data.get(sid)
        history[sid] = _series_to_records(s) if s is not None else []

    # Taylor Rule (uses long history)
    taylor_rule = _compute_taylor_rule(fred_long)

    # ACM decomposition
    acm = _download_acm_sync()

    as_of = str(today)
    # Refine asOf from FEDFUNDS latest date
    ff = fred_data.get("FEDFUNDS")
    if ff is not None and not ff.empty:
        last_idx = ff.dropna().index
        if len(last_idx):
            as_of = str(last_idx[-1].date())

    return {
        "asOf": as_of,
        "yields": yields,
        "spread_2y10y": spread_2y10y,
        "spread_3m10y": spread_3m10y,
        "inverted": inverted,
        "history": history,
        "taylor_rule": taylor_rule,
        "acm": acm,
    }


@async_cached("rates_data")
async def get_rates_data() -> dict:
    """Full yield curve, Taylor Rule, ACM decomposition, credit spreads."""
    try:
        return await asyncio.to_thread(_get_rates_data_sync)
    except Exception as exc:
        log.warning("get_rates_data failed: %s", exc)
        # Unknown, not "not inverted": the envelope is marked unavailable so
        # it is neither cached nor read as a real curve reading.
        return {
            "asOf": None,
            "status": "unavailable",
            "error": str(exc),
            "yields": {},
            "spread_2y10y": None,
            "spread_3m10y": None,
            "inverted": None,
            "history": {},
            "taylor_rule": {"implied": [], "actual": []},
            "acm": {"expectations": [], "term_premium": [], "source": "unavailable"},
        }
