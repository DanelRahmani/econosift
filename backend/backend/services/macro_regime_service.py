"""Macro regime classifier — 4-quadrant growth/inflation model with asset allocation signals."""
from __future__ import annotations

import math
from backend import provenance as pv
from backend.cache import async_cached
from backend.services import macro_expansion_service as mes

# Growth: Chicago Fed National Activity Index, 3-month average (CFNAIMA3) —
# live and monthly. The OECD CLI previously used here (USALOLITONOSTSAM)
# stopped updating on FRED in Jan 2024, so every regime since then was
# classified on a frozen growth reading (audit D-17/D-29).
_GROWTH_SERIES = "CFNAIMA3"
_GROWTH_LABEL = "Chicago Fed National Activity Index, 3-mo avg (CFNAI-MA3)"
_SERIES = (_GROWTH_SERIES, "CPIAUCSL", "FEDFUNDS", "DGS10", "DGS2")
# A monthly input older than this is stale: the regime is not computed.
_MAX_AGE_DAYS = 150
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


def _provenance(result: dict, series: dict[str, list[dict]]) -> dict:
    def fred(sid: str, title: str, freq: str, units: str | None = None) -> dict:
        pts = [p for p in series.get(sid, []) if p.get("value") is not None]
        return pv.fred(sid, title, units=units, frequency=freq, observed=pts[-1]["date"] if pts else None)

    growth = fred(_GROWTH_SERIES, _GROWTH_LABEL, "monthly", "index")
    cpi = fred("CPIAUCSL", "Consumer price index for all urban consumers, all items", "monthly", "index")
    ff = fred("FEDFUNDS", "Effective federal funds rate", "monthly", "%")
    d10 = fred("DGS10", "Market yield on US Treasury securities at 10-year constant maturity", "daily", "%")
    d2 = fred("DGS2", "Market yield on US Treasury securities at 2-year constant maturity", "daily", "%")
    cpi_yoy = pv.derived("(latest CPIAUCSL / CPIAUCSL about 12 months earlier - 1) x 100 (percent)", [cpi],
                         title="CPI inflation, year over year", observed=result["metrics"]["cpi_as_of"])
    classify = pv.derived(
        "growth = 'rising' if CFNAI-MA3 is above its value about 3 months earlier, else 'falling'; inflation = "
        "'above' if CPI year-over-year > 2.5%, else 'below'; rising+below = Goldilocks, rising+above = "
        "Reflationary, falling+above = Stagflation, falling+below = Deflationary",
        [growth, cpi_yoy], title="Macro regime", observed=result["metrics"]["growth_as_of"])
    table = pv.derived("fixed lookup table keyed by the classified regime (not estimated from data)",
                       ["regime"], title="Regime allocation rule of thumb")
    return {
        "*": classify,
        "regime": classify, "quadrant": classify,
        "growth_signal": classify, "inflation_signal": classify,
        "growth_z": pv.derived(
            "(3-month change in CFNAI-MA3 - mean) / standard deviation of all historical 3-month changes",
            [growth], title="Growth z-score", observed=result["metrics"]["growth_as_of"]),
        "inflation_z": pv.derived(
            "(CPI year-over-year - mean) / standard deviation of the history of monthly CPI year-over-year values",
            [cpi], title="Inflation z-score", observed=result["metrics"]["cpi_as_of"]),
        "metrics.growth_current": growth,
        "metrics.growth_change_3m": pv.derived("latest CFNAI-MA3 minus its value about 3 months earlier", [growth],
                                               title="Growth momentum, 3 months",
                                               observed=result["metrics"]["growth_as_of"]),
        "metrics.cpi_yoy": cpi_yoy,
        "metrics.fed_funds": ff,
        "metrics.yield_spread_2y10y": pv.derived("DGS10 - DGS2 (latest observations, percentage points)",
                                                 [d10, d2], title="10y-2y Treasury spread"),
        "asset_signals": table,
        "allocation": table,
    }


@async_cached("macro_regime", skip_if=_regime_unavailable)
async def get_macro_regime() -> dict:
    data = await mes.fetch_fred_series(_SERIES, _START)
    lei   = data.get(_GROWTH_SERIES, [])
    cpi   = data.get("CPIAUCSL", [])
    ff    = data.get("FEDFUNDS", [])
    dgs10 = data.get("DGS10", [])
    dgs2  = data.get("DGS2", [])

    # If the core growth/inflation series didn't come back, don't fabricate a
    # regime (an empty fetch would otherwise classify as "Deflationary" with
    # null metrics). Surface it so the UI can show a real reason.
    if not cpi or not lei:
        return {
            "available": False,
            "reason": "FRED macro series unavailable — check the FRED API key in Admin, then use “Clear cache & re-warm”.",
        }
    # Refuse to classify on a frozen input rather than silently reuse it.
    stale = [sid for sid, pts in ((_GROWTH_SERIES, lei), ("CPIAUCSL", cpi))
             if _age_days(pts) is None or _age_days(pts) > _MAX_AGE_DAYS]
    if stale:
        return {
            "available": False,
            "reason": f"Input series not updated recently: {', '.join(stale)}.",
        }

    lei_cur = _latest(lei)
    lei_3m  = _val_n_months_ago(lei, 3)
    # Missing momentum is unknown, not "falling".
    if lei_cur is None or lei_3m is None:
        return {"available": False, "reason": f"{_GROWTH_SERIES} history too short for a 3-month change."}
    growth_signal = "rising" if lei_cur > lei_3m else "falling"

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

    # z-score of the 3-month *change* against the history of 3-month changes
    # (previously a level was scored against averaged levels).
    growth_changes = [lei_vals[i] - lei_vals[i - 3] for i in range(3, len(lei_vals))]
    growth_z = (_zscore(lei_cur - lei_3m, growth_changes)
                if len(growth_changes) >= 24 else None)
    inflation_z = _zscore(cpi_yoy, _cpi_yoy_history(cpi_vals)) if cpi_yoy and len(cpi_vals) >= 24 else None

    d10 = _latest(dgs10)
    d2  = _latest(dgs2)
    spread = round(d10 - d2, 4) if d10 and d2 else None

    result = {
        "available": True,
        "regime": regime,
        "quadrant": _REGIME_QUADRANT[regime],
        "growth_z": round(growth_z, 2) if growth_z is not None else None,
        "inflation_z": round(inflation_z, 2) if inflation_z is not None else None,
        "growth_signal": growth_signal,
        "inflation_signal": inflation_signal,
        "growth_indicator": _GROWTH_LABEL,
        "metrics": {
            "growth_current": lei_cur,
            "growth_change_3m": round(lei_cur - lei_3m, 4),
            "growth_as_of": lei[-1]["date"] if lei else None,
            "cpi_as_of": cpi[-1]["date"] if cpi else None,
            "cpi_yoy": cpi_yoy,
            "fed_funds": _latest(ff),
            "yield_spread_2y10y": spread,
        },
        "asset_signals": _REGIME_SIGNALS[regime],
        "allocation": _ALLOCATION[regime],
    }
    return pv.attach(result, _provenance(result, data))


def _age_days(pts: list[dict]) -> int | None:
    """Days since the latest observation."""
    from datetime import date, datetime
    if not pts:
        return None
    return (date.today() - datetime.strptime(pts[-1]["date"][:10], "%Y-%m-%d").date()).days


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
