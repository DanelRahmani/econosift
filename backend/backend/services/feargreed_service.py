"""Fear & Greed Index — a 7-signal composite (compute tier 🟢).

Each signal is normalised to 0–100 (0 = extreme fear, 100 = extreme greed) and
the index is their average over whatever signals resolve. Any signal whose data
is unavailable is dropped rather than guessed, so the index degrades gracefully
(e.g. when there is no FRED key, or options data is missing).

Signals:
  1. S&P 500 vs 125-day SMA  (momentum z-score)
  2. New Highs / New Lows ratio (from breadth)
  3. McClellan Summation Index percentile
  4. Put/Call OI ratio (SPY options, inverted)
  5. VIX percentile (inverted)
  6. Stocks vs Bonds 20-day relative return (SPY − TLT)
  7. HY credit spread BAMLH0A0HYM2 percentile (inverted)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cached
from ..config import FRED_API_KEY
from . import yfinance_service as yfs
from . import breadth_service


def _clip(x: float) -> float:
    return float(max(0.0, min(100.0, x)))


def _percentile_score(series: pd.Series, *, invert: bool = False) -> float | None:
    """Score the latest value by its percentile rank within the series."""
    s = series.dropna()
    if len(s) < 20:
        return None
    cur = float(s.iloc[-1])
    pct = float((s <= cur).mean()) * 100.0
    return _clip(100.0 - pct if invert else pct)


def _label(score: float) -> str:
    if score < 25:
        return "Extreme Fear"
    if score < 45:
        return "Fear"
    if score < 55:
        return "Neutral"
    if score < 75:
        return "Greed"
    return "Extreme Greed"


def _sp_momentum() -> tuple[float | None, pd.Series]:
    frame = yfs.get_close_frame(("^GSPC",), "2y")
    if frame is None or frame.empty or "^GSPC" not in frame.columns:
        return None, pd.Series(dtype=float)
    s = frame["^GSPC"].dropna()
    if len(s) < 150:
        return None, pd.Series(dtype=float)
    sma = s.rolling(125).mean()
    gap = (s / sma - 1.0).dropna()
    z = (gap - gap.rolling(252, min_periods=60).mean()) / gap.rolling(252, min_periods=60).std()
    score_series = (50.0 + z * 20.0).clip(0, 100)
    cur = score_series.dropna()
    return (round(float(cur.iloc[-1]), 1) if len(cur) else None), score_series


def _vix() -> tuple[float | None, pd.Series]:
    frame = yfs.get_close_frame(("^VIX",), "2y")
    if frame is None or frame.empty or "^VIX" not in frame.columns:
        return None, pd.Series(dtype=float)
    s = frame["^VIX"].dropna()
    # Rolling inverted percentile for the history series.
    roll = s.rolling(252, min_periods=60).apply(
        lambda w: 100.0 - (w <= w.iloc[-1]).mean() * 100.0, raw=False)
    return _percentile_score(s, invert=True), roll


def _stocks_vs_bonds() -> tuple[float | None, pd.Series]:
    frame = yfs.get_close_frame(("SPY", "TLT"), "1y")
    if frame is None or frame.empty or "SPY" not in frame.columns or "TLT" not in frame.columns:
        return None, pd.Series(dtype=float)
    spy = frame["SPY"].dropna()
    tlt = frame["TLT"].dropna()
    rel = (spy.pct_change(20) - tlt.pct_change(20)).dropna()
    # Map a ±10% relative move to the full 0–100 range.
    score_series = (50.0 + rel * 500.0).clip(0, 100)
    cur = score_series.dropna()
    return (round(float(cur.iloc[-1]), 1) if len(cur) else None), score_series


def _hy_spread() -> tuple[float | None, pd.Series]:
    if not FRED_API_KEY:
        return None, pd.Series(dtype=float)
    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_API_KEY)
        s = fred.get_series("BAMLH0A0HYM2", observation_start="2022-01-01")
        s = pd.Series(s).dropna()
        s.index = pd.to_datetime(s.index)
    except Exception:
        return None, pd.Series(dtype=float)
    if len(s) < 60:
        return None, pd.Series(dtype=float)
    roll = s.rolling(252, min_periods=60).apply(
        lambda w: 100.0 - (w <= w.iloc[-1]).mean() * 100.0, raw=False)
    return _percentile_score(s, invert=True), roll


def _put_call() -> float | None:
    """SPY total put/call open-interest ratio, inverted to a 0–100 score.

    High put/call (hedging) → fear → low score. Best-effort: yfinance options
    can be slow or empty, so failures simply drop this signal.
    """
    try:
        import yfinance as yf
        t = yf.Ticker("SPY")
        exps = (t.options or [])[:3]
        put_oi = call_oi = 0
        for e in exps:
            chain = t.option_chain(e)
            call_oi += float(chain.calls["openInterest"].fillna(0).sum())
            put_oi += float(chain.puts["openInterest"].fillna(0).sum())
        if call_oi <= 0:
            return None
        ratio = put_oi / call_oi
        # Typical put/call OI ~0.8–1.6; map inverted into 0–100.
        return _clip(100.0 - (ratio - 0.7) / (1.7 - 0.7) * 100.0)
    except Exception:
        return None


def _highs_lows(breadth_snap: dict) -> float | None:
    hi = breadth_snap.get("newHighs")
    lo = breadth_snap.get("newLows")
    if hi is None or lo is None or (hi + lo) == 0:
        return None
    return _clip(hi / (hi + lo) * 100.0)


@cached("feargreed")
def fear_greed() -> dict:
    breadth_snap = breadth_service.breadth("sp500")
    internals = breadth_service.breadth_internals("sp500")

    sp_score, sp_series = _sp_momentum()
    vix_score, vix_series = _vix()
    svb_score, svb_series = _stocks_vs_bonds()
    hy_score, hy_series = _hy_spread()

    summation = internals.get("summation", pd.Series(dtype=float))
    mcc_score = _percentile_score(summation)
    mcc_series = summation.rolling(252, min_periods=40).apply(
        lambda w: (w <= w.iloc[-1]).mean() * 100.0, raw=False) if len(summation) else pd.Series(dtype=float)

    signals = [
        {"key": "spMomentum", "label": "S&P 500 vs 125-day SMA", "score": sp_score},
        {"key": "highLow", "label": "New Highs / Lows", "score": _highs_lows(breadth_snap)},
        {"key": "mcclellan", "label": "McClellan Summation", "score": mcc_score},
        {"key": "putCall", "label": "Put/Call Ratio", "score": _put_call()},
        {"key": "vix", "label": "Volatility (VIX)", "score": vix_score},
        {"key": "stocksBonds", "label": "Stocks vs Bonds", "score": svb_score},
        {"key": "hySpread", "label": "Junk Bond Demand", "score": hy_score},
    ]
    for s in signals:
        s["label_text"] = _label(s["score"]) if s["score"] is not None else None
        if s["score"] is not None:
            s["score"] = round(float(s["score"]), 1)

    avail = [s["score"] for s in signals if s["score"] is not None]
    index = round(float(np.mean(avail)), 1) if avail else None

    # 90-day history: mean of the time-series-able signals per day.
    hist_frame = pd.concat(
        [s.rename(k) for k, s in (
            ("sp", sp_series), ("vix", vix_series),
            ("svb", svb_series), ("hy", hy_series), ("mcc", mcc_series))
         if s is not None and len(s)],
        axis=1,
    ) if any(len(s) for s in (sp_series, vix_series, svb_series, hy_series, mcc_series)) else pd.DataFrame()
    history: list[dict] = []
    if not hist_frame.empty:
        composite = hist_frame.mean(axis=1).dropna().tail(90)
        history = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 1)}
                   for d, v in composite.items()]

    return {
        "index": index,
        "label": _label(index) if index is not None else None,
        "asOf": breadth_snap.get("asOf"),
        "signals": signals,
        "history": history,
    }
