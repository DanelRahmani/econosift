"""Macro indicators, country data, FX, Fama-French — Phase 8 expansion included."""
from __future__ import annotations

import asyncio
import io
import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd
import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import provenance as pv
from ..cache import cached
from ..config import COUNTRIES, INDICATORS
from ..services import macro_service
from ..services import regime_service
from ..services import yfinance_service as yfs
from ..sources import source_frankfurter, source_datareader, source_imf
from ..sources._annual import yoy_pct

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/macro", tags=["macro"])

# CBOE Treasury yield indices — quoted directly as yield in percent, no API key.
YIELD_TENORS = [("^IRX", "3M", 0.25), ("^FVX", "5Y", 5.0),
                ("^TNX", "10Y", 10.0), ("^TYX", "30Y", 30.0)]

# FRED series read by this router: id -> (title, units, frequency[, note]).
_FRED_META: dict[str, tuple] = {
    "CPIAUCSL": ("Consumer Price Index for All Urban Consumers: All Items", "index 1982-84=100", "monthly"),
    "CPILFESL": ("CPI for All Urban Consumers: All Items Less Food and Energy", "index 1982-84=100", "monthly"),
    "PCEPI": ("Personal Consumption Expenditures: Chain-type Price Index", "index", "monthly"),
    "PCEPILFE": ("PCE Chain-type Price Index Excluding Food and Energy", "index", "monthly"),
    "PPIFIS": ("Producer Price Index by Commodity: Final Demand", "index Nov 2009=100", "monthly"),
    "T5YIE": ("5-Year Breakeven Inflation Rate", "%", "daily"),
    "T5YIFR": ("5-Year, 5-Year Forward Inflation Expectation Rate", "%", "daily"),
    "T10YIE": ("10-Year Breakeven Inflation Rate", "%", "daily"),
    "MICH": ("University of Michigan: Inflation Expectation", "%", "monthly",
             "Median expected price change over the next 12 months (Michigan Surveys of Consumers)."),
    "M2SL": ("M2 money stock", "billions of US$, seasonally adjusted", "monthly"),
    "GDP": ("Gross Domestic Product", "billions of US$, SAAR", "quarterly"),
    "GDPC1": ("Real Gross Domestic Product", "billions of chained US$, SAAR", "quarterly"),
    "GDPPOT": ("Real Potential Gross Domestic Product", "billions of chained US$", "quarterly"),
    "A191RL1Q225SBEA": ("Real GDP, percent change from preceding period", "% (annualised, SAAR)", "quarterly"),
    "UNRATE": ("Unemployment Rate", "%", "monthly"),
    "PAYEMS": ("All Employees, Total Nonfarm", "thousands of persons", "monthly"),
    "ICSA": ("Initial Claims", "claims", "weekly"),
    "CIVPART": ("Labor Force Participation Rate", "%", "monthly"),
    "AHETPI": ("Average Hourly Earnings of Production and Nonsupervisory Employees, Total Private",
               "US$ per hour", "monthly"),
    "JTSJOL": ("Job Openings: Total Nonfarm (JOLTS)", "thousands", "monthly"),
    "JTSQUR": ("Quits Rate: Total Nonfarm (JOLTS)", "%", "monthly"),
    "SAHMREALTIME": ("Real-time Sahm Rule Recession Indicator", "percentage points", "monthly"),
    "INDPRO": ("Industrial Production: Total Index", "index", "monthly"),
    "TCU": ("Capacity Utilization: Total Industry", "%", "monthly"),
    "CSUSHPINSA": ("S&P/Case-Shiller U.S. National Home Price Index", "index Jan 2000=100", "monthly"),
    "HOUST": ("New Privately-Owned Housing Units Started: Total Units", "thousands of units, SAAR", "monthly"),
    "MORTGAGE30US": ("30-Year Fixed Rate Mortgage Average in the United States", "%", "weekly"),
    "EXHOSLUSM495S": ("Existing Home Sales", "units, SAAR", "monthly"),
    "PERMIT": ("New Privately-Owned Housing Units Authorized by Building Permits: Total Units",
               "thousands of units, SAAR", "monthly"),
    "MSPUS": ("Median Sales Price of Houses Sold for the United States", "US$", "quarterly"),
    "USREC": ("NBER based Recession Indicators for the United States", "0/1 indicator", "monthly"),
    "CFNAI": ("Chicago Fed National Activity Index", "index", "monthly"),
    "FEDFUNDS": ("Federal Funds Effective Rate", "%", "monthly"),
    "NFCI": ("Chicago Fed National Financial Conditions Index", "index", "weekly"),
    "STLFSI4": ("St. Louis Fed Financial Stress Index", "index", "weekly"),
    "WALCL": ("Federal Reserve Total Assets (Less Eliminations from Consolidation)", "millions of US$", "weekly"),
    "DRCCLACBS": ("Delinquency Rate on Credit Card Loans, All Commercial Banks", "%", "quarterly"),
    "BUSLOANS": ("Commercial and Industrial Loans, All Commercial Banks", "billions of US$", "monthly"),
    "USEPUINDXD": ("Economic Policy Uncertainty Index for United States", "index", "daily"),
}

_GSCPI_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"


# ---------------------------------------------------------------------------
# Existing routes (unchanged)
# ---------------------------------------------------------------------------

@router.get("/indicators")
async def indicators():
    return {"indicators": INDICATORS}


@router.get("/countries")
async def countries():
    return {"countries": COUNTRIES}


@router.get("/search-countries")
async def search_countries(q: str = Query("")):
    """Search the full World Bank country universe (~200 economies) by name or code.

    Returns ISO2 + name matches so the frontend can add any WB-tracked country
    to the chart selection, not just the 20 predefined ones.
    """
    if not q or len(q.strip()) < 2:
        return {"countries": []}

    from ..services.atlas_service import _country_universe

    try:
        import pycountry
    except ImportError:
        return {"countries": []}

    q_lower = q.strip().lower()
    results: list[dict] = []
    seen: set[str] = set()

    for eco in _country_universe():
        iso3 = eco.get("iso3", "")
        name = eco.get("name", "")
        if not iso3 or not name:
            continue

        name_lower = name.lower()

        # Match by name substring or exact ISO3 code
        if q_lower in name_lower or q_lower == iso3.lower():
            if iso3 in seen:
                continue
            seen.add(iso3)

            # Convert ISO3 → ISO2 where possible
            iso2 = ""
            try:
                pc = pycountry.countries.get(alpha_3=iso3)
                if pc:
                    iso2 = getattr(pc, "alpha_2", "") or ""
            except Exception:
                pass

            results.append({
                "iso2": iso2 or iso3,  # fallback to ISO3 if no ISO2 mapping
                "iso3": iso3,
                "name": name,
            })

    # Sort by relevance (exact match first, then starts-with, then contains)
    results.sort(key=lambda r: (
        0 if r["name"].lower() == q_lower else 1 if r["name"].lower().startswith(q_lower) else 2,
        r["name"],
    ))

    return {"countries": results[:25]}


@router.get("/data")
async def data(
    countries: str = Query(...),
    indicator: str = Query(...),
    start: int = 2000,
    end: int = Query(default_factory=lambda: date.today().year),
):
    iso2_list = [c.strip().upper() for c in countries.split(",") if c.strip()]
    series = await macro_service.get_macro_data(indicator, iso2_list, start, end)
    result = {
        "indicator": indicator,
        "unit": macro_service.get_unit(indicator),
        "series": series,
    }
    if not series:
        return result
    prov = {"*": _waterfall_ref()}
    for s in series:
        prov[f"series.{s['country']}"] = _macro_series_refs(indicator, s)
    return pv.attach(result, prov)


def _fx_provenance(base: str, observed: dict[str, str | None], group: str, latest: str | None) -> dict:
    """Frankfurter (ECB reference) rates: one key per quoted currency, ``<group>.<CCY>``."""
    prov = {"*": pv.ref("frankfurter", None, "ECB euro foreign exchange reference rates via Frankfurter",
                        frequency="daily (ECB working days)", observed=latest)}
    for ccy, day in observed.items():
        prov[f"{group}.{ccy}"] = pv.ref("frankfurter", f"{base}/{ccy}", f"{base}/{ccy} reference rate",
                                        units=f"{ccy} per 1 {base}", frequency="daily", observed=day)
    return prov


@router.get("/fx")
async def fx(base: str = "USD", targets: str = "EUR,GBP,JPY"):
    tgt = tuple(t.strip().upper() for t in targets.split(",") if t.strip())
    result = await source_frankfurter.latest(base.upper(), tgt)
    if result.get("error") or not result.get("rates"):
        return result
    day = result.get("date")
    return pv.attach(result, _fx_provenance(result["base"], {c: day for c in result["rates"]}, "rates", day))


