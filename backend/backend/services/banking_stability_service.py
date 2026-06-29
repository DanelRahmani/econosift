"""Banking & Financial Stability service — Phase 28.

Bank NPL ratios, capital adequacy, bank Z-scores, domestic credit growth,
and BIS credit-to-GDP gaps. Composite banking crisis early-warning model.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ..cache import async_cached
from . import atlas_service
from ..sources import source_bis

log = logging.getLogger(__name__)

BANKING_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE",
    "CA", "AU", "JP", "KR", "CN", "IN", "BR", "MX", "ZA",
]


def _latest(year_map: dict[int, float]) -> float | None:
    if not year_map:
        return None
    return year_map[max(year_map)]


def _banking_signal(npl: float | None, cap: float | None, zscore: float | None,
                    credit_gap: float | None) -> str:
    flags = 0
    if npl is not None and npl > 10:
        flags += 1
    elif npl is not None and npl > 5:
        flags += 1
    if cap is not None and cap < 6:
        flags += 1
    if zscore is not None and zscore < 10:
        flags += 1
    if credit_gap is not None and credit_gap > 10:
        flags += 1
    if flags >= 3:
        return "red"
    elif flags >= 1:
        return "yellow"
    return "green"


@async_cached("banking_stability")
async def get_banking_stability() -> dict:
    cur_year = datetime.now().year
    start, end = 2014, cur_year - 1

    (wb_npl, wb_cap, wb_zs, wb_dc) = await asyncio.gather(
        atlas_service._wb_timeline("npl_ratio", start, end),
        atlas_service._wb_timeline("bank_capital", start, end),
        atlas_service._wb_timeline("bank_zscore", start, end),
        atlas_service._wb_timeline("domestic_credit", start, end),
    )

    # Fetch BIS credit gaps for all countries
    credit_gaps_raw = await source_bis.get_credit_gaps_bulk(
        tuple(BANKING_COUNTRIES)
    )

    from ..config import iso2_to_iso3, COUNTRY_NAMES

    countries_out = []
    for iso2 in BANKING_COUNTRIES:
        iso3 = iso2_to_iso3(iso2)
        name = COUNTRY_NAMES.get(iso2, iso2)

        npl_map = wb_npl.get(iso3, {})
        cap_map = wb_cap.get(iso3, {})
        zs_map = wb_zs.get(iso3, {})
        dc_map = wb_dc.get(iso3, {})

        npl_val = _latest(npl_map)
        cap_val = _latest(cap_map)
        zs_val = _latest(zs_map)
        dc_val = _latest(dc_map)

        # Latest credit gap from BIS
        cg_pts = credit_gaps_raw.get(iso2, [])
        cg_latest = cg_pts[-1]["value"] if cg_pts else None

        signal = _banking_signal(npl_val, cap_val, zs_val, cg_latest)

        countries_out.append({
            "iso2": iso2, "name": name,
            "signal": signal,
            "kpis": {
                "nplRatio": npl_val,
                "capitalAdequacy": cap_val,
                "bankZscore": zs_val,
                "domesticCreditGrowth": dc_val,
                "creditGap": cg_latest,
            },
        })

    countries_out.sort(key=lambda c: c["kpis"]["nplRatio"] or 0, reverse=True)

    red_count = sum(1 for c in countries_out if c["signal"] == "red")
    yellow_count = sum(1 for c in countries_out if c["signal"] == "yellow")

    return {
        "asOf": str(datetime.now().date()),
        "source": "World Bank / BIS",
        "countries": countries_out,
        "summary": {
            "redCount": red_count,
            "yellowCount": yellow_count,
            "greenCount": len(countries_out) - red_count - yellow_count,
            "totalCountries": len(countries_out),
        },
    }
