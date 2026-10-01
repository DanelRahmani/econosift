"""Live risk-free rates from FRED — updates with the nightly refresh cycle."""

from __future__ import annotations

import asyncio
import logging

from ..cache import async_cached

log = logging.getLogger(__name__)

# ── Country → (FRED series, tenor) for the risk-free rate ───────────────────
# A DCF/CAPM discount rate needs a long-term government yield, matching the
# US 10Y Treasury. These were 3-month interbank and overnight policy rates
# (on the mistaken note that FRED lacks non-US 10Y yields), which understated
# the rate wherever the curve slopes up (audit D-32). Where FRED publishes no
# 10Y series the short rate is kept and labelled as a proxy.
_TENOR_10Y = "10Y government bond"
_COUNTRY_SERIES: dict[str, tuple[str, str]] = {
    "United States":  ("DGS10", _TENOR_10Y),
    "United Kingdom": ("IRLTLT01GBM156N", _TENOR_10Y),
    "Germany":        ("IRLTLT01DEM156N", _TENOR_10Y),
    "Japan":          ("IRLTLT01JPM156N", _TENOR_10Y),
    "France":         ("IRLTLT01FRM156N", _TENOR_10Y),
    "Switzerland":    ("IRLTLT01CHM156N", _TENOR_10Y),
    "Canada":         ("IRLTLT01CAM156N", _TENOR_10Y),
    "Australia":      ("IRLTLT01AUM156N", _TENOR_10Y),
    "Netherlands":    ("IRLTLT01NLM156N", _TENOR_10Y),
    "India":          ("INDIRLTLT01STM", _TENOR_10Y),
    "Korea":          ("IRLTLT01KRM156N", _TENOR_10Y),
    "Italy":          ("IRLTLT01ITM156N", _TENOR_10Y),
    "Spain":          ("IRLTLT01ESM156N", _TENOR_10Y),
    "Belgium":        ("IRLTLT01BEM156N", _TENOR_10Y),
    "Austria":        ("IRLTLT01ATM156N", _TENOR_10Y),
    "Finland":        ("IRLTLT01FIM156N", _TENOR_10Y),
    "Ireland":        ("IRLTLT01IEM156N", _TENOR_10Y),
    "Portugal":       ("IRLTLT01PTM156N", _TENOR_10Y),
    "Sweden":         ("IRLTLT01SEM156N", _TENOR_10Y),
    "Denmark":        ("IRLTLT01DKM156N", _TENOR_10Y),
    "Norway":         ("IRLTLT01NOM156N", _TENOR_10Y),
    "Poland":         ("IRLTLT01PLM156N", _TENOR_10Y),
    "Israel":         ("IRLTLT01ILM156N", _TENOR_10Y),
    "South Africa":   ("IRLTLT01ZAM156N", _TENOR_10Y),
    "Mexico":         ("IRLTLT01MXM156N", _TENOR_10Y),
    "New Zealand":    ("IRLTLT01NZM156N", _TENOR_10Y),
    "China":          ("IR3TIB01CNM156N", "3M interbank (proxy)"),
    "Brazil":         ("IRSTCI01BRM156N", "overnight rate (proxy)"),
    "Russia":         ("IRSTCI01RUM156N", "overnight rate (proxy)"),
}



def ten_year_series(country: str) -> str | None:
    """FRED id of *country*'s 10-year government bond yield, or None (no series, or only a short-rate proxy)."""
    sid, tenor = _COUNTRY_SERIES.get(country, (None, None))
    return sid if tenor == _TENOR_10Y else None


# An observation older than this is reported as stale (monthly OECD series
# publish with a lag of one to two months).
_STALE_DAYS = 120

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
    """Risk-free rate and ERP per country.

    Each row says what the rate is: ``series`` / ``tenor`` / ``asOf`` for an
    observed FRED value, ``basis: "fallback"`` when FRED had nothing and a
    hard-coded estimate stands in, and ``stale`` when the observation is old.
    """
    from datetime import date

    from .macro_expansion_service import _fetch_fred_series_sync

    series_ids = [sid for sid, _ in _COUNTRY_SERIES.values()]
    try:
        fred_data = await asyncio.to_thread(
            _fetch_fred_series_sync, series_ids, "2024-01-01"
        )
    except Exception as exc:
        log.warning("risk_free_service: FRED fetch failed: %s", exc)
        fred_data = {}

    result: list[dict] = []
    for country, (sid, tenor) in _COUNTRY_SERIES.items():
        pts = [p for p in (fred_data.get(sid) or []) if p.get("value") is not None]
        if pts:
            obs = str(pts[-1]["date"])[:10]
            row = {
                # FRED gives percentage values like 4.40 → convert to decimal 0.044
                "riskFreeRate": round(float(pts[-1]["value"]) / 100, 4),
                "basis": "observed", "series": sid, "tenor": tenor, "asOf": obs,
                "stale": (date.today() - date.fromisoformat(obs)).days > _STALE_DAYS,
            }
        elif country in _FALLBACK:
            row = {"riskFreeRate": _FALLBACK[country], "basis": "fallback", "series": None,
                   "tenor": "hard-coded estimate", "asOf": None, "stale": None}
        else:
            continue
        result.append({"name": country, **row, "erp": _get_country_erp(country)})

    return result