@router.get("/fx/history")
async def fx_history(
    base: str = "USD",
    targets: str = "EUR,GBP,JPY",
    start: str = "2020-01-01",
    end: str = Query(default_factory=lambda: date.today().isoformat()),
):
    tgt = tuple(t.strip().upper() for t in targets.split(",") if t.strip())
    result = await source_frankfurter.history(base.upper(), tgt, start, end)
    if result.get("error") or not any(s["data"] for s in result.get("series", [])):
        return result
    last = {s["currency"]: s["data"][-1]["date"] for s in result["series"] if s["data"]}
    return pv.attach(result, _fx_provenance(result["base"], last, "series", max(last.values())))


@router.get("/snapshot")
async def snapshot(countries: str = Query(...)):
    """Latest headline indicators per country for side-by-side comparison cards."""
    iso2_list = [c.strip().upper() for c in countries.split(",") if c.strip()][:4]
    return await macro_service.get_snapshot(iso2_list, date.today().year)


@router.get("/forecast")
async def forecast(
    countries: str = Query(...),
    indicator: str = Query(...),
    end: int = Query(default_factory=lambda: date.today().year + 5),
):
    """IMF World Economic Outlook projections for overlaying on historical charts."""
    iso2_list = tuple(c.strip().upper() for c in countries.split(",") if c.strip())
    start = date.today().year - 1
    series = await source_imf.fetch(indicator, iso2_list, start, end)
    result = {
        "indicator": indicator,
        "unit": macro_service.get_unit(indicator),
        "source": source_imf.SOURCE_LABEL,
        "series": series or [],
    }
    if not series:
        return result
    weo = source_imf.INDICATOR_MAP.get(indicator)
    prov = {"*": pv.ref("imf", weo, f"IMF World Economic Outlook: {indicator}",
                        units=macro_service.get_unit(indicator) or None, frequency="annual",
                        flags=("estimate",),
                        note="Values for the current year onward are IMF projections.")}
    for s in series:
        estimated = any(p.get("estimate") for p in s["data"])
        prov[f"series.{s['country']}"] = pv.ref(
            "imf", weo, f"IMF World Economic Outlook: {indicator}, {s['countryName']}",
            units=macro_service.get_unit(indicator) or None, frequency="annual",
            flags=("estimate",) if estimated else (),
            note=f"Projections run to {s['data'][-1]['year']}." if estimated and s["data"] else None)
    return pv.attach(result, prov)


@router.get("/yield-curve")
async def yield_curve():
    """US Treasury yield curve with inversion detection (recession signal)."""
    syms = tuple(t[0] for t in YIELD_TENORS)
    frame = await asyncio.to_thread(yfs.get_close_frame, syms, "5d")

    points = []
    by_label: dict[str, float] = {}
    for sym, label, years in YIELD_TENORS:
        yld = None
        if frame is not None and sym in frame.columns:
            s = frame[sym].dropna()
            if len(s):
                yld = round(float(s.iloc[-1]), 3)
        points.append({"tenor": label, "years": years, "yield": yld})
        if yld is not None:
            by_label[label] = yld

    spread_10y_3m = (round(by_label["10Y"] - by_label["3M"], 3)
                     if "10Y" in by_label and "3M" in by_label else None)
    spread_10y_5y = (round(by_label["10Y"] - by_label["5Y"], 3)
                     if "10Y" in by_label and "5Y" in by_label else None)
    inverted = bool((spread_10y_3m is not None and spread_10y_3m < 0))

    result = {
        "points": points,
        "spread10y3m": spread_10y_3m,
        "spread10y5y": spread_10y_5y,
        "inverted": inverted,
    }
    if not by_label:
        return result
    prov = {"*": pv.ref("yahoo", None, "CBOE Treasury yield indices", units="% yield", frequency="daily")}
    names = {"3M": "13-week Treasury bill", "5Y": "5-year Treasury note",
             "10Y": "10-year Treasury note", "30Y": "30-year Treasury bond"}
    for sym, label, _years in YIELD_TENORS:
        if label in by_label:
            prov[f"points.{label}"] = pv.yahoo(sym, f"CBOE {names[label]} yield index, daily close",
                                               units="% yield", frequency="daily",
                                               observed=pv.last_date(frame[sym].dropna()))
    prov["spread10y3m"] = pv.derived("10Y yield − 3M yield, in percentage points",
                                     ["points.10Y", "points.3M"], title="10Y–3M spread")
    prov["spread10y5y"] = pv.derived("10Y yield − 5Y yield, in percentage points",
                                     ["points.10Y", "points.5Y"], title="10Y–5Y spread")
    prov["inverted"] = pv.derived("true when the 10Y − 3M spread is below zero", ["spread10y3m"],
                                  title="Yield-curve inversion")
    return pv.attach(result, prov)


@router.get("/regime-series")
async def regime_series(country: str = "US", start: int = 2000):
    """2×2 Goldilocks regime classifier: quarterly GDP growth vs CPI inflation (historical series)."""
    return await asyncio.to_thread(regime_service.regime_series, country.upper(), start)


@router.get("/fama-french")
async def fama_french():
    factors = await asyncio.to_thread(source_datareader.fama_french)
    result = {"factors": factors}
    if not factors:
        return result
    return pv.attach(result, {"*": pv.ref(
        "kenfrench", "F-F_Research_Data_Factors", "Fama/French 3 factors (Mkt-RF, SMB, HML) and RF",
        units="% per calendar year", frequency="annual", observed=str(max(f["year"] for f in factors)),
        note="Ken French's annual table, or the monthly factors compounded to complete calendar years "
             "when the bulk file is present.")})


# ---------------------------------------------------------------------------
# Phase 8: Macro Expansion routes
# ---------------------------------------------------------------------------

def _yoy(series: list[dict]) -> list[dict]:
    """Year-over-year % change, whatever the series frequency.

    The lag is one year of observations for the series' own frequency
    (12 monthly, 4 quarterly, 52 weekly). A fixed ``pct_change(12)`` applied
    to quarterly GDP produced a 3-year change labelled YoY (audit D-09), and
    any row-count lag misreads a series with a missing observation; the lag
    is matched by date (``yoy_pct``).
    """
    if not series:
        return []
    df = pd.DataFrame(series).set_index("date")
    return [
        {"date": str(d.date()), "value": round(float(v), 4)}
        for d, v in yoy_pct(df["value"]).items()
    ]


def _latest(series: list[dict]) -> float | None:
    return series[-1]["value"] if series else None


def _latest_obs_date(*series_groups) -> str | None:
    """Most recent observation date across the given series.

    ``asOf`` must describe the data, not the request: stamping today's date
    made months-old releases look current. Accepts FRED-style dicts of
    ``{series_id: [{"date", "value"}]}`` and/or plain series lists.
    """
    dates: list[str] = []
    for g in series_groups:
        seqs = g.values() if isinstance(g, dict) else [g]
        for seq in seqs:
            if seq:
                d = seq[-1].get("date")
                if d:
                    dates.append(str(d)[:10])
    return max(dates) if dates else None


def _fred_ref(sid: str, seq: list[dict] | None = None, *, yoy: bool = False,
              units: str | None = None, transform: str | None = None) -> dict:
    """Ref for a FRED series in ``_FRED_META``; ``observed`` is the last date of ``seq``."""
    title, base_units, freq, *note = _FRED_META[sid]
    if yoy:
        units = units or "% y/y"
        transform = transform or "year-over-year % change: (value / value one year earlier − 1) × 100"
    return pv.fred(sid, title, units=units or base_units, frequency=freq,
                   observed=_latest_obs_date(seq or []), transform=transform,
                   note=note[0] if note else None)


def _put(prov: dict, ref, *paths: str) -> None:
    for path in paths:
        prov[path] = ref


def _fred_prov(data: dict, spec: list[tuple]) -> dict:
    """Provenance map from ``(series id, year-over-year?, *response paths)`` entries.

    ``data`` is the ``{series id: [{date, value}]}`` payload the endpoint read.
    """
    prov = {"*": pv.ref("fred", None, "Federal Reserve Economic Data (US series)")}
    for sid, yoy, *paths in spec:
        seq = _yoy(data.get(sid, [])) if yoy else data.get(sid, [])
        _put(prov, _fred_ref(sid, seq, yoy=yoy), *paths)
    return prov


def _waterfall_ref() -> dict:
    """Default ref for data taken from the macro source waterfall (provider varies per point)."""
    r = pv.ref("other", None, "Macro source waterfall",
               note="Each country's series lists the providers that supplied its points.")
    r["providerName"] = "Macro source waterfall"
    return r


