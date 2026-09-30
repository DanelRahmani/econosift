"""Global Macro Atlas service — Phase 13.

Serves country-level macro indicators for ~200 countries (2000–2024),
backed by World Bank (primary) + IMF WEO (gap-fill).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from .. import provenance as pv
from ..cache import cached, async_cached

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Indicator metadata
# ---------------------------------------------------------------------------

INDICATORS: list[dict] = [
    {"id": "gdp_growth",     "label": "GDP Growth (annual %)",          "unit": "%",  "goodDirection": "high"},
    {"id": "inflation",      "label": "Inflation, CPI (annual %)",      "unit": "%",  "goodDirection": "low"},
    {"id": "unemployment",   "label": "Unemployment Rate",               "unit": "%",  "goodDirection": "low"},
    {"id": "debt_gdp",       "label": "General Government Debt (% of GDP)", "unit": "%",  "goodDirection": "low"},
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
    "co2_per_capita":  "EN.GHG.CO2.PC.CE.AR5",
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
    "income_bottom20": "SI.DST.FRST.20",  # lowest 20% share (was mis-keyed bottom40)
    "poverty_215":     "SI.POV.DDAY",
    "poverty_365":     "SI.POV.LMIC",
    "poverty_685":     "SI.POV.UMIC",
    # Supply Chain (Phase 29)
    "food_imports":    "TM.VAL.FOOD.ZS.UN",
    "fuel_imports":    "TM.VAL.FUEL.ZS.UN",
    # Business Dynamism (Phase 30)
    "new_business_density": "IC.BUS.NDNS.ZS",
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
    "fiscal_balance":  "GGXCNL_NGDP",
}

# How World Bank and IMF WEO series combine per indicator (default: World
# Bank first, IMF fills gaps). The two do not always measure the same thing:
#   gdp_per_capita — WB is constant US$, WEO NGDPDPC is *current* US$: never mix.
#   debt_gdp — WB GC.DOD.TOTL.GD.ZS is *central* government debt and sparse;
#     WEO GGXWDG_NGDP is general government gross debt, the standard
#     cross-country measure, so it leads and WB only fills gaps.
_MERGE_POLICY: dict[str, str] = {
    "gdp_per_capita": "wb_only",
    "debt_gdp": "imf_first",
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

def _numeric_id(iso3: str) -> str | None:
    """ISO 3166-1 numeric code for an alpha-3 code (e.g. "USA" -> "840").

    The choropleth in the frontend matches world-110m TopoJSON geographies by
    their numeric id, so every country entry must carry one (or ``None`` when
    no ISO numeric exists, e.g. Kosovo).
    """
    try:
        import pycountry

        pc = pycountry.countries.get(alpha_3=iso3)
        return pc.numeric if pc else None
    except Exception:
        return None


def _country_universe() -> list[dict]:
    """Return list of {iso3, name, id, regions} for all non-aggregate WB economies.

    ``id`` is the ISO 3166-1 numeric code used to match the frontend choropleth
    geographies.  Primary source is a pre-generated static JSON file shipped
    with the repo (regenerated periodically).  Falls back to a live wbgapi call
    only if the file is missing or corrupt — the WB economy list changes rarely.
    """
    import json as _json
    import os as _os

    # Tier 1 — static JSON (always available, zero-latency)
    static_path = _os.path.join(_os.path.dirname(__file__), "..", "..", "data", "country_universe.json")
    try:
        if _os.path.exists(static_path):
            with open(static_path, "r", encoding="utf-8") as fh:
                data = _json.load(fh)
            if isinstance(data, list) and len(data) > 100:
                # The static file only stores {iso3, name, regions}; derive the
                # numeric id here so it survives regenerations of the JSON.
                for c in data:
                    if "id" not in c:
                        c["id"] = _numeric_id(c.get("iso3", ""))
                return data
            logger.warning("country_universe.json is too short (%s entries), falling back to API", len(data) if isinstance(data, list) else type(data))
    except Exception:
        logger.exception("Failed to load country_universe.json, falling back to API")

    # Tier 2 — live wbgapi (fallback)
    try:
        import wbgapi as wb

        countries: list[dict] = []
        for eco in wb.economy.list():
            if eco.get("aggregate"):
                continue
            iso3: str = eco.get("id", "")
            if not iso3:
                continue
            name: str = eco.get("value") or eco.get("name") or iso3
            regions: list[str] = [
                region_id
                for region_id, members in _REGION_MAP.items()
                if iso3 in members
            ]
            countries.append({"iso3": iso3, "name": name, "id": _numeric_id(iso3), "regions": regions})

        return countries

    except Exception:
        logger.exception("atlas _country_universe failed (both static file and live API)")
        return []


# ---------------------------------------------------------------------------
# World Bank full-universe timeline (async cached)
# ---------------------------------------------------------------------------

def _wb_fetch_sync(series_id: str, start: int, end: int) -> dict[str, dict[int, float]]:
    """Call wbgapi for all economies and return {iso3: {year: value}}."""
    import wbgapi as wb
    import pandas as pd
    from ..sources.source_worldbank import WB_DATABASE

    df = wb.data.DataFrame(
        series_id,
        economy="all",
        time=range(start, end + 1),
        labels=False,
        skipBlanks=True,
        db=WB_DATABASE.get(series_id),
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


def _wb_bulk_sync(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
    """Read the locally-downloaded World Bank parquet -> {iso3: {year: value}}.

    Returns ``{}`` when the bulk file for this indicator isn't present (only the
    core indicators in ``bulk_data_service.WB_INDICATORS`` are downloaded), so
    the caller falls back to a live wbgapi call.
    """
    from .bulk_data_service import load_worldbank

    iso3_list = [c["iso3"] for c in _country_universe()]
    df = load_worldbank(indicator, iso3_list, start, end)
    out: dict[str, dict[int, float]] = {}
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        try:
            iso3 = str(row["iso3"])
            out.setdefault(iso3, {})[int(row["year"])] = float(row["value"])
        except (ValueError, TypeError, KeyError):
            continue
    return out


def stamp_periods(countries: list[dict]) -> str | None:
    """Date a country-comparison payload by its data, not by today.

    Sets, on each country row, ``periods`` (KPI -> date of the latest point in
    that KPI's ``history`` series) and ``latestYear`` (the row's newest year),
    and returns the newest year overall for the payload's ``asOf``. Annual
    World Bank series lag by one to five years, and by different amounts per
    indicator, so a single "today" stamp presented years-old data as current.
    """
    newest: int | None = None
    for c in countries:
        periods = {k: pts[-1]["date"] for k, pts in (c.get("history") or {}).items() if pts}
        years = [int(str(p)[:4]) for p in periods.values()]
        c["periods"] = periods
        c["latestYear"] = max(years) if years else None
        if years:
            newest = max(newest or 0, max(years))
    return str(newest) if newest else None


def _int_year_keys(data: dict) -> dict[str, dict[int, float]]:
    """Restore int year keys after a round-trip through the SQLite cache tier.

    JSON object keys are always strings, so a cached ``{iso3: {2020: v}}``
    comes back as ``{iso3: {"2020": v}}`` after a restart — and every
    ``year in series`` lookup with an int year then silently misses.
    """
    return {c: {int(y): v for y, v in years.items()} for c, years in (data or {}).items()}


async def _wb_timeline(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
    return _int_year_keys(await _wb_timeline_cached(indicator, start, end))


async def _imf_timeline(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
    return _int_year_keys(await _imf_timeline_cached(indicator, start, end))


@async_cached("atlas_wb_timeline")
async def _wb_timeline_cached(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
    series_id = _WB_CODES.get(indicator)
    if not series_id:
        return {}
    # Bulk-first (fast + offline-resilient), then live wbgapi fallback — mirrors
    # the pattern in sources/source_worldbank.fetch().
    try:
        bulk = await asyncio.to_thread(_wb_bulk_sync, indicator, start, end)
        if bulk:
            return bulk
    except Exception:
        logger.exception("atlas _wb_timeline bulk read failed for %s", indicator)
    try:
        return await asyncio.to_thread(_wb_fetch_sync, series_id, start, end)
    except Exception:
        logger.exception("atlas _wb_timeline live fetch failed for %s", indicator)
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
async def _imf_timeline_cached(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
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

def _timeline_all_null(result) -> bool:
    """Empty if no country carries a single non-null value (don't cache it)."""
    if not isinstance(result, dict):
        return True
    countries = result.get("countries") or []
    if not countries:
        return True
    for c in countries:
        for v in (c.get("values") or {}).values():
            if v is not None:
                return False
    return True


def _newest_year(by_country: dict) -> int | None:
    """Newest year present in a ``{iso3: {year: value}}`` map."""
    years = [y for yrs in by_country.values() for y in yrs]
    return max(years) if years else None


def _timeline_provenance(indicator: str, meta: dict, policy: str, wb_data: dict, imf_data: dict,
                         countries: list[dict]) -> dict:
    """Source map for an Atlas timeline (see provenance.py).

    The value of each country/year is the World Bank figure, with IMF WEO filling
    years the World Bank lacks (``imfYears``); ``debt_gdp`` leads with IMF instead.
    """
    wb_yr, imf_yr = _newest_year(wb_data), _newest_year(imf_data)
    refs: list[dict] = []
    wb_code = _WB_CODES.get(indicator)
    if wb_code:
        note = None
        if indicator == "debt_gdp":
            note = "This World Bank series is central-government debt; IMF general-government debt is used first."
        refs.append(pv.ref("worldbank", wb_code, meta["label"], units=meta["unit"], frequency="annual",
                           observed=str(wb_yr) if wb_yr else None, note=note))
    imf_code = _IMF_CODES.get(indicator)
    if imf_code and policy != "wb_only" and any(c.get("imfYears") for c in countries):
        imf_ref = pv.ref(
            "imf", imf_code, f"{meta['label']} (IMF WEO)", units=meta["unit"], frequency="annual",
            observed=str(imf_yr) if imf_yr else None,
            note="Supplies the years listed in each country's imfYears; WEO values for the current year "
                 "onward (projections) are excluded.")
        refs = [imf_ref] + refs if policy == "imf_first" else refs + [imf_ref]
    return {"*": refs[0] if len(refs) == 1 else refs}


@async_cached("atlas_timeline", skip_if=_timeline_all_null)
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
        return pv.attach({
            "indicator": indicator,
            "label": meta["label"],
            "unit": meta["unit"],
            "goodDirection": meta["goodDirection"],
            "start": start,
            "end": end,
            "countries": countries_out,
        }, {"*": pv.derived(
            "Supply-chain vulnerability composite (food + fuel import dependency) from the supply-chain "
            "service, placed on the end year only; earlier years are empty.",
            [pv.ref("worldbank", _WB_CODES["food_imports"], "Food imports (% of merchandise imports)",
                    units="%", frequency="annual"),
             pv.ref("worldbank", _WB_CODES["fuel_imports"], "Fuel imports (% of merchandise imports)",
                    units="%", frequency="annual")],
            title=meta["label"])})

    wb_data, imf_data = await asyncio.gather(
        _wb_timeline(indicator, start, end),
        _imf_timeline(indicator, start, end),
    )
    policy = _MERGE_POLICY.get(indicator, "wb_first")
    if policy == "wb_only":
        imf_data = {}
    # WEO values for the current year onward are projections, not data.
    this_year = date.today().year
    imf_data = {c: {y: v for y, v in yrs.items() if y < this_year} for c, yrs in imf_data.items()}

    all_years = list(range(start, end + 1))
    countries_out: list[dict] = []

    for country in universe:
        iso3 = country["iso3"]
        wb_country = wb_data.get(iso3, {})
        imf_country = imf_data.get(iso3, {})

        first, second = ((imf_country, wb_country) if policy == "imf_first"
                         else (wb_country, imf_country))
        values: dict[str, float | None] = {}
        imf_years: list[int] = []
        for y in all_years:
            src = first if y in first else (second if y in second else None)
            values[str(y)] = src[y] if src is not None else None
            if src is imf_country and src is not None:
                imf_years.append(y)

        countries_out.append({
            "iso3":    iso3,
            "id":      country["id"],
            "name":    country["name"],
            "regions": country["regions"],
            "values":  values,
            # Years supplied by IMF WEO rather than the World Bank.
            **({"imfYears": imf_years} if imf_years else {}),
        })

    return pv.attach({
        "indicator":     indicator,
        "label":         meta["label"],
        "unit":          meta["unit"],
        "goodDirection": meta["goodDirection"],
        "start":         start,
        "end":           end,
        "countries":     countries_out,
    }, _timeline_provenance(indicator, meta, policy, wb_data, imf_data, countries_out))


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

    # Same sources as the timeline it is sliced from, dated to the requested year.
    src = timeline.get("provenance", {}).get("*")
    prov: dict = {}
    if src:
        was_list = isinstance(src, list)
        refs = [dict(r) if r.get("provider") == "derived" else dict(r, observed=str(year))
                for r in (src if was_list else [src])]
        prov["*"] = refs if was_list else refs[0]
    prov["stats"] = pv.derived(
        "avg = mean of the countries reporting a value; top/bottom = ten highest/lowest values; "
        "count_reporting = countries with a value", ["*"], title="Snapshot statistics", observed=str(year))
    return pv.attach({
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
    }, prov)


def get_indicators() -> dict:
    return {"indicators": INDICATORS}


def get_regions() -> dict:
    return {"regions": REGIONS}
