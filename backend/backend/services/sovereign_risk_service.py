from __future__ import annotations
import asyncio
from backend import provenance as pv
from backend.cache import async_cached
from backend.services.yield_curve_service import get_yield_curves
from backend.services.country_risk_service import get_country_risk
from backend.services import atlas_service

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


def _wb_refs(wb_entry: dict) -> list[dict]:
    """Refs for the country-risk indicators actually present in ``wb_entry``."""
    indic = wb_entry.get("indicators", {})
    sources = wb_entry.get("sources", {})
    year = wb_entry.get("year")
    codes = atlas_service._WB_CODES
    refs: list[dict] = []
    if indic.get("debt_gdp") is not None:
        if str(sources.get("debt_gdp", "")).startswith("IMF"):
            refs.append(pv.ref("imf", atlas_service._IMF_CODES["debt_gdp"],
                               "General government gross debt (% of GDP)", units="% of GDP",
                               frequency="annual", observed=str(year) if year else None))
        else:
            refs.append(pv.ref("worldbank", codes["debt_gdp"], "Central government debt (% of GDP)",
                               units="% of GDP", frequency="annual", observed=str(year) if year else None,
                               note="Central-government debt, used only where the IMF general-government figure is missing."))
    for key, title, units in (("current_account", "Current account balance (% of GDP)", "% of GDP"),
                              ("inflation", "Inflation, consumer prices (annual %)", "% per year")):
        if indic.get(key) is not None:
            refs.append(pv.ref("worldbank", codes[key], title, units=units, frequency="annual",
                               note="Latest annual value since 2018; each indicator has its own year."))
    if indic.get("fiscal_balance") is not None:
        if sources.get("fiscal_balance"):
            refs.append(pv.ref("imf", atlas_service._IMF_CODES["fiscal_balance"],
                               "General government net lending/borrowing (% of GDP)", units="% of GDP",
                               frequency="annual", note="Fills countries the World Bank series misses."))
        else:
            refs.append(pv.ref("worldbank", "GC.BAL.CASH.GD.ZS", "Cash surplus/deficit (% of GDP)",
                               units="% of GDP", frequency="annual",
                               note="Latest annual value since 2018."))
    if indic.get("reserves_growth") is not None:
        refs.append(pv.derived(
            "(latest total reserves - previous available year) / |previous| x 100",
            [pv.ref("worldbank", codes["reserves_total"], "Total reserves incl. gold (current US$)",
                    units="current US$", frequency="annual")],
            title="Reserves growth (% YoY)"))
    if indic.get("unemployment") is not None:
        refs.append(pv.ref("worldbank", codes["unemployment"], "Unemployment, total (% of labour force)",
                           units="% of labour force", frequency="annual",
                           note="Latest annual value since 2018."))
    return refs


def _provenance(curves: dict, iso_wb: dict, countries: list[dict]) -> dict:
    """Source map for the sovereign risk panel (see provenance.py)."""
    up = curves.get("provenance", {}) if isinstance(curves, dict) else {}
    composite = ("composite_score = market score + World Bank score. Market score = 10y spread vs US "
                 "clamped to +/-3pp, mapped to 0-50 (25 when the spread is missing). World Bank score = "
                 "share of indicators flagged red x 50 (25 when there are no signals). "
                 "Signal: green < 30, yellow 30-60, red > 60.")
    prov: dict = {
        "*": pv.derived(composite, title="Sovereign risk composite"),
        "countries": pv.derived(composite, title="Sovereign risk composite"),
    }
    for c in countries:
        row = f"countries.{c['iso3']}"
        wb_entry = iso_wb.get(c["iso3"], {})
        missing = c["spread_vs_us"] is None or not wb_entry.get("signals")
        prov[row] = pv.derived(
            composite, title=f"{c['name']} sovereign risk composite",
            flags=["fallback"] if missing else [],
            note=("A missing spread or missing indicator signals were replaced by a neutral 25-point "
                  "half-score." if missing else None))
        for field in ("yield_10y", "spread_vs_us"):
            src = up.get(f"foreign_10y.{c['name']}" + (".spread_vs_us" if field == "spread_vs_us" else ""))
            if isinstance(src, dict):
                prov[f"{row}.{field}"] = dict(src)
        refs = _wb_refs(wb_entry)
        if refs:
            prov[f"{row}.wb_indicators"] = refs
        prov[f"{row}.wb_signals"] = pv.derived(
            "green / yellow / red per indicator against fixed thresholds (see the Country Risk panel)",
            [f"{row}.wb_indicators"], title=f"{c['name']} indicator traffic lights")
    prov["top_risk"] = pv.derived("the five countries with the highest composite score",
                                  ["countries"], title="Top risk")
    prov["bottom_risk"] = pv.derived("the five countries with the lowest composite score",
                                     ["countries"], title="Bottom risk")
    return prov


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
    return pv.attach({
        "countries": countries,
        "top_risk": countries[:5],
        "bottom_risk": countries[-5:],
    }, _provenance(curves, iso_wb, countries))