def _macro_series_refs(indicator: str, entry: dict, *, actuals_only: bool = False) -> list[dict]:
    """One ref per provider that supplied points of a ``get_macro_data`` series.

    Provider, series id and transform come from the adapter that produced the
    points (each point carries its own ``src`` label).
    """
    from ..sources import source_dbnomics, source_ecb, source_fred, source_worldbank

    iso2 = entry.get("country", "")
    unit = macro_service.get_unit(indicator) or None
    by_src: dict[str, list[dict]] = {}
    for p in entry.get("data", []):
        if actuals_only and p.get("estimate"):
            continue
        label = p.get("src") or entry.get("source_label")
        if label:
            by_src.setdefault(label, []).append(p)

    def method_text(method: str | None) -> str | None:
        return {"mean": "annual mean of the source's observations (complete years only)",
                "yoy": "% change of the annual mean vs the prior year (complete years only)"}.get(method or "")

    refs = []
    for label, pts in by_src.items():
        low = label.lower()
        series = transform = None
        units = unit
        if "frankfurter" in low:
            ccy = source_frankfurter.COUNTRY_CCY.get(iso2)
            series = f"USD/{ccy}" if ccy else None
            units = f"{ccy} per USD" if ccy else unit
            transform = "annual mean of daily reference rates (complete years only)"
        elif "fred" in low:
            series, method = source_fred.INDICATOR_MAP.get(indicator, (None, None))
            transform = method_text(method)
        elif "world bank" in low:
            series = source_worldbank.INDICATOR_MAP.get(indicator)
        elif "imf" in low:
            series = source_imf.INDICATOR_MAP.get(indicator)
        elif "db.nomics" in low:
            series = source_dbnomics._series_path(indicator, iso2)
            transform = method_text(source_dbnomics._METHOD.get(indicator, "mean"))
        elif "ecb" in low:
            if indicator == "inflation" and iso2 in source_ecb.ECB_COUNTRY:
                series = f"ICP.M.{source_ecb.ECB_COUNTRY[iso2]}.N.000000.4.ANR"
            elif indicator == "interest_rate":
                series = source_ecb.POLICY_RATE_KEY
            transform = method_text("mean")
        kw = dict(units=units, frequency="annual", observed=str(pts[-1]["year"]), transform=transform,
                  flags=("estimate",) if any(p.get("estimate") for p in pts) else ())
        if "ecb" in low and "frankfurter" not in low and series:
            kw["url"] = f"https://data.ecb.europa.eu/data/datasets/{series.split('.')[0]}"  # dataset page
        if "frankfurter" in low:
            # label_to_ref would match "ecb" inside "Frankfurter (ECB FX data)"
            ref_ = pv.ref("frankfurter", series, label, **kw)
        else:
            ref_ = pv.label_to_ref(label, series=series, **kw)
        ref_["title"] = f"{next((i['label'] for i in INDICATORS if i['id'] == indicator), indicator)} ({label})"
        refs.append(ref_)
    return refs


@router.get("/rates")
async def rates():
    """Full yield curve, Taylor Rule, ACM decomposition, credit spreads."""
    from ..services import rates_service
    return await rates_service.get_rates_data()


@router.get("/taylor-rule")
async def taylor_rule():
    """US Taylor Rule implied rate vs actual Fed Funds + output gap."""
    import asyncio
    from ..services.rates_service import _compute_taylor_rule, _fetch_many_fred_sync

    loop = asyncio.get_event_loop()
    fred = await loop.run_in_executor(
        None, _fetch_many_fred_sync,
        ["CPIAUCSL", "GDPC1", "GDPPOT", "FEDFUNDS"], "2000-01-01",
    )
    tr = await loop.run_in_executor(None, _compute_taylor_rule, fred)
    implied = tr.get("implied", [])
    actual = tr.get("actual", [])
    output_gap = tr.get("output_gap", [])

    # Merge into a unified series keyed by date
    by_date: dict[str, dict] = {}
    for pt in implied:
        by_date.setdefault(pt["date"], {})["taylorRate"] = pt["value"]
    for pt in actual:
        by_date.setdefault(pt["date"], {})["fedFunds"] = pt["value"]
    for pt in output_gap:
        by_date.setdefault(pt["date"], {})["outputGap"] = pt["value"]

    merged = [{"date": d, **vals} for d, vals in sorted(by_date.items())]
    result = {"data": merged}
    if not merged:
        return result
    cpi, gdp, pot, ff = (_fred_ref(sid, None) for sid in ("CPIAUCSL", "GDPC1", "GDPPOT", "FEDFUNDS"))
    for ref_, sid in ((cpi, "CPIAUCSL"), (gdp, "GDPC1"), (pot, "GDPPOT"), (ff, "FEDFUNDS")):
        if sid in fred:
            ref_["observed"] = pv.last_date(fred[sid])
    prov = {
        "*": pv.derived("Taylor rule from FRED CPI, real GDP, potential GDP and the fed funds rate",
                        [cpi, gdp, pot, ff], title="US Taylor rule"),
        "data.taylorRate": pv.derived(
            "0.5 + π + 0.5 × (π − 2) + 0.5 × output gap, clipped to −5…25; "
            "π = 12-month % change in CPI, output gap = (real GDP − potential GDP) / potential GDP × 100",
            [cpi, gdp, pot], title="Taylor-rule implied policy rate",
            observed=implied[-1]["date"] if implied else None),
        "data.outputGap": pv.derived(
            "(real GDP − potential GDP) / potential GDP × 100, quarterly values held forward monthly",
            [gdp, pot], title="Output gap", observed=output_gap[-1]["date"] if output_gap else None),
    }
    prov["data.fedFunds"] = dict(ff, transform="monthly value (last observation in the month)")
    return pv.attach(result, prov)


@router.get("/inflation")
async def inflation(country: str = Query("US", description="ISO2 country code (FRED data is US-only)")):
    """CPI, Core CPI, PCE, Core PCE, PPI, breakevens, Michigan survey, M2, Quantity Theory."""
    if country.upper() != "US":
        # Fall back to World Bank CPI data for non-US countries
        from ..services import macro_service
        iso2_list = [country.upper()]
        series = await macro_service.get_macro_data("inflation", iso2_list, 2000, date.today().year)
        cpi_data: list[dict] = []
        if series and series[0].get("data"):
            cpi_data = [
                {"date": str(d["year"]), "value": d["value"]}
                for d in series[0]["data"]
                if d.get("value") is not None
            ]
        latest_cpi = cpi_data[-1]["value"] if cpi_data else None
        result = {
            "asOf": cpi_data[-1]["date"] if cpi_data else None,
            "kpis": {"cpiYoY": latest_cpi},
            "history": {"cpiYoY": cpi_data},
            "note": "Detailed breakdowns (PCE, Core CPI, breakevens) are US-only. Showing World Bank CPI inflation.",
        }
        if not cpi_data:
            return result
        prov = {"*": _waterfall_ref()}
        _put(prov, _macro_series_refs("inflation", series[0]), "kpis.cpiYoY", "history.cpiYoY")
        return pv.attach(result, prov)
    from ..services.macro_expansion_service import fetch_fred_series

    series_ids = (
        "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "PPIFIS",
        "T5YIE", "T5YIFR", "T10YIE", "MICH", "M2SL", "GDP",
    )
    data = await fetch_fred_series(series_ids, start="2000-01-01")

    cpi_yoy = _yoy(data.get("CPIAUCSL", []))
    core_cpi_yoy = _yoy(data.get("CPILFESL", []))
    pce_yoy = _yoy(data.get("PCEPI", []))
    core_pce_yoy = _yoy(data.get("PCEPILFE", []))
    ppi_yoy = _yoy(data.get("PPIFIS", []))
    m2_yoy = _yoy(data.get("M2SL", []))
    gdp_yoy = _yoy(data.get("GDP", []))

    result = {
        "asOf": cpi_yoy[-1]["date"] if cpi_yoy else None,
        "kpis": {
            "cpiYoY": _latest(cpi_yoy),
            "coreCpiYoY": _latest(core_cpi_yoy),
            "pceYoY": _latest(pce_yoy),
            "corePceYoY": _latest(core_pce_yoy),
            "breakeven5y": _latest(data.get("T5YIE", [])),
            "michigan5y": _latest(data.get("MICH", [])),
        },
        "history": {
            "cpiYoY": cpi_yoy,
            "coreCpiYoY": core_cpi_yoy,
            "pceYoY": pce_yoy,
            "corePceYoY": core_pce_yoy,
            "ppiYoY": ppi_yoy,
            "breakeven5y": data.get("T5YIE", []),
            "breakeven10y": data.get("T10YIE", []),
            "forward5y5y": data.get("T5YIFR", []),
            "michigan5y": data.get("MICH", []),
            "m2": data.get("M2SL", []),
            "m2Yoy": m2_yoy,
        },
        "quantityTheory": {
            "nominalGdpYoY": gdp_yoy,
            "m2YoY": m2_yoy,
        },
    }
    if not any(data.values()):
        return result
    return pv.attach(result, _fred_prov(data, [
        ("CPIAUCSL", True, "kpis.cpiYoY", "history.cpiYoY"),
        ("CPILFESL", True, "kpis.coreCpiYoY", "history.coreCpiYoY"),
        ("PCEPI", True, "kpis.pceYoY", "history.pceYoY"),
        ("PCEPILFE", True, "kpis.corePceYoY", "history.corePceYoY"),
        ("PPIFIS", True, "history.ppiYoY"),
        ("T5YIE", False, "kpis.breakeven5y", "history.breakeven5y"),
        ("T10YIE", False, "history.breakeven10y"),
        ("T5YIFR", False, "history.forward5y5y"),
        ("MICH", False, "kpis.michigan5y", "history.michigan5y"),
        ("M2SL", False, "history.m2"),
        ("M2SL", True, "history.m2Yoy", "quantityTheory.m2YoY"),
        ("GDP", True, "quantityTheory.nominalGdpYoY"),
    ]))


