"""Live risk-free rates from FRED — updates with the nightly refresh cycle."""

from __future__ import annotations

import asyncio
import logging

from ..cache import async_cached

log = logging.getLogger(__name__)

# ── Country → FRED series for risk-free rate ────────────────────────────────
# Preference order: 10Y government bond > interbank rate
# Falls back to estimate if no FRED series available.
_COUNTRY_SERIES: dict[str, str] = {
    "United States":  "DGS10",            # 10Y Treasury (standard for US valuation)
    "United Kingdom": "IR3TIB01GBM156N",  # 3M interbank (proxy; FRED lacks UK 10Y)
    "Germany":        "IR3TIB01DEM156N",  # 3M interbank
    "Japan":          "IR3TIB01JPM156N",  # 3M interbank (Japan 10Y ≈ 1%, 3M ≈ 0.7%)
    "France":         "IR3TIB01FRM156N",
    "Switzerland":    "IR3TIB01CHM156N",
    "Canada":         "IR3TIB01CAM156N",
    "Australia":      "IR3TIB01AUM156N",
    "China":          "IR3TIB01CNM156N",
    "India":          "IRSTCI01INM156N",  # RBI repo rate (central bank policy rate)
    "Brazil":         "IRSTCI01BRM156N",  # SELIC rate (central bank policy rate)
    "Russia":         "IRSTCI01RUM156N",  # CBR key rate (central bank policy rate)
    "Netherlands":    "IR3TIB01NLM156N",
}

# ── Fallback estimates (updated 2026) ──────────────────────────────────────
# Used when FRED series is unavailable or returns empty.
_FALLBACK: dict[str, float] = {
    "United States":  0.0400,
    "United Kingdom": 0.0425,
    "Germany":        0.0250,
    "Japan":          0.0100,
    "France":         0.0300,
    "Netherlands":    0.0275,
    "Switzerland":    0.0100,
    "Canada":         0.0350,
    "Australia":      0.0400,
    "China":          0.0250,
    "India":          0.0650,
    "Brazil":         0.1000,
    "Russia":         0.1600,
}

# ── ERP from live Damodaran Excel (with fallback) ───────────────────────────

def _get_country_erp(country: str) -> float:
    """Get ERP for a country from the live Damodaran cache, with fallback."""
    try:
        from .discount_rates import load_erp
        data = load_erp()
        countries = data.get("countries", {})
        entry = countries.get(country)
        if entry and isinstance(entry, dict) and "erp" in entry:
            val = float(entry["erp"])
            if val:  # ERP values in the dict are stored as e.g. 4.869 (percentage)
                return round(val / 100, 4)
    except Exception:
        pass

    # Fallback
    return _FALLBACK_ERP.get(country, 0.05)


# Minimal hardcoded fallbacks — only used if Damodaran JSON fails or is missing
_FALLBACK_ERP: dict[str, float] = {
    "United States": 0.0446,
    "Germany": 0.0460,
    "Japan": 0.0460,
    "United Kingdom": 0.0500,
    "France": 0.0500,
    "Netherlands": 0.0460,
    "Switzerland": 0.0446,
    "Canada": 0.0460,
    "Australia": 0.0460,
    "China": 0.0620,
    "India": 0.0700,
    "Brazil": 0.0900,
    "Russia": 0.1000,
}


@async_cached("risk_free_rates")
async def get_risk_free_rates() -> list[dict]:
    """Return live risk-free rates per country from FRED, with fallbacks."""
    from .macro_expansion_service import _fetch_fred_series_sync

    series_ids = list(_COUNTRY_SERIES.values())
    try:
        fred_data = await asyncio.to_thread(
            _fetch_fred_series_sync, series_ids, "2024-01-01"
        )
    except Exception as exc:
        log.warning("risk_free_service: FRED fetch failed: %s", exc)
        fred_data = {}

    result: list[dict] = []
    for country, sid in _COUNTRY_SERIES.items():
        rf: float | None = None

        # Try FRED first — take the last (most recent) data point
        pts = fred_data.get(sid) or []
        if pts and pts[-1].get("value") is not None:
            # FRED gives percentage values like 4.40 → convert to decimal 0.044
            rf = round(float(pts[-1]["value"]) / 100, 4)
        else:
            rf = _FALLBACK.get(country)

        if rf is None:
            continue

        erp = _get_country_erp(country)
        result.append({"name": country, "riskFreeRate": rf, "erp": erp})

    return result
