"""Energy Transition & Climate Economics service — Phase 28.

Cross-country climate/energy indicators: CO2/capita, renewable energy share,
energy imports, oil/gas/coal rents as % of GDP.
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

ENERGY_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "NZ", "JP", "KR", "CN", "IN", "BR", "MX", "ZA",
]

THRESHOLDS = {
    "co2_per_capita":  [(None, 5, "green"), (5, 10, "yellow"), (10, None, "red")],
    "renewable_share": [(30, None, "green"), (15, 30, "yellow"), (None, 15, "red")],
    "energy_imports":  [(None, 20, "green"), (20, 50, "yellow"), (50, None, "red")],
    "fossil_rents":    [(None, 2, "green"), (2, 10, "yellow"), (10, None, "red")],
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
    ("co2PerCapita", "EN.GHG.CO2.PC.CE.AR5", "Carbon dioxide (CO2) emissions excluding LULUCF per capita",
     "t CO2e per capita"),
    ("renewableShare", "EG.FEC.RNEW.ZS", "Renewable energy consumption (% of total final energy consumption)",
     "% of final energy consumption"),
    ("energyImports", "EG.IMP.CONS.ZS", "Energy imports, net (% of energy use)", "% of energy use"),
    ("oilRents", "NY.GDP.PETR.RT.ZS", "Oil rents", "% of GDP"),
    ("gasRents", "NY.GDP.NGAS.RT.ZS", "Natural gas rents", "% of GDP"),
    ("coalRents", "NY.GDP.COAL.RT.ZS", "Coal rents", "% of GDP"),
]


def _provenance(countries: list[dict]) -> dict:
    prov = wb_country_provenance(countries, _WB_SPECS)
    prov["kpis.fossilRentsTotal"] = pv.derived(
        "oil rents + natural gas rents + coal rents (% of GDP); a missing component counts as 0 and each "
        "component is its own latest available year",
        ["kpis.oilRents", "kpis.gasRents", "kpis.coalRents"], title="Fossil-fuel rents, total")
    prov["summary"] = pv.derived(
        "simple mean (avgCo2PerCapita, avgRenewableShare) or count (highCo2Count: CO2 per capita above 10 t) "
        "of the countries' latest KPI values",
        ["kpis.co2PerCapita", "kpis.renewableShare"], title="Cross-country summary")
    return prov


@async_cached("energy_data")
async def get_energy_data() -> dict:
    cur_year = datetime.now().year
    start, end = 2014, cur_year - 1

    (wb_co2, wb_ren, wb_eimp, wb_oil, wb_gas, wb_coal) = await asyncio.gather(
        atlas_service._wb_timeline("co2_per_capita", start, end),
        atlas_service._wb_timeline("renewable_share", start, end),
        atlas_service._wb_timeline("energy_imports", start, end),
        atlas_service._wb_timeline("oil_rents", start, end),
        atlas_service._wb_timeline("gas_rents", start, end),
        atlas_service._wb_timeline("coal_rents", start, end),
    )

    from ..config import iso2_to_iso3, COUNTRY_NAMES

    countries_out = []
    for iso2 in ENERGY_COUNTRIES:
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso2)

        co2_map = wb_co2.get(iso3, {})
        ren_map = wb_ren.get(iso3, {})
        eimp_map = wb_eimp.get(iso3, {})
        oil_map = wb_oil.get(iso3, {})
        gas_map = wb_gas.get(iso3, {})
        coal_map = wb_coal.get(iso3, {})

        co2_val = _latest(co2_map)
        ren_val = _latest(ren_map)
        eimp_val = _latest(eimp_map)
        oil_val = _latest(oil_map)
        gas_val = _latest(gas_map)
        coal_val = _latest(coal_map)
        fossil_total = (
            round((oil_val or 0) + (gas_val or 0) + (coal_val or 0), 1)
            if any(v is not None for v in [oil_val, gas_val, coal_val]) else None
        )

        countries_out.append({
            "iso2": iso2, "name": name,
            "latestYear": end,
            "kpis": {
                "co2PerCapita": co2_val,
                "co2Signal": _signal("co2_per_capita", co2_val),
                "renewableShare": ren_val,
                "renewableSignal": _signal("renewable_share", ren_val),
                "energyImports": eimp_val,
                "energyImportsSignal": _signal("energy_imports", eimp_val),
                "oilRents": oil_val,
                "gasRents": gas_val,
                "coalRents": coal_val,
                "fossilRentsTotal": fossil_total,
                "fossilRentsSignal": _signal("fossil_rents", fossil_total),
            },
            "history": {
                "co2PerCapita": _to_timeseries(co2_map),
                "renewableShare": _to_timeseries(ren_map),
                "energyImports": _to_timeseries(eimp_map),
                "oilRents": _to_timeseries(oil_map),
                "gasRents": _to_timeseries(gas_map),
                "coalRents": _to_timeseries(coal_map),
            },
        })

    countries_out.sort(key=lambda c: c["kpis"]["co2PerCapita"] or 0, reverse=True)

    with_co2 = [c["kpis"]["co2PerCapita"] for c in countries_out if c["kpis"]["co2PerCapita"] is not None]
    with_ren = [c["kpis"]["renewableShare"] for c in countries_out if c["kpis"]["renewableShare"] is not None]
    high_co2 = sum(1 for c in countries_out if c["kpis"]["co2Signal"] == "red")

    result = {
        "asOf": atlas_service.stamp_periods(countries_out),
        "source": "World Bank",
        "countries": countries_out,
        "summary": {
            "avgCo2PerCapita": round(sum(with_co2) / len(with_co2), 1) if with_co2 else None,
            "avgRenewableShare": round(sum(with_ren) / len(with_ren), 1) if with_ren else None,
            "highCo2Count": high_co2,
            "totalCountries": len(countries_out),
        },
    }
    return pv.attach(result, _provenance(countries_out))
