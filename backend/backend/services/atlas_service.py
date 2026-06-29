"""Global Macro Atlas service — Phase 13.

Serves country-level macro indicators for ~200 countries (2000–2024),
backed by World Bank (primary) + IMF WEO (gap-fill).
"""
from __future__ import annotations

import asyncio
import logging

from ..cache import cached, async_cached

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Indicator metadata
# ---------------------------------------------------------------------------

INDICATORS: list[dict] = [
    {"id": "gdp_growth",     "label": "GDP Growth (annual %)",          "unit": "%",  "goodDirection": "high"},
    {"id": "inflation",      "label": "Inflation, CPI (annual %)",      "unit": "%",  "goodDirection": "low"},
    {"id": "unemployment",   "label": "Unemployment Rate",               "unit": "%",  "goodDirection": "low"},
    {"id": "debt_gdp",       "label": "Government Debt (% of GDP)",     "unit": "%",  "goodDirection": "low"},
    {"id": "current_account","label": "Current Account (% of GDP)",     "unit": "%",  "goodDirection": "neutral"},
    {"id": "gdp_per_capita", "label": "GDP per Capita (constant US$)",  "unit": "US$","goodDirection": "high"},
    {"id": "gini",           "label": "Gini Coefficient (0=equal, 100=unequal)", "unit": "", "goodDirection": "low"},
    {"id": "food_imports",   "label": "Food Imports (% of merchandise imports)", "unit": "%", "goodDirection": "high"},
    {"id": "fuel_imports",   "label": "Fuel Imports (% of merchandise imports)", "unit": "%", "goodDirection": "high"},
    {"id": "age_dependency", "label": "Age Dependency Ratio (% of working-age)", "unit": "%", "goodDirection": "low"},
    {"id": "urbanization",   "label": "Urban Population (% of total)", "unit": "%", "goodDirection": "neutral"},
    {"id": "life_expectancy","label": "Life Expectancy at Birth (years)", "unit": "years", "goodDirection": "high"},
    {"id": "supply_chain_vulnerability", "label": "Supply Chain Vulnerability Score", "unit": "%", "goodDirection": "low"},
]

_INDICATOR_IDS = {ind["id"] for ind in INDICATORS}

# World Bank series codes (matching source_worldbank.py INDICATOR_MAP)
_WB_CODES: dict[str, str] = {
    "gdp_growth":      "NY.GDP.MKTP.KD.ZG",
    "inflation":       "FP.CPI.TOTL.ZG",
    "unemployment":    "SL.UEM.TOTL.ZS",
    "debt_gdp":        "GC.DOD.TOTL.GD.ZS",
    "current_account": "BN.CAB.XOKA.GD.ZS",
    "gdp_per_capita":  "NY.GDP.PCAP.KD",
    # Fiscal (Phase 25)
    "tax_revenue":     "GC.TAX.TOTL.GD.ZS",
    "govt_expenditure": "GC.XPN.TOTL.GD.ZS",
    "govt_revenue":    "GC.REV.XGRT.GD.ZS",
    "gross_savings":   "NY.GNS.ICTR.ZS",
    "fiscal_balance":  "GC.NLD.TOTL.GD.ZS",
    # Trade flows (Phase 26)
    "exports_gdp":     "NE.EXP.GNFS.ZS",
    "imports_gdp":     "NE.IMP.GNFS.ZS",
    "merchandise_trade": "TG.VAL.TOTL.GD.ZS",
    # Labor market (Phase 28)
    "lfpr":            "SL.TLF.CACT.ZS",
    "youth_unemp":     "SL.UEM.1524.ZS",
    "emp_pop_ratio":   "SL.EMP.TOTL.SP.ZS",
    "vulnerable_emp":  "SL.EMP.VULN.ZS",
    "gdp_per_worker":  "SL.GDP.PCAP.EM.KD",
    # Energy & Climate (Phase 28)
    "co2_per_capita":  "EN.ATM.CO2E.PC",
    "renewable_share": "EG.FEC.RNEW.ZS",
    "energy_imports":  "EG.IMP.CONS.ZS",
    "oil_rents":       "NY.GDP.PETR.RT.ZS",
    "gas_rents":       "NY.GDP.NGAS.RT.ZS",
    "coal_rents":      "NY.GDP.COAL.RT.ZS",
    # Currency Crisis (Phase 28)
    "short_term_debt": "DT.DOD.DSTC.ZS",
    "reserves_total":  "FI.RES.TOTL.CD",
    # Banking Stability (Phase 28)
    "npl_ratio":       "FB.AST.NPER.ZS",
    "bank_capital":    "FB.BNK.CAPA.ZS",
    "bank_zscore":     "GFDD.SI.01",
    "domestic_credit": "FS.AST.DOMO.GD.ZS",
    # Inequality (Phase 29)
    "gini":            "SI.POV.GINI",
    "income_top10":    "SI.DST.10TH.10",
    "income_bottom40": "SI.DST.FRST.20",
    "poverty_215":     "SI.POV.DDAY",
    "poverty_365":     "SI.POV.LMIC",
    "poverty_685":     "SI.POV.UMIC",
    # Supply Chain (Phase 29)
    "food_imports":    "TM.VAL.FOOD.ZS.UN",
    "fuel_imports":    "TM.VAL.FUEL.ZS.UN",
    # Business Dynamism (Phase 30)
    "new_business_density": "IC.BUS.NDNS.ZS",
    "startup_time": "IC.REG.DURS",
    # Demographics (Phase 30)
    "age_dependency": "SP.POP.DPND",
    "urbanization": "SP.URB.TOTL.IN.ZS",
    "life_expectancy": "SP.DYN.LE00.IN",
}

