"""FX Rates panel service — yfinance-backed, 16 currency pairs vs a base."""
from __future__ import annotations

import math
from datetime import date

import pandas as pd

from ..cache import cached
from ..services import yfinance_service as yfs

# Currency universe (quote currencies vs the base).
_QUOTE_CCYS = [
    "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
    "CNY", "INR", "MXN", "BRL", "SEK", "NOK", "ZAR", "HKD", "SGD",
]

# Approximate trading-day offsets for change windows.
_WINDOWS = {"change1d": 1, "change1w": 5, "change1m": 21, "change1y": 252}

_SPARKLINE_DAYS = 30


def _clean(x) -> float | None:
    """Return a finite float or None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _pct_change(series: pd.Series, n: int) -> float | None:
    """Percent change of last value vs n bars ago; guarded."""
    s = series.dropna()
    if len(s) <= n:
        # Use whatever history we have down to 2 points.
        if len(s) < 2:
            return None
        n = len(s) - 1
    old = _clean(s.iloc[-(n + 1)])
    new = _clean(s.iloc[-1])
    if old is None or new is None or old == 0:
        return None
    return round((new / old - 1.0) * 100.0, 4)


def _sparkline(series: pd.Series, days: int = _SPARKLINE_DAYS) -> list[float]:
    s = series.dropna().tail(days)
    result = []
    for v in s:
        c = _clean(v)
        if c is not None:
            result.append(round(c, 6))
    return result


@cached("fx_rates")
def fx_rates(base: str = "USD") -> dict:
    """Return FX panel: current rate + changes + sparkline for 16 pairs vs base."""
    base = base.upper()

    # Build primary tickers: base + quote (e.g. USDEUR=X, USDJPY=X).
    primary_tickers = tuple(f"{base}{ccy}=X" for ccy in _QUOTE_CCYS)

    # Fetch 1y of daily closes in one batch call.
    frame = yfs.get_close_frame(primary_tickers, "1y")

    # Also fetch inverse tickers for pairs that came back empty.
    # We do a second call only for the missing ones to stay efficient.
    empty_ccys = [
        ccy for ccy, tk in zip(_QUOTE_CCYS, primary_tickers)
        if frame is None or frame.empty or tk not in frame.columns or frame[tk].dropna().empty
    ]

    inv_frame: pd.DataFrame = pd.DataFrame()
    if empty_ccys:
        inv_tickers = tuple(f"{ccy}{base}=X" for ccy in empty_ccys)
        inv_frame = yfs.get_close_frame(inv_tickers, "1y")

    as_of = date.today().isoformat()
    pairs: list[dict] = []

    for ccy in _QUOTE_CCYS:
        primary_tk = f"{base}{ccy}=X"
        inv_tk = f"{ccy}{base}=X"
        pair_label = f"{base}/{ccy}"

        series: pd.Series | None = None
        inverted = False

        # Try primary ticker first.
        if (
            frame is not None
            and not frame.empty
            and primary_tk in frame.columns
            and not frame[primary_tk].dropna().empty
        ):
            series = frame[primary_tk].dropna()
        # Fall back to inverse ticker and invert the series.
        elif (
            not inv_frame.empty
            and inv_tk in inv_frame.columns
            and not inv_frame[inv_tk].dropna().empty
        ):
            raw_inv = inv_frame[inv_tk].dropna()
            # Guard division by zero / near-zero.
            safe = raw_inv[raw_inv != 0]
            if not safe.empty:
                series = (1.0 / safe).reindex(raw_inv.index)
                inverted = True

        if series is None or series.dropna().empty:
            # Return a stub so the consumer always gets the full universe.
            pairs.append({
                "pair": pair_label,
                "quote": ccy,
                "rate": None,
                "change1d": None,
                "change1w": None,
                "change1m": None,
                "change1y": None,
                "sparkline": [],
                "inverted": inverted,
            })
            continue

        rate = _clean(series.iloc[-1])
        entry: dict = {
            "pair": pair_label,
            "quote": ccy,
            "rate": rate,
            "inverted": inverted,
            "sparkline": _sparkline(series),
        }
        for key, n in _WINDOWS.items():
            entry[key] = _pct_change(series, n)

        pairs.append(entry)

    return {
        "base": base,
        "asOf": as_of,
        "pairs": pairs,
    }
