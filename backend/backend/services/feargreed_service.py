"""Fear & Greed Index — a 7-signal composite (compute tier 🟢).

Each signal is normalised to 0–100 (0 = extreme fear, 100 = extreme greed) and
the index is their average over whatever signals resolve. Any signal whose data
is unavailable is dropped rather than guessed, so the index degrades gracefully
(e.g. when there is no FRED key, or options data is missing).

Signals:
  1. S&P 500 vs 125-day SMA  (momentum z-score)
  2. New Highs / New Lows ratio (from breadth, intraday 52-week extremes)
  3. McClellan Summation Index percentile
  4. Put/Call OI ratio (SPY options, inverted)
  5. VIX percentile (inverted)
  6. Stocks vs Bonds 20-day relative return (SPY − TLT)
  7. HY credit spread BAMLH0A0HYM2 percentile (inverted)

Date alignment (audit P2-24 / C-21): every series is cut at the breadth
``asOf`` session so no signal uses data from a later session, and each signal
reports the date of the observation it actually used. The headline and the
90-day history use identical definitions (rolling 252-session percentiles),
so the last history point equals the mean of the time-series signals. The
put/call signal is a live options snapshot with no history; it is part of
the headline only and flagged as not session-aligned.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .. import provenance as pv
from ..cache import cached
from ..config import FRED_API_KEY
from . import yfinance_service as yfs
from . import breadth_service

_WINDOW = 252
# A signal whose latest observation is more than this many business days
# older than the as-of session is flagged stale (FRED OAS lags ~1 day).
_STALE_BDAYS = 3


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


def _rolling_pct(s: pd.Series, *, invert: bool = False, min_periods: int = 60) -> pd.Series:
    """Rolling 252-session percentile rank of each value within its window."""
    s = s.dropna()
    if s.empty:
        return pd.Series(dtype=float)
    pct = s.rolling(_WINDOW, min_periods=min_periods).apply(
        lambda w: (w <= w[-1]).mean() * 100.0, raw=True)
    return (100.0 - pct) if invert else pct


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


def _cut(s: pd.Series, as_of: pd.Timestamp | None) -> pd.Series:
    """Series observations on or before the as-of session, tz-naive dates."""
    s = s.dropna()
    if s.empty:
        return s
    idx = pd.to_datetime(s.index)
    s.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    return s.loc[:as_of] if as_of is not None else s


def _closes(symbols: tuple[str, ...], period: str, as_of) -> dict[str, pd.Series]:
    frame = yfs.get_close_frame(symbols, period)
    if frame is None or frame.empty:
        return {}
    return {s: _cut(frame[s], as_of) for s in symbols if s in frame.columns}


def _sp_momentum(as_of) -> pd.Series:
    s = _closes(("^GSPC",), "2y", as_of).get("^GSPC", pd.Series(dtype=float))
    if len(s) < 150:
        return pd.Series(dtype=float)
    gap = (s / s.rolling(125).mean() - 1.0).dropna()
    z = (gap - gap.rolling(_WINDOW, min_periods=60).mean()) / gap.rolling(_WINDOW, min_periods=60).std()
    return (50.0 + z * 20.0).clip(0, 100).dropna()


def _vix(as_of) -> pd.Series:
    s = _closes(("^VIX",), "2y", as_of).get("^VIX", pd.Series(dtype=float))
    return _rolling_pct(s, invert=True).dropna()


def _stocks_vs_bonds(as_of) -> pd.Series:
    c = _closes(("SPY", "TLT"), "1y", as_of)
    if "SPY" not in c or "TLT" not in c:
        return pd.Series(dtype=float)
    rel = (c["SPY"].pct_change(20) - c["TLT"].pct_change(20)).dropna()
    # Map a ±10% relative move to the full 0–100 range.
    return (50.0 + rel * 500.0).clip(0, 100)


def _hy_spread(as_of) -> pd.Series:
    if not FRED_API_KEY:
        return pd.Series(dtype=float)
    try:
        from fredapi import Fred
        s = pd.Series(Fred(api_key=FRED_API_KEY).get_series(
            "BAMLH0A0HYM2", observation_start="2022-01-01"))
    except Exception:
        return pd.Series(dtype=float)
    return _rolling_pct(_cut(s, as_of), invert=True).dropna()


def _highs_lows(hl: pd.DataFrame) -> pd.Series:
    if hl is None or hl.empty:
        return pd.Series(dtype=float)
    denom = (hl["highs"] + hl["lows"]).replace(0, np.nan)
    return (hl["highs"] / denom * 100.0).dropna()


_PCR_MIN_HISTORY = 60


def _put_call_ratio() -> float | None:
    """SPY total put/call open-interest ratio over the nearest 3 expiries."""
    try:
        import yfinance as yf
        t = yf.Ticker("SPY")
        put_oi = call_oi = 0.0
        for e in (t.options or [])[:3]:
            chain = t.option_chain(e)
            call_oi += float(chain.calls["openInterest"].fillna(0).sum())
            put_oi += float(chain.puts["openInterest"].fillna(0).sum())
        # Open interest reads 0 before the exchanges publish it each morning;
        # that is "not yet available", not a ratio of zero.
        return put_oi / call_oi if call_oi > 0 and put_oi > 0 else None
    except Exception:
        return None


def _put_call() -> dict:
    """Put/call signal scored against its own recorded history.

    SPY is the market's main hedging vehicle, so its open-interest put/call
    ratio sits structurally around 2–2.5; a fixed 0.7–1.7 band (the previous
    mapping) pinned the score at 0 permanently (audit L-01). No free source
    publishes the history, so each day's ratio is recorded and today's value
    is ranked (inverted: more hedging = more fear) once enough sessions exist.
    """
    from . import snapshots
    ratio = _put_call_ratio()
    today = datetime.now(ZoneInfo("America/New_York")).date()
    if ratio is None:
        return {"score": None, "ratio": None, "historyDays": None, "asOf": None}
    snapshots.record("spy_pcr_oi", "SPY", ratio, today)
    hist = [v for _, v in snapshots.history("spy_pcr_oi", "SPY", _WINDOW)]
    score = None
    if len(hist) >= _PCR_MIN_HISTORY:
        score = _clip(100.0 - float(np.mean(np.array(hist) <= ratio)) * 100.0)
    return {"score": score, "ratio": round(ratio, 3), "historyDays": len(hist),
            "asOf": today.isoformat()}


def _signal(key: str, label: str, series: pd.Series, as_of) -> dict:
    """Headline entry for a time-series signal: its value on the latest
    observation at or before ``as_of``, with that observation's date."""
    s = series.dropna()
    if s.empty:
        return {"key": key, "label": label, "score": None, "asOf": None, "stale": None}
    obs = s.index[-1]
    stale = bool(as_of is not None and len(pd.bdate_range(obs, as_of)) - 1 > _STALE_BDAYS)
    return {"key": key, "label": label, "score": round(float(s.iloc[-1]), 1),
            "asOf": obs.strftime("%Y-%m-%d"), "stale": stale}


