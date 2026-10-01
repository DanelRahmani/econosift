"""Supply Chain Vulnerability service — Phase 34.

Computes a composite supply chain vulnerability score from existing
World Bank indicators: food import dependency + fuel import dependency.
Higher score = more vulnerable to supply chain disruption.

The Herfindahl import concentration index (bilateral trade partner data)
was investigated but is not accessible via free APIs (imfp DNS failure,
WB partner share data too complex to aggregate). The food + fuel layers
already capture the most actionable supply chain risk dimensions.
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

# Countries to include
SUPPLY_CHAIN_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "NZ", "JP", "KR", "CN", "IN", "BR", "MX", "ZA",
    "ID", "TR", "SA", "NG", "EG", "AR", "CL", "TH", "VN", "PH",
]


def _latest(year_map: dict[int, float]) -> float | None:
    if not year_map:
        return None
    return year_map[max(year_map)]


def _provenance(countries: list[dict]) -> dict:
    """Row fields sit directly on each ``countries`` row, so keys are ``countries.<field>``."""
    prov = wb_country_provenance(countries, [
        ("foodImports", "TM.VAL.FOOD.ZS.UN", "Food imports (% of merchandise imports)", "% of merchandise imports"),
        ("fuelImports", "TM.VAL.FUEL.ZS.UN", "Fuel imports (% of merchandise imports)", "% of merchandise imports"),
    ], prefixes=("countries.",))
    prov["countries.compositeScore"] = pv.derived(
        "(food import share + fuel import share) / 2, only when both shares exist; each share is its own "
        "latest available year",
        ["countries.foodImports", "countries.fuelImports"], title="Supply chain vulnerability score")
    return prov


@async_cached("supply_chain_vulnerability")
async def get_supply_chain_data() -> dict:
    """Fetch food + fuel import dependency and compute composite score."""
    cur_year = datetime.now().year
    start, end = 2014, cur_year - 1

    # Fetch both indicators from World Bank
    (wb_food, wb_fuel) = await asyncio.gather(
        atlas_service._wb_timeline("food_imports", start, end),
        atlas_service._wb_timeline("fuel_imports", start, end),
    )

    from ..config import iso2_to_iso3, COUNTRY_NAMES

    countries_out = []
    for iso2 in SUPPLY_CHAIN_COUNTRIES:
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso2)

        food_map = wb_food.get(iso3, {})
        fuel_map = wb_fuel.get(iso3, {})

        food_val = _latest(food_map)
        fuel_val = _latest(fuel_map)

        # Composite score: average of food + fuel import dependency
        # Higher = more vulnerable. Range: 0–100 (both are % of imports).
        # Both shares are required: a single share passed off as the average
        # of two is not comparable with the other countries' scores.
        composite: float | None = None
        if food_val is not None and fuel_val is not None:
            composite = round((food_val + fuel_val) / 2, 1)

        countries_out.append({
            "iso2": iso2,
            "name": name,
            "compositeScore": composite,
            "foodImports": food_val,
            "fuelImports": fuel_val,
            "periods": {
                "foodImports": max(food_map) if food_map else None,
                "fuelImports": max(fuel_map) if fuel_map else None,
            },
        })

    countries_out.sort(
        key=lambda c: c["compositeScore"] if c["compositeScore"] is not None else -1,
        reverse=True,
    )

    years = [y for c in countries_out for y in c["periods"].values() if y]

    result = {
        "asOf": str(max(years)) if years else None,
        "source": "World Bank",
        "methodology": "Composite = (food_import_share + fuel_import_share) / 2. Higher = more vulnerable to trade disruption.",
        "countries": countries_out,
        "summary": {
            "totalCountries": len(countries_out),
            "highestRisk": countries_out[0]["compositeScore"] if countries_out else None,
            "lowestRisk": countries_out[-1]["compositeScore"] if countries_out else None,
        },
    }
    return pv.attach(result, _provenance(countries_out))
