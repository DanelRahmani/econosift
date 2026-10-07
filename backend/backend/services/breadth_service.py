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

Point-in-time membership (audit P2-35 / C-23): a symbol is counted on a
session only if it was an index member then - today's roster with the
membership change log undone back to that session. Prices are not masked (a
joiner's 52-week high still uses its pre-join prices); only counting is.

Limitation: names Yahoo no longer serves (delisted or acquired) cannot be
priced, so former members that left the index inside the window drop out; the
residual is reported as ``membership.missingSymbols``. When the change log is
unavailable the mask falls back to today's roster on every session and the
response says so.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .. import provenance as pv
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
# A change dated this far back (a little over the 2y download) can matter.
_WINDOW_DAYS = 740


def _now_ny() -> datetime:
    return datetime.now(_NY)


def _member_mask(index_dates: pd.DatetimeIndex, columns: list[str],
                 roster: set[str], changes: list[dict]) -> pd.DataFrame:
    """Bool frame: was each symbol an index member on each session.

    Starts from today's roster and undoes the change log newest-first - the
    rule of ``constituents.members_as_of`` (a change dated D takes effect on D,
    so an added symbol is a member from D inclusive) - as one slice assignment
    per change, never per session.
    """
    col = {s: i for i, s in enumerate(columns)}
    mask = np.zeros((len(index_dates), len(columns)), dtype=bool)
    for s in roster:
        if s in col:
            mask[:, col[s]] = True
    for ch in changes:  # newest first
        pos = int(index_dates.searchsorted(pd.Timestamp(ch["date"]), side="left"))
        if pos == 0:
            continue
        if ch.get("added") in col:
            mask[:pos, col[ch["added"]]] = False   # had not joined yet
        if ch.get("removed") in col:
            mask[:pos, col[ch["removed"]]] = True  # still a member
    return pd.DataFrame(mask, index=index_dates, columns=columns)


def _membership_note(index: str, point_in_time: bool, missing: int) -> str:
    name = _INDEX_NAMES.get(index, index)
    if not point_in_time:
        return (f"today's {name} members applied to the whole window "
                "(change log unavailable) — survivorship")
    if missing:
        who = "member has" if missing == 1 else "members have"
        return (f"point-in-time {name} members; {missing} {who} no Yahoo data "
                "(delisted or acquired) and left out")
    return f"point-in-time {name} members"


def _ohlc_frames(index: str) -> dict:
    """Two years of OHLC as ``{"close","high","low","member","meta"}``.

    ``close``/``high``/``low`` are frames of every symbol that was a member at
    some point in the window (columns with data; index = session dates);
    ``member`` is a bool frame of the same shape - True when the symbol was an
    index member on that session. Trailing sessions that are still in progress
    or thinly covered (share of members with a bar) are dropped. ``meta`` is
    ``{"pointInTime": bool, "missingSymbols": int}``.
    """
    roster = list(constituents.constituent_symbols(index))
    if not roster:
        return {}
    now = _now_ny()
    changes = constituents.get_membership_changes(index) or []
    window_start = now.date() - timedelta(days=_WINDOW_DAYS)
    in_window = [c for c in changes if c["date"] >= window_start]
    known = set(roster)
    extra = sorted({s for c in in_window for s in (c.get("added"), c.get("removed"))
                    if s and s not in known})
    syms = tuple(roster + extra)
    raw = yfs.get_ohlc_frame(syms, "2y", adjust=False)
    if not raw:
        return {}
    close = pd.DataFrame({s: df["Close"] for s, df in raw.items()}).sort_index()
    high = pd.DataFrame({s: df["High"] for s, df in raw.items()}).reindex(close.index)
    low = pd.DataFrame({s: df["Low"] for s, df in raw.items()}).reindex(close.index)
    idx = pd.to_datetime(close.index)
    close.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    high.index = low.index = close.index

    # Point-in-time membership over every union symbol (including ones Yahoo
    # returned nothing for, so the residual can be counted).
    full = _member_mask(close.index, list(syms), known, in_window)
    no_data = [s for s in full.columns if s not in close.columns]
    missing = int(full[no_data].any(axis=0).sum()) if no_data else 0
    member = full[list(close.columns)]

    # Drop a bar for today's session while the market is still open.
    if len(close) and close.index[-1].date() == now.date() and now.time() < _CLOSE:
        close, high, low = close.iloc[:-1], high.iloc[:-1], low.iloc[:-1]
        member = member.iloc[:-1]

    # Drop trailing rows that too few members have printed yet.
    n_members = member.sum(axis=1).replace(0, np.nan)
    coverage = (close.notna() & member).sum(axis=1) / n_members
    complete = coverage[coverage >= _MIN_COVERAGE]
    if complete.empty:
        return {}
    last = complete.index[-1]
    return {"close": close.loc[:last], "high": high.loc[:last], "low": low.loc[:last],
            "member": member.loc[:last],
            "meta": {"pointInTime": bool(changes), "missingSymbols": missing}}


def _membership_block(index: str, frames: dict) -> dict:
    meta = frames.get("meta") or {}
    pit = bool(meta.get("pointInTime"))
    missing = int(meta.get("missingSymbols", 0))
    return {"pointInTime": pit, "missingSymbols": missing,
            "note": _membership_note(index, pit, missing)}


def _adv_decl_series(frame: pd.DataFrame, member: pd.DataFrame | None = None) -> pd.DataFrame:
    """Daily advancers/decliners across the universe.

    Returns a frame indexed by date with columns adv, dec, net (adv-dec) and
    the ratio-adjusted net advance ``rana = (adv-dec)/(adv+dec)``. Only
    symbols with a bar on both consecutive sessions are compared, and only
    index members on the session counted (``member`` mask; None = everyone).
    """
    if frame.empty:
        return pd.DataFrame(columns=["adv", "dec", "net", "rana"])
    delta = frame - frame.shift(1)
    up, down = delta > 0, delta < 0
    if member is not None:
        up, down = up & member, down & member
    adv = up.sum(axis=1)
    dec = down.sum(axis=1)
    out = pd.DataFrame({"adv": adv, "dec": dec})
    out["net"] = out["adv"] - out["dec"]
    total = (out["adv"] + out["dec"]).replace(0, np.nan)
    out["rana"] = (out["net"] / total).fillna(0.0)
    return out.iloc[1:]  # first row has no prior session


def _highs_lows_series(high: pd.DataFrame, low: pd.DataFrame,
                       close: pd.DataFrame,
                       member: pd.DataFrame | None = None) -> pd.DataFrame:
    """Daily count of members at a new 52-week intraday high / low.

    A member is counted on a session only if it was an index member then
    (``member`` mask; None = everyone), traded that session and has at least
    30 sessions of history in the trailing window.
    """
    traded = close.notna()
    enough = close.notna().rolling(_LOOKBACK_52W, min_periods=1).sum() >= 30
    hi_max = high.rolling(_LOOKBACK_52W, min_periods=1).max()
    lo_min = low.rolling(_LOOKBACK_52W, min_periods=1).min()
    is_hi = (high >= hi_max - 1e-9) & traded & enough
    is_lo = (low <= lo_min + 1e-9) & traded & enough
    if member is not None:
        is_hi, is_lo = is_hi & member, is_lo & member
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
        "newHighs": None, "newLows": None, "membership": None,
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
    close, high, low, member = frames["close"], frames["high"], frames["low"], frames["member"]
    if len(close) < 2:
        return _unavailable(index)

    as_of = close.index[-1]
    last = close.iloc[-1]
    prev = close.iloc[-2]
    in_index = member.iloc[-1]
    valid = last.notna() & prev.notna() & in_index
    diff = last[valid] - prev[valid]
    advancing = int((diff > 0).sum())
    declining = int((diff < 0).sum())
    unchanged = int((diff == 0).sum())
    total = int(valid.sum())

    hl = _highs_lows_series(high, low, close, member)

    # % above SMA50 / SMA200 — members that printed on the as-of session.
    def _pct_above(n: int) -> float | None:
        if len(close) < n:
            return None
        sma = close.rolling(n, min_periods=int(n * 0.9)).mean().iloc[-1]
        ok = last.notna() & sma.notna() & in_index
        denom = int(ok.sum())
        return round(float((last[ok] > sma[ok]).sum()) / denom * 100.0, 1) if denom else None

    ad = _adv_decl_series(close, member)
    mc = mcclellan(ad)
    cum_ad = ad["net"].cumsum()

    membership = _membership_block(index, frames)

    def _series(s: pd.Series, n: int = 90) -> list[dict]:
        s = s.dropna().tail(n)
        return [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in s.items()]

    return pv.attach({
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
        "membership": membership,
    }, _provenance(index, as_of.strftime("%Y-%m-%d"), membership))


_INDEX_NAMES = {"sp500": "S&P 500", "ndx": "Nasdaq-100", "dow": "Dow Jones Industrial Average"}


def _provenance(index: str, as_of: str, membership: dict | None = None) -> dict:
    name = _INDEX_NAMES.get(index, index)
    inputs = [
        pv.ref("yahoo", None, f"Daily open/high/low/close of each {name} member",
               units="price as traded (split-adjusted, not dividend-adjusted)",
               frequency="daily", observed=as_of),
        pv.ref("wikipedia", None, f"Current {name} constituents"),
        pv.ref("wikipedia", None, f"{name} membership change log"),
    ]
    residual = (membership or {}).get("note")

    def d(formula: str, title: str, note: str | None = None) -> dict:
        return pv.derived(formula, inputs, title=title, observed=as_of, note=note)

    adv = d("count of members whose close is above / below / equal to the previous session's close",
            "Advancers, decliners, unchanged")
    hilo = d("count of members whose session high (low) is the highest (lowest) of the trailing 252 sessions",
             "New 52-week highs / lows")
    return {
        "*": d("breadth statistics over the index's point-in-time members, last completed session",
               f"{name} breadth", note=residual),
        "advancing": adv, "declining": adv, "unchanged": adv, "total": adv, "advDeclHistory": adv,
        "newHighs": hilo, "newLows": hilo,
        "pctAboveSma50": d("share of members closing above their 50-session simple moving average",
                           "% above 50-day SMA"),
        "pctAboveSma200": d("share of members closing above their 200-session simple moving average",
                            "% above 200-day SMA"),
        "mcclellanOscillator": d("1000 × (EMA19 − EMA39) of (advancers − decliners) / (advancers + decliners)",
                                 "McClellan Oscillator (ratio-adjusted)"),
        "mcclellanSummation": d("running sum of the McClellan Oscillator from the start of the 2-year window",
                                "McClellan Summation Index"),
        "cumulativeAdLine": d("running sum of (advancers − decliners)", "Cumulative advance-decline line"),
    }


def breadth_internals(index: str = "sp500") -> dict:
    """Series the Fear & Greed engine needs without a second download.

    Returns the McClellan summation series, the daily new-high / new-low
    counts and the as-of session, all from the same session-aligned,
    point-in-time frame (plus the ``membership`` note).
    """
    frames = _ohlc_frames(index)
    empty = {"summation": pd.Series(dtype=float), "highsLows": pd.DataFrame(), "asOf": None}
    if not frames or len(frames["close"]) < 2:
        return empty
    close, member = frames["close"], frames["member"]
    mc = mcclellan(_adv_decl_series(close, member))
    return {
        "summation": mc["summation"] if not mc.empty else pd.Series(dtype=float),
        "highsLows": _highs_lows_series(frames["high"], frames["low"], close, member),
        "asOf": close.index[-1],
        "membership": _membership_block(index, frames),
    }