@cached("feargreed")
def fear_greed() -> dict:
    internals = breadth_service.breadth_internals("sp500")
    as_of = internals.get("asOf")

    series = {
        "spMomentum": ("S&P 500 vs 125-day SMA", _sp_momentum(as_of)),
        "highLow": ("New Highs / Lows", _highs_lows(internals.get("highsLows"))),
        "mcclellan": ("McClellan Summation", _rolling_pct(internals.get("summation", pd.Series(dtype=float)), min_periods=40)),
        "vix": ("Volatility (VIX)", _vix(as_of)),
        "stocksBonds": ("Stocks vs Bonds", _stocks_vs_bonds(as_of)),
        "hySpread": ("Junk Bond Demand", _hy_spread(as_of)),
    }
    signals = [_signal(k, label, s, as_of) for k, (label, s) in series.items()]
    pc = _put_call()
    signals.insert(3, {
        "key": "putCall", "label": "Put/Call Ratio",
        "score": round(pc["score"], 1) if pc["score"] is not None else None,
        # Live options snapshot at fetch time — not aligned to the session.
        "asOf": pc["asOf"], "stale": None, "aligned": False,
        "raw": pc["ratio"], "historyDays": pc["historyDays"],
        **({"note": f"Building history ({pc['historyDays']}/{_PCR_MIN_HISTORY} sessions)"}
           if pc["ratio"] is not None and pc["score"] is None else {}),
    })
    for s in signals:
        s["label_text"] = _label(s["score"]) if s["score"] is not None else None

    avail = [s["score"] for s in signals if s["score"] is not None]
    index = round(float(np.mean(avail)), 1) if avail else None

    # 90-session history: mean of the time-series signals per session, with
    # a lagging series (FRED OAS) carried forward at most _STALE_BDAYS days.
    frame = pd.concat({k: s for k, (_, s) in series.items() if len(s)}, axis=1)
    history: list[dict] = []
    if not frame.empty:
        frame = frame.sort_index().ffill(limit=_STALE_BDAYS)
        if as_of is not None:
            frame = frame.loc[:as_of]
        composite = frame.mean(axis=1).dropna().tail(90)
        history = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 1)}
                   for d, v in composite.items()]

    return pv.attach({
        **({"status": "unavailable"} if not avail else {}),
        "index": index,
        "label": _label(index) if index is not None else None,
        "asOf": as_of.strftime("%Y-%m-%d") if as_of is not None else None,
        "signals": signals,
        "history": history,
        "historyExcludes": ["putCall"],
        "signalCount": len(avail),
    }, _provenance(signals))