# IMF WEO indicator codes (matching source_imf.py INDICATOR_MAP)
_IMF_CODES: dict[str, str] = {
    "gdp_growth":      "NGDP_RPCH",
    "inflation":       "PCPIPCH",
    "unemployment":    "LUR",
    "debt_gdp":        "GGXWDG_NGDP",
    "current_account": "BCA_NGDPD",
    "gdp_per_capita":  "NGDPDPC",
}

# ---------------------------------------------------------------------------
# Region constants (ISO3 membership)
# ---------------------------------------------------------------------------

_G7 = {"USA", "CAN", "GBR", "FRA", "DEU", "ITA", "JPN"}

_G20 = _G7 | {
    "ARG", "AUS", "BRA", "CHN", "IND", "IDN",
    "MEX", "RUS", "SAU", "ZAF", "KOR", "TUR",
}

# config.EUROZONE ISO2 → ISO3
_EUROZONE = {
    "AUT", "BEL", "CYP", "EST", "FIN", "FRA", "DEU", "GRC",
    "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "PRT",
    "SVK", "SVN", "ESP", "HRV",
}

# MSCI Emerging Markets
_EM = {
    "BRA", "CHL", "CHN", "COL", "CZE", "EGY", "GRC", "HUN",
    "IND", "IDN", "KOR", "KWT", "MYS", "MEX", "PER", "PHL",
    "POL", "QAT", "SAU", "ZAF", "TWN", "THA", "TUR", "ARE",
}

REGIONS: list[dict] = [
    {"id": "G7",       "label": "G7",               "members": sorted(_G7)},
    {"id": "G20",      "label": "G20",              "members": sorted(_G20)},
    {"id": "Eurozone", "label": "Eurozone",          "members": sorted(_EUROZONE)},
    {"id": "EM",       "label": "Emerging Markets",  "members": sorted(_EM)},
]

_REGION_MAP: dict[str, set[str]] = {
    "G7":       _G7,
    "G20":      _G20,
    "Eurozone": _EUROZONE,
    "EM":       _EM,
}


# ---------------------------------------------------------------------------
# Country universe (cached sync)
# ---------------------------------------------------------------------------