@router.get("/employment")
async def employment(country: str = Query("US", description="ISO2 country code (FRED data is US-only)")):
    """GDP growth, unemployment, NFP, jobless claims, JOLTS, Sahm Rule, industrial production."""
    if country.upper() != "US":
        # Fall back to World Bank data for non-US countries
        from ..services import macro_service
        iso2_list = [country.upper()]
        gdp_series, unemp_series = await asyncio.gather(
            macro_service.get_macro_data("gdp_growth", iso2_list, 2000, date.today().year),
            macro_service.get_macro_data("unemployment", iso2_list, 2000, date.today().year),
        )
        def _extract(s):
            if s and s[0].get("data"):
                # Actuals only — an IMF projection must not become the KPI.
                return [{"date": str(d["year"]), "value": d["value"]} for d in s[0]["data"]
                        if d.get("value") is not None and not d.get("estimate")]
            return []
        gdp_data = _extract(gdp_series)
        unemp_data = _extract(unemp_series)
        result = {
            "asOf": gdp_data[-1]["date"] if gdp_data else None,
            "kpis": {
                "gdpYoY": gdp_data[-1]["value"] if gdp_data else None,
                "unemployment": unemp_data[-1]["value"] if unemp_data else None,
            },
            "history": {"gdpYoY": gdp_data, "unemployment": unemp_data},
            "note": "NFP, JOLTS, and other high-frequency data are US-only (FRED). Showing World Bank GDP growth & unemployment.",
        }
        prov = {"*": _waterfall_ref()}
        for field, indicator, rows, ser in (("gdpYoY", "gdp_growth", gdp_data, gdp_series),
                                            ("unemployment", "unemployment", unemp_data, unemp_series)):
            if rows:
                _put(prov, _macro_series_refs(indicator, ser[0], actuals_only=True),
                     f"kpis.{field}", f"history.{field}")
        return pv.attach(result, prov) if len(prov) > 1 else result
    from ..services.macro_expansion_service import fetch_fred_series

    series_ids = (
        "A191RL1Q225SBEA",  # Real GDP, q/q % change at a seasonally adjusted annual rate
        "GDPC1",             # Real GDP level (quarterly) → true YoY
        "UNRATE",            # Unemployment rate
        "PAYEMS",            # Nonfarm payrolls (NFP)
        "ICSA",              # Initial jobless claims (weekly)
        "CIVPART",           # Labor force participation rate
        "CCSA",              # Continued claims
        "AHETPI",            # Avg hourly earnings, total private
        "JTSJOL",            # JOLTS job openings
        "JTSQUR",            # JOLTS quit rate
        "SAHMREALTIME",      # Sahm Rule real-time
        "INDPRO",            # Industrial production index
        "TCU",               # Capacity utilization
    )
    data = await fetch_fred_series(series_ids, start="2000-01-01")

    nfp = data.get("PAYEMS", [])
    # NFP is level; compute MoM change
    nfp_mom: list[dict] = []
    if nfp:
        df_nfp = pd.DataFrame(nfp).set_index("date")
        df_nfp.index = pd.to_datetime(df_nfp.index)
        df_nfp = df_nfp.sort_index()
        df_nfp["diff"] = df_nfp["value"].diff()
        nfp_mom = [
            {"date": str(d.date()), "value": round(float(v), 2)}
            for d, v in df_nfp["diff"].dropna().items()
        ]

    result = {
        "asOf": _latest_obs_date(data),
        "kpis": {
            # True YoY from the GDPC1 level; the headline BEA print (q/q SAAR)
            # is kept separately and labelled as such (audit D-10).
            "gdpYoY": _latest(_yoy(data.get("GDPC1", []))),
            "gdpQoQSaar": _latest(data.get("A191RL1Q225SBEA", [])),
            "unemploymentRate": _latest(data.get("UNRATE", [])),
            "nfpLatest": nfp_mom[-1]["value"] if nfp_mom else None,
            "joblessClaims": _latest(data.get("ICSA", [])),
            "laborParticipation": _latest(data.get("CIVPART", [])),
        },
        "history": {
            "gdpYoY": _yoy(data.get("GDPC1", [])),
            "gdpQoQSaar": data.get("A191RL1Q225SBEA", []),
            "unemploymentRate": data.get("UNRATE", []),
            "nfp": nfp_mom,
            "joblessClaims": data.get("ICSA", []),
            "sahmRule": data.get("SAHMREALTIME", []),
            "joltsOpenings": data.get("JTSJOL", []),
            "joltsQuits": data.get("JTSQUR", []),
            "indProd": data.get("INDPRO", []),
            "capUtil": data.get("TCU", []),
            "avgHourlyEarnings": data.get("AHETPI", []),
            "laborParticipation": data.get("CIVPART", []),
        },
    }
    if not any(data.values()):
        return result
    prov = _fred_prov(data, [
        ("GDPC1", True, "kpis.gdpYoY", "history.gdpYoY"),
        ("A191RL1Q225SBEA", False, "kpis.gdpQoQSaar", "history.gdpQoQSaar"),
        ("UNRATE", False, "kpis.unemploymentRate", "history.unemploymentRate"),
        ("ICSA", False, "kpis.joblessClaims", "history.joblessClaims"),
        ("CIVPART", False, "kpis.laborParticipation", "history.laborParticipation"),
        ("SAHMREALTIME", False, "history.sahmRule"),
        ("JTSJOL", False, "history.joltsOpenings"),
        ("JTSQUR", False, "history.joltsQuits"),
        ("INDPRO", False, "history.indProd"),
        ("TCU", False, "history.capUtil"),
        ("AHETPI", False, "history.avgHourlyEarnings"),
    ])
    _put(prov, _fred_ref("PAYEMS", nfp_mom, units="thousands of persons",
                         transform="month-over-month change in the payroll level"),
         "kpis.nfpLatest", "history.nfp")
    return pv.attach(result, prov)


@router.get("/housing")
async def housing(country: str = Query("US", description="ISO2 country code (FRED data is US-only)")):
    """Case-Shiller, housing starts, mortgage rate, existing home sales, recession periods."""
    if country.upper() != "US":
        return {"asOf": None, "kpis": {}, "history": {}, "note": "FRED data is US-only. For cross-country data use /macro/data or /macro/country-risk."}
    from ..services.macro_expansion_service import fetch_fred_series, fetch_recession_dates

    series_ids = (
        "CSUSHPINSA",        # Case-Shiller National HPI
        "HOUST",             # Housing starts
        "MORTGAGE30US",      # 30Y fixed mortgage rate
        "EXHOSLUSM495S",     # Existing home sales
        "PERMIT",            # Building permits
        "MSPUS",             # Median sales price of houses
    )
    data, recessions = await asyncio.gather(
        fetch_fred_series(series_ids, start="2000-01-01"),
        fetch_recession_dates(),
    )

    cs_yoy = _yoy(data.get("CSUSHPINSA", []))

    result = {
        "asOf": _latest_obs_date(data),
        "kpis": {
            "caseShillerYoY": _latest(cs_yoy),
            "housingStarts": _latest(data.get("HOUST", [])),
            "mortgageRate": _latest(data.get("MORTGAGE30US", [])),
            "existingHomeSales": _latest(data.get("EXHOSLUSM495S", [])),
        },
        "history": {
            "caseShillerYoY": cs_yoy,
            "caseShillerIndex": data.get("CSUSHPINSA", []),
            "housingStarts": data.get("HOUST", []),
            "mortgageRate": data.get("MORTGAGE30US", []),
            "existingHomeSales": data.get("EXHOSLUSM495S", []),
            "buildingPermits": data.get("PERMIT", []),
            "medianSalesPrice": data.get("MSPUS", []),
        },
        "recessionPeriods": recessions,
    }
    if not any(data.values()):
        return result
    prov = _fred_prov(data, [
        ("CSUSHPINSA", True, "kpis.caseShillerYoY", "history.caseShillerYoY"),
        ("CSUSHPINSA", False, "history.caseShillerIndex"),
        ("HOUST", False, "kpis.housingStarts", "history.housingStarts"),
        ("MORTGAGE30US", False, "kpis.mortgageRate", "history.mortgageRate"),
        ("EXHOSLUSM495S", False, "kpis.existingHomeSales", "history.existingHomeSales"),
        ("PERMIT", False, "history.buildingPermits"),
        ("MSPUS", False, "history.medianSalesPrice"),
    ])
    if recessions:
        prov["recessionPeriods"] = pv.fred(
            "USREC", _FRED_META["USREC"][0], units="0/1 indicator", frequency="monthly",
            transform="runs of months flagged 1 become {start, end} periods",
            note=("The end of a recession still in progress is its last month flagged 1 in USREC."
                  if recessions[-1].get("ongoing") else None))
    return pv.attach(result, prov)


