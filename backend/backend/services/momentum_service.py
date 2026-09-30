"""Cross-Sectional Momentum service — Phase 14.

Sorts a stock universe by a prior-return signal into deciles and reports:
  - decile-average prior returns (1=weakest, k=strongest momentum)
  - top-20 and bottom-20 ranked stocks
  - missing tickers that lacked sufficient history

Signal offsets (trading-day iloc):
  "1m"    : price[-1] / price[-21]  - 1
  "3m"    : price[-1] / price[-63]  - 1
  "6m"    : price[-1] / price[-126] - 1
  "12m1m" : price[-21] / price[-252] - 1  (skip recent month, classic momentum)
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

_SIGNAL_OFFSETS: dict[str, tuple[int, int]] = {
    # (numerator_offset, denominator_offset)  — both negative iloc from end
    "1m":    (-1,  -21),
    "3m":    (-1,  -63),
    "6m":    (-1,  -126),
    "12m1m": (-21, -252),
}

# Minimum history rows needed for each signal
_MIN_ROWS: dict[str, int] = {
    "1m":    22,
    "3m":    64,
    "6m":    127,
    "12m1m": 253,
}

_SIGNAL_FORMULAS = {
    "1m": "close (latest) ÷ close 21 sessions earlier − 1",
    "3m": "close (latest) ÷ close 63 sessions earlier − 1",
    "6m": "close (latest) ÷ close 126 sessions earlier − 1",
    "12m1m": "close 21 sessions ago ÷ close 252 sessions ago − 1 (skips the most recent month)",
}
_INDEX_NAMES = {"sp500": "S&P 500", "ndx": "Nasdaq-100", "dow": "Dow Jones Industrial Average"}

_DEFAULT_UNIVERSE = "dow"
_DEFAULT_SIGNAL   = "12m1m"
_FETCH_PERIOD     = "2y"   # enough for 12m-1m


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


def _compute_signal(series: pd.Series, signal: str) -> Optional[float]:
    """Return prior-return for *series* using *signal* offsets.

    Returns None when there is insufficient history.
    """
    num_off, den_off = _SIGNAL_OFFSETS[signal]
    min_rows = _MIN_ROWS[signal]
    s = series.dropna()
    if len(s) < min_rows:
        return None
    try:
        price_num = float(s.iloc[num_off])
        price_den = float(s.iloc[den_off])
    except (IndexError, TypeError, ValueError):
        return None
    if price_den == 0:
        return None
    ret = price_num / price_den - 1.0
    return _clean(ret)


def _error_response(universe: str, signal: str, missing: list[str]) -> dict:
    return {
        "universe": universe,
        "signal":   signal,
        "asOf":     date.today().isoformat(),
        "error":    "insufficient data",
        "deciles":  [],
        "top":      [],
        "bottom":   [],
        "missing":  missing,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("momentum_ranked")
def get_momentum(universe: str = _DEFAULT_UNIVERSE, signal: str = _DEFAULT_SIGNAL) -> dict:
    """Return cross-sectional momentum ranking for *universe* using *signal*.

    Returns:
        {
          "universe": str,
          "signal":   str,
          "asOf":     "YYYY-MM-DD",
          "deciles":  [{"decile": int, "avgReturn": float, "count": int}, ...],
          "top":      [{"ticker": str, "momentum": float}, ...],   # up to 20, desc
          "bottom":   [{"ticker": str, "momentum": float}, ...],   # up to 20, asc
          "missing":  [str, ...]
        }
    """
    if signal not in _SIGNAL_OFFSETS:
        log.warning("momentum_service: unknown signal %r; using default", signal)
        signal = _DEFAULT_SIGNAL

    # 1. Resolve universe
    try:
        symbols = constituents.constituent_symbols(universe)
    except Exception:
        log.exception("momentum_service: failed to fetch universe %r", universe)
        return _error_response(universe, signal, [])

    if not symbols:
        return _error_response(universe, signal, [])

    # 2. Fetch prices (~2 years of daily closes)
    try:
        frame: pd.DataFrame = yfs.get_close_frame(tuple(symbols), _FETCH_PERIOD)
    except Exception:
        log.exception("momentum_service: get_close_frame failed")
        return _error_response(universe, signal, symbols)

    if frame is None or frame.empty:
        return _error_response(universe, signal, symbols)

    # 3. Compute signal per ticker
    returns: dict[str, float] = {}
    missing: list[str] = []

    for ticker in symbols:
        if ticker not in frame.columns:
            missing.append(ticker)
            continue
        ret = _compute_signal(frame[ticker], signal)
        if ret is None:
            missing.append(ticker)
        else:
            returns[ticker] = ret

    if len(returns) < 10:
        return _error_response(universe, signal, missing)

    # 4. Sort all tickers by momentum (ascending)
    sorted_tickers = sorted(returns.items(), key=lambda kv: kv[1])  # asc → decile 1 = weakest

    # 5. Split into deciles (1 = weakest, k = strongest momentum)
    n = len(sorted_tickers)
    k = min(10, n)
    # Assign each ticker a decile label (1..k)
    decile_labels: list[int] = []
    for i in range(n):
        # decile 1 = lowest momentum, k = highest
        label = int(np.floor(i * k / n)) + 1
        label = min(label, k)  # clamp to k
        decile_labels.append(label)

    # Build decile summaries
    from collections import defaultdict
    bucket: dict[int, list[float]] = defaultdict(list)
    for (ticker, ret), dlabel in zip(sorted_tickers, decile_labels):
        bucket[dlabel].append(ret)

    deciles = []
    for d in range(1, k + 1):
        vals = bucket.get(d, [])
        avg = _clean(float(np.mean(vals))) if vals else None
        deciles.append({
            "decile":    d,
            "avgReturn": avg,
            "count":     len(vals),
        })

    # 6. Top-20 (highest momentum) and bottom-20 (lowest momentum)
    sorted_desc = sorted(returns.items(), key=lambda kv: kv[1], reverse=True)
    top    = [{"ticker": t, "momentum": _clean(r)} for t, r in sorted_desc[:20]]
    bottom = [{"ticker": t, "momentum": _clean(r)} for t, r in sorted_desc[-20:][::-1]]

    name = _INDEX_NAMES.get(universe, universe)
    inputs = [
        pv.ref("yahoo", None, f"Daily adjusted close of each {name} member", units="price (split/dividend adjusted)",
               frequency="daily", observed=pv.last_date(frame)),
        pv.ref("wikipedia", None, f"Current {name} constituents"),
    ]
    signal_formula = (f"{_SIGNAL_FORMULAS[signal]}, using each ticker's own last non-missing closes "
                      "(trading-day offsets)")
    return pv.attach({
        "universe": universe,
        "signal":   signal,
        "asOf":     date.today().isoformat(),
        "deciles":  deciles,
        "top":      top,
        "bottom":   bottom,
        "missing":  missing,
    }, {
        "*": pv.derived(f"Cross-sectional momentum over today's {name} members: {signal_formula}", inputs,
                        title=f"{name} momentum ranking", observed=pv.last_date(frame)),
        "deciles": pv.derived("mean signal return of the tickers in each equal-count bucket by rank "
                              "(decile 1 = weakest, up to 10 = strongest)", inputs, title="Momentum deciles",
                              observed=pv.last_date(frame)),
        "top": pv.derived(f"the 20 highest signal returns: {signal_formula}", inputs, title="Strongest momentum",
                          observed=pv.last_date(frame)),
        "bottom": pv.derived(f"the 20 lowest signal returns: {signal_formula}", inputs, title="Weakest momentum",
                             observed=pv.last_date(frame)),
    })
