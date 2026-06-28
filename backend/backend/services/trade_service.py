"""Trade Flows & Globalization service — Phase 26.

Computes trade KPIs across major economies: exports/GDP, imports/GDP,
trade balance, trade openness, and merchandise trade.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ..cache import async_cached
from . import atlas_service

log = logging.getLogger(__name__)

# Countries to include in trade comparison
TRADE_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "JP", "KR", "CN", "IN", "BR", "MX",
]


def _latest(year_map: dict[int, float]) -> float | None:
    if not year_map:
        return None
    return year_map[max(year_map)]


def _to_timeseries(year_map: dict[int, float]) -> list[dict]:
    """Convert {year: value} to [{date, value}] for frontend."""
    return [{"date": str(y), "value": v} for y, v in sorted(year_map.items())]


@async_cached("trade_flows")
async def get_trade_data() -> dict:
    """Fetch trade KPIs for major economies."""
    cur_year = datetime.now().year
    start, end = 2015, cur_year - 1

    # Fetch all required World Bank indicators
    (wb_exports, wb_imports, wb_merch) = await asyncio.gather(
        atlas_service._wb_timeline("exports_gdp", start, end),
        atlas_service._wb_timeline("imports_gdp", start, end),
        atlas_service._wb_timeline("merchandise_trade", start, end),
    )

    universe = atlas_service._country_universe()
    iso3_to_name = {c["iso3"]: c["name"] for c in universe}

    countries_out = []
    for iso2 in TRADE_COUNTRIES:
        from ..config import ISO2_TO_ISO3, COUNTRY_NAMES
        iso3 = ISO2_TO_ISO3.get(iso2, iso2)
        name = COUNTRY_NAMES.get(iso2, iso3_to_name.get(iso3, iso2))

        exp_pts = wb_exports.get(iso3, {})
        imp_pts = wb_imports.get(iso3, {})
        merch_pts = wb_merch.get(iso3, {})

        latest_exp = _latest(exp_pts)
        latest_imp = _latest(imp_pts)
        latest_merch = _latest(merch_pts)

        # Compute derived metrics
        trade_balance = None
        if latest_exp is not None and latest_imp is not None:
            trade_balance = round(latest_exp - latest_imp, 1)

        trade_openness = None
        if latest_exp is not None and latest_imp is not None:
            trade_openness = round(latest_exp + latest_imp, 1)

        countries_out.append({
            "iso2": iso2,
            "iso3": iso3,
            "name": name,
            "latestYear": end,
            "kpis": {
                "exportsGdp": latest_exp,
                "importsGdp": latest_imp,
                "tradeBalance": trade_balance,
                "tradeOpenness": trade_openness,
                "merchandiseTrade": latest_merch,
            },
            "history": {
                "exportsGdp": _to_timeseries(exp_pts),
                "importsGdp": _to_timeseries(imp_pts),
                "tradeBalance": _to_timeseries(
                    {y: exp_pts.get(y, 0) - imp_pts.get(y, 0)
                     for y in sorted(set(exp_pts) | set(imp_pts))}
                ),
                "merchandiseTrade": _to_timeseries(merch_pts),
            },
        })

    # Sort by trade balance descending (surplus first)
    countries_out.sort(
        key=lambda c: c["kpis"]["tradeBalance"] if c["kpis"]["tradeBalance"] is not None else -9999,
        reverse=True,
    )

    # Compute aggregate stats
    exp_values = [c["kpis"]["exportsGdp"] for c in countries_out if c["kpis"]["exportsGdp"] is not None]
    imp_values = [c["kpis"]["importsGdp"] for c in countries_out if c["kpis"]["importsGdp"] is not None]
    bal_values = [c["kpis"]["tradeBalance"] for c in countries_out if c["kpis"]["tradeBalance"] is not None]

    top_surplus = countries_out[0]["name"] if countries_out and countries_out[0]["kpis"]["tradeBalance"] and countries_out[0]["kpis"]["tradeBalance"] > 0 else None
    top_surplus_val = countries_out[0]["kpis"]["tradeBalance"] if top_surplus else None

    return {
        "asOf": str(datetime.now().date()),
        "source": "World Bank",
        "countries": countries_out,
        "summary": {
            "avgExportsGdp": round(sum(exp_values) / len(exp_values), 1) if exp_values else None,
            "avgImportsGdp": round(sum(imp_values) / len(imp_values), 1) if imp_values else None,
            "avgTradeBalance": round(sum(bal_values) / len(bal_values), 1) if bal_values else None,
            "topSurplusCountry": top_surplus,
            "topSurplusValue": top_surplus_val,
            "totalCountries": len(countries_out),
        },
    }
