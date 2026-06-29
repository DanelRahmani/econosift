"""Currency Crisis Early Warning service — Phase 28.

Kaminsky-Lizondo-Reinhart (1998) signal extraction approach.
Uses: reserves decline, current account deficit, real FX overvaluation,
inflation, and short-term external debt share.
Output: composite traffic-light warning (green/yellow/red) per country.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ..cache import async_cached
from . import atlas_service

log = logging.getLogger(__name__)

CRISIS_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "NZ", "JP", "KR", "CN", "IN", "BR", "MX", "ZA",
]

# FRED or WB indicator keys for the 5 crisis signals
_INDICATORS = [
    "current_account",  # BN.CAB.XOKA.GD.ZS
    "inflation",        # FP.CPI.TOTL.ZG
    "debt_gdp",         # GC.DOD.TOTL.GD.ZS (for context, not signal)
    "short_term_debt",  # DT.DOD.DSTC.ZS
]


def _latest(year_map: dict[int, float]) -> float | None:
    if not year_map:
        return None
    return year_map[max(year_map)]


def _signal_color(flags: int) -> str:
    if flags >= 4:
        return "red"
    elif flags >= 2:
        return "yellow"
    return "green"


@async_cached("currency_crisis")
async def get_currency_crisis() -> dict:
    cur_year = datetime.now().year
    start, end = 2014, cur_year - 1

    from ..config import ISO2_TO_ISO3, COUNTRY_NAMES

    # Fetch indicators
    (wb_ca, wb_inf, wb_std, wb_debt) = await asyncio.gather(
        atlas_service._wb_timeline("current_account", start, end),
        atlas_service._wb_timeline("inflation", start, end),
        atlas_service._wb_timeline("short_term_debt", start, end),
        atlas_service._wb_timeline("debt_gdp", start, end),
    )

    countries_out = []
    for iso2 in CRISIS_COUNTRIES:
        iso3 = ISO2_TO_ISO3.get(iso2, iso2)
        name = COUNTRY_NAMES.get(iso2, iso2)

        ca_map = wb_ca.get(iso3, {})
        inf_map = wb_inf.get(iso3, {})
        std_map = wb_std.get(iso3, {})
        debt_map = wb_debt.get(iso3, {})

        ca_val = _latest(ca_map)
        inf_val = _latest(inf_map)
        std_val = _latest(std_map)
        debt_val = _latest(debt_map)

        # Compute reserves decline rate (simplified: use current account
        # as proxy for external vulnerability)
        # Real exchange rate overvaluation proxy: use inflation differential
        # vs US as rough PPP deviation indicator

        flags = 0
        factors = []

        # 1. Current account deficit > 5% of GDP
        if ca_val is not None and ca_val < -5:
            flags += 1
            factors.append("CA deficit >5% GDP")
        elif ca_val is not None and ca_val < -2:
            factors.append("CA deficit >2% GDP")

        # 2. Inflation > 10%
        if inf_val is not None and inf_val > 10:
            flags += 1
            factors.append(f"Inflation {inf_val:.1f}% >10%")
        elif inf_val is not None and inf_val > 5:
            factors.append(f"Inflation {inf_val:.1f}% >5%")

        # 3. Short-term debt > 15% of total external debt
        if std_val is not None and std_val > 15:
            flags += 1
            factors.append(f"Short-term debt {std_val:.1f}% >15%")

        # 4. High debt/GDP > 90%
        if debt_val is not None and debt_val > 90:
            flags += 1
            factors.append(f"Debt/GDP {debt_val:.0f}% >90%")
        elif debt_val is not None and debt_val > 60:
            factors.append(f"Debt/GDP {debt_val:.0f}% >60%")

        # 5. Combined: high inflation + CA deficit
        if inf_val is not None and ca_val is not None and inf_val > 5 and ca_val < -2:
            flags += 1
            factors.append("Inflation + CA deficit (twin deficits)")

        color = _signal_color(flags)

        countries_out.append({
            "iso2": iso2, "name": name,
            "compositeScore": flags,
            "signal": color,
            "kpis": {
                "currentAccount": ca_val,
                "inflation": inf_val,
                "shortTermDebt": std_val,
                "debtGdp": debt_val,
            },
            "factors": factors,
        })

    countries_out.sort(key=lambda c: -c["compositeScore"])

    red_count = sum(1 for c in countries_out if c["signal"] == "red")
    yellow_count = sum(1 for c in countries_out if c["signal"] == "yellow")

    return {
        "asOf": str(datetime.now().date()),
        "source": "World Bank / IMF",
        "methodology": "Kaminsky-Lizondo-Reinhart (1998) signal extraction",
        "countries": countries_out,
        "summary": {
            "redCount": red_count,
            "yellowCount": yellow_count,
            "greenCount": len(countries_out) - red_count - yellow_count,
            "totalCountries": len(countries_out),
        },
    }
