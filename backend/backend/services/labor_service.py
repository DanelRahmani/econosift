"""Labor Market Deep Dive service — Phase 28.

Cross-country labor indicators: LFPR, youth unemployment, employment/population
ratio, vulnerable employment share, GDP per employed person.
US wage growth and productivity via FRED.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from .. import provenance as pv
from ..cache import async_cached
from . import atlas_service
from .fiscal_service import wb_country_provenance

log = logging.getLogger(__name__)

LABOR_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "NZ", "JP", "KR", "CN", "IN", "BR", "MX", "ZA",
]

THRESHOLDS = {
    "lfpr":           [(65, None, "green"), (55, 65, "yellow"), (None, 55, "red")],
    "youth_unemp":    [(None, 10, "green"), (10, 20, "yellow"), (20, None, "red")],
    "emp_pop_ratio":  [(60, None, "green"), (50, 60, "yellow"), (None, 50, "red")],
    "vulnerable_emp": [(None, 10, "green"), (10, 30, "yellow"), (30, None, "red")],
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


_WB_SPECS = [
    ("lfpr", "SL.TLF.CACT.ZS",
     "Labor force participation rate, total (% of population ages 15+, modeled ILO estimate)",
     "% of population 15+"),
    ("youthUnemp", "SL.UEM.1524.ZS",
     "Unemployment, youth total (% of labor force ages 15-24, modeled ILO estimate)", "% of labor force 15-24"),
    ("empPopRatio", "SL.EMP.TOTL.SP.ZS",
     "Employment to population ratio, 15+, total (modeled ILO estimate)", "% of population 15+"),
    ("vulnerableEmp", "SL.EMP.VULN.ZS",
     "Vulnerable employment, total (% of total employment, modeled ILO estimate)", "% of employment"),
    ("gdpPerWorker", "SL.GDP.PCAP.EM.KD", "GDP per person employed (constant PPP $)", "constant PPP $"),
]


def _provenance(countries: list[dict]) -> dict:
    prov = wb_country_provenance(countries, _WB_SPECS)
    prov["kpis.productivityGrowth"] = pv.derived(
        "(latest GDP per person employed / previous available observation - 1) x 100",
        ["kpis.gdpPerWorker"], title="Productivity growth")
    prov["summary"] = pv.derived(
        "simple mean (avgLfpr, avgYouthUnemp) or count (highYouthUnempCount: youth unemployment above 20%) "
        "of the countries' latest KPI values",
        ["kpis.lfpr", "kpis.youthUnemp"], title="Cross-country summary")
    return prov


@async_cached("labor_data")
async def get_labor_data() -> dict:
    cur_year = datetime.now().year
    start, end = 2014, cur_year - 1

    (wb_lfpr, wb_yu, wb_epr, wb_vul, wb_gpw) = await asyncio.gather(
        atlas_service._wb_timeline("lfpr", start, end),
        atlas_service._wb_timeline("youth_unemp", start, end),
        atlas_service._wb_timeline("emp_pop_ratio", start, end),
        atlas_service._wb_timeline("vulnerable_emp", start, end),
        atlas_service._wb_timeline("gdp_per_worker", start, end),
    )

    from ..config import iso2_to_iso3, COUNTRY_NAMES

    countries_out = []
    for iso2 in LABOR_COUNTRIES:
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso2)

        lfpr_map = wb_lfpr.get(iso3, {})
        yu_map = wb_yu.get(iso3, {})
        epr_map = wb_epr.get(iso3, {})
        vul_map = wb_vul.get(iso3, {})
        gpw_map = wb_gpw.get(iso3, {})

        lfpr_v = _latest(lfpr_map)
        yu_v = _latest(yu_map)
        epr_v = _latest(epr_map)
        vul_v = _latest(vul_map)
        gpw_v = _latest(gpw_map)

        # Productivity growth (YoY)
        gpw_growth = None
        if gpw_map and len(gpw_map) >= 2:
            yrs = sorted(gpw_map)
            prev, cur = gpw_map[yrs[-2]], gpw_map[yrs[-1]]
            if prev and prev != 0:
                gpw_growth = round((cur / prev - 1) * 100, 2)

        countries_out.append({
            "iso2": iso2, "name": name,
            "latestYear": end,
            "kpis": {
                "lfpr": lfpr_v,
                "lfprSignal": _signal("lfpr", lfpr_v),
                "youthUnemp": yu_v,
                "youthUnempSignal": _signal("youth_unemp", yu_v),
                "empPopRatio": epr_v,
                "empPopRatioSignal": _signal("emp_pop_ratio", epr_v),
                "vulnerableEmp": vul_v,
                "vulnerableEmpSignal": _signal("vulnerable_emp", vul_v),
                "gdpPerWorker": gpw_v,
                "productivityGrowth": gpw_growth,
            },
            "history": {
                "lfpr": _to_timeseries(lfpr_map),
                "youthUnemp": _to_timeseries(yu_map),
                "empPopRatio": _to_timeseries(epr_map),
                "vulnerableEmp": _to_timeseries(vul_map),
                "gdpPerWorker": _to_timeseries(gpw_map),
            },
        })

    countries_out.sort(key=lambda c: c["kpis"]["youthUnemp"] or 0, reverse=True)

    # Summary stats
    with_lfpr = [c["kpis"]["lfpr"] for c in countries_out if c["kpis"]["lfpr"] is not None]
    with_yu = [c["kpis"]["youthUnemp"] for c in countries_out if c["kpis"]["youthUnemp"] is not None]
    high_red = sum(1 for c in countries_out if c["kpis"]["youthUnempSignal"] == "red")

    result = {
        "asOf": atlas_service.stamp_periods(countries_out),
        "source": "World Bank",
        "countries": countries_out,
        "summary": {
            "avgLfpr": round(sum(with_lfpr) / len(with_lfpr), 1) if with_lfpr else None,
            "avgYouthUnemp": round(sum(with_yu) / len(with_yu), 1) if with_yu else None,
            "highYouthUnempCount": high_red,
            "totalCountries": len(countries_out),
        },
    }
    return pv.attach(result, _provenance(countries_out))