@cached("atlas_country_universe")
def _country_universe() -> list[dict]:
    """Return list of {iso3, name, id, regions} for all non-aggregate WB economies."""
    try:
        import wbgapi as wb
        import pycountry

        countries: list[dict] = []
        for eco in wb.economy.list():
            # skip aggregates (regions, income groups, etc.)
            if eco.get("aggregate"):
                continue
            iso3: str = eco.get("id", "")
            if not iso3:
                continue
            name: str = eco.get("value") or eco.get("name") or iso3

            # ISO 3166-1 numeric id
            numeric_id: str | None = None
            try:
                pc = pycountry.countries.get(alpha_3=iso3)
                if pc:
                    numeric_id = pc.numeric  # zero-padded string "004" etc.
            except Exception:
                pass

            # Regions this country belongs to
            regions: list[str] = [
                region_id
                for region_id, members in _REGION_MAP.items()
                if iso3 in members
            ]

            countries.append({
                "iso3": iso3,
                "name": name,
                "id": numeric_id,
                "regions": regions,
            })

        return countries

    except Exception:
        logger.exception("atlas _country_universe failed")
        return []


# ---------------------------------------------------------------------------
# World Bank full-universe timeline (async cached)
# ---------------------------------------------------------------------------

def _wb_fetch_sync(series_id: str, start: int, end: int) -> dict[str, dict[int, float]]:
    """Call wbgapi for all economies and return {iso3: {year: value}}."""
    import wbgapi as wb
    import pandas as pd

    df = wb.data.DataFrame(
        series_id,
        economy="all",
        time=range(start, end + 1),
        labels=False,
        skipBlanks=True,
    )
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