@router.get("/housing/global")
async def housing_global():
    """BIS residential property prices for major economies (real, 2010=100).

    Returns price indices and YoY changes for ~20 countries for cross-country comparison.
    """
    from ..sources.source_bis import get_property_prices_bulk

    COUNTRIES_BIS = [
        "US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO",
        "CA", "AU", "NZ", "JP", "KR", "CN",
    ]
    raw = await get_property_prices_bulk(tuple(COUNTRIES_BIS), real=True)

    from ..config import COUNTRY_NAMES
    countries_out = []
    for iso2 in COUNTRIES_BIS:
        pts = raw.get(iso2, [])
        if not pts:
            continue
        # Sort by date, get latest value and compute YoY
        pts.sort(key=lambda x: x["date"])
        latest = pts[-1]
        # YoY: latest quarter vs the same quarter one year earlier. (Averaging
        # the running year's available quarters against the full previous
        # year compared a partial period with a complete one — audit D-03.)
        by_period = {str(p["date"]): p["value"] for p in pts}
        prev_val = None
        latest_date = str(latest["date"])
        if "-Q" in latest_date:
            yr, q = latest_date.split("-Q")
            prev_val = by_period.get(f"{int(yr) - 1}-Q{q}")
        yoy = (round((latest["value"] / prev_val - 1) * 100, 2)
               if prev_val and prev_val > 0 else None)
        name = COUNTRY_NAMES.get(iso2, iso2)
        countries_out.append({
            "iso2": iso2,
            "name": name,
            "latestIndex": latest["value"],
            "latestDate": latest["date"],
            "yoyChange": yoy,
            "history": pts[-40:],  # last 10 years of quarterly data
        })

    countries_out.sort(key=lambda c: c["yoyChange"] or float("-inf"), reverse=True)
    result = {
        "asOf": max((str(c["latestDate"]) for c in countries_out if c.get("latestDate")), default=None),
        "source": "BIS (Bank for International Settlements)",
        "note": "Real residential property price indices, 2010=100",
        "countries": countries_out,
    }
    if not countries_out:
        return result
    prov = {"*": pv.ref("bis", "WS_SPP", "BIS residential property prices, real index",
                        units="index 2010=100", frequency="quarterly")}
    for c in countries_out:
        key = f"countries.{c['iso2']}"
        prov[key] = pv.ref("bis", "WS_SPP", f"BIS residential property prices, real index: {c['name']}",
                           units="index 2010=100", frequency="quarterly", observed=str(c["latestDate"]))
        prov[f"{key}.yoyChange"] = pv.derived(
            "latest quarter's index ÷ index of the same quarter one year earlier − 1, in %", [key],
            title=f"House-price change, {c['name']}", observed=str(c["latestDate"]))
    return pv.attach(result, prov)


@router.get("/fiscal")
async def fiscal_sustainability():
    """Fiscal sustainability dashboard: debt/GDP, fiscal balance, tax revenue,
    r-g differential, and gross savings for 18 major economies."""
    from ..services.fiscal_service import get_fiscal_data
    return await get_fiscal_data()


@router.get("/trade")
async def trade_flows():
    """Trade flows dashboard: exports/GDP, imports/GDP, trade balance,
    trade openness, and merchandise trade for 18 major economies."""
    from ..services.trade_service import get_trade_data
    return await get_trade_data()


@router.get("/business")
async def business_dynamism():
    """Business dynamism dashboard: new business density, startup time,
    and historical Doing Business scores for 20 major economies."""
    from ..services.business_service import get_business_data
    return await get_business_data()


@router.get("/labor")
async def labor_market():
    """Labor market deep dive: LFPR, youth unemployment, employment/population
    ratio, vulnerable employment, GDP per worker for 20 major economies."""
    from ..services.labor_service import get_labor_data
    return await get_labor_data()


@router.get("/energy")
async def energy_climate():
    """Energy transition & climate dashboard: CO2/capita, renewable share,
    energy imports, oil/gas/coal rents for 20 major economies."""
    from ..services.energy_service import get_energy_data
    return await get_energy_data()


@router.get("/inequality")
async def inequality():
    """Inequality & development dashboard: Gini coefficient, income shares,
    poverty headcount ratios for 20 major economies."""
    from ..services.inequality_service import get_inequality_data
    return await get_inequality_data()


# Commodity config: (display name, sector, Yahoo front-month future, unit).
# One source per row: price and every change window come from the same daily
# series. (Previously the price came from FRED spot / monthly World Bank
# averages while 1D/1W changes came from futures, gold's FRED series had been
# discontinued since 2022, and 1W/YTD were never computed — audit L-05/D-15.)
_COMMODITY_CONFIG = [
    ("WTI Crude Oil", "Energy", "CL=F", "USD/bbl"),
    ("Brent Crude", "Energy", "BZ=F", "USD/bbl"),
    ("Natural Gas", "Energy", "NG=F", "USD/MMBtu"),
    ("Gold", "Metals", "GC=F", "USD/oz"),
    ("Silver", "Metals", "SI=F", "USD/oz"),
    ("Copper", "Metals", "HG=F", "USD/lb"),
    ("Wheat", "Agriculture", "ZW=F", "USc/bu"),
    ("Corn", "Agriculture", "ZC=F", "USc/bu"),
    ("Soybeans", "Agriculture", "ZS=F", "USc/bu"),
]
_COMMODITY_SOURCE = "Yahoo Finance — continuous front-month futures (roll dates can cause small jumps)"
_ECONOSIFT_BASKET = ["CL=F", "GC=F", "NG=F", "HG=F", "ZW=F"]


def _pct_change_since(s: pd.Series, since: pd.Timestamp) -> float | None:
    """% change from the last close on or before ``since`` to the latest close."""
    base = s.loc[:since]
    if base.empty or not base.iloc[-1]:
        return None
    return round((float(s.iloc[-1]) / float(base.iloc[-1]) - 1) * 100, 2)


def _commodities_provenance(table_rows: list[dict], gold_oil_ratio: list[dict],
                            econosift_index: list[dict]) -> dict:
    """One Yahoo futures ref per row (``table.<ticker>``) plus formulas for its changes and the composites."""
    prov = {"*": pv.ref("yahoo", None, "Continuous front-month futures", frequency="daily",
                        note="Roll dates can cause small jumps.")}
    windows = {"change1d": "previous close", "change1w": "the last close on or before 7 days earlier",
               "change1m": "the last close on or before one calendar month earlier",
               "changeYtd": "the last close on or before 31 December of the prior year"}
    for r in table_rows:
        if not r["asOf"]:
            continue
        key = f"table.{r['ticker']}"
        prov[key] = pv.yahoo(r["ticker"], f"{r['name']} front-month future, daily close", units=r["unit"],
                             frequency="daily", observed=r["asOf"])
        for field, base in windows.items():
            prov[f"{key}.{field}"] = pv.derived(f"latest close ÷ {base} − 1, in %", [key],
                                                title=f"{r['name']} change", observed=r["asOf"])
    for kpi, tick in (("wti", "CL=F"), ("gold", "GC=F"), ("natGas", "NG=F"), ("copper", "HG=F"),
                      ("wheat", "ZW=F")):
        if f"table.{tick}" in prov:
            prov[f"kpis.{kpi}"] = prov[f"table.{tick}"]
    for kpi, tick in (("wtiChange1d", "CL=F"), ("goldChange1d", "GC=F")):
        if f"table.{tick}.change1d" in prov:
            prov[f"kpis.{kpi}"] = prov[f"table.{tick}.change1d"]
    if gold_oil_ratio:
        prov["ratios.goldOilRatio"] = pv.derived(
            "gold future close ÷ WTI future close on the same session (sessions with WTI ≤ 0 dropped)",
            ["table.GC=F", "table.CL=F"], title="Gold/oil ratio", observed=gold_oil_ratio[-1]["date"])
    if econosift_index:
        prov["axiomIndex"] = pv.derived(
            "mean of the closes of " + ", ".join(_ECONOSIFT_BASKET) + ", each rebased to 100 on the first "
            "common session on or after 2020-01-01, on sessions where every leg traded",
            [f"table.{t}" for t in _ECONOSIFT_BASKET], title="EconoSift Commodity Index",
            observed=econosift_index[-1]["date"])
    return prov


