"""S&P 500 / Nasdaq-100 / Dow 30 treemap data (compute tier 🟢).

Returns per-stock price, 1-day or period return%, market cap, 52-week
high/low, sector, and GICS Sub-Industry so the frontend can render an
interactive squarified treemap with d3-hierarchy.

Stocks missing either a market cap or a computable return are dropped — the
frontend needs both to size and colour each tile.
"""
from __future__ import annotations

import datetime
import math

import pandas as pd

from .. import provenance as pv
from ..cache import cached
from . import constituents
from . import yfinance_service as yfs
from .sector_service import session_base

# Map UI period strings to the yfinance download window.
_PERIOD_MAP: dict[str, str] = {
    "1d":  "5d",
    "1w":  "1mo",
    "1m":  "3mo",
    "3m":  "6mo",
    "ytd": "1y",
    "1y":  "2y",
}

VALID_PERIODS = set(_PERIOD_MAP.keys())

# Session counts shared with the sector chart and table (sector_service.session_base).
_SESSIONS: dict[str, int] = {"1w": 5, "1m": 21, "3m": 63, "1y": 252}


def _return_pct(frame: pd.DataFrame, period: str) -> pd.Series:
    """Compute per-column return% over the requested period.

    * ``1d``  → last close vs previous close.
    * ``ytd`` → last close vs the last close before 1 Jan of the latest year (the prior year-end).
      A symbol with no close before 1 Jan has no honest base and is omitted (NaN).
    * 1w/1m/3m/1y → last close vs the close 5/21/63/252 sessions earlier (``session_base``, as the
      sector chart and table); a symbol whose history does not reach that base is omitted.

    Returns a Series indexed by symbol.  Symbols without enough rows are
    omitted (NaN → dropped by caller).
    """
    if frame.empty or len(frame) < 2:
        return pd.Series(dtype=float)

    last = frame.iloc[-1]

    if period == "1d":
        prev = frame.iloc[-2]
        raw = (last / prev - 1.0) * 100.0
        return raw.where(prev != 0)

    if period == "ytd":
        latest_year = frame.index[-1].year
        jan1 = pd.Timestamp(latest_year, 1, 1)
        prior = frame[frame.index < jan1]
        if prior.empty:
            return pd.Series(dtype=float)
        first = prior.ffill().iloc[-1]
    else:
        n = _SESSIONS[period]
        out = {}
        for sym in frame.columns:
            s = frame[sym].dropna()
            base = session_base(s, n)
            if base:
                out[sym] = (float(s.iloc[-1]) / base - 1.0) * 100.0
        return pd.Series(out, dtype=float)

    raw = (last / first - 1.0) * 100.0
    return raw.where(first != 0)


