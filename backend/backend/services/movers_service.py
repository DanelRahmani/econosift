"""Top movers from an index's constituents (compute tier 🟢).

Gainers, losers, unusual volume (last session > 2× its 3-month average), and
fresh 52-week highs / lows — all from the cached constituent universe plus one
close download and one volume download.
"""
from __future__ import annotations

import pandas as pd

from ..cache import cached
from . import yfinance_service as yfs
from . import constituents


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

    frame = yfs.get_close_frame(syms, "1y")
    if frame is None or frame.empty:
        return empty
    frame = frame.sort_index()
    as_of = frame.index[-1].strftime("%Y-%m-%d")

    last = frame.iloc[-1]
    prev = frame.iloc[-2] if len(frame) > 1 else last

    # 1-day % change per symbol.
    rows: list[dict] = []
    window = frame.tail(252)
    for sym in frame.columns:
        cur = last.get(sym)
        pr = prev.get(sym)
        if pd.isna(cur) or pd.isna(pr) or pr == 0:
            continue
        chg = round((float(cur) / float(pr) - 1.0) * 100.0, 2)
        rows.append({"ticker": sym, "name": names.get(sym, sym),
                     "price": round(float(cur), 2), "changePercent": chg})

    gainers = sorted(rows, key=lambda r: r["changePercent"], reverse=True)[:limit]
    losers = sorted(rows, key=lambda r: r["changePercent"])[:limit]

    # 52-week highs / lows.
    highs: list[dict] = []
    lows: list[dict] = []
    by_sym = {r["ticker"]: r for r in rows}
    for sym in frame.columns:
        s = window[sym].dropna()
        if len(s) < 30 or sym not in by_sym:
            continue
        cur = s.iloc[-1]
        if cur >= s.max() - 1e-9:
            highs.append(by_sym[sym])
        elif cur <= s.min() + 1e-9:
            lows.append(by_sym[sym])
    highs = sorted(highs, key=lambda r: r["changePercent"], reverse=True)[:limit]
    lows = sorted(lows, key=lambda r: r["changePercent"])[:limit]

    # Unusual volume: last session vs trailing 3-month average.
    unusual: list[dict] = []
    vol = yfs.get_volume_frame(syms, "3mo")
    if vol is not None and not vol.empty:
        vol = vol.sort_index()
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

    return {
        "index": index, "asOf": as_of,
        "gainers": gainers, "losers": losers,
        "unusualVolume": unusual, "newHighs": highs, "newLows": lows,
    }
