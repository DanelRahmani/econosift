"""Market breadth metrics over an index's constituents.

Everything derives from one batched OHLC download of the index members
(compute tier 🟢, runs on page load). We compute the classic breadth
internals — advancers/decliners, new highs/lows, % above SMA50/200, the
ratio-adjusted McClellan Oscillator/Summation index, and the cumulative
advance-decline line — and expose the daily A/D, new-high/low and McClellan
series so the Fear & Greed engine can reuse them without re-downloading.

Session alignment (audit P2-24 / C-22): every count describes one completed
US session, ``asOf``. A bar for a session that is still trading is dropped,
and a symbol whose latest bar is older than ``asOf`` is left out of that
session's counts instead of contributing a stale reading.

New 52-week highs/lows use the intraday High/Low — the convention of published
counts — with ties counting (a session that matches its 52-week extreme has
reached it).

Limitation: membership is today's constituent list applied to the whole
two-year window (the A/D line and McClellan history carry mild survivorship);
the session-level counts are unaffected.
"""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..cache import cached
from . import yfinance_service as yfs
from . import constituents

_NY = ZoneInfo("America/New_York")
_CLOSE = time(16, 0)
# A session counts as complete only if at least this share of the universe
# has a bar for it (guards against a half-published final row).
_MIN_COVERAGE = 0.9
_LOOKBACK_52W = 252
# McClellan EMAs are seeded from the first observation; discard this many
# sessions before using the series so the seed no longer matters.
_MCCLELLAN_WARMUP = 120


def _now_ny() -> datetime:
    return datetime.now(_NY)


def _ohlc_frames(index: str) -> dict[str, pd.DataFrame]:
    """Two years of constituent OHLC as ``{"close","high","low"}`` frames.

    Columns are members with data; the index is session dates. Trailing
    sessions that are still in progress or thinly covered are dropped.
    """
    syms = tuple(constituents.constituent_symbols(index))
    if not syms:
        return {}
    raw = yfs.get_ohlc_frame(syms, "2y", adjust=False)
    if not raw:
        return {}
    close = pd.DataFrame({s: df["Close"] for s, df in raw.items()}).sort_index()
    high = pd.DataFrame({s: df["High"] for s, df in raw.items()}).reindex(close.index)
    low = pd.DataFrame({s: df["Low"] for s, df in raw.items()}).reindex(close.index)
    idx = pd.to_datetime(close.index)
    close.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    high.index = low.index = close.index

    # Drop a bar for today's session while the market is still open.
    now = _now_ny()
    if len(close) and close.index[-1].date() == now.date() and now.time() < _CLOSE:
        close, high, low = close.iloc[:-1], high.iloc[:-1], low.iloc[:-1]

    # Drop trailing rows that too few members have printed yet.
    coverage = close.notna().sum(axis=1) / max(close.shape[1], 1)
    complete = coverage[coverage >= _MIN_COVERAGE]
    if complete.empty:
        return {}
    last = complete.index[-1]
    return {"close": close.loc[:last], "high": high.loc[:last], "low": low.loc[:last]}


