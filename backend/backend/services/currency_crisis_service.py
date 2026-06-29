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
from ..sources import source_bis

log = logging.getLogger(__name__)

CRISIS_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
    "CA", "AU", "NZ", "JP", "KR", "CN", "IN", "BR", "MX", "ZA",
]

# FRED or WB indicator keys for the crisis signals
_INDICATORS = [
    "current_account",  # BN.CAB.XOKA.GD.ZS
    "inflation",        # FP.CPI.TOTL.ZG
    "debt_gdp",         # GC.DOD.TOTL.GD.ZS (for context, not signal)
    "short_term_debt",  # DT.DOD.DSTC.ZS
    "reserves_total",   # FI.RES.TOTL.CD (Phase 32)
]


def _latest(year_map: dict[int, float]) -> float | None:
    if not year_map:
        return None
    return year_map[max(year_map)]


def _signal_color(flags: int) -> str:
    if flags >= 5:
        return "red"
    elif flags >= 3:
        return "yellow"
    return "green"


@async_cached("currency_crisis")
async def get_currency_crisis() -> dict:
    cur_year = datetime.now().year
    start, end = 2014, cur_year - 1

    from ..config import iso2_to_iso3, COUNTRY_NAMES

    # Fetch World Bank indicators + reserves
    (wb_ca, wb_inf, wb_std, wb_debt, wb_res) = await asyncio.gather(
        atlas_service._wb_timeline("current_account", start, end),
        atlas_service._wb_timeline("inflation", start, end),
        atlas_service._wb_timeline("short_term_debt", start, end),
        atlas_service._wb_timeline("debt_gdp", start, end),
        atlas_service._wb_timeline("reserves_total", start, end),
    )

    # Fetch BIS effective FX data
    bis_iso2s = tuple(CRISIS_COUNTRIES)
    bis_fx_raw: dict[str, list[dict]] = {}
    try:
        bis_fx_raw = await source_bis.get_effective_fx_bulk(bis_iso2s)
    except Exception:
        log.warning("BIS effective FX fetch failed, skipping FX overvaluation signal")

    countries_out = []
    for iso2 in CRISIS_COUNTRIES:
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso2)

        ca_map = wb_ca.get(iso3, {})
        inf_map = wb_inf.get(iso3, {})
        std_map = wb_std.get(iso3, {})
        debt_map = wb_debt.get(iso3, {})
        res_map = wb_res.get(iso3, {})

        ca_val = _latest(ca_map)
        inf_val = _latest(inf_map)
        std_val = _latest(std_map)
        debt_val = _latest(debt_map)

        # Compute reserves decline rate (% YoY)
        reserves_decline: float | None = None
        if res_map and len(res_map) >= 2:
            yrs = sorted(res_map)
            prev_res, cur_res = res_map[yrs[-2]], res_map[yrs[-1]]
            if prev_res and prev_res != 0:
                reserves_decline = round(((cur_res - prev_res) / prev_res) * -100, 1)

        # Compute FX overvaluation (% above 5Y average)
        fx_overval: float | None = None
        bis_history = bis_fx_raw.get(iso2, [])
        if len(bis_history) >= 5:
            recent = bis_history[-5:]  # last 5 annual values
            values = [p["value"] for p in recent]
            avg5y = sum(values) / len(values)
            latest_fx = values[-1]
            if avg5y and avg5y != 0:
                fx_overval = round(((latest_fx - avg5y) / avg5y) * 100, 1)

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

        # 5. Reserves declining > 10% YoY
        if reserves_decline is not None and reserves_decline > 10:
            flags += 1
            factors.append(f"Reserves declining {reserves_decline:.0f}% YoY")
        elif reserves_decline is not None and reserves_decline > 5:
            factors.append(f"Reserves declining {reserves_decline:.0f}% YoY")

        # 6. FX overvaluation > 15% above 5Y trend
        if fx_overval is not None and fx_overval > 15:
            flags += 1
            factors.append(f"FX overvalued {fx_overval:.0f}% vs 5Y avg")
        elif fx_overval is not None and fx_overval > 10:
            factors.append(f"FX overvalued {fx_overval:.0f}% vs 5Y avg")

        color = _signal_color(flags)

        countries_out.append({
            "iso2": iso2, "name": name,
            "compositeScore": flags,
            "maxScore": 6,
            "signal": color,
            "kpis": {
                "currentAccount": ca_val,
                "inflation": inf_val,
                "shortTermDebt": std_val,
                "debtGdp": debt_val,
                "reservesDecline": reserves_decline,
                "fxOvervaluation": fx_overval,
            },
            "factors": factors,
        })

    countries_out.sort(key=lambda c: -c["compositeScore"])

    red_count = sum(1 for c in countries_out if c["signal"] == "red")
    yellow_count = sum(1 for c in countries_out if c["signal"] == "yellow")

    return {
        "asOf": str(datetime.now().date()),
        "source": "World Bank / IMF / BIS",
        "methodology": "Kaminsky-Lizondo-Reinhart (1998) 6-signal extraction model",
        "countries": countries_out,
        "summary": {
            "redCount": red_count,
            "yellowCount": yellow_count,
            "greenCount": len(countries_out) - red_count - yellow_count,
            "totalCountries": len(countries_out),
        },
    }
