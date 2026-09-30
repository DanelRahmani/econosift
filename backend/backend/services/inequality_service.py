"""Inequality & Development service — Phase 29.

Cross-country inequality indicators: Gini coefficient, income shares,
poverty headcount ratios, GDP per capita.

The World Bank re-based its poverty lines to 2021 PPP in June 2025: the series
behind ``poverty_215`` / ``poverty_365`` / ``poverty_685`` (SI.POV.DDAY / LMIC /
UMIC) now measure $3.00 / $4.20 / $8.30 a day. The keys keep their old names
for API compatibility; labels must use the new lines.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ..cache import async_cached
from . import atlas_service

log = logging.getLogger(__name__)

INEQ_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "NZ", "JP", "KR", "CN", "IN", "BR", "MX", "ZA",
]

THRESHOLDS = {
    "gini":         [(None, 30, "green"), (30, 45, "yellow"), (45, None, "red")],
    "income_top10": [(None, 25, "green"), (25, 35, "yellow"), (35, None, "red")],
    "poverty_215":  [(None, 5, "green"), (5, 20, "yellow"), (20, None, "red")],
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
    return [{"date": str(y), "value": v} for y, v in sorted(year_map.items())]


@async_cached("inequality_data")
async def get_inequality_data() -> dict:
    cur_year = datetime.now().year
    start, end = 2018, cur_year - 1  # shorter range for faster WB queries

    (wb_gini, wb_top10, wb_p215, wb_p365) = await asyncio.gather(
        atlas_service._wb_timeline("gini", start, end),
        atlas_service._wb_timeline("income_top10", start, end),
        atlas_service._wb_timeline("poverty_215", start, end),
        atlas_service._wb_timeline("poverty_365", start, end),
    )

    from ..config import iso2_to_iso3, COUNTRY_NAMES

    countries_out = []
    for iso2 in INEQ_COUNTRIES:
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso2)

        gini_map = wb_gini.get(iso3, {})
        top10_map = wb_top10.get(iso3, {})
        p215_map = wb_p215.get(iso3, {})
        p365_map = wb_p365.get(iso3, {})

        gini_v = _latest(gini_map)
        top10_v = _latest(top10_map)
        p215_v = _latest(p215_map)
        p365_v = _latest(p365_map)

        countries_out.append({
            "iso2": iso2, "name": name,
            "latestYear": end,
            "kpis": {
                "gini": gini_v,
                "giniSignal": _signal("gini", gini_v),
                "incomeTop10": top10_v,
                "incomeTop10Signal": _signal("income_top10", top10_v),
                "poverty215": p215_v,
                "poverty215Signal": _signal("poverty_215", p215_v),
                "poverty365": p365_v,
            },
            "history": {
                "gini": _to_timeseries(gini_map),
                "incomeTop10": _to_timeseries(top10_map),
                "poverty215": _to_timeseries(p215_map),
                "poverty365": _to_timeseries(p365_map),
            },
        })

    countries_out.sort(key=lambda c: c["kpis"]["gini"] or 0, reverse=True)

    with_gini = [c["kpis"]["gini"] for c in countries_out if c["kpis"]["gini"] is not None]
    with_p215 = [c["kpis"]["poverty215"] for c in countries_out if c["kpis"]["poverty215"] is not None]
    high_gini = sum(1 for c in countries_out if c["kpis"]["giniSignal"] == "red")

    return {
        "asOf": atlas_service.stamp_periods(countries_out),
        "source": "World Bank",
        "countries": countries_out,
        "summary": {
            "avgGini": round(sum(with_gini) / len(with_gini), 1) if with_gini else None,
            "avgPoverty215": round(sum(with_p215) / len(with_p215), 1) if with_p215 else None,
            "highGiniCount": high_gini,
            "totalCountries": len(countries_out),
        },
    }
