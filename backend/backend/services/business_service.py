"""Business Dynamism service — Phase 30.

Computes business formation KPIs across major economies: new business
density (registrations per 1,000 working-age population), time to start
a business (days), and historical Doing Business scores.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from ..cache import async_cached
from . import atlas_service

log = logging.getLogger(__name__)

# Countries to include — expand to 20 for broader coverage
BUSINESS_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "JP", "KR", "CN", "IN", "BR", "MX", "ID", "ZA",
]

# Thresholds for traffic-light signals
THRESHOLDS = {
    "new_business_density": [(5, None, "green"), (2, 5, "yellow"), (None, 2, "red")],
    "startup_time": [(None, 5, "green"), (5, 20, "yellow"), (20, None, "red")],
}


def _signal(indicator: str, value: float | None) -> str:
    if value is None:
        return "unknown"
    for lo, hi, label in THRESHOLDS.get(indicator, []):
        if lo is None and hi is not None and value < hi:
            return label
        if hi is None and lo is not None and value >= lo:
            return label
        if lo is not None and hi is not None and lo <= value < hi:
            return label
    return "unknown"


def _latest(year_map: dict[int, float]) -> float | None:
    if not year_map:
        return None
    return year_map[max(year_map)]


def _to_timeseries(year_map: dict[int, float]) -> list[dict]:
    """Convert {year: value} to [{date, value}] for frontend."""
    return [{"date": str(y), "value": v} for y, v in sorted(year_map.items())]


def _load_doing_business() -> dict:
    """Load historical Doing Business scores from static JSON."""
    data_path = Path(__file__).resolve().parent.parent / "data" / "doing_business.json"
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.warning("Failed to load doing_business.json: %s", exc)
        return {"countries": {}}


@async_cached("business_dynamism")
async def get_business_data() -> dict:
    """Fetch business dynamism KPIs for major economies."""
    cur_year = datetime.now().year
    start, end = 2010, cur_year - 1

    # Fetch World Bank indicators
    wb_density = await atlas_service._wb_timeline("new_business_density", start, end)
    # "Time to start a business" (IC.REG.DURS) came from Doing Business, which
    # the World Bank discontinued in 2021 and has since archived: no source.
    wb_startup: dict = {}

    universe = atlas_service._country_universe()
    iso3_to_name = {c["iso3"]: c["name"] for c in universe}

    # Load Doing Business data
    db_data = _load_doing_business()
    db_countries = db_data.get("countries", {})

    from ..config import iso2_to_iso3, COUNTRY_NAMES

    countries_out = []
    for iso2 in BUSINESS_COUNTRIES:
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso3_to_name.get(iso3, iso2))

        density_pts = wb_density.get(iso3, {})
        startup_pts = wb_startup.get(iso3, {})

        latest_density = _latest(density_pts)
        latest_startup = _latest(startup_pts)

        # Doing Business score (latest available, 2019 if available)
        db_entry = db_countries.get(iso2, {})
        db_scores = db_entry.get("scores", {})
        latest_db_score = _latest({int(k): v for k, v in db_scores.items()})

        countries_out.append({
            "iso2": iso2,
            "iso3": iso3,
            "name": name,
            "latestYear": end,
            "kpis": {
                "newBusinessDensity": latest_density,
                "newBusinessDensitySignal": _signal("new_business_density", latest_density),
                "startupTime": latest_startup,
                "startupTimeSignal": _signal("startup_time", latest_startup),
                "doingBusinessScore": latest_db_score,
            },
            "history": {
                "newBusinessDensity": _to_timeseries(density_pts),
                "startupTime": _to_timeseries(startup_pts),
                "doingBusinessScore": [{"date": k, "value": v} for k, v in sorted(db_scores.items())],
            },
        })

    # Sort by business density descending (most dynamic first)
    countries_out.sort(key=lambda c: c["kpis"]["newBusinessDensity"] or 0, reverse=True)

    # Summary stats
    density_values = [c["kpis"]["newBusinessDensity"] for c in countries_out if c["kpis"]["newBusinessDensity"] is not None]
    startup_values = [c["kpis"]["startupTime"] for c in countries_out if c["kpis"]["startupTime"] is not None]
    db_scores_all = [c["kpis"]["doingBusinessScore"] for c in countries_out if c["kpis"]["doingBusinessScore"] is not None]

    return {
        "asOf": atlas_service.stamp_periods(countries_out),
        "source": "World Bank",
        "unavailable": {"startupTime": "Discontinued by the World Bank (Doing Business, 2021)"},
        "countries": countries_out,
        "summary": {
            "avgBusinessDensity": round(sum(density_values) / len(density_values), 2) if density_values else None,
            "avgStartupDays": round(sum(startup_values) / len(startup_values), 1) if startup_values else None,
            "avgDoingBusinessScore": round(sum(db_scores_all) / len(db_scores_all), 1) if db_scores_all else None,
            "totalCountries": len(countries_out),
        },
    }
