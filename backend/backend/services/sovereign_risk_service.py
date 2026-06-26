from __future__ import annotations
import asyncio
from backend.cache import async_cached
from backend.services.yield_curve_service import get_yield_curves
from backend.services.country_risk_service import get_country_risk

_NAME_TO_ISO = {
    "Germany": "DEU", "UK": "GBR", "Japan": "JPN", "France": "FRA",
    "Italy": "ITA", "Spain": "ESP", "Canada": "CAN", "Australia": "AUS",
}


def _market_score(spread: float | None) -> float:
    """Map spread (percentage points) to 0–50 score. Negative = safer than US."""
    if spread is None:
        return 25.0
    clamped = max(-3.0, min(3.0, spread))
    return round((clamped + 3.0) / 6.0 * 50.0, 1)


def _wb_score(signals: dict) -> float:
    """Count reds → map to 0–50 score."""
    reds = sum(1 for v in signals.values() if v == "red")
    total = len(signals)
    if total == 0:
        return 25.0
    return round(reds / total * 50.0, 1)


@async_cached("sovereign_risk")
async def get_sovereign_risk() -> dict:
    curves, wb = await asyncio.gather(get_yield_curves(), get_country_risk())

    foreign_10y: dict[str, dict] = curves.get("foreign_10y", {})
    iso_wb = {c["iso3"]: c for c in wb.get("countries", [])}

    countries = []
    for country_name, iso3 in _NAME_TO_ISO.items():
        fy = foreign_10y.get(country_name, {})
        spread = fy.get("spread_vs_us")
        wb_entry = iso_wb.get(iso3, {})
        signals = wb_entry.get("signals", {})
        ms = _market_score(spread)
        ws = _wb_score(signals)
        composite = round(ms + ws, 1)
        signal = "green" if composite < 30 else ("yellow" if composite <= 60 else "red")
        countries.append({
            "iso3": iso3,
            "name": country_name,
            "yield_10y": fy.get("yield_10y"),
            "spread_vs_us": spread,
            "composite_score": composite,
            "signal": signal,
            "wb_indicators": wb_entry.get("indicators", {}),
            "wb_signals": signals,
        })

    countries.sort(key=lambda c: c["composite_score"], reverse=True)
    return {
        "countries": countries,
        "top_risk": countries[:5],
        "bottom_risk": countries[-5:],
    }
