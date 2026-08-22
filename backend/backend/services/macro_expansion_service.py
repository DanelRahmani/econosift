"""Shared FRED multi-series fetcher for Phase 8 macro expansion endpoints."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import pandas as pd

from ..cache import async_cached
from ..config import FRED_API_KEY
from .ratelimit import fred_limiter

log = logging.getLogger(__name__)


def _fetch_fred_series_sync(
    series_ids: list[str],
    start: str,
    vintage: str | None = None,
    first_release: bool = False,
) -> dict[str, list[dict]]:
    """Fetch FRED series, optionally as they stood at a past point in time.

    By default this returns the *latest revision* of every observation, which is
    the right choice for describing history but wrong for evaluating a model:
    GDP and payrolls are revised heavily, so a rule scored on revised data looks
    better than it could ever have been in real time. The Sahm rule is the sharp
    case — it is explicitly designed to fire in real time, so grading it on
    revised data defeats its purpose.

    ``first_release`` returns each observation as first published.
    ``vintage`` (YYYY-MM-DD) returns the series as it stood on that date.
    """
    if not FRED_API_KEY:
        return {}
    from fredapi import Fred
    fred = Fred(api_key=FRED_API_KEY)
    result: dict[str, list[dict]] = {}
    for sid in series_ids:
        try:
            # Throttled: a cold cache fans out dozens of series at once and FRED
            # caps at 120 requests/minute per key.
            with fred_limiter:
                if first_release:
                    s = fred.get_series_first_release(sid)
                    if s is not None and not s.empty and start:
                        s = s[s.index >= pd.Timestamp(start)]
                elif vintage:
                    s = fred.get_series_as_of_date(sid, vintage)
                    # ALFRED returns a long frame (date, realtime_start, value);
                    # collapse to the latest value known as of the vintage date.
                    if s is not None and len(s) and not isinstance(s, pd.Series):
                        s = (
                            s.sort_values("realtime_start")
                            .groupby("date")["value"]
                            .last()
                        )
                        s.index = pd.to_datetime(s.index)
                        if start:
                            s = s[s.index >= pd.Timestamp(start)]
                        s = pd.to_numeric(s, errors="coerce").dropna()
                else:
                    s = fred.get_series(sid, observation_start=start)
            if s is None or s.empty:
                result[sid] = []
                continue
            records = []
            for idx, val in s.items():
                if pd.isna(val):
                    continue
                if hasattr(idx, "date"):
                    d = str(idx.date())
                else:
                    d = str(idx)[:10]
                records.append({"date": d, "value": round(float(val), 6)})
            result[sid] = records
        except Exception as exc:
            log.warning("FRED fetch failed for %s: %s", sid, exc)
            result[sid] = []
    return result


@async_cached("fred_multi_series")
async def fetch_fred_series(
    series_ids: list[str] | tuple[str, ...],
    start: str = "2000-01-01",
    as_pct_change: list[str] | None = None,
    as_yoy: list[str] | None = None,
    vintage: str | None = None,
    first_release: bool = False,
) -> dict[str, list[dict]]:
    """Fetch multiple FRED series and return {series_id: [{date, value}, ...]}.

    ``vintage`` / ``first_release`` request the data as it stood in the past
    rather than at its latest revision — see :func:`_fetch_fred_series_sync`.
    Both are part of the cache key (``_make_key`` folds in every kwarg), so
    vintage requests cannot collide with latest-revision entries.
    """
    try:
        ids = list(series_ids)
        raw = await asyncio.to_thread(
            _fetch_fred_series_sync, ids, start, vintage, first_release
        )
        # Apply YoY % change for requested series
        yoy_ids = set(as_pct_change or []) | set(as_yoy or [])
        for sid in yoy_ids:
            series = raw.get(sid, [])
            if not series:
                continue
            df = pd.DataFrame(series).set_index("date")
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            df["value"] = df["value"].pct_change(12) * 100
            raw[sid] = [
                {"date": str(d.date()), "value": round(float(v), 4)}
                for d, v in df["value"].dropna().items()
            ]
        return raw
    except Exception as exc:
        log.warning("fetch_fred_series error: %s", exc)
        return {}


def _fetch_recession_dates_sync() -> list[dict]:
    if not FRED_API_KEY:
        return []
    from fredapi import Fred
    fred = Fred(api_key=FRED_API_KEY)
    try:
        s = fred.get_series("USREC", observation_start="1950-01-01")
        if s is None or s.empty:
            return []
        s = s.sort_index()
        periods: list[dict] = []
        in_recession = False
        rec_start: str | None = None
        for idx, val in s.items():
            v = int(val) if not pd.isna(val) else 0
            d = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
            if v == 1 and not in_recession:
                in_recession = True
                rec_start = d
            elif v == 0 and in_recession:
                in_recession = False
                periods.append({"start": rec_start, "end": d})
        # If still in recession at end of data
        if in_recession and rec_start:
            periods.append({"start": rec_start, "end": str(date.today())})
        return periods
    except Exception as exc:
        log.warning("fetch_recession_dates error: %s", exc)
        return []


@async_cached("recession_dates")
async def fetch_recession_dates() -> list[dict]:
    """Return list of {start, end} dicts for US recession periods (USREC series)."""
    try:
        return await asyncio.to_thread(_fetch_recession_dates_sync)
    except Exception as exc:
        log.warning("fetch_recession_dates async error: %s", exc)
        return []
