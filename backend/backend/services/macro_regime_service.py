"""Macro regime classifier — 4-quadrant growth/inflation model with asset allocation signals."""
from __future__ import annotations

import math
from backend.cache import async_cached
from backend.services import macro_expansion_service as mes

_SERIES = ("USALOLITONOSTSAM", "CPIAUCSL", "FEDFUNDS", "DGS10", "DGS2")
_START = "2000-01-01"

_REGIME_QUADRANT = {
    "Goldilocks":    1,
    "Reflationary":  2,
    "Stagflation":   3,
    "Deflationary":  4,
}

_REGIME_SIGNALS = {
    "Goldilocks":   {"equities": "overweight", "bonds": "neutral",     "commodities": "neutral",     "credit": "overweight"},
    "Reflationary": {"equities": "overweight", "bonds": "underweight", "commodities": "overweight",  "credit": "neutral"},
    "Stagflation":  {"equities": "underweight","bonds": "underweight", "commodities": "overweight",  "credit": "underweight"},
    "Deflationary": {"equities": "underweight","bonds": "overweight",  "commodities": "underweight", "credit": "underweight"},
}

# Numeric allocation weights per regime (%)
_ALLOCATION = {
    "Goldilocks":    {"equities": 55, "bonds": 20, "commodities": 10, "cash": 15},
    "Reflationary":  {"equities": 50, "bonds": 10, "commodities": 25, "cash": 15},
    "Stagflation":   {"equities": 20, "bonds": 15, "commodities": 35, "cash": 30},
    "Deflationary":  {"equities": 20, "bonds": 45, "commodities": 5,  "cash": 30},
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


def _regime_unavailable(result) -> bool:
    """Don't cache a regime we couldn't actually compute from live data."""
    return isinstance(result, dict) and result.get("available") is False


@async_cached("macro_regime", skip_if=_regime_unavailable)
async def get_macro_regime() -> dict:
    data = await mes.fetch_fred_series(_SERIES, _START)
    lei   = data.get("USALOLITONOSTSAM", [])
    cpi   = data.get("CPIAUCSL", [])
    ff    = data.get("FEDFUNDS", [])
    dgs10 = data.get("DGS10", [])
    dgs2  = data.get("DGS2", [])

    # If the core growth/inflation series didn't come back, don't fabricate a
    # regime (an empty fetch would otherwise classify as "Deflationary" with
    # null metrics). Surface it so the UI can show a real reason.
    if not cpi and not lei:
        return {
            "available": False,
            "reason": "FRED macro series unavailable — check the FRED API key in Admin, then use “Clear cache & re-warm”.",
        }

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

    # --- Z-scores: compute from historical LEI changes & CPI YoY ---
    lei_vals = [pt["value"] for pt in lei if pt.get("value") is not None]
    cpi_vals = [pt["value"] for pt in cpi if pt.get("value") is not None]

    growth_z = _zscore(lei_cur, _ma3m(lei_vals)) if lei_cur and len(lei_vals) >= 24 else None
    inflation_z = _zscore(cpi_yoy, _cpi_yoy_history(cpi_vals)) if cpi_yoy and len(cpi_vals) >= 24 else None

    d10 = _latest(dgs10)
    d2  = _latest(dgs2)
    spread = round(d10 - d2, 4) if d10 and d2 else None

    return {
        "available": True,
        "regime": regime,
        "quadrant": _REGIME_QUADRANT[regime],
        "growth_z": round(growth_z, 2) if growth_z is not None else None,
        "inflation_z": round(inflation_z, 2) if inflation_z is not None else None,
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
        "allocation": _ALLOCATION[regime],
    }


def _ma3m(vals: list[float]) -> list[float] | None:
    """3-month moving average over raw CPI level series."""
    if len(vals) < 15:
        return None
    out = []
    window = 3
    for i in range(len(vals) - window + 1):
        out.append(sum(vals[i:i+window]) / window)
    return out


def _cpi_yoy_history(cpi_levels: list[float]) -> list[float] | None:
    """Compute 12-month YoY % changes over CPI level series."""
    if len(cpi_levels) < 13:
        return None
    yoy = []
    for i in range(12, len(cpi_levels)):
        if cpi_levels[i-12] > 0:
            yoy.append((cpi_levels[i] / cpi_levels[i-12] - 1) * 100)
    return yoy


def _zscore(value: float, history: list[float]) -> float | None:
    """Z-score: (value - mean) / std, using population statistics."""
    if not history or len(history) < 4:
        return None
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (value - mean) / std
