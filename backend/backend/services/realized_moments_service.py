"""Realized Moments service — Phase 15.

Computes Garman-Klass realized variance, realized skewness, and realized
kurtosis from daily OHLC data for a single ticker time-series, and provides
a cross-sectional sort by prior skewness to test the MAX/MIN effect.
"""
from __future__ import annotations

import logging
import math
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from .. import provenance as pv
from . import constituents
from . import yfinance_service as yfs
from ..cache import cached

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GK_K = 2 * math.log(2) - 1          # ≈ 0.3863; Garman-Klass open-to-close coefficient
_WINDOWS = (21, 63, 252)               # 1M, 3M, 12M rolling windows
_MIN_TS_ROWS = 22                      # minimum OHLC rows for get_moments
_XS_FETCH_PERIOD = "1y"               # fetch period for cross-section
_MIN_XS_NAMES = 10                    # minimum valid tickers for cross-section


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _clean(x) -> Optional[float]:
    """Convert to Python float; map NaN/inf/None → None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _gk_variance(df: pd.DataFrame) -> pd.Series:
    """Per-day Garman-Klass variance estimate.

    Formula: 0.5 * ln(H/L)^2 - _GK_K * ln(C/O)^2
    Returns a Series aligned to df.index (may contain NaN where O or C == 0).
    """
    ln_hl = np.log(df["High"] / df["Low"])
    ln_co = np.log(df["Close"] / df["Open"])
    return 0.5 * ln_hl ** 2 - _GK_K * ln_co ** 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("moments_single")
def get_moments(ticker: str, period: str = "3y") -> dict:
    """Return realized moments time-series for *ticker*.

    Returns:
        {
          "ticker": str,
          "period": str,
          "asOf":   "YYYY-MM-DD",
          "series": [{"date","rvol21","rvol63","rvol252","skew21","skew63","skew252",
                       "kurt21","kurt63","kurt252"}, ...],   # last 756 rows
          "latest": {"rvol21","skew21","kurt21"} | None,
          "error":  str   (only on failure)
        }
    """
    ohlc = yfs.get_ohlc_frame((ticker,), period)
    df = ohlc.get(ticker)

    if df is None or len(df) < _MIN_TS_ROWS:
        return {
            "ticker": ticker,
            "period": period,
            "asOf":   date.today().isoformat(),
            "error":  "insufficient price history",
            "series": [],
            "latest": None,
        }

    logret = np.log(df["Close"]).diff().dropna()
    gk = _gk_variance(df)

    # Rolling realized vol annualised from GK variance; clip(lower=0) before sqrt
    # to guard against negative GK values caused by large open-to-close gaps.
    rvol: dict[int, pd.Series] = {}
    for w in _WINDOWS:
        rvol[w] = np.sqrt(gk.clip(lower=0).rolling(w).mean() * 252)

    # Rolling skewness and excess kurtosis from log-returns
    skew: dict[int, pd.Series] = {}
    kurt: dict[int, pd.Series] = {}
    for w in _WINDOWS:
        skew[w] = logret.rolling(w).skew()
        kurt[w] = logret.rolling(w).kurt()   # pandas .kurt() returns excess kurtosis

    # Build the shared date index from df; keep last 756 rows (~3y of trading days)
    idx = df.index[-756:]

    series = []
    for dt in idx:
        row: dict = {"date": pd.Timestamp(dt).strftime("%Y-%m-%d")}
        for w in _WINDOWS:
            row[f"rvol{w}"]  = _clean(rvol[w].get(dt))
            row[f"skew{w}"]  = _clean(skew[w].get(dt) if dt in skew[w].index else None)
            row[f"kurt{w}"]  = _clean(kurt[w].get(dt) if dt in kurt[w].index else None)
        series.append(row)

    # Latest finite values (last non-None in each series)
    def _last_finite(s: pd.Series) -> Optional[float]:
        finite = s.dropna()
        finite = finite[np.isfinite(finite)]
        return _clean(finite.iloc[-1]) if len(finite) else None

    latest = {
        "rvol21": _last_finite(rvol[21]),
        "skew21": _last_finite(skew[21]),
        "kurt21": _last_finite(kurt[21]),
    }

    ohlc_ref = pv.yahoo(ticker, "Daily open/high/low/close (adjusted)", units="price (split/dividend adjusted)",
                        frequency="daily", observed=pv.last_date(df))
    return pv.attach({
        "ticker": ticker,
        "period": period,
        "asOf":   date.today().isoformat(),
        "series": series,
        "latest": latest,
    }, {
        "*": pv.derived("Rolling realised moments over 21, 63 and 252 sessions from daily prices", [ohlc_ref],
                        title="Realised moments", observed=pv.last_date(df)),
        "series.rvol": pv.derived(
            "√(252 × mean over the window of max(Garman-Klass daily variance, 0)), where daily variance = "
            "0.5·ln(High/Low)² − (2·ln2 − 1)·ln(Close/Open)²", [ohlc_ref], title="Realised volatility (Garman-Klass)"),
        "series.skew": pv.derived("sample skewness of daily log returns of the close over the window", [ohlc_ref],
                                  title="Realised skewness"),
        "series.kurt": pv.derived("sample excess kurtosis of daily log returns of the close over the window",
                                  [ohlc_ref], title="Realised excess kurtosis"),
        "latest": pv.derived("the most recent finite 21-session values of the three series above", ["series.rvol"],
                             title="Latest 21-session moments", observed=pv.last_date(df)),
    })


@cached("moments_crosssection")
def get_crosssection(universe: str = "dow", window: int = 21) -> dict:
    """Cross-sectional skewness sort to test the MAX/MIN effect.

    Splits the universe into *window*-day formation / forward windows.
    Returns decile-average forward returns sorted by prior skewness.

    Returns:
        {
          "universe": str,
          "window":   int,
          "asOf":     "YYYY-MM-DD",
          "deciles":  [{"decile","avgSkew","avgFwdReturn","count"}, ...],
          "names":    [{"ticker","priorSkew","fwdReturn"}, ...],
          "missing":  [str, ...],
          "error":    str   (only on failure)
        }
    """
    # 1. Resolve universe
    try:
        symbols = constituents.constituent_symbols(universe)
    except Exception:
        log.exception("realized_moments_service: failed to fetch universe %r", universe)
        return {
            "universe": universe, "window": window, "asOf": date.today().isoformat(),
            "error": "failed to resolve universe", "deciles": [], "names": [], "missing": [],
        }

    if not symbols:
        return {
            "universe": universe, "window": window, "asOf": date.today().isoformat(),
            "error": "insufficient data", "deciles": [], "names": [], "missing": [],
        }

    # 2. Fetch OHLC (~1 year)
    try:
        ohlc = yfs.get_ohlc_frame(tuple(symbols), _XS_FETCH_PERIOD)
    except Exception:
        log.exception("realized_moments_service: get_ohlc_frame failed")
        return {
            "universe": universe, "window": window, "asOf": date.today().isoformat(),
            "error": "insufficient data", "deciles": [], "names": [], "missing": list(symbols),
        }

    # 3. Compute prior skew and forward return per ticker
    valid: list[dict] = []
    missing: list[str] = []
    min_rows = 2 * window + 1

    for sym in symbols:
        df = ohlc.get(sym)
        if df is None or len(df) < min_rows:
            missing.append(sym)
            continue

        t = len(df) - window           # formation cut-point (iloc index)
        logret = np.log(df["Close"]).diff().dropna()

        # Map logret index positions back to iloc positions of df
        # logret has one fewer row than df; align by tail
        logret_arr = logret.values      # numpy array, length = len(df) - 1
        # Formation slice: rows [t-window : t] of the log-return series
        # logret index i corresponds to df row i+1 (diff drops first)
        # So iloc slice of logret for formation: [t-window-1 : t-1]
        # But we keep it simple: use the last `window` returns before bar t
        formation_ret = logret_arr[t - window - 1 : t - 1] if t - window - 1 >= 0 else logret_arr[:t - 1]

        if len(formation_ret) < window:
            missing.append(sym)
            continue

        prior_skew = float(pd.Series(formation_ret).skew())

        # Forward return: from price at bar t-1 to last bar
        try:
            p_start = float(df["Close"].iloc[t - 1])
            p_end   = float(df["Close"].iloc[-1])
        except (IndexError, TypeError, ValueError):
            missing.append(sym)
            continue
        if p_start == 0:
            missing.append(sym)
            continue
        fwd_return = p_end / p_start - 1.0

        if not math.isfinite(prior_skew) or not math.isfinite(fwd_return):
            missing.append(sym)
            continue

        valid.append({"ticker": sym, "priorSkew": prior_skew, "fwdReturn": fwd_return})

    if len(valid) < _MIN_XS_NAMES:
        return {
            "universe": universe, "window": window, "asOf": date.today().isoformat(),
            "error": "insufficient data", "deciles": [], "names": valid, "missing": missing,
        }

    # 4. Sort by priorSkew ascending (1 = most negative skew, k = most positive)
    valid.sort(key=lambda r: r["priorSkew"])
    n = len(valid)
    k = min(10, n)

    from collections import defaultdict
    bucket_skew: dict[int, list[float]] = defaultdict(list)
    bucket_fwd:  dict[int, list[float]] = defaultdict(list)

    for i, rec in enumerate(valid):
        label = min(int(np.floor(i * k / n)) + 1, k)
        bucket_skew[label].append(rec["priorSkew"])
        bucket_fwd[label].append(rec["fwdReturn"])

    deciles = []
    for d in range(1, k + 1):
        skews = bucket_skew.get(d, [])
        fwds  = bucket_fwd.get(d, [])
        deciles.append({
            "decile":       d,
            "avgSkew":      _clean(float(np.mean(skews))) if skews else None,
            "avgFwdReturn": _clean(float(np.mean(fwds)))  if fwds  else None,
            "count":        len(fwds),
        })

    names = [
        {"ticker": r["ticker"], "priorSkew": _clean(r["priorSkew"]), "fwdReturn": _clean(r["fwdReturn"])}
        for r in valid
    ]

    name = {"sp500": "S&P 500", "ndx": "Nasdaq-100", "dow": "Dow Jones Industrial Average"}.get(universe, universe)
    inputs = [
        pv.ref("yahoo", None, f"Daily adjusted close of each {name} member", units="price (split/dividend adjusted)",
               frequency="daily", observed=max((str(o.index[-1])[:10] for o in ohlc.values()), default=None)),
        pv.ref("wikipedia", None, f"Current {name} constituents"),
    ]
    return pv.attach({
        "universe": universe,
        "window":   window,
        "asOf":     date.today().isoformat(),
        "deciles":  deciles,
        "names":    names,
        "missing":  missing,
    }, {
        "*": pv.derived(
            f"Skewness sort over today's {name} members: priorSkew = sample skewness of the {window} daily log "
            f"returns before the split point, fwdReturn = close-to-close return over the last {window} sessions; "
            "names are ranked by priorSkew into up to 10 equal-count deciles (one formation/forward pair, not a "
            "time series)", inputs, title="Skewness cross-section"),
        "deciles": pv.derived("mean priorSkew and mean fwdReturn of the names in each decile", inputs,
                              title="Skewness deciles"),
    })