def _provenance(signals: list[dict]) -> dict:
    """Source of each signal (``signals.<key>``) and of the index built on them."""
    obs = {s["key"]: s.get("asOf") for s in signals}
    flags = {s["key"]: (("stale",) if s.get("stale") else ()) for s in signals}

    def yahoo(sym: str, title: str, key: str) -> dict:
        return pv.yahoo(sym, title, frequency="daily", observed=obs.get(key))

    breadth_inputs = [
        pv.ref("yahoo", None, "Daily high/low/close of each S&P 500 member",
               units="price as traded", frequency="daily", observed=obs.get("highLow")),
        pv.ref("wikipedia", None, "Current S&P 500 constituents"),
    ]

    def d(key: str, formula: str, inputs: list, title: str, **kw) -> dict:
        return pv.derived(formula, inputs, title=title, observed=obs.get(key), flags=flags.get(key, ()), **kw)

    prov = {
        "signals.spMomentum": d(
            "spMomentum", "50 + 20 × z-score (252 sessions) of close / 125-day SMA − 1, clipped to 0–100",
            [yahoo("^GSPC", "S&P 500 index, daily close", "spMomentum")], "S&P 500 momentum"),
        "signals.highLow": d(
            "highLow", "new 52-week highs / (highs + lows) × 100 across S&P 500 members",
            breadth_inputs, "New highs vs new lows"),
        "signals.mcclellan": d(
            "mcclellan", "percentile rank (252 sessions) of the McClellan Summation Index",
            breadth_inputs, "McClellan Summation"),
        "signals.putCall": d(
            "putCall",
            "100 − percentile rank of today's put/call open-interest ratio within its recorded history",
            [pv.yahoo("SPY", "Put and call open interest, nearest 3 expiries", observed=obs.get("putCall")),
             pv.ref("econosift", "spy_pcr_oi", "Daily record of the SPY put/call ratio", frequency="daily")],
            "Put/call ratio",
            note=f"Scored once {_PCR_MIN_HISTORY} sessions are recorded; no free source publishes this history."),
        "signals.vix": d(
            "vix", "100 − percentile rank (252 sessions) of the VIX close",
            [yahoo("^VIX", "CBOE Volatility Index, daily close", "vix")], "Volatility"),
        "signals.stocksBonds": d(
            "stocksBonds", "50 + 500 × (20-session return of SPY − 20-session return of TLT), clipped to 0–100",
            [yahoo("SPY", "SPDR S&P 500 ETF, daily adjusted close", "stocksBonds"),
             yahoo("TLT", "iShares 20+ Year Treasury ETF, daily adjusted close", "stocksBonds")],
            "Stocks vs bonds"),
        "signals.hySpread": d(
            "hySpread", "100 − percentile rank (252 sessions) of the high-yield option-adjusted spread",
            [pv.fred("BAMLH0A0HYM2", "ICE BofA US High Yield Index Option-Adjusted Spread",
                     units="%", frequency="daily", observed=obs.get("hySpread"))],
            "Junk bond demand"),
    }
    scored = [f"signals.{s['key']}" for s in signals if s.get("score") is not None]
    index = pv.derived("equal-weighted mean of the signals that have a score", scored,
                       title="Fear & Greed index (EconoSift's own; not CNN's)")
    prov.update({"index": index, "label": index, "*": index,
                 "history": pv.derived("per-session mean of the time-series signals (put/call excluded)",
                                       [k for k in scored if k != "signals.putCall"],
                                       title="Fear & Greed history")})
    return prov