def _adv_decl_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Daily advancers/decliners across the universe.

    Returns a frame indexed by date with columns adv, dec, net (adv-dec) and
    the ratio-adjusted net advance ``rana = (adv-dec)/(adv+dec)``. Only
    symbols with a bar on both consecutive sessions are compared.
    """
    if frame.empty:
        return pd.DataFrame(columns=["adv", "dec", "net", "rana"])
    delta = frame - frame.shift(1)
    adv = (delta > 0).sum(axis=1)
    dec = (delta < 0).sum(axis=1)
    out = pd.DataFrame({"adv": adv, "dec": dec})
    out["net"] = out["adv"] - out["dec"]
    total = (out["adv"] + out["dec"]).replace(0, np.nan)
    out["rana"] = (out["net"] / total).fillna(0.0)
    return out.iloc[1:]  # first row has no prior session


def _highs_lows_series(high: pd.DataFrame, low: pd.DataFrame,
                       close: pd.DataFrame) -> pd.DataFrame:
    """Daily count of members at a new 52-week intraday high / low.

    A member is counted on a session only if it traded that session and has
    at least 30 sessions of history in the trailing window.
    """
    traded = close.notna()
    enough = close.notna().rolling(_LOOKBACK_52W, min_periods=1).sum() >= 30
    hi_max = high.rolling(_LOOKBACK_52W, min_periods=1).max()
    lo_min = low.rolling(_LOOKBACK_52W, min_periods=1).min()
    is_hi = (high >= hi_max - 1e-9) & traded & enough
    is_lo = (low <= lo_min + 1e-9) & traded & enough
    return pd.DataFrame({"highs": is_hi.sum(axis=1), "lows": is_lo.sum(axis=1)})


def mcclellan(adv_decl: pd.DataFrame) -> pd.DataFrame:
    """Ratio-adjusted McClellan Oscillator and Summation Index.

    Oscillator = 1000·(EMA19(RANA) − EMA39(RANA)); Summation = cumulative sum
    of the oscillator. Scaling by 1000 puts the oscillator on its conventional
    ±100 range. The Summation *level* is relative to the window start (a
    constant offset); percentile ranks of it are unaffected by that offset.
    """
    if adv_decl.empty:
        return pd.DataFrame(columns=["oscillator", "summation"])
    rana = adv_decl["rana"]
    ema19 = rana.ewm(span=19, adjust=False).mean()
    ema39 = rana.ewm(span=39, adjust=False).mean()
    osc = (ema19 - ema39) * 1000.0
    out = pd.DataFrame({"oscillator": osc, "summation": osc.cumsum()})
    # Drop the EMA seeding period when enough history exists.
    return out.iloc[_MCCLELLAN_WARMUP:] if len(out) > _MCCLELLAN_WARMUP + 60 else out


def _unavailable(index: str) -> dict:
    # Unknown is None, never 0 — a zero would be displayed (and read) as a
    # real "no stocks advanced" reading. The status marks it uncacheable.
    return {
        "index": index, "asOf": None, "status": "unavailable", "total": None,
        "advancing": None, "declining": None, "unchanged": None,
        "newHighs": None, "newLows": None,
        "pctAboveSma50": None, "pctAboveSma200": None,
        "mcclellanOscillator": None, "mcclellanSummation": None,
        "cumulativeAdLine": [], "advDeclHistory": [],
    }


@cached("breadth")
def breadth(index: str = "sp500") -> dict:
    """Full breadth snapshot for an index's last completed session (🟢)."""
    frames = _ohlc_frames(index)
    if not frames:
        return _unavailable(index)
    close, high, low = frames["close"], frames["high"], frames["low"]
    if len(close) < 2:
        return _unavailable(index)

    as_of = close.index[-1]
    last = close.iloc[-1]
    prev = close.iloc[-2]
    valid = last.notna() & prev.notna()
    diff = last[valid] - prev[valid]
    advancing = int((diff > 0).sum())
    declining = int((diff < 0).sum())
    unchanged = int((diff == 0).sum())
    total = int(valid.sum())

    hl = _highs_lows_series(high, low, close)

    # % above SMA50 / SMA200 — members that printed on the as-of session.
    def _pct_above(n: int) -> float | None:
        if len(close) < n:
            return None
        sma = close.rolling(n, min_periods=int(n * 0.9)).mean().iloc[-1]
        ok = last.notna() & sma.notna()
        denom = int(ok.sum())
        return round(float((last[ok] > sma[ok]).sum()) / denom * 100.0, 1) if denom else None

    ad = _adv_decl_series(close)
    mc = mcclellan(ad)
    cum_ad = ad["net"].cumsum()

    def _series(s: pd.Series, n: int = 90) -> list[dict]:
        s = s.dropna().tail(n)
        return [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in s.items()]

    return {
        "index": index,
        "asOf": as_of.strftime("%Y-%m-%d"),
        "session": "close",
        "total": total,
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "newHighs": int(hl["highs"].iloc[-1]),
        "newLows": int(hl["lows"].iloc[-1]),
        "pctAboveSma50": _pct_above(50),
        "pctAboveSma200": _pct_above(200),
        "mcclellanOscillator": (round(float(mc["oscillator"].iloc[-1]), 2)
                                if not mc.empty else None),
        "mcclellanSummation": (round(float(mc["summation"].iloc[-1]), 2)
                               if not mc.empty else None),
        "cumulativeAdLine": _series(cum_ad),
        "advDeclHistory": [
            {"date": d.strftime("%Y-%m-%d"), "adv": int(r.adv), "dec": int(r.dec)}
            for d, r in ad.tail(90).iterrows()
        ],
    }


def breadth_internals(index: str = "sp500") -> dict:
    """Series the Fear & Greed engine needs without a second download.

    Returns the McClellan summation series, the daily new-high / new-low
    counts and the as-of session, all from the same session-aligned frame.
    """
    frames = _ohlc_frames(index)
    empty = {"summation": pd.Series(dtype=float), "highsLows": pd.DataFrame(), "asOf": None}
    if not frames or len(frames["close"]) < 2:
        return empty
    close = frames["close"]
    mc = mcclellan(_adv_decl_series(close))
    return {
        "summation": mc["summation"] if not mc.empty else pd.Series(dtype=float),
        "highsLows": _highs_lows_series(frames["high"], frames["low"], close),
        "asOf": close.index[-1],
    }