def _get_commodities_sync() -> dict:
    """Commodity futures: price and 1D/1W/1M/YTD changes from one daily series."""
    from ..services import yfinance_service as yfs

    tickers = tuple(c[2] for c in _COMMODITY_CONFIG)
    frame = yfs.get_close_frame(tickers, "5y")
    closes: dict[str, pd.Series] = {}
    if frame is not None and not frame.empty:
        for t in tickers:
            if t in frame.columns:
                s = frame[t].dropna()
                s.index = pd.to_datetime(s.index)
                if len(s):
                    closes[t] = s

    table_rows = []
    as_of_dates = []
    for name, sector, tick, unit in _COMMODITY_CONFIG:
        s = closes.get(tick)
        row = {"ticker": tick, "name": name, "sector": sector, "unit": unit,
               "source": _COMMODITY_SOURCE, "price": None, "change1d": None,
               "change1w": None, "change1m": None, "changeYtd": None, "asOf": None}
        if s is not None and len(s) >= 2:
            last = s.index[-1]
            as_of_dates.append(last)
            row.update({
                "price": round(float(s.iloc[-1]), 4),
                "change1d": round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2),
                "change1w": _pct_change_since(s, last - pd.Timedelta(days=7)),
                "change1m": _pct_change_since(s, last - pd.DateOffset(months=1)),
                "changeYtd": _pct_change_since(s, pd.Timestamp(last.year - 1, 12, 31)),
                "asOf": str(last.date()),
            })
        table_rows.append(row)

    def row_val(nm: str, field: str = "price") -> float | None:
        for r in table_rows:
            if r["name"] == nm:
                return r.get(field)
        return None

    kpis = {
        "wti": row_val("WTI Crude Oil"), "gold": row_val("Gold"),
        "natGas": row_val("Natural Gas"), "copper": row_val("Copper"),
        "wheat": row_val("Wheat"),
        "wtiChange1d": row_val("WTI Crude Oil", "change1d"),
        "goldChange1d": row_val("Gold", "change1d"),
    }

    # Gold/Oil ratio (oz of gold in barrels of WTI), same-day closes only.
    gold_oil_ratio: list[dict] = []
    if "GC=F" in closes and "CL=F" in closes:
        both = pd.concat([closes["GC=F"], closes["CL=F"]], axis=1, join="inner").dropna()
        both = both[both.iloc[:, 1] > 0]  # WTI briefly traded negative in Apr 2020
        gold_oil_ratio = [{"date": str(d.date()), "value": round(float(g / o), 4)}
                          for d, (g, o) in both.iterrows()]

    # EconoSift Commodity Index: equal-weighted, each leg rebased to 100 on the
    # first common session, computed only on sessions where every leg traded.
    econosift_index: list[dict] = []
    legs = [closes[t] for t in _ECONOSIFT_BASKET if t in closes]
    if len(legs) == len(_ECONOSIFT_BASKET):
        basket = pd.concat(legs, axis=1, join="inner").dropna()
        basket = basket[basket.index >= pd.Timestamp("2020-01-01")]
        if not basket.empty and (basket.iloc[0] > 0).all():
            idx = (basket / basket.iloc[0]).mean(axis=1) * 100
            econosift_index = [{"date": str(d.date()), "value": round(float(v), 4)}
                               for d, v in idx.items()]

    today = str(max(as_of_dates).date()) if as_of_dates else None
    result = {
        "asOf": today, "kpis": kpis, "table": table_rows,
        "ratios": {"goldOilRatio": gold_oil_ratio},
        "axiomIndex": econosift_index,
        "source": _COMMODITY_SOURCE,
    }
    if not as_of_dates:
        return result
    return pv.attach(result, _commodities_provenance(table_rows, gold_oil_ratio, econosift_index))


@router.get("/commodities")
async def commodities():
    """Commodity futures prices, changes, Gold/Oil ratio, EconoSift Commodity Index."""
    return await asyncio.to_thread(_get_commodities_sync)


# FX pairs for heatmap — FRED DEX* series (daily, H.10). Each series has a
# fixed quote direction: DEXUS** are USD per foreign unit (EUR/USD style) and
# DEX**US are foreign units per USD (USD/JPY style) — both already match the
# market convention of the label, so no series is inverted. (Previously the
# DEX**US series were inverted a second time, showing USD/JPY ≈ 0.0064 with a
# sign-flipped change, and DEXCHUS/DEXSZUS were labelled CHF/SEK when they are
# CNY/CHF — audit D-07.)
_FX_PAIRS_FRED = [
    ("DEXUSEU", "EUR/USD"), ("DEXUSUK", "GBP/USD"), ("DEXJPUS", "USD/JPY"),
    ("DEXSZUS", "USD/CHF"), ("DEXCAUS", "USD/CAD"), ("DEXUSAL", "AUD/USD"),
    ("DEXUSNZ", "NZD/USD"), ("DEXSDUS", "USD/SEK"), ("DEXNOUS", "USD/NOK"),
    ("DEXMXUS", "USD/MXN"), ("DEXBZUS", "USD/BRL"), ("DEXKOUS", "USD/KRW"),
    ("DEXCHUS", "USD/CNY"),
]


def _get_fx_heatmap_sync() -> dict:
    """FX heatmap using FRED daily exchange rates."""
    from ..services.macro_expansion_service import _fetch_fred_series_sync

    fred_ids = [p[0] for p in _FX_PAIRS_FRED]
    start_date = (date.today() - timedelta(days=30)).isoformat()
    fred_data = _fetch_fred_series_sync(fred_ids, start=start_date)

    crosses = []
    for fred_id, pair in _FX_PAIRS_FRED:
        series = fred_data.get(fred_id, [])
        price = change1d = None
        if series and series[-1]["value"] > 0:
            price = round(series[-1]["value"], 6)
            if len(series) >= 2 and series[-2]["value"] > 0:
                change1d = round((series[-1]["value"] / series[-2]["value"] - 1) * 100, 4)
        crosses.append({"pair": pair, "ticker": fred_id, "price": price, "change1d": change1d,
                        "asOf": series[-1]["date"] if series else None})

    result = {"crosses": crosses, "asOf": _latest_obs_date(fred_data)}
    if not any(c["asOf"] for c in crosses):
        return result
    prov = {"*": pv.ref("fred", None, "Federal Reserve H.10 daily exchange rates", frequency="daily")}
    for fred_id, pair in _FX_PAIRS_FRED:
        row = next(c for c in crosses if c["ticker"] == fred_id)
        if not row["asOf"]:
            continue
        base, quote = pair.split("/")
        key = f"crosses.{fred_id}"
        prov[key] = pv.fred(fred_id, f"{pair} noon buying rate in New York (H.10)", units=f"{quote} per {base}",
                            frequency="daily", observed=row["asOf"])
        prov[f"{key}.change1d"] = pv.derived("latest observation ÷ previous observation − 1, in %", [key],
                                             title=f"{pair} 1-day change", observed=row["asOf"])
    return pv.attach(result, prov)


@router.get("/fx/heatmap")
async def fx_heatmap():
    """1D % change for major currency crosses (FX heatmap)."""
    return await asyncio.to_thread(_get_fx_heatmap_sync)


# G10 PPP pairs: (pair label, FRED spot series, foreign currency, WB economy).
# PPP is the World Bank ICP "PPP conversion factor, GDP" (PA.NUS.PPP, local
# currency per international $ = per US$), an absolute level. The previous
# relative-PPP chain from Jan-2005 CPI assumed 2005 rates were at fair value,
# used OECD MEI CPI series that FRED discontinued (Japan's froze in 2021; UK
# and Australia no longer exist) and mixed a 60-day-old spot into the base
# (audit D-14/D-17). The euro area has no WB aggregate, so Germany's ICP
# factor stands in for EUR and is labelled as such.
_PPP_PAIRS = [
    ("EUR/USD", "DEXUSEU", "EUR", "DEU"),
    ("GBP/USD", "DEXUSUK", "GBP", "GBR"),
    ("USD/JPY", "DEXJPUS", "JPY", "JPN"),
    ("USD/CHF", "DEXSZUS", "CHF", "CHE"),
    ("AUD/USD", "DEXUSAL", "AUD", "AUS"),
    ("USD/CAD", "DEXCAUS", "CAD", "CAN"),
    ("USD/SEK", "DEXSDUS", "SEK", "SWE"),
    ("USD/NOK", "DEXNOUS", "NOK", "NOR"),
]


@cached("wb_ppp_factor")
def _wb_ppp_factors() -> dict[str, dict]:
    """Latest PA.NUS.PPP per economy: {iso3: {"value", "year"}}."""
    import wbgapi as wb
    out: dict[str, dict] = {}
    this_year = date.today().year
    df = wb.data.DataFrame("PA.NUS.PPP", [p[3] for p in _PPP_PAIRS],
                           time=range(this_year - 6, this_year + 1))
    for iso3, row in df.iterrows():
        row = row.dropna()
        if len(row):
            out[str(iso3)] = {"value": float(row.iloc[-1]), "year": int(str(row.index[-1])[2:])}
    return out


