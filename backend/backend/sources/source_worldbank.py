"""World Bank source via wbgapi. Broad 200+ country coverage."""
from __future__ import annotations

import asyncio
import pandas as pd

from ..cache import async_cached
from ..config import ISO2_TO_ISO3, COUNTRY_NAMES
from ..models import SeriesResult, make_series

SOURCE_LABEL = "World Bank"

INDICATOR_MAP = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "inflation": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
    "debt_gdp": "GC.DOD.TOTL.GD.ZS",
    "trade_gdp": "NE.TRD.GNFS.ZS",
    "current_account": "BN.CAB.XOKA.GD.ZS",
    "gdp_per_capita": "NY.GDP.PCAP.KD",
    "population": "SP.POP.TOTL",
    # Fiscal sustainability (Phase 25)
    "tax_revenue": "GC.TAX.TOTL.GD.ZS",
    "govt_expenditure": "GC.XPN.TOTL.GD.ZS",
    "govt_revenue": "GC.REV.XGRT.GD.ZS",
    "gross_savings": "NY.GNS.ICTR.ZS",
    "fiscal_balance": "GC.NLD.TOTL.GD.ZS",
    # Trade flows (Phase 26)
    "exports_gdp": "NE.EXP.GNFS.ZS",
    "imports_gdp": "NE.IMP.GNFS.ZS",
    "merchandise_trade": "TG.VAL.TOTL.GD.ZS",
    # Labor market (Phase 28)
    "lfpr": "SL.TLF.CACT.ZS",
    "youth_unemp": "SL.UEM.1524.ZS",
    "emp_pop_ratio": "SL.EMP.TOTL.SP.ZS",
    "vulnerable_emp": "SL.EMP.VULN.ZS",
    "gdp_per_worker": "SL.GDP.PCAP.EM.KD",
    # Energy & Climate (Phase 28)
    "co2_per_capita": "EN.ATM.CO2E.PC",
    "renewable_share": "EG.FEC.RNEW.ZS",
    "energy_imports": "EG.IMP.CONS.ZS",
    "oil_rents": "NY.GDP.PETR.RT.ZS",
    "gas_rents": "NY.GDP.NGAS.RT.ZS",
    "coal_rents": "NY.GDP.COAL.RT.ZS",
    # Currency Crisis (Phase 28)
    "short_term_debt": "DT.DOD.DSTC.ZS",
    # Banking Stability (Phase 28)
    "npl_ratio": "FB.AST.NPER.ZS",
    "bank_capital": "FB.BNK.CAPA.ZS",
    "bank_zscore": "GFDD.SI.01",
    "domestic_credit": "FS.AST.DOMO.GD.ZS",
    # Inequality & Development (Phase 29)
    "gini": "SI.POV.GINI",
    "income_top10": "SI.DST.10TH.10",
    "income_bottom40": "SI.DST.FRST.20",
    "poverty_215": "SI.POV.DDAY",
    "poverty_365": "SI.POV.LMIC",
    "poverty_685": "SI.POV.UMIC",
    # Supply Chain (Phase 29)
    "food_imports": "TM.VAL.FOOD.ZS.UN",
    "fuel_imports": "TM.VAL.FUEL.ZS.UN",
    # Business Dynamism (Phase 30)
    "new_business_density": "IC.BUS.NDNS.ZS",
    "startup_time": "IC.REG.DURS",
}


def _fetch_sync(series_id: str, iso3_list: list[str], start: int, end: int) -> dict:
    import wbgapi as wb
    df = wb.data.DataFrame(
        series_id, economy=iso3_list, time=range(start, end + 1),
        labels=False, skipBlanks=True,
    )
    return _parse(df)


def _parse(df: pd.DataFrame) -> dict[str, list[tuple[int, float]]]:
    """Return {iso3: [(year, value)]}."""
    out: dict[str, list[tuple[int, float]]] = {}
    if df is None or df.empty:
        return out
    # wbgapi: rows = economies, columns = 'YR2000'...
    for economy, row in df.iterrows():
        points: list[tuple[int, float]] = []
        for col, val in row.items():
            year = str(col).replace("YR", "")
            try:
                y = int(year)
                if pd.notna(val):
                    points.append((y, float(val)))
            except (ValueError, TypeError):
                continue
        if points:
            out[str(economy)] = sorted(points)
    return out


@async_cached("wb_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
    series_id = INDICATOR_MAP.get(indicator_key)
    if not series_id:
        return []
    iso3_to_iso2 = {ISO2_TO_ISO3.get(c, c): c for c in countries}
    iso3_list = list(iso3_to_iso2.keys())

    # Try bulk data first
    try:
        from ..services.bulk_data_service import load_worldbank
        bulk = await asyncio.to_thread(load_worldbank, indicator_key, iso3_list, start, end)
        if bulk is not None and not bulk.empty:
            out: dict[str, list[tuple[int, float]]] = {}
            for _, row in bulk.iterrows():
                iso3 = str(row["iso3"])
                try:
                    out.setdefault(iso3, []).append((int(row["year"]), float(row["value"])))
                except (ValueError, TypeError):
                    continue
            parsed = {k: sorted(v) for k, v in out.items()}
        else:
            raise Exception("bulk data not available")
    except Exception:
        try:
            parsed = await asyncio.to_thread(_fetch_sync, series_id, iso3_list, start, end)
        except Exception:
            return []

    results: list[SeriesResult] = []
    for iso3, points in parsed.items():
        iso2 = iso3_to_iso2.get(iso3, iso3)
        results.append(make_series(
            iso2, COUNTRY_NAMES.get(iso2, iso2), points, SOURCE_LABEL))
    return results