@cached("treemap")
def treemap(index: str = "sp500", period: str = "1d") -> dict:
    """Build the treemap payload for a given index and period.

    Returns::

        {
            "index": str,
            "period": str,
            "asOf": str | None,       # last trading date (YYYY-MM-DD)
            "stocks": [
                {
                    "symbol": str,
                    "name": str,
                    "sector": str | None,
                    "industry": str | None,
                    "price": float,
                    "changePercent": float,
                    "marketCap": float,
                    "high52": float,
                    "low52": float,
                }
            ]
        }

    Stocks missing market cap or return% are silently dropped.
    """
    if period not in VALID_PERIODS:
        period = "1d"

    empty = {"index": index, "period": period, "asOf": None, "stocks": []}

    members = constituents.get_constituents(index)
    if not members:
        return empty

    syms = tuple(c["symbol"] for c in members)
    meta = {c["symbol"]: c for c in members}  # symbol → {name, sector, industry}

    # --- Price history (batch download, cached) ---
    window = _PERIOD_MAP[period]
    frame = yfs.get_close_frame(syms, window)
    if frame is None or frame.empty:
        return empty
    frame = frame.sort_index()

    # --- 52-week high/low ---
    # Prefer a full year of history; if the current window already covers it
    # (e.g. "2y"), reuse it.  Otherwise do a second cached download.
    if len(frame) >= 200:
        frame_1y = frame.tail(252)
    else:
        frame_1y = yfs.get_close_frame(syms, "1y")
        if frame_1y is not None and not frame_1y.empty:
            frame_1y = frame_1y.sort_index().tail(252)
        else:
            frame_1y = frame.tail(252)

    # --- Return % ---
    ret = _return_pct(frame, period)

    # --- Market caps (batch, cached) ---
    mcaps = yfs.get_market_caps(syms)

    as_of: str | None = frame.index[-1].strftime("%Y-%m-%d") if len(frame) else None

    stocks: list[dict] = []
    last_row = frame.iloc[-1] if len(frame) else pd.Series(dtype=float)

    for sym in frame.columns:
        # --- price ---
        price_raw = last_row.get(sym)
        if price_raw is None or (isinstance(price_raw, float) and math.isnan(price_raw)):
            continue
        if pd.isna(price_raw):
            continue
        price = round(float(price_raw), 2)

        # --- changePercent ---
        chg_raw = ret.get(sym)
        if chg_raw is None or pd.isna(chg_raw):
            continue
        change_pct = round(float(chg_raw), 2)

        # --- marketCap ---
        mcap = mcaps.get(sym)
        if mcap is None or mcap <= 0 or math.isnan(mcap):
            continue

        # --- 52-week high / low ---
        col_1y = frame_1y[sym].dropna() if sym in frame_1y.columns else pd.Series(dtype=float)
        if col_1y.empty:
            high52 = price
            low52 = price
        else:
            high52 = round(float(col_1y.max()), 2)
            low52 = round(float(col_1y.min()), 2)

        info = meta.get(sym, {})
        stocks.append({
            "symbol":        sym,
            "name":          info.get("name", sym),
            "sector":        info.get("sector"),
            "industry":      info.get("industry"),
            "price":         price,
            "changePercent": change_pct,
            "marketCap":     mcap,
            "high52":        high52,
            "low52":         low52,
        })

    return pv.attach({"index": index, "period": period, "asOf": as_of, "stocks": stocks},
                     _provenance(period, as_of))



_RETURN_FORMULA = {
    "1d": "(last close / previous close − 1) × 100",
    "ytd": "(last close / last close of the previous calendar year − 1) × 100",
    "1w": "(last close / close 5 trading sessions earlier − 1) × 100",
    "1m": "(last close / close 21 trading sessions earlier − 1) × 100",
    "3m": "(last close / close 63 trading sessions earlier − 1) × 100",
    "1y": "(last close / close 252 trading sessions earlier − 1) × 100",
}


def _provenance(period: str, as_of: str | None) -> dict:
    """``stocks.<field>`` keys (one per tile field, the same for every stock) and the payload default."""
    closes = pv.ref("yahoo", None, "Daily adjusted close of each member", units="price, split- and "
                    "dividend-adjusted", frequency="daily", observed=as_of)
    members = pv.ref("wikipedia", None, "Index constituents with GICS sector and sub-industry")
    return {
        "*": pv.derived("per-stock price, return, market cap and 52-week range for the index members",
                        [closes, members], title="Index treemap", observed=as_of),
        "stocks.price": closes,
        "stocks.changePercent": pv.derived(
            _RETURN_FORMULA[period], [closes], title=f"Return, period {period}", observed=as_of,
            note="Same session base as the sector chart and table; a member whose history does not reach "
                 "it has no tile." if period in _SESSIONS else None),
        "stocks.marketCap": pv.yahoo(None, "fast_info.market_cap (current market capitalisation)", units="USD"),
        "stocks.high52": pv.derived("highest close of the last 252 sessions (the price if no history)", [closes],
                                    title="52-week high", observed=as_of),
        "stocks.low52": pv.derived("lowest close of the last 252 sessions (the price if no history)", [closes],
                                   title="52-week low", observed=as_of),
        "stocks.name": members, "stocks.sector": members, "stocks.industry": members,
    }