def _get_fx_ppp_sync() -> dict:
    """Spot vs World Bank ICP PPP for G10 currencies against the USD.

    ``overvaluation`` is always that of the *non-USD* currency (``currency``):
    +20 means it buys 20% more at the market rate than PPP says it should.
    """
    from ..services.macro_expansion_service import _fetch_fred_series_sync

    try:
        factors = _wb_ppp_factors()
    except Exception as exc:
        log.warning("PPP: World Bank PA.NUS.PPP fetch failed: %s", exc)
        return {"pairs": [], "error": str(exc)}
    spots = _fetch_fred_series_sync([p[1] for p in _PPP_PAIRS],
                                    start=(date.today() - timedelta(days=30)).isoformat())

    pairs_out = []
    for pair_label, dex_id, ccy, iso3 in _PPP_PAIRS:
        series = spots.get(dex_id, [])
        spot = series[-1]["value"] if series and series[-1]["value"] > 0 else None
        f = factors.get(iso3)
        usd_base = pair_label.startswith("USD/")
        row = {"pair": pair_label, "currency": ccy, "spot": round(spot, 6) if spot else None,
               "ppp": None, "overvaluation": None,
               "spotAsOf": series[-1]["date"] if series else None,
               "pppYear": f["year"] if f else None,
               "pppBasis": "Germany ICP (euro-area proxy)" if iso3 == "DEU" else f"{iso3} ICP"}
        if spot and f and f["value"] > 0:
            ppp_fx_per_usd = f["value"]
            spot_fx_per_usd = spot if usd_base else 1.0 / spot
            row["ppp"] = round(ppp_fx_per_usd if usd_base else 1.0 / ppp_fx_per_usd, 6)
            row["overvaluation"] = round((ppp_fx_per_usd / spot_fx_per_usd - 1) * 100, 2)
        pairs_out.append(row)

    spot_dates = [p["spotAsOf"] for p in pairs_out if p["spotAsOf"]]
    result = {
        "pairs": pairs_out,
        "asOf": max(spot_dates) if spot_dates else None,
        "source": "Spot: FRED H.10 (DEX*) · PPP: World Bank ICP PA.NUS.PPP",
    }
    prov = {"*": pv.derived("spot FX (FRED H.10) compared with the World Bank ICP PPP conversion factor",
                            title="FX vs purchasing power parity")}
    for (pair_label, dex_id, ccy, iso3), row in zip(_PPP_PAIRS, pairs_out):
        key = f"pairs.{ccy}"
        base, quote = pair_label.split("/")
        if row["spotAsOf"]:
            prov[f"{key}.spot"] = pv.fred(dex_id, f"{pair_label} noon buying rate in New York (H.10)",
                                          units=f"{quote} per {base}", frequency="daily",
                                          observed=row["spotAsOf"])
        if row["pppYear"]:
            wb_ref = pv.ref("worldbank", "PA.NUS.PPP", f"PPP conversion factor, GDP ({iso3})",
                            units=f"{ccy} per international $", frequency="annual",
                            observed=str(row["pppYear"]), flags=("proxy",) if iso3 == "DEU" else (),
                            note="Germany's factor stands in for the euro area." if iso3 == "DEU" else None)
            prov[f"{key}.ppp"] = pv.derived(
                "World Bank PPP factor (local currency per international $), inverted for pairs quoted "
                "as USD per foreign unit", [wb_ref], title=f"{pair_label} PPP rate", observed=str(row["pppYear"]))
        if row["overvaluation"] is not None:
            prov[f"{key}.overvaluation"] = pv.derived(
                "(PPP rate ÷ spot rate − 1) × 100, both as local currency per USD; positive = the non-USD "
                "currency is stronger than PPP implies", [f"{key}.spot", f"{key}.ppp"],
                title=f"{ccy} over/undervaluation vs PPP", observed=row["spotAsOf"])
    return pv.attach(result, prov) if pairs_out else result


@router.get("/fx/ppp")
async def fx_ppp():
    """Purchasing Power Parity implied exchange rates vs spot for G10 pairs."""
    return await asyncio.to_thread(_get_fx_ppp_sync)


def _download_gscpi_sync() -> list[dict]:
    """Download NY Fed Global Supply Chain Pressure Index."""
    url = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        df = pd.read_excel(io.BytesIO(resp.content))
        # Find date column and GSCPI column
        date_col = df.columns[0]
        gscpi_col = next(
            (c for c in df.columns if "gscpi" in str(c).lower() or "index" in str(c).lower()),
            df.columns[1] if len(df.columns) > 1 else None,
        )
        if gscpi_col is None:
            return []
        df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=["_date"]).sort_values("_date")
        return [
            {"date": str(r._date.date()), "value": round(float(getattr(r, str(gscpi_col))), 4)}
            for r in df.itertuples()
            if not pd.isna(getattr(r, str(gscpi_col), float("nan")))
        ]
    except Exception as exc:
        log.warning("GSCPI download failed: %s", exc)
        return []


@router.get("/leading")
async def leading(base_year: int = Query(2020, description="Base year for IS-LM-PC normalization"),
                   country: str = Query("US", description="ISO2 country code (FRED data is US-only)")):
    """Leading Economic Indicators: LEI, CFNAI, ISM PMI, GSCPI, IS-LM-PC framework data."""
    if country.upper() != "US":
        return {"asOf": None, "kpis": {}, "history": {}, "islmpc": {}, "baseYear": base_year,
                "note": "FRED data is US-only. For cross-country data use /macro/data or /macro/country-risk."}
    from ..services.macro_expansion_service import fetch_fred_series

    # The Conference Board LEI (FRED USSLIND, frozen since Feb 2020) and ISM
    # Manufacturing PMI (NAPM, removed from FRED) have no free live source —
    # both are licensed. They are reported as unavailable with the reason
    # rather than as years-old values that look current (audit D-16).
    series_ids = (
        "CFNAI",              # Chicago Fed National Activity Index
        "GDPC1",              # Real GDP (quarterly)
        "FEDFUNDS",           # Federal Funds Rate
        "M2SL",               # M2 Money Supply
        "UNRATE",             # Unemployment rate
        "CPIAUCSL",           # CPI level
    )
    data, gscpi = await asyncio.gather(
        fetch_fred_series(series_ids, start="2000-01-01"),
        asyncio.to_thread(_download_gscpi_sync),
    )

    # --- IS-LM-PC: normalize series to given base year = 100 ---
    def _normalize(series: list[dict], base_year: int) -> list[dict]:
        """Normalize so the average value in base_year = 100."""
        if not series:
            return []
        base_vals = [p["value"] for p in series if p["date"][:4] == str(base_year)]
        if not base_vals:
            # Fall back to all values
            base_vals = [p["value"] for p in series]
        if not base_vals:
            return series
        base = sum(base_vals) / len(base_vals)
        if base == 0:
            return series
        return [{"date": p["date"], "value": round(p["value"] / base * 100, 2)} for p in series]

    islmpc = {
        "gdp": _normalize(data.get("GDPC1", []), base_year),
        "fedFunds": _normalize(data.get("FEDFUNDS", []), base_year),
        "m2": _normalize(data.get("M2SL", []), base_year),
        "unrate": _normalize(data.get("UNRATE", []), base_year),
        "cpi": _normalize(data.get("CPIAUCSL", []), base_year),
        "baseYear": base_year,
    }

    result = {
        "asOf": _latest_obs_date(data),
        "kpis": {
            "lei": None,
            "cfnai": _latest(data.get("CFNAI", [])),
            "ismPmi": None,
            "gscpi": gscpi[-1]["value"] if gscpi else None,
        },
        "history": {
            "lei": [],
            "cfnai": data.get("CFNAI", []),
            "ismPmi": [],
            "gscpi": gscpi,
        },
        "unavailable": {
            "lei": "Conference Board LEI is licensed; its FRED copy (USSLIND) stopped in Feb 2020.",
            "ismPmi": "ISM Manufacturing PMI is licensed and no longer published on FRED.",
        },
        "islmpc": islmpc,
        "baseYear": base_year,
    }
    if not any(data.values()) and not gscpi:
        return result
    prov = _fred_prov(data, [("CFNAI", False, "kpis.cfnai", "history.cfnai")])
    for field, sid in (("gdp", "GDPC1"), ("fedFunds", "FEDFUNDS"), ("m2", "M2SL"), ("unrate", "UNRATE"),
                       ("cpi", "CPIAUCSL")):
        prov[f"islmpc.{field}"] = pv.derived(
            f"value ÷ mean of the {base_year} observations × 100 (mean of the whole series if {base_year} "
            "has none)", [_fred_ref(sid, data.get(sid, []))], title=f"{_FRED_META[sid][0]}, rebased",
            observed=_latest_obs_date(data.get(sid, [])))
    if gscpi:
        _put(prov, pv.ref("nyfed", "gscpi_data.xlsx", "Global Supply Chain Pressure Index",
                          units="standard deviations from the average", frequency="monthly",
                          observed=gscpi[-1]["date"], url=_GSCPI_URL),
             "kpis.gscpi", "history.gscpi")
    return pv.attach(result, prov)


