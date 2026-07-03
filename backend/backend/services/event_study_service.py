"""Event Study Lab — CAR/AAR abnormal returns around events (earnings, FOMC).

Public entry point:
  - run_event_study : fetch prices + event dates, run the market-model event study

Testable pure core:
  - _event_study : takes a pre-built close-price DataFrame + event dates
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import yfinance as yf

from . import yfinance_service as yfs
from ..cache import cached

_MARKET_COL = "^GSPC"
_GAP_BEFORE_EVENT = 10   # trading days between end of estimation window and event
_MIN_EST_OBS = 30        # minimum estimation-window observations to fit alpha/beta

# Scheduled FOMC decision (second) days, 2015-01 through the most recent past
# meeting. Source: Federal Reserve Board public meeting calendar —
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# This is a fixed reference calendar (like a holiday list), not fabricated
# market data.
FOMC_DECISION_DATES: list[str] = [
    "2015-01-28", "2015-03-18", "2015-04-29", "2015-06-17", "2015-07-29",
    "2015-09-17", "2015-10-28", "2015-12-16",
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27",
    "2016-09-21", "2016-11-02", "2016-12-14",
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26",
    "2017-09-20", "2017-11-01", "2017-12-13",
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01",
    "2018-09-26", "2018-11-08", "2018-12-19",
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31",
    "2019-09-18", "2019-10-30", "2019-12-11",
    "2020-01-29", "2020-03-18", "2020-04-29", "2020-06-10", "2020-07-29",
    "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28",
    "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
    "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
    "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
    "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _clean(x) -> float | None:
    """Convert to Python float; map NaN/inf/None -> None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _simple_returns(px: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns, dropping rows where ALL values are NaN."""
    return px.pct_change().dropna(how="all")


def _fetch_earnings_dates(ticker: str, lookback_years: int) -> list[pd.Timestamp]:
    """Past earnings dates for ``ticker`` within the lookback window, deduped to date."""
    cutoff = pd.Timestamp.now(tz="UTC") - pd.DateOffset(years=lookback_years)
    now = pd.Timestamp.now(tz="UTC")
    try:
        ed = yf.Ticker(ticker).earnings_dates
        if ed is None or ed.empty:
            return []
        idx = pd.to_datetime(ed.index)
        if idx.tz is not None:
            idx = idx.tz_convert("UTC")
        else:
            idx = idx.tz_localize("UTC")
        dates = sorted({d.normalize() for d in idx if cutoff <= d <= now})
        return dates
    except Exception:
        return []


def _fetch_fomc_dates(lookback_years: int) -> list[pd.Timestamp]:
    """Past FOMC decision dates within the lookback window."""
    cutoff = pd.Timestamp.now(tz="UTC") - pd.DateOffset(years=lookback_years)
    now = pd.Timestamp.now(tz="UTC")
    dates = []
    for d_str in FOMC_DECISION_DATES:
        try:
            d = pd.Timestamp(d_str, tz="UTC")
        except Exception:
            continue
        if cutoff <= d <= now:
            dates.append(d)
    return sorted(dates)


def _event_study(
    px: pd.DataFrame,
    event_dates: list,
    ticker: str,
    mkt_col: str,
    window: int,
    est_window: int,
) -> dict:
    """Pure market-model event study over a pre-built close-price frame.

    ``px`` must be a DataFrame indexed by date with columns including
    ``ticker`` and ``mkt_col``. ``event_dates`` are timestamp-like values
    (the raw, possibly-non-trading-day, event dates).
    """
    if not event_dates or ticker not in px.columns or mkt_col not in px.columns:
        return {"error": "no events with sufficient data"}

    px2 = px[[ticker, mkt_col]].dropna(how="any")
    if px2.empty:
        return {"error": "no events with sufficient data"}

    rets = _simple_returns(px2)
    if rets.empty:
        return {"error": "no events with sufficient data"}

    trading_days = rets.index  # DatetimeIndex of days with a valid return
    n_days = len(trading_days)

    events_out: list[dict] = []
    car_paths: list[np.ndarray] = []

    for ev in event_dates:
        ev_ts = pd.Timestamp(ev)
        if ev_ts.tzinfo is not None:
            ev_ts = ev_ts.tz_localize(None)
        # Align: trading_days may be tz-naive; ensure comparison works
        idx_naive = trading_days.tz_localize(None) if trading_days.tz is not None else trading_days

        # Find event day t0 = first trading day ON/after ev_ts
        pos_candidates = np.searchsorted(idx_naive.values, np.datetime64(ev_ts), side="left")
        if pos_candidates >= n_days:
            continue  # event is after all available data
        t0 = pos_candidates

        est_end = t0 - _GAP_BEFORE_EVENT
        est_start = est_end - est_window
        if est_start < 0 or est_end <= est_start:
            continue  # insufficient estimation history

        win_start = t0 - window
        win_end = t0 + window
        if win_start < 0 or win_end >= n_days:
            continue  # insufficient event-window data

        est_slice = rets.iloc[est_start:est_end]
        stock_est = est_slice[ticker].values
        mkt_est = est_slice[mkt_col].values
        if len(stock_est) < _MIN_EST_OBS:
            continue

        # OLS: stock_est = alpha + beta * mkt_est
        A = np.vstack([np.ones_like(mkt_est), mkt_est]).T
        try:
            coef, *_ = np.linalg.lstsq(A, stock_est, rcond=None)
        except Exception:
            continue
        alpha, beta = coef[0], coef[1]

        win_slice = rets.iloc[win_start:win_end + 1]
        stock_win = win_slice[ticker].values
        mkt_win = win_slice[mkt_col].values
        expected = alpha + beta * mkt_win
        ar = stock_win - expected
        cum_ar = np.cumsum(ar)

        car_paths.append(cum_ar)
        events_out.append({
            "date": idx_naive[t0].strftime("%Y-%m-%d"),
            "car": _clean(cum_ar[-1]),
            "eventDayReturn": _clean(rets.iloc[t0][ticker]) if t0 < len(rets) else None,
        })

    if not events_out:
        return {"error": "no events with sufficient data"}

    n = len(events_out)
    car_matrix = np.vstack(car_paths)  # shape (n, 2*window+1)
    avg_car_by_day = car_matrix.mean(axis=0)
    car_path = [
        {"day": d, "avgCar": _clean(avg_car_by_day[d + window])}
        for d in range(-window, window + 1)
    ]

    final_cars = np.array([e["car"] for e in events_out], dtype=float)
    mean_car = float(final_cars.mean())
    median_car = float(np.median(final_cars))
    hit_rate = float((final_cars > 0).sum() / n * 100.0)

    t_stat = None
    if n >= 2:
        sd = final_cars.std(ddof=1)
        if sd > 0:
            t_stat = float(mean_car / (sd / math.sqrt(n)))

    return {
        "ticker": ticker,
        "nEvents": n,
        "kpis": {
            "meanCar": _clean(mean_car),
            "medianCar": _clean(median_car),
            "hitRate": _clean(hit_rate),
            "tStat": _clean(t_stat),
        },
        "carPath": car_path,
        "events": events_out,
        "window": window,
        "estWindow": est_window,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("event_study")
def run_event_study(
    ticker: str,
    event_type: str,
    window: int = 5,
    est_window: int = 120,
    lookback_years: int = 5,
) -> dict:
    """Run an event study of ``ticker`` abnormal returns around ``event_type`` events.

    ``event_type`` is one of {"earnings", "fomc"}. Returns::

        {
          "ticker", "eventType", "nEvents",
          "kpis": {"meanCar", "medianCar", "hitRate", "tStat"},
          "carPath": [{"day", "avgCar"}, ...],
          "events": [{"date", "car", "eventDayReturn"}, ...],
          "window", "estWindow"
        }

    or ``{"error": "..."}`` on failure.
    """
    ticker = ticker.upper().strip()

    if event_type == "earnings":
        event_dates = _fetch_earnings_dates(ticker, lookback_years)
        if not event_dates:
            return {"error": "no earnings dates available"}
    elif event_type == "fomc":
        event_dates = _fetch_fomc_dates(lookback_years)
        if not event_dates:
            return {"error": "no FOMC dates available"}
    else:
        return {"error": f"unknown event_type: {event_type}"}

    px = yfs.get_close_frame((ticker, _MARKET_COL), "10y")
    if px.empty or ticker not in px.columns or _MARKET_COL not in px.columns:
        return {"error": "insufficient price data"}

    result = _event_study(px, event_dates, ticker, _MARKET_COL, window, est_window)
    if "error" in result:
        return result

    result["eventType"] = event_type
    return result
