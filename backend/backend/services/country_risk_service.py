"""Country Risk sovereign panel — Phase 16.

6-KPI traffic-light dashboard per country (~200-country WB universe).
Reuses atlas_service WB fetch pattern for 4 existing indicators.
Adds 2 new WB series: fiscal balance + reserves growth (YoY%).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ..cache import async_cached
from . import atlas_service

log = logging.getLogger(__name__)

THRESHOLDS: dict[str, dict] = {
    "debt_gdp":        {"green": "<60",     "yellow": "60-90",    "red": ">90",
                        "bounds": [(None, 60, "green"), (60, 90, "yellow"), (90, None, "red")]},
    "current_account": {"green": ">-2",     "yellow": "-2 to -5", "red": "<-5",
                        "bounds": [(-2, None, "green"), (-5, -2, "yellow"), (None, -5, "red")]},
    "inflation":       {"green": "<4",      "yellow": "4-8",      "red": ">8",
                        "bounds": [(None, 4, "green"), (4, 8, "yellow"), (8, None, "red")]},
    "fiscal_balance":  {"green": ">-3",     "yellow": "-3 to -6", "red": "<-6",
                        "bounds": [(-3, None, "green"), (-6, -3, "yellow"), (None, -6, "red")]},
    "reserves_growth": {"green": ">5",      "yellow": "0-5",      "red": "<0",
                        "bounds": [(5, None, "green"), (0, 5, "yellow"), (None, 0, "red")]},
    "unemployment":    {"green": "<5",      "yellow": "5-8",      "red": ">8",
                        "bounds": [(None, 5, "green"), (5, 8, "yellow"), (8, None, "red")]},
}

_NEW_WB_CODES = {
    "fiscal_balance": "GC.BAL.CASH.GD.ZS",
    "reserves_total": "FI.RES.TOTL.CD",
}


def _signal(indicator: str, value: float | None) -> str | None:
    if value is None:
        return None
    bounds = THRESHOLDS[indicator]["bounds"]
    for lo, hi, label in bounds:
        if lo is None and hi is not None:
            if value < hi:
                return label
        elif lo is not None and hi is None:
            if value >= lo:
                return label
        elif lo is not None and hi is not None:
            if lo <= value < hi:
                return label
    return None


def _fetch_wb_sync(wb_code: str, start: int, end: int) -> dict[str, dict[int, float]]:
    try:
        import wbgapi as wb
        import pandas as pd
        df = wb.data.DataFrame(wb_code, economy="all", time=range(start, end + 1),
                               labels=False, skipBlanks=True)
        out: dict[str, dict[int, float]] = {}
        if df is None or df.empty:
            return out
        for economy, row in df.iterrows():
            year_map: dict[int, float] = {}
            for col, val in row.items():
                yr_str = str(col).replace("YR", "")
                try:
                    y = int(yr_str)
                    if pd.notna(val):
                        year_map[y] = float(val)
                except (ValueError, TypeError):
                    continue
            if year_map:
                out[str(economy)] = year_map
        return out
    except Exception:
        log.exception("_fetch_wb_sync failed for %s", wb_code)
        return {}


def _latest(year_map: dict[int, float], min_year: int = 2018) -> tuple[float | None, int | None]:
    if not year_map:
        return None, None
    candidates = {y: v for y, v in year_map.items() if y >= min_year}
    if not candidates:
        return None, None
    yr = max(candidates)
    return candidates[yr], yr


@async_cached("country_risk")
async def get_country_risk(countries: tuple[str, ...] | None = None) -> dict:
    cur_year = datetime.now().year
    start, end = 2018, cur_year - 1

    wb_debt, wb_ca, wb_inf, wb_unemp, wb_fisc, wb_res = await asyncio.gather(
        atlas_service._wb_timeline("debt_gdp",        start, end),
        atlas_service._wb_timeline("current_account", start, end),
        atlas_service._wb_timeline("inflation",       start, end),
        atlas_service._wb_timeline("unemployment",    start, end),
        asyncio.to_thread(_fetch_wb_sync, _NEW_WB_CODES["fiscal_balance"], start, end),
        asyncio.to_thread(_fetch_wb_sync, _NEW_WB_CODES["reserves_total"], start, end),
    )

    universe = atlas_service._country_universe()
    result = []

    for c in universe:
        iso3 = c["iso3"]
        if countries and iso3 not in countries:
            continue

        d_val, d_yr = _latest(wb_debt.get(iso3, {}))
        ca_val, _   = _latest(wb_ca.get(iso3, {}))
        inf_val, _  = _latest(wb_inf.get(iso3, {}))
        un_val, _   = _latest(wb_unemp.get(iso3, {}))
        fb_val, _   = _latest(wb_fisc.get(iso3, {}))

        rg_val: float | None = None
        res_map = wb_res.get(iso3, {})
        if res_map:
            sorted_years = sorted(res_map.keys())
            if len(sorted_years) >= 2:
                r_latest = res_map[sorted_years[-1]]
                r_prior  = res_map[sorted_years[-2]]
                if r_prior and r_prior != 0:
                    rg_val = round((r_latest - r_prior) / abs(r_prior) * 100, 2)

        indic = {
            "debt_gdp":        round(d_val, 2) if d_val is not None else None,
            "current_account": round(ca_val, 2) if ca_val is not None else None,
            "inflation":       round(inf_val, 2) if inf_val is not None else None,
            "fiscal_balance":  round(fb_val, 2) if fb_val is not None else None,
            "reserves_growth": rg_val,
            "unemployment":    round(un_val, 2) if un_val is not None else None,
        }
        signals = {k: _signal(k, v) for k, v in indic.items()}

        result.append({
            "iso3":       iso3,
            "name":       c["name"],
            "year":       d_yr or (cur_year - 1),
            "indicators": indic,
            "signals":    signals,
        })

    result.sort(key=lambda row: sum(1 for v in row["signals"].values() if v == "red"), reverse=True)

    return {
        "countries":  result,
        "thresholds": {k: {kk: vv for kk, vv in v.items() if kk != "bounds"}
                       for k, v in THRESHOLDS.items()},
    }