@router.get("/financial-conditions")
async def financial_conditions(country: str = Query("US", description="ISO2 country code (FRED data is US-only)")):
    """NFCI, STLFSI, Fed balance sheet, credit card delinquency, C&I loans, EPU."""
    if country.upper() != "US":
        return {"asOf": None, "kpis": {}, "history": {}, "note": "FRED data is US-only. For cross-country data use /macro/data or /macro/country-risk."}
    from ..services.macro_expansion_service import fetch_fred_series

    series_ids = (
        "NFCI",           # Chicago Fed National Financial Conditions Index
        "STLFSI4",        # St. Louis Fed Financial Stress Index
        "WALCL",          # US Federal Reserve balance sheet (total assets, millions)
        "DRCCLACBS",      # Credit card delinquency rate
        "BUSLOANS",       # Commercial & Industrial Loans (billions)
        "USEPUINDXD",     # Economic Policy Uncertainty Index (daily → monthly available)
    )
    data = await fetch_fred_series(series_ids, start="2000-01-01")

    # WALCL is in millions USD → convert to trillions
    fed_bs_raw = data.get("WALCL", [])
    fed_bs = [
        {"date": p["date"], "value": round(p["value"] / 1_000_000, 4)}
        for p in fed_bs_raw if p.get("value") is not None
    ]
    # BUSLOANS is in billions USD → convert to trillions
    ci_raw = data.get("BUSLOANS", [])
    ci_loans = [
        {"date": p["date"], "value": round(p["value"] / 1_000, 4)}
        for p in ci_raw if p.get("value") is not None
    ]

    result = {
        "asOf": _latest_obs_date(data),
        "kpis": {
            "nfci": _latest(data.get("NFCI", [])),
            "stlfsi": _latest(data.get("STLFSI4", [])),
            "fedBalanceSheet": _latest(fed_bs),
            "ciLoans": _latest(ci_loans),
        },
        "history": {
            "nfci": data.get("NFCI", []),
            "stlfsi": data.get("STLFSI4", []),
            "fedBalanceSheet": fed_bs,
            "creditCardDelinquency": data.get("DRCCLACBS", []),
            "ciLoans": ci_loans,
            "economicPolicyUncertainty": data.get("USEPUINDXD", []),
        },
    }
    if not any(data.values()):
        return result
    prov = _fred_prov(data, [
        ("NFCI", False, "kpis.nfci", "history.nfci"),
        ("STLFSI4", False, "kpis.stlfsi", "history.stlfsi"),
        ("DRCCLACBS", False, "history.creditCardDelinquency"),
        ("USEPUINDXD", False, "history.economicPolicyUncertainty"),
    ])
    _put(prov, _fred_ref("WALCL", fed_bs, units="trillions of US$", transform="millions of US$ ÷ 1,000,000"),
         "kpis.fedBalanceSheet", "history.fedBalanceSheet")
    _put(prov, _fred_ref("BUSLOANS", ci_loans, units="trillions of US$", transform="billions of US$ ÷ 1,000"),
         "kpis.ciLoans", "history.ciLoans")
    return pv.attach(result, prov)


@router.get("/credit-gaps")
async def credit_gaps():
    """BIS credit-to-GDP gaps for major economies.

    Returns latest gap (% of GDP) and history for each country.
    Gaps >10pp signal elevated systemic risk per BIS methodology.
    """
    from ..sources.source_bis import get_credit_gaps_bulk

    COUNTRIES = ["US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE",
                 "CA", "AU", "JP", "KR", "CN"]
    raw = await get_credit_gaps_bulk(tuple(COUNTRIES))

    from ..config import COUNTRY_NAMES
    countries_out = []
    for iso2 in COUNTRIES:
        pts = raw.get(iso2, [])
        if not pts:
            continue
        pts.sort(key=lambda x: x["date"])
        latest = pts[-1] if pts else None
        name = COUNTRY_NAMES.get(iso2, iso2)
        # BIS methodology: gap >10 = elevated risk, gap >2 = warning
        gap_val = latest["value"] if latest else None
        if gap_val is not None:
            if gap_val > 10:
                signal = "red"
            elif gap_val > 2:
                signal = "yellow"
            else:
                signal = "green"
        else:
            signal = "unknown"
        countries_out.append({
            "iso2": iso2,
            "name": name,
            "latestGap": gap_val,
            "latestDate": latest["date"] if latest else None,
            "signal": signal,
            "history": pts[-40:] if pts else [],
        })

    countries_out.sort(key=lambda c: c["latestGap"] or float("-inf"), reverse=True)
    result = {
        "asOf": max((str(c["latestDate"]) for c in countries_out if c.get("latestDate")), default=None),
        "source": "BIS (Bank for International Settlements)",
        "note": "Credit-to-GDP gap = deviation from long-term trend. >10pp = elevated systemic risk.",
        "countries": countries_out,
    }
    if not countries_out:
        return result
    prov = {"*": pv.ref("bis", "WS_CREDIT_GAP", "BIS credit-to-GDP gap, private non-financial sector",
                        units="percentage points of GDP", frequency="quarterly")}
    for c in countries_out:
        key = f"countries.{c['iso2']}"
        prov[key] = pv.ref("bis", "WS_CREDIT_GAP", f"BIS credit-to-GDP gap: {c['name']}",
                           units="percentage points of GDP", frequency="quarterly",
                           observed=str(c["latestDate"]))
        prov[f"{key}.signal"] = pv.derived("red if the latest gap > 10, yellow if > 2, otherwise green", [key],
                                           title=f"Credit-gap signal, {c['name']}",
                                           observed=str(c["latestDate"]))
    return pv.attach(result, prov)


@router.get("/positioning")
async def positioning():
    """CFTC Commitments of Traders: net speculator positioning for 6 key futures."""
    from ..services import cot_service
    return await cot_service.get_cot_data()


# ---------------------------------------------------------------------------
# Econometric Lab (Phase 15)
# ---------------------------------------------------------------------------

class RegressRequest(BaseModel):
    dep: str
    indep: list[str] = Field(min_length=1, max_length=5)
    countries: list[str]
    start: int = 2000
    end: int = Field(default_factory=lambda: date.today().year)


@router.post("/regress")
async def regress(req: RegressRequest):
    """Pooled OLS regression of a World Bank indicator on 1–5 other indicators."""
    from ..services import econ_lab_service
    countries = [c.strip().upper() for c in req.countries if c.strip()]
    indep = [i.strip() for i in req.indep if i.strip()]
    if not countries:
        return {
            "dep": req.dep,
            "indep": indep,
            "countries": [],
            "start": req.start,
            "end": req.end,
            "error": "at least one country required",
            "coefficients": [],
            "residuals": [],
            "nObs": 0,
        }
    try:
        return await econ_lab_service.regress(req.dep, indep, countries, req.start, req.end)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Phase 16 – Country Risk + Central Banks
# ---------------------------------------------------------------------------

from ..services import country_risk_service as _crs
from ..services import centralbanks_service as _cbs


@router.get("/country-risk")
async def country_risk(countries: str | None = None):
    c = tuple(x.strip() for x in countries.split(",") if x.strip()) if countries else None
    return await _crs.get_country_risk(c)


@router.get("/centralbanks")
async def centralbanks():
    return await _cbs.get_centralbanks()


# ---------------------------------------------------------------------------
# Phase 18A – Macro Regime Classifier
# ---------------------------------------------------------------------------

from ..services.macro_regime_service import get_macro_regime


@router.get("/regime")
async def macro_regime():
    """4-quadrant macro regime classifier: growth × inflation with asset allocation signals."""
    return await get_macro_regime()

# ---------------------------------------------------------------------------
# Phase 18B – Funding & Sentiment
# (Taylor Rule is handled by the /rates-service route above — @router.get("/taylor-rule") at line ~175)
# ---------------------------------------------------------------------------

@router.get("/funding")
async def funding_liquidity():
    """Funding and Liquidity gauge."""
    from ..services.funding_service import get_funding_liquidity
    return await get_funding_liquidity()

@router.get("/net-liquidity")
async def net_liquidity():
    """Fed plumbing: net liquidity (WALCL − RRP − TGA), reserves, SPX overlay."""
    from ..services.liquidity_service import get_net_liquidity
    return await get_net_liquidity()

@router.get("/credit-conditions")
async def credit_conditions():
    """SOFR-IORB reserve scarcity, SLOOS lending standards, excess bond premium, NFCI/ANFCI."""
    from ..services.credit_conditions_service import get_credit_conditions
    return await get_credit_conditions()

@router.get("/oil-shocks")
async def oil_shocks():
    """Demand vs. oil-specific decomposition of real WTI returns (Kilian-style proxy)."""
    from ..services.oil_shock_service import get_oil_shocks
    return await get_oil_shocks()

@router.get("/risk-dial")
async def risk_dial():
    """Composite exposure multiplier blending the standalone risk indicators."""
    from ..services.composite_signal_service import get_composite_dial
    return await get_composite_dial()

@router.get("/risk-dial/backtest")
async def risk_dial_backtest(cost_bps: float = 10.0):
    """Walk-forward self-evaluation of the composite dial vs buy-and-hold."""
    from ..services.composite_signal_service import get_dial_backtest
    return await get_dial_backtest(cost_bps)

@router.get("/recession-probability")
async def recession_probability():
    """NY-Fed-style 12-month-ahead probit on the 10y–3m spread + Sahm rule."""
    from ..services.recession_service import get_recession_probability
    return await get_recession_probability()

@router.get("/sentiment")
async def macro_sentiment():
    """Macro Sentiment Signals via Finnhub news."""
    from ..services.sentiment_service import get_macro_sentiment
    return await asyncio.to_thread(get_macro_sentiment)
