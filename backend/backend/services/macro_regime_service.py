"""Macro regime classifier — 4-quadrant growth/inflation model with asset allocation signals."""
from __future__ import annotations

from backend.cache import async_cached
from backend.services import macro_expansion_service as mes

_SERIES = ("USALOLITONOSTSAM", "CPIAUCSL", "FEDFUNDS", "DGS10", "DGS2")
_START = "2000-01-01"

_REGIME_SIGNALS = {
    "Goldilocks":   {"equities": "overweight", "bonds": "neutral",     "commodities": "neutral",     "credit": "overweight"},
    "Reflationary": {"equities": "overweight", "bonds": "underweight", "commodities": "overweight",  "credit": "neutral"},
    "Stagflation":  {"equities": "underweight","bonds": "underweight", "commodities": "overweight",  "credit": "underweight"},
    "Deflationary": {"equities": "underweight","bonds": "overweight",  "commodities": "underweight", "credit": "underweight"},
}


def _latest(pts: list[dict]) -> float | None:
    for pt in reversed(pts):
        if pt.get("value") is not None:
            return pt["value"]
    return None


def _val_n_months_ago(pts: list[dict], months: int) -> float | None:
    from datetime import datetime, timedelta
    if not pts:
        return None
    last_date = datetime.strptime(pts[-1]["date"][:10], "%Y-%m-%d")
    target = last_date - timedelta(days=30 * months)
    for pt in reversed(pts):
        d = datetime.strptime(pt["date"][:10], "%Y-%m-%d")
        if d <= target and pt.get("value") is not None:
            return pt["value"]
    return None


def _cpi_yoy(pts: list[dict]) -> float | None:
    cur = _latest(pts)
    ago = _val_n_months_ago(pts, 12)
    if cur and ago and ago > 0:
        return round((cur / ago - 1) * 100, 2)
    return None


@async_cached("macro_regime")
async def get_macro_regime() -> dict:
    data = await mes.fetch_fred_series(_SERIES, _START)
    lei   = data.get("USALOLITONOSTSAM", [])
    cpi   = data.get("CPIAUCSL", [])
    ff    = data.get("FEDFUNDS", [])
    dgs10 = data.get("DGS10", [])
    dgs2  = data.get("DGS2", [])

    lei_cur = _latest(lei)
    lei_3m  = _val_n_months_ago(lei, 3)
    growth_signal = "rising" if (lei_cur and lei_3m and lei_cur > lei_3m) else "falling"

    cpi_yoy = _cpi_yoy(cpi)
    inflation_signal = "above" if (cpi_yoy is not None and cpi_yoy > 2.5) else "below"

    regime = {
        ("rising", "below"):  "Goldilocks",
        ("rising", "above"):  "Reflationary",
        ("falling", "above"): "Stagflation",
        ("falling", "below"): "Deflationary",
    }[(growth_signal, inflation_signal)]

    d10 = _latest(dgs10)
    d2  = _latest(dgs2)
    spread = round(d10 - d2, 4) if d10 and d2 else None

    return {
        "regime": regime,
        "growth_signal": growth_signal,
        "inflation_signal": inflation_signal,
        "metrics": {
            "lei_current": lei_cur,
            "lei_change_3m": round(lei_cur - lei_3m, 4) if lei_cur and lei_3m else None,
            "cpi_yoy": cpi_yoy,
            "fed_funds": _latest(ff),
            "yield_spread_2y10y": spread,
        },
        "asset_signals": _REGIME_SIGNALS[regime],
    }
