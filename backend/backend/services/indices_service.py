"""Global equity indices snapshot for the dashboard (compute tier 🟢).

A single batched close download yields price, 1-day %, a 5-day sparkline,
1-month %, and year-to-date % for ~25 indices grouped by region.
"""
from __future__ import annotations

import pandas as pd

from .. import provenance as pv
from ..cache import cached
from . import yfinance_service as yfs

# (yahoo symbol, display name, region)
INDICES: list[tuple[str, str, str]] = [
    # Americas
    ("^GSPC", "S&P 500", "Americas"),
    ("^DJI", "Dow Jones", "Americas"),
    ("^IXIC", "Nasdaq Composite", "Americas"),
    ("^NDX", "Nasdaq 100", "Americas"),
    ("^RUT", "Russell 2000", "Americas"),
    ("^GSPTSE", "S&P/TSX (Canada)", "Americas"),
    ("^BVSP", "Bovespa (Brazil)", "Americas"),
    ("^MXX", "IPC (Mexico)", "Americas"),
    # EMEA
    ("^FTSE", "FTSE 100 (UK)", "EMEA"),
    ("^GDAXI", "DAX (Germany)", "EMEA"),
    ("^FCHI", "CAC 40 (France)", "EMEA"),
    ("^STOXX50E", "Euro Stoxx 50", "EMEA"),
    ("^IBEX", "IBEX 35 (Spain)", "EMEA"),
    ("FTSEMIB.MI", "FTSE MIB (Italy)", "EMEA"),
    ("^AEX", "AEX (Netherlands)", "EMEA"),
    ("^SSMI", "SMI (Switzerland)", "EMEA"),
    ("^OMX", "OMX 30 (Sweden)", "EMEA"),
    # Asia-Pacific
    ("^N225", "Nikkei 225 (Japan)", "Asia-Pacific"),
    ("^HSI", "Hang Seng (HK)", "Asia-Pacific"),
    ("000001.SS", "Shanghai Composite", "Asia-Pacific"),
    ("^STI", "Straits Times (SG)", "Asia-Pacific"),
    ("^KS11", "KOSPI (Korea)", "Asia-Pacific"),
    ("^TWII", "TAIEX (Taiwan)", "Asia-Pacific"),
    ("^BSESN", "Sensex (India)", "Asia-Pacific"),
    ("^AXJO", "ASX 200 (Australia)", "Asia-Pacific"),
]


def _pct(cur: float | None, ref: float | None) -> float | None:
    if cur is None or ref is None or ref == 0:
        return None
    return round((cur / ref - 1.0) * 100.0, 2)


@cached("indices")
def global_indices() -> dict:
    syms = tuple(i[0] for i in INDICES)
    frame = yfs.get_close_frame(syms, "1y")
    rows: list[dict] = []
    as_of = None

    if frame is not None and not frame.empty:
        frame = frame.sort_index()
        as_of = frame.index[-1].strftime("%Y-%m-%d")
        year = frame.index[-1].year
        ytd_start = frame[frame.index >= f"{year}-01-01"]

    for sym, name, region in INDICES:
        row = {"symbol": sym, "name": name, "region": region,
               "price": None, "asOf": None, "change1d": None, "spark": [],
               "change1m": None, "changeYtd": None}
        if frame is not None and not frame.empty and sym in frame.columns:
            s = frame[sym].dropna()
            if len(s):
                cur = float(s.iloc[-1])
                row["price"] = round(cur, 2)
                # Markets close at different times: date each index by its own last bar.
                row["asOf"] = s.index[-1].strftime("%Y-%m-%d")
                row["change1d"] = _pct(cur, float(s.iloc[-2]) if len(s) > 1 else None)
                row["spark"] = [round(float(x), 2) for x in s.tail(5)]
                row["change1m"] = _pct(cur, float(s.iloc[-22]) if len(s) > 21 else None)
                ys = ytd_start[sym].dropna() if sym in ytd_start.columns else pd.Series(dtype=float)
                row["changeYtd"] = _pct(cur, float(ys.iloc[0]) if len(ys) else None)
        rows.append(row)

    regions = ["Americas", "EMEA", "Asia-Pacific"]
    prov: dict = {"*": pv.ref("yahoo", None, "Index levels, latest daily bar", frequency="daily", observed=as_of,
                              note="Markets close at different times; each index carries its own session date.")}
    for r in rows:
        prov[f"indices.{r['symbol']}"] = pv.yahoo(
            r["symbol"], f"{r['name']} — latest daily bar", frequency="daily", observed=r["asOf"],
            note="The last trade while that market's session is open.")
    return pv.attach({"asOf": as_of, "regions": regions, "indices": rows}, prov)