@async_cached("atlas_wb_timeline")
async def _wb_timeline(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
    series_id = _WB_CODES.get(indicator)
    if not series_id:
        return {}
    try:
        return await asyncio.to_thread(_wb_fetch_sync, series_id, start, end)
    except Exception:
        logger.exception("atlas _wb_timeline failed for %s", indicator)
        return {}


# ---------------------------------------------------------------------------
# IMF WEO gap-fill timeline (async cached)
# ---------------------------------------------------------------------------

def _imf_fetch_sync(weo_code: str, start: int, end: int) -> dict[str, dict[int, float]]:
    """Call imfp for all countries (no country filter) keyed by FULL ISO3 ref_area."""
    import imfp
    import pandas as pd

    df = imfp.imf_dataset(
        "WEO",
        indicator=[weo_code],
        start_year=start,
        end_year=end,
    )
    out: dict[str, dict[int, float]] = {}
    if df is None or not hasattr(df, "empty") or df.empty:
        return out

    cols = {c.lower(): c for c in df.columns}
    country_col = cols.get("ref_area") or cols.get("country") or cols.get("reference_area")
    year_col = cols.get("time_period") or cols.get("year") or cols.get("date")
    value_col = cols.get("obs_value") or cols.get("value")
    if not (country_col and year_col and value_col):
        return out

    for _, row in df.iterrows():
        # Use FULL code — NO [:2] truncation (that's the bug in source_imf.py)
        iso3 = str(row[country_col]).upper()
        try:
            y = int(str(row[year_col])[:4])
            v = float(row[value_col])
        except (ValueError, TypeError):
            continue
        out.setdefault(iso3, {})[y] = v

    return out


@async_cached("atlas_imf_timeline")
async def _imf_timeline(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
    weo_code = _IMF_CODES.get(indicator)
    if not weo_code:
        return {}
    try:
        return await asyncio.to_thread(_imf_fetch_sync, weo_code, start, end)
    except Exception:
        logger.exception("atlas _imf_timeline failed for %s (best-effort, continuing)", indicator)
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@async_cached("atlas_timeline")
async def get_timeline(indicator: str, start: int = 2000, end: int = 2024) -> dict:
    """Return full timeline for all countries for the given indicator."""
    if indicator not in _INDICATOR_IDS:
        raise ValueError(f"Unknown indicator: {indicator!r}")

    meta = next(m for m in INDICATORS if m["id"] == indicator)
    universe = _country_universe()

    # Computed indicators (not direct WB codes)
    if indicator == "supply_chain_vulnerability":
        from .supply_chain_service import get_supply_chain_data
        sc_data = await get_supply_chain_data()
        # Build timeline format from supply chain data
        countries_out: list[dict] = []
        sc_by_iso2 = {c["iso2"]: c for c in sc_data["countries"]}
        for country in universe:
            iso2 = country["id"]
            sc = sc_by_iso2.get(iso2, {})
            values: dict[str, float | None] = {}
            for y in range(start, end + 1):
                # Supply chain data only has latest, use for most recent year
                values[str(y)] = sc.get("compositeScore") if y == end else None
            countries_out.append({
                "iso3": country["iso3"],
                "id": country["id"],
                "name": country["name"],
                "regions": country["regions"],
                "values": values,
            })
        return {
            "indicator": indicator,
            "label": meta["label"],
            "unit": meta["unit"],
            "goodDirection": meta["goodDirection"],
            "start": start,
            "end": end,
            "countries": countries_out,
        }

    wb_data, imf_data = await asyncio.gather(
        _wb_timeline(indicator, start, end),
        _imf_timeline(indicator, start, end),
    )

    all_years = list(range(start, end + 1))
    countries_out: list[dict] = []

    for country in universe:
        iso3 = country["iso3"]
        wb_country = wb_data.get(iso3, {})
        imf_country = imf_data.get(iso3, {})

        values: dict[str, float | None] = {}
        for y in all_years:
            if y in wb_country:
                values[str(y)] = wb_country[y]
            elif y in imf_country:
                values[str(y)] = imf_country[y]
            else:
                values[str(y)] = None

        countries_out.append({
            "iso3":    iso3,
            "id":      country["id"],
            "name":    country["name"],
            "regions": country["regions"],
            "values":  values,
        })

    return {
        "indicator":     indicator,
        "label":         meta["label"],
        "unit":          meta["unit"],
        "goodDirection": meta["goodDirection"],
        "start":         start,
        "end":           end,
        "countries":     countries_out,
    }


async def get_snapshot(indicator: str, year: int) -> dict:
    """Slice get_timeline to a single year and compute stats."""
    meta = next((m for m in INDICATORS if m["id"] == indicator), None)
    if meta is None:
        raise ValueError(f"Unknown indicator: {indicator!r}")

    timeline = await get_timeline(indicator)
    year_key = str(year)

    countries_out: list[dict] = []
    values_for_stats: list[float] = []

    for c in timeline["countries"]:
        v = c["values"].get(year_key)
        countries_out.append({
            "iso3":    c["iso3"],
            "id":      c["id"],
            "name":    c["name"],
            "regions": c["regions"],
            "value":   v,
        })
        if v is not None:
            values_for_stats.append((c["name"], c["iso3"], v))

    # Stats: ignore nulls
    non_null = [(name, iso3, v) for name, iso3, v in values_for_stats]
    avg = round(sum(v for _, _, v in non_null) / len(non_null), 4) if non_null else None

    # top 10 descending, bottom 10 ascending
    sorted_desc = sorted(non_null, key=lambda x: x[2], reverse=True)
    sorted_asc  = sorted(non_null, key=lambda x: x[2])

    top    = [{"iso3": iso3, "name": name, "value": v} for name, iso3, v in sorted_desc[:10]]
    bottom = [{"iso3": iso3, "name": name, "value": v} for name, iso3, v in sorted_asc[:10]]

    return {
        "indicator":       indicator,
        "unit":            meta["unit"],
        "year":            year,
        "countries":       countries_out,
        "stats": {
            "avg":             avg,
            "count_reporting": len(non_null),
            "top":             top,
            "bottom":          bottom,
        },
    }


def get_indicators() -> dict:
    return {"indicators": INDICATORS}


def get_regions() -> dict:
    return {"regions": REGIONS}
