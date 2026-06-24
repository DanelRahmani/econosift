"""Market breadth metrics over an index's constituents.

Everything derives from one batched adjusted-close download of the index
members (compute tier 🟢, runs on page load). We compute the classic breadth
internals — advancers/decliners, new highs/lows, % above SMA50/200, the
ratio-adjusted McClellan Oscillator/Summation index, and the cumulative
advance-decline line — and expose the daily A/D + McClellan series so the
Fear & Greed engine can reuse them without re-downloading.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cached
from . import yfinance_service as yfs
from . import constituents


def _close_frame(index: str) -> pd.DataFrame:
    """One year of constituent closes; columns are members with data."""
    syms = tuple(constituents.constituent_symbols(index))
    if not syms:
        return pd.DataFrame()
    frame = yfs.get_close_frame(syms, "1y")
    if frame is None or frame.empty:
        return pd.DataFrame()
    return frame.sort_index()


def _adv_decl_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Daily advancers/decliners across the universe.

    Returns a frame indexed by date with columns adv, dec, net (adv-dec) and
    the ratio-adjusted net advance ``rana = (adv-dec)/(adv+dec)``.
    """
    if frame.empty:
        return pd.DataFrame(columns=["adv", "dec", "net", "rana"])
    delta = frame.diff()
    adv = (delta > 0).sum(axis=1)
    dec = (delta < 0).sum(axis=1)
    out = pd.DataFrame({"adv": adv, "dec": dec})
    out["net"] = out["adv"] - out["dec"]
    total = (out["adv"] + out["dec"]).replace(0, np.nan)
    out["rana"] = (out["net"] / total).fillna(0.0)
    return out.iloc[1:]  # first row is all-NaN diff


def mcclellan(adv_decl: pd.DataFrame) -> pd.DataFrame:
    """Ratio-adjusted McClellan Oscillator and Summation Index.

    Oscillator = 1000·(EMA19(RANA) − EMA39(RANA)); Summation = cumulative sum
    of the oscillator. Scaling by 1000 puts the oscillator on its conventional
    ±100 range.
    """
    if adv_decl.empty:
        return pd.DataFrame(columns=["oscillator", "summation"])
    rana = adv_decl["rana"]
    ema19 = rana.ewm(span=19, adjust=False).mean()
    ema39 = rana.ewm(span=39, adjust=False).mean()
    osc = (ema19 - ema39) * 1000.0
    return pd.DataFrame({"oscillator": osc, "summation": osc.cumsum()})


@cached("breadth")
def breadth(index: str = "sp500") -> dict:
    """Full breadth snapshot for an index (compute tier 🟢)."""
    frame = _close_frame(index)
    empty = {
        "index": index, "asOf": None, "total": 0,
        "advancing": 0, "declining": 0, "unchanged": 0,
        "newHighs": 0, "newLows": 0,
        "pctAboveSma50": None, "pctAboveSma200": None,
        "mcclellanOscillator": None, "mcclellanSummation": None,
        "cumulativeAdLine": [], "advDeclHistory": [],
    }
    if frame.empty:
        return empty

    last = frame.iloc[-1]
    prev = frame.iloc[-2] if len(frame) > 1 else last
    valid = last.notna() & prev.notna()
    diff = last[valid] - prev[valid]
    advancing = int((diff > 0).sum())
    declining = int((diff < 0).sum())
    unchanged = int((diff == 0).sum())
    total = int(valid.sum())

    # 52-week highs / lows: today's close at the extreme of the trailing window.
    window = frame.tail(252)
    highs = lows = 0
    for col in frame.columns:
        s = window[col].dropna()
        if len(s) < 30:
            continue
        cur = s.iloc[-1]
        if cur >= s.max() - 1e-9:
            highs += 1
        elif cur <= s.min() + 1e-9:
            lows += 1

    # % above SMA50 / SMA200.
    def _pct_above(n: int) -> float | None:
        if len(frame) < n:
            return None
        sma = frame.tail(n).mean()
        comp = (last > sma) & last.notna() & sma.notna()
        denom = (last.notna() & sma.notna()).sum()
        return round(float(comp.sum()) / float(denom) * 100.0, 1) if denom else None

    ad = _adv_decl_series(frame)
    mc = mcclellan(ad)
    cum_ad = ad["net"].cumsum()

    def _series(s: pd.Series, n: int = 90) -> list[dict]:
        s = s.dropna().tail(n)
        return [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in s.items()]

    return {
        "index": index,
        "asOf": frame.index[-1].strftime("%Y-%m-%d"),
        "total": total,
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "newHighs": highs,
        "newLows": lows,
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

    Returns the McClellan summation series and the daily new-high / new-low
    ratio context derived from the same constituent frame.
    """
    frame = _close_frame(index)
    if frame.empty:
        return {"summation": pd.Series(dtype=float)}
    ad = _adv_decl_series(frame)
    mc = mcclellan(ad)
    return {"summation": mc["summation"] if not mc.empty else pd.Series(dtype=float)}
