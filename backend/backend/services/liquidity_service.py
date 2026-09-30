"""Fed plumbing / net liquidity service using FRED data.

Net liquidity = Fed balance sheet (WALCL) − overnight reverse repo (RRPONTSYD)
− Treasury General Account (WTREGEN). All series are normalised to trillions
of USD on a weekly (Wednesday, matching the H.4.1 release) grid.
"""
from __future__ import annotations

import asyncio
import logging

import pandas as pd

from ..cache import async_cached
from ..config import FRED_API_KEY
from . import macro_expansion_service as mes
from . import yfinance_service as yfs

log = logging.getLogger(__name__)

_LIQ_SERIES = ("WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL")
_START = "2015-01-01"

# FRED native units → trillions USD (verified against live H.4.1 magnitudes)
_TO_TRILLIONS = {
    "WALCL": 1e-6,      # millions
    "RRPONTSYD": 1e-3,  # billions
    "WTREGEN": 1e-6,    # millions
    "WRESBAL": 1e-6,    # millions
}


def _weekly_series(pts: list[dict], scale: float) -> pd.Series:
    """[{date, value}] → weekly (W-WED) last-observation series in trillions."""
    clean = [(p["date"], p["value"]) for p in pts if p.get("value") is not None]
    if not clean:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(d): float(v) * scale for d, v in clean}).sort_index()
    return s.resample("W-WED").last().ffill()


def _to_points(s: pd.Series, digits: int = 4) -> list[dict]:
    return [
        {"date": str(idx.date()), "value": round(float(v), digits)}
        for idx, v in s.dropna().items()
    ]


def _compute_net_liquidity(data: dict[str, list[dict]], spx_pts: list[dict]) -> dict:
    """Pure computation over already-fetched FRED points; unit-testable."""
    walcl = _weekly_series(data.get("WALCL", []), _TO_TRILLIONS["WALCL"])
    rrp = _weekly_series(data.get("RRPONTSYD", []), _TO_TRILLIONS["RRPONTSYD"])
    tga = _weekly_series(data.get("WTREGEN", []), _TO_TRILLIONS["WTREGEN"])
    reserves = _weekly_series(data.get("WRESBAL", []), _TO_TRILLIONS["WRESBAL"])

    if walcl.empty:
        return {}

    # RRP starts later than WALCL/TGA; treat missing early history as zero so
    # net liquidity is defined over the full balance-sheet window.
    frame = pd.DataFrame({"walcl": walcl, "rrp": rrp, "tga": tga})
    frame[["rrp", "tga"]] = frame[["rrp", "tga"]].fillna(0.0)
    frame = frame.dropna(subset=["walcl"])
    net = frame["walcl"] - frame["rrp"] - frame["tga"]

    def _latest(s: pd.Series) -> float | None:
        s = s.dropna()
        return round(float(s.iloc[-1]), 4) if not s.empty else None

    net_latest = _latest(net)
    change_4w = None
    if len(net.dropna()) > 4:
        change_4w = round(float(net.dropna().iloc[-1] - net.dropna().iloc[-5]), 4)

    spx = _weekly_series(spx_pts, 1.0)

    return {
        # Date of the latest Fed balance-sheet (H.4.1) observation.
        "asOf": max((p["date"] for p in data.get("WALCL", []) if p.get("value") is not None), default=None),
        "kpis": {
            "netLiquidity": net_latest,
            "netLiquidity4wChange": change_4w,
            "rrp": _latest(rrp),
            "tga": _latest(tga),
            "reserves": _latest(reserves),
        },
        "history": {
            "netLiquidity": _to_points(net),
            "fedBalanceSheet": _to_points(walcl),
            "rrp": _to_points(rrp),
            "tga": _to_points(tga),
            "reserves": _to_points(reserves),
            "spx": _to_points(spx, digits=2),
        },
    }


def _fetch_spx_points() -> list[dict]:
    """Weekly ^GSPC closes for the overlay chart (best-effort)."""
    try:
        frame = yfs.get_close_frame(("^GSPC",), "10y")
        if frame is None or frame.empty or "^GSPC" not in frame.columns:
            return []
        s = frame["^GSPC"].dropna()
        s.index = pd.to_datetime(s.index)
        return [{"date": str(d.date()), "value": float(v)} for d, v in s.items()]
    except Exception as exc:
        log.warning("net_liquidity SPX overlay fetch failed: %s", exc)
        return []


@async_cached("net_liquidity")
async def get_net_liquidity() -> dict:
    """Weekly Fed-plumbing dashboard: net liquidity, RRP, TGA, reserves, SPX overlay."""
    if not FRED_API_KEY:
        return {"error": "FRED API key required"}

    data = await mes.fetch_fred_series(_LIQ_SERIES, start=_START)
    spx_pts = await asyncio.to_thread(_fetch_spx_points)
    return _compute_net_liquidity(data, spx_pts)
