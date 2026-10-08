"""Top movers from an index's constituents (compute tier 🟢).

Gainers, losers, unusual volume (last session > 2× its 3-month average), and
fresh 52-week highs / lows — from the same session-aligned constituent prices
as the breadth bar, so the lists agree with its counts, plus one volume
download.
"""
from __future__ import annotations

import pandas as pd

from .. import provenance as pv
from ..cache import cached
from . import yfinance_service as yfs
from . import breadth_service, constituents


def _names(index: str) -> dict[str, str]:
    return {c["symbol"]: c["name"] for c in constituents.get_constituents(index)}


@cached("movers")
def top_movers(index: str = "sp500", limit: int = 10) -> dict:
    members = constituents.get_constituents(index)
    syms = tuple(c["symbol"] for c in members)
    names = {c["symbol"]: c["name"] for c in members}
    empty = {"index": index, "asOf": None, "gainers": [], "losers": [],
             "unusualVolume": [], "newHighs": [], "newLows": []}
    if not syms:
        return empty

    # Prices as traded for the last completed session — the breadth bar's
    # frames. (Adjusted closes from a separate download made the 1-day change
    # differ from the quoted one on ex-dividend days, and the new-high/low
    # lists disagree with the breadth counts shown next to them.)
    frames = breadth_service._ohlc_frames(index)
    if not frames or len(frames["close"]) < 2:
        return empty
    # Only symbols that are index members on the last session (the frames also
    # carry former members for the point-in-time breadth counts).
    keep = frames["member"].iloc[-1]
    keep = keep[keep].index
    close, high, low = frames["close"][keep], frames["high"][keep], frames["low"][keep]
    session = close.index[-1]
    as_of = session.strftime("%Y-%m-%d")

    last = close.iloc[-1]
    prev = close.iloc[-2]

    # 1-day % change per symbol.
    rows: list[dict] = []
    for sym in close.columns:
        cur = last.get(sym)
        pr = prev.get(sym)
        if pd.isna(cur) or pd.isna(pr) or pr == 0:
            continue
        chg = round((float(cur) / float(pr) - 1.0) * 100.0, 2)
        rows.append({"ticker": sym, "name": names.get(sym, sym),
                     "price": round(float(cur), 2), "changePercent": chg})

    gainers = sorted(rows, key=lambda r: r["changePercent"], reverse=True)[:limit]
    losers = sorted(rows, key=lambda r: r["changePercent"])[:limit]

    # 52-week highs / lows: session high (low) is the extreme of the trailing
    # 252 sessions — the definition the breadth counts use.
    by_sym = {r["ticker"]: r for r in rows}
    hi_max = high.tail(252).max()
    lo_min = low.tail(252).min()
    sessions = close.tail(252).notna().sum()
    highs = [by_sym[s] for s in close.columns
             if s in by_sym and sessions[s] >= 30 and high[s].iloc[-1] >= hi_max[s] - 1e-9]
    lows = [by_sym[s] for s in close.columns
            if s in by_sym and sessions[s] >= 30 and low[s].iloc[-1] <= lo_min[s] + 1e-9]
    highs = sorted(highs, key=lambda r: r["changePercent"], reverse=True)[:limit]
    lows = sorted(lows, key=lambda r: r["changePercent"])[:limit]

    # Unusual volume: last session vs trailing 3-month average.
    unusual: list[dict] = []
    vol = yfs.get_volume_frame(syms, "3mo")
    if vol is not None and not vol.empty:
        vol = vol.sort_index()
        vol = vol[pd.to_datetime(vol.index).tz_localize(None).normalize() <= session]
    if vol is not None and not vol.empty:
        last_vol = vol.iloc[-1]
        avg_vol = vol.tail(63).mean()
        for sym in vol.columns:
            lv = last_vol.get(sym)
            av = avg_vol.get(sym)
            if pd.isna(lv) or pd.isna(av) or av <= 0:
                continue
            ratio = float(lv) / float(av)
            if ratio >= 2.0 and sym in by_sym:
                unusual.append({**by_sym[sym], "volume": int(lv),
                                "avgVolume": int(av), "volumeRatio": round(ratio, 2)})
        unusual = sorted(unusual, key=lambda r: r["volumeRatio"], reverse=True)[:limit]

    prices = pv.ref("yahoo", None, f"Daily high/low/close of each {index} member",
                    units="price as traded (split-adjusted)", frequency="daily", observed=as_of)
    members_ref = pv.ref("wikipedia", None, f"Current {index} constituents")
    change = pv.derived("close / previous close − 1", [prices, members_ref],
                        title="1-day change, last completed session", observed=as_of)
    hilo = pv.derived("session high (low) is the highest (lowest) of the trailing 252 sessions",
                      [prices, members_ref], title="New 52-week highs / lows", observed=as_of)
    return pv.attach({
        "index": index, "asOf": as_of,
        "gainers": gainers, "losers": losers,
        "unusualVolume": unusual, "newHighs": highs, "newLows": lows,
    }, {
        "*": change, "gainers": change, "losers": change,
        "newHighs": hilo, "newLows": hilo,
        "unusualVolume": pv.derived(
            "last session's volume ≥ 2 × its trailing 63-session average",
            [pv.ref("yahoo", None, f"Daily share volume of each {index} member", frequency="daily", observed=as_of),
             members_ref],
            title="Unusual volume", observed=as_of),
    })
