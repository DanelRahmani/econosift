"""Fiscal Sustainability service — Phase 25.

Computes fiscal KPIs across major economies: revenue, expenditure, tax revenue,
fiscal balance, debt/GDP, gross savings, and the r-g differential
(interest rate vs GDP growth — key to debt sustainability).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from .. import provenance as pv
from ..cache import async_cached
from . import atlas_service

log = logging.getLogger(__name__)

# Countries to include in fiscal comparison
FISCAL_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "JP", "KR", "CN", "IN", "BR", "MX",
]

# Thresholds for traffic-light signals
THRESHOLDS = {
    "debt_gdp": [(None, 60, "green"), (60, 90, "yellow"), (90, None, "red")],
    "fiscal_balance": [(-3, None, "green"), (-6, -3, "yellow"), (None, -6, "red")],
    "tax_revenue": [(25, None, "green"), (15, 25, "yellow"), (None, 15, "red")],
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


def wb_country_provenance(countries: list[dict], specs: list[tuple[str, str, str, str]],
                          prefixes: tuple[str, ...] = ("kpis.", "history.")) -> dict:
    """Provenance for a World Bank country-comparison table.

    ``specs`` is ``(field, World Bank series code, title, units)``; each field
    gets ``<prefix><field>`` for every prefix. ``observed`` is the newest year
    of that field across rows (``periods`` is set by ``stamp_periods``); the
    year differs by country, so each row's own ``periods`` is authoritative.
    """
    prov: dict = {"*": pv.ref("worldbank", None, "World Development Indicators", frequency="annual")}
    for field, code, title, units in specs:
        years = [str(c["periods"][field]) for c in countries if (c.get("periods") or {}).get(field)]
        r = pv.ref("worldbank", code, title, units=units, frequency="annual",
                   observed=max(years) if years else None,
                   note="Latest year available per country; each row's `periods` gives its own year.")
        for prefix in prefixes:
            prov[f"{prefix}{field}"] = r
    return prov


_WB_SPECS = [
    ("debtGdp", "GC.DOD.TOTL.GD.ZS", "Central government debt, total", "% of GDP"),
    ("fiscalBalance", "GC.NLD.TOTL.GD.ZS", "Net lending (+) / net borrowing (-)", "% of GDP"),
    ("taxRevenue", "GC.TAX.TOTL.GD.ZS", "Tax revenue", "% of GDP"),
    ("govtRevenue", "GC.REV.XGRT.GD.ZS", "Revenue, excluding grants", "% of GDP"),
    ("govtExpenditure", "GC.XPN.TOTL.GD.ZS", "Expense", "% of GDP"),
    ("grossSavings", "NY.GNS.ICTR.ZS", "Gross savings", "% of GDP"),
    ("gdpGrowth", "NY.GDP.MKTP.KD.ZG", "GDP growth", "annual %"),
]


def _provenance(countries: list[dict]) -> dict:
    prov = wb_country_provenance(countries, _WB_SPECS)
    prov["kpis.primaryBalance"] = pv.derived(
        "equals kpis.fiscalBalance (World Bank net lending/borrowing); interest costs are not separated out",
        ["kpis.fiscalBalance"], title="Primary balance (as computed here)")
    prov["kpis.adverseDynamics"] = pv.derived(
        "true when debtGdp > 90 and gdpGrowth < 2.0 (a heuristic flag, not an r-g calculation)",
        ["kpis.debtGdp", "kpis.gdpGrowth"], title="Adverse debt dynamics flag")
    prov["summary"] = pv.derived(
        "simple mean (avgDebtGdp, avgFiscalBalance) or count (adverseDynamicsCount) of the countries' latest KPI values",
        ["kpis.debtGdp", "kpis.fiscalBalance", "kpis.adverseDynamics"], title="Cross-country summary")
    return prov


@async_cached("fiscal_sustainability")
async def get_fiscal_data() -> dict:
    """Fetch fiscal KPIs for major economies and compute debt sustainability."""
    cur_year = datetime.now().year
    start, end = 2015, cur_year - 1

    # Fetch all required World Bank indicators
    (wb_debt, wb_growth, wb_rev, wb_exp, wb_tax, wb_sav, wb_fisc) = await asyncio.gather(
        atlas_service._wb_timeline("debt_gdp", start, end),
        atlas_service._wb_timeline("gdp_growth", start, end),
        atlas_service._wb_timeline("govt_revenue", start, end),
        atlas_service._wb_timeline("govt_expenditure", start, end),
        atlas_service._wb_timeline("tax_revenue", start, end),
        atlas_service._wb_timeline("gross_savings", start, end),
        atlas_service._wb_timeline("fiscal_balance", start, end),
    )

    universe = atlas_service._country_universe()
    # Build iso3 -> name mapping for display
    iso3_to_name = {c["iso3"]: c["name"] for c in universe}

    countries_out = []
    for iso2 in FISCAL_COUNTRIES:
        from ..config import iso2_to_iso3, COUNTRY_NAMES
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso3_to_name.get(iso3, iso2))

        debt_pts = wb_debt.get(iso3, {})
        growth_pts = wb_growth.get(iso3, {})
        rev_pts = wb_rev.get(iso3, {})
        exp_pts = wb_exp.get(iso3, {})
        tax_pts = wb_tax.get(iso3, {})
        sav_pts = wb_sav.get(iso3, {})
        fisc_pts = wb_fisc.get(iso3, {})

        latest_debt = _latest(debt_pts)
        latest_growth = _latest(growth_pts)
        latest_rev = _latest(rev_pts)
        latest_exp = _latest(exp_pts)
        latest_tax = _latest(tax_pts)
        latest_sav = _latest(sav_pts)
        latest_fisc = _latest(fisc_pts)

        # Compute primary balance: fiscal balance + interest costs
        # (approximate: fiscal balance + (debt/GDP * avg interest rate / 100))
        # For simplicity, just use fiscal balance directly if available
        primary_balance = latest_fisc  # WB fiscal balance is net lending/borrowing

        # r-g differential: crude estimate using average central bank rate
        # A proper calculation would use effective interest rate on government debt
        # Here we flag countries where growth < 2% and debt > 90% as "adverse dynamics"
        adverse_dynamics = (
            latest_debt is not None and latest_growth is not None
            and latest_debt > 90 and latest_growth < 2.0
        )

        countries_out.append({
            "iso2": iso2,
            "iso3": iso3,
            "name": name,
            "latestYear": end,
            "kpis": {
                "debtGdp": latest_debt,
                "debtGdpSignal": _signal("debt_gdp", latest_debt),
                "fiscalBalance": latest_fisc,
                "fiscalBalanceSignal": _signal("fiscal_balance", latest_fisc),
                "taxRevenue": latest_tax,
                "taxRevenueSignal": _signal("tax_revenue", latest_tax),
                "govtRevenue": latest_rev,
                "govtExpenditure": latest_exp,
                "grossSavings": latest_sav,
                "gdpGrowth": latest_growth,
                "primaryBalance": primary_balance,
                "adverseDynamics": adverse_dynamics,
            },
            "history": {
                "debtGdp": _to_timeseries(debt_pts),
                "fiscalBalance": _to_timeseries(fisc_pts),
                "taxRevenue": _to_timeseries(tax_pts),
                "gdpGrowth": _to_timeseries(growth_pts),
                "govtRevenue": _to_timeseries(rev_pts),
                "govtExpenditure": _to_timeseries(exp_pts),
                "grossSavings": _to_timeseries(sav_pts),
            },
        })

    # Sort by debt/GDP descending
    countries_out.sort(key=lambda c: c["kpis"]["debtGdp"] or 0, reverse=True)

    # Compute aggregate stats
    debt_values = [c["kpis"]["debtGdp"] for c in countries_out if c["kpis"]["debtGdp"] is not None]
    fisc_values = [c["kpis"]["fiscalBalance"] for c in countries_out if c["kpis"]["fiscalBalance"] is not None]
    adverse_count = sum(1 for c in countries_out if c["kpis"]["adverseDynamics"])

    result = {
        "asOf": atlas_service.stamp_periods(countries_out),
        "source": "World Bank",
        "countries": countries_out,
        "summary": {
            "avgDebtGdp": round(sum(debt_values) / len(debt_values), 1) if debt_values else None,
            "avgFiscalBalance": round(sum(fisc_values) / len(fisc_values), 1) if fisc_values else None,
            "adverseDynamicsCount": adverse_count,
            "totalCountries": len(countries_out),
        },
    }
    return pv.attach(result, _provenance(countries_out))
