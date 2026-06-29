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

from ..config import COUNTRIES, INDICATORS
from ..services import macro_service
from ..services import regime_service
from ..services import yfinance_service as yfs
from ..sources import source_frankfurter, source_datareader, source_imf

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/macro", tags=["macro"])

# CBOE Treasury yield indices — quoted directly as yield in percent, no API key.
YIELD_TENORS = [("^IRX", "3M", 0.25), ("^FVX", "5Y", 5.0),
                ("^TNX", "10Y", 10.0), ("^TYX", "30Y", 30.0)]


# ---------------------------------------------------------------------------
# Existing routes (unchanged)
# ---------------------------------------------------------------------------

@router.get("/indicators")
async def indicators():
    return {"indicators": INDICATORS}


@router.get("/countries")
async def countries():
    return {"countries": COUNTRIES}


@router.get("/data")
async def data(
    countries: str = Query(...),
    indicator: str = Query(...),
    start: int = 2000,
    end: int = Query(default_factory=lambda: date.today().year),
):
    iso2_list = [c.strip().upper() for c in countries.split(",") if c.strip()]
    series = await macro_service.get_macro_data(indicator, iso2_list, start, end)
    return {
        "indicator": indicator,
        "unit": macro_service.get_unit(indicator),
        "series": series,
    }


@router.get("/fx")
async def fx(base: str = "USD", targets: str = "EUR,GBP,JPY"):
    tgt = tuple(t.strip().upper() for t in targets.split(",") if t.strip())
    return await source_frankfurter.latest(base.upper(), tgt)


@router.get("/fx/history")
async def fx_history(
    base: str = "USD",
    targets: str = "EUR,GBP,JPY",
    start: str = "2020-01-01",
    end: str = Query(default_factory=lambda: date.today().isoformat()),
):
    tgt = tuple(t.strip().upper() for t in targets.split(",") if t.strip())
    return await source_frankfurter.history(base.upper(), tgt, start, end)


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
    return {
        "indicator": indicator,
        "unit": macro_service.get_unit(indicator),
        "source": source_imf.SOURCE_LABEL,
        "series": series or [],
    }


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

    return {
        "points": points,
        "spread10y3m": spread_10y_3m,
        "spread10y5y": spread_10y_5y,
        "inverted": inverted,
    }


@router.get("/regime-series")
async def regime_series(country: str = "US", start: int = 2000):
    """2×2 Goldilocks regime classifier: quarterly GDP growth vs CPI inflation (historical series)."""
    return await asyncio.to_thread(regime_service.regime_series, country.upper(), start)


@router.get("/fama-french")
async def fama_french():
    factors = await asyncio.to_thread(source_datareader.fama_french)
    return {"factors": factors}


# ---------------------------------------------------------------------------
# Phase 8: Macro Expansion routes
# ---------------------------------------------------------------------------

def _yoy(series: list[dict]) -> list[dict]:
    """Compute rolling 12-month YoY % change from a monthly series."""
    if not series:
        return []
    df = pd.DataFrame(series).set_index("date")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df["yoy"] = df["value"].pct_change(12) * 100
    return [
        {"date": str(d.date()), "value": round(float(v), 4)}
        for d, v in df["yoy"].dropna().items()
    ]


def _latest(series: list[dict]) -> float | None:
    return series[-1]["value"] if series else None


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
    return {"data": merged}


@router.get("/inflation")
async def inflation(country: str = Query("US", description="ISO2 country code (FRED data is US-only)")):
    """CPI, Core CPI, PCE, Core PCE, PPI, breakevens, Michigan survey, M2, Quantity Theory."""
    if country.upper() != "US":
        return {"asOf": None, "kpis": {}, "history": {}, "note": "FRED data is US-only. For cross-country data use /macro/data or /macro/country-risk."}
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

    return {
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


@router.get("/employment")
async def employment(country: str = Query("US", description="ISO2 country code (FRED data is US-only)")):
    """GDP growth, unemployment, NFP, jobless claims, JOLTS, Sahm Rule, industrial production."""
    if country.upper() != "US":
        return {"asOf": None, "kpis": {}, "history": {}, "note": "FRED data is US-only. For cross-country data use /macro/data or /macro/country-risk."}
    from ..services.macro_expansion_service import fetch_fred_series

    series_ids = (
        "A191RL1Q225SBEA",  # Real GDP YoY quarterly
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

    return {
        "asOf": str(date.today()),
        "kpis": {
            "gdpYoY": _latest(data.get("A191RL1Q225SBEA", [])),
            "unemploymentRate": _latest(data.get("UNRATE", [])),
            "nfpLatest": nfp_mom[-1]["value"] if nfp_mom else None,
            "joblessClaims": _latest(data.get("ICSA", [])),
            "laborParticipation": _latest(data.get("CIVPART", [])),
        },
        "history": {
            "gdpYoY": data.get("A191RL1Q225SBEA", []),
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

    return {
        "asOf": str(date.today()),
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
        # Date format: quarterly "2020-Q1" etc. — extract year
        latest_date = latest["date"]
        try:
            y = int(latest_date.split("-Q")[0]) if "-Q" in latest_date else int(latest_date)
        except (ValueError, IndexError):
            y = None
        # Find latest value from previous year (any quarter)
        prev_val = None
        if y is not None:
            prev_year_pts = [p for p in pts if str(y - 1) in str(p["date"])]
            if prev_year_pts:
                # Average all quarters of previous year
                prev_val = sum(p["value"] for p in prev_year_pts) / len(prev_year_pts)
        # Average latest year's quarters for current value
        cur_year_pts = [p for p in pts if str(y) in str(p["date"])] if y is not None else [latest]
        cur_val = sum(p["value"] for p in cur_year_pts) / len(cur_year_pts) if cur_year_pts else latest["value"]
        yoy = round((cur_val / prev_val - 1) * 100, 2) if prev_val and prev_val > 0 else None
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
    return {
        "asOf": str(date.today()),
        "source": "BIS (Bank for International Settlements)",
        "note": "Real residential property price indices, 2010=100",
        "countries": countries_out,
    }


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


# Commodity config: (display name, sector, FRED series for spot price)
_COMMODITY_CONFIG = [
    ("WTI Crude Oil", "Energy", "DCOILWTICO"),
    ("Brent Crude", "Energy", "DCOILBRENTEU"),
    ("Natural Gas", "Energy", "DHHNGSP"),
    ("Gold", "Metals", "GOLDAMGBD228NLBR"),
    ("Silver", "Metals", "DSLVUSDM"),
    ("Copper", "Metals", "PCOPPUSDM"),
    ("Wheat", "Agriculture", "PWHEAMTUSDM"),
    ("Corn", "Agriculture", "PMAIZEUSDM"),
    ("Soybeans", "Agriculture", "PSOYBUSDM"),
]

_YF_FALLBACK = {
    "WTI Crude Oil": "CL=F", "Brent Crude": "BZ=F", "Natural Gas": "NG=F",
    "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
    "Wheat": "ZW=F", "Corn": "ZC=F", "Soybeans": "ZS=F",
}

_AXIOM_BASKET_FRED = ["DCOILWTICO", "GOLDAMGBD228NLBR", "DHHNGSP", "PCOPPUSDM", "PWHEAMTUSDM"]


def _get_commodities_sync() -> dict:
    """Fetch commodity prices primarily from FRED, with yfinance for 1D/1W changes."""
    import yfinance as yf

    today = str(date.today())
    from ..services.macro_expansion_service import _fetch_fred_series_sync

    fred_ids = [c[2] for c in _COMMODITY_CONFIG]
    fred_data = _fetch_fred_series_sync(fred_ids, start=(date.today() - timedelta(days=365)).isoformat())

    table_rows = []
    for name, sector, fred_id in _COMMODITY_CONFIG:
        series = fred_data.get(fred_id, [])
        price = round(series[-1]["value"], 4) if series else None
        change1m = None
        if len(series) >= 22:
            prev = series[-22]["value"]
            if prev and price:
                change1m = round((price / prev - 1) * 100, 2)
        table_rows.append({
            "ticker": fred_id, "name": name, "sector": sector,
            "price": price, "change1d": None, "change1w": None,
            "change1m": change1m, "changeYtd": None,
        })

    # yfinance fallback for 1D/1W changes only
    try:
        for name, yf_tick in _YF_FALLBACK.items():
            try:
                tk = yf.Ticker(yf_tick)
                hist = tk.history(period="5d")
                if hist is None or hist.empty:
                    continue
                closes = hist["Close"].dropna()
                if len(closes) < 2:
                    continue
                ch1d = round((float(closes.iloc[-1]) / float(closes.iloc[-2]) - 1) * 100, 2) if len(closes) >= 2 else None
                ch1w = round((float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 2) if len(closes) >= 5 else None
                for row in table_rows:
                    if row["name"] == name:
                        row["change1d"] = ch1d
                        row["change1w"] = ch1w
                        if row["price"] is None:
                            row["price"] = round(float(closes.iloc[-1]), 4)
                        break
            except Exception:
                pass
    except Exception as exc:
        log.debug("yfinance commodity fallback failed: %s", exc)

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

    # Gold/Oil ratio from FRED
    gold_oil_ratio: list[dict] = []
    try:
        gold_s = fred_data.get("GOLDAMGBD228NLBR", [])
        oil_s = fred_data.get("DCOILWTICO", [])
        oil_map = {p["date"]: p["value"] for p in oil_s if p.get("value", 0) > 0}
        gold_oil_ratio = [
            {"date": p["date"], "value": round(p["value"] / oil_map[p["date"]], 4)}
            for p in gold_s if p["date"] in oil_map
        ]
        # Try 5Y history too
        hist_fred = _fetch_fred_series_sync(
            ["GOLDAMGBD228NLBR", "DCOILWTICO"],
            start=(date.today() - timedelta(days=5 * 365)).isoformat(),
        )
        if hist_fred:
            g5 = hist_fred.get("GOLDAMGBD228NLBR", [])
            o5 = hist_fred.get("DCOILWTICO", [])
            om5 = {p["date"]: p["value"] for p in o5 if p.get("value", 0) > 0}
            r5 = [{"date": p["date"], "value": round(p["value"] / om5[p["date"]], 4)}
                  for p in g5 if p["date"] in om5]
            if len(r5) > len(gold_oil_ratio):
                gold_oil_ratio = r5
    except Exception as exc:
        log.debug("Gold/Oil ratio failed: %s", exc)

    # Axiom Commodity Index (equal-weighted, normalized, from FRED)
    axiom_index: list[dict] = []
    try:
        ax_data = _fetch_fred_series_sync(_AXIOM_BASKET_FRED, start="2020-01-01")
        closes_basket: dict[str, pd.Series] = {}
        for fid in _AXIOM_BASKET_FRED:
            pts = ax_data.get(fid, [])
            if len(pts) >= 2:
                s = pd.Series({p["date"]: p["value"] for p in pts})
                s.index = pd.to_datetime(s.index)
                s = s.sort_index()
                ref = float(s.iloc[0])
                if ref > 0:
                    closes_basket[fid] = s / ref
        if closes_basket:
            idx_df = pd.DataFrame(closes_basket).mean(axis=1) * 100
            axiom_index = [
                {"date": str(d.date()), "value": round(float(v), 4)}
                for d, v in idx_df.dropna().items()
            ]
    except Exception as exc:
        log.debug("Axiom commodity index failed: %s", exc)

    return {
        "asOf": today, "kpis": kpis, "table": table_rows,
        "ratios": {"goldOilRatio": gold_oil_ratio},
        "axiomIndex": axiom_index,
    }


@router.get("/commodities")
async def commodities():
    """Commodity futures prices, changes, Gold/Oil ratio, Axiom Commodity Index."""
    return await asyncio.to_thread(_get_commodities_sync)


# FX pairs for heatmap — use FRED DEX* series (daily, reliable)
_FX_PAIRS_FRED = [
    ("DEXUSEU", "EUR/USD", False),   ("DEXUSUK", "GBP/USD", False),
    ("DEXJPUS", "USD/JPY", True),    ("DEXCHUS", "USD/CHF", True),
    ("DEXCAUS", "USD/CAD", True),    ("DEXUSAL", "AUD/USD", False),
    ("DEXUSNZ", "NZD/USD", False),   ("DEXSZUS", "USD/SEK", True),
    ("DEXNOUS", "USD/NOK", True),    ("DEXMXUS", "USD/MXN", True),
    ("DEXBZUS", "USD/BRL", True),    ("DEXKOUS", "USD/KRW", True),
]


def _get_fx_heatmap_sync() -> dict:
    """FX heatmap using FRED daily exchange rates."""
    from ..services.macro_expansion_service import _fetch_fred_series_sync

    fred_ids = [p[0] for p in _FX_PAIRS_FRED]
    start_date = (date.today() - timedelta(days=30)).isoformat()
    fred_data = _fetch_fred_series_sync(fred_ids, start=start_date)

    crosses = []
    for fred_id, pair, is_inverted in _FX_PAIRS_FRED:
        try:
            series = fred_data.get(fred_id, [])
            if len(series) >= 2:
                latest = series[-1]["value"]
                prev = series[-2]["value"]
                if is_inverted and latest > 0 and prev > 0:
                    change1d = round((prev / latest - 1) * 100, 4)
                    price = round(1 / latest, 6)
                elif not is_inverted:
                    change1d = round((latest / prev - 1) * 100, 4)
                    price = round(latest, 6)
                else:
                    price = None; change1d = None
            elif len(series) == 1 and series[0]["value"] > 0:
                v = series[0]["value"]
                price = round(1 / v, 6) if is_inverted else round(v, 6)
                change1d = None
            else:
                price = None; change1d = None
            crosses.append({"pair": pair, "ticker": fred_id, "price": price, "change1d": change1d})
        except Exception:
            crosses.append({"pair": pair, "ticker": fred_id, "price": None, "change1d": None})

    return {"crosses": crosses, "asOf": str(date.today())}


@router.get("/fx/heatmap")
async def fx_heatmap():
    """1D % change for major currency crosses (FX heatmap)."""
    return await asyncio.to_thread(_get_fx_heatmap_sync)


# G10 PPP pairs: (pair_label, dex_series, is_inverted, foreign_cpi_series)
_PPP_PAIRS = [
    ("EUR/USD", "DEXUSEU", False, "CP0000EZ19M086NEST"),
    ("GBP/USD", "DEXUSUK", False, "GBPCPIALLMINMEI"),
    ("USD/JPY", "DEXJPUS", True,  "JPNCPIALLMINMEI"),
    ("USD/CHF", "DEXCHUS", True,  "CHECPIALLMINMEI"),
    ("AUD/USD", "DEXUSAL", False, "AUSCPIALLMINMEI"),
    ("USD/CAD", "DEXCAUS", True,  "CANCPIALLMINMEI"),
    ("USD/SEK", "DEXSZUS", True,  "SWECPIALLMINMEI"),
    ("USD/NOK", "DEXNOUS", True,  "NORCPIALLMINMEI"),
]


def _get_fx_ppp_sync() -> dict:
    """Compute PPP-implied exchange rates vs spot for G10 pairs using FRED CPI + DEX."""
    if not __import__("os").environ.get("FRED_API_KEY"):
        return {"pairs": [], "note": "FRED_API_KEY required for PPP calculation"}

    from fredapi import Fred
    from ..config import FRED_API_KEY
    from ..services.macro_expansion_service import _fetch_fred_series_sync

    fred = Fred(api_key=FRED_API_KEY)

    # Fetch US CPI
    try:
        us_cpi_raw = _fetch_fred_series_sync(["CPIAUCSL"], start="2005-01-01").get("CPIAUCSL", [])
    except Exception as exc:
        log.warning("PPP: US CPI fetch failed: %s", exc)
        return {"pairs": [], "error": str(exc)}

    # Build CPI maps (date -> value)
    us_cpi_map = {p["date"]: p["value"] for p in us_cpi_raw}

    pairs_out = []
    for pair_label, dex_id, is_inverted, fg_cpi_id in _PPP_PAIRS:
        try:
            # Spot rate from FRED DEX
            dex_raw = _fetch_fred_series_sync([dex_id], start=(date.today() - timedelta(days=60)).isoformat())
            dex_series = dex_raw.get(dex_id, [])
            if len(dex_series) < 2:
                pairs_out.append({"pair": pair_label, "spot": None, "ppp": None, "overvaluation": None})
                continue

            spot_val = dex_series[-1]["value"]
            spot = round(1 / spot_val, 6) if is_inverted and spot_val > 0 else round(spot_val, 6)

            # Foreign CPI
            fg_cpi_raw = _fetch_fred_series_sync([fg_cpi_id], start="2005-01-01").get(fg_cpi_id, [])
            fg_cpi_map = {p["date"]: p["value"] for p in fg_cpi_raw}

            # Find latest date where both US and foreign CPI are available
            common_dates = sorted(set(us_cpi_map.keys()) & set(fg_cpi_map.keys()))
            if len(common_dates) < 2:
                pairs_out.append({"pair": pair_label, "spot": spot, "ppp": None, "overvaluation": None})
                continue

            latest = common_dates[-1]
            earliest = common_dates[0]

            us_now = us_cpi_map[latest]
            us_base = us_cpi_map[earliest]
            fg_now = fg_cpi_map[latest]
            fg_base = fg_cpi_map[earliest]

            if not all([us_now, us_base, fg_now, fg_base]) or us_base == 0 or fg_base == 0:
                pairs_out.append({"pair": pair_label, "spot": spot, "ppp": None, "overvaluation": None})
                continue

            # PPP implied rate: base_spot * (US CPI change) / (foreign CPI change)
            # Use earliest common date spot as base
            base_spot_raw = dex_series[0]["value"] if dex_series else None
            if base_spot_raw is None or base_spot_raw == 0:
                pairs_out.append({"pair": pair_label, "spot": spot, "ppp": None, "overvaluation": None})
                continue

            base_spot = round(1 / base_spot_raw, 6) if is_inverted else round(base_spot_raw, 6)
            ppp = round(base_spot * (us_now / us_base) / (fg_now / fg_base), 6)
            overvaluation = round((spot / ppp - 1) * 100, 2) if spot and ppp else None

            pairs_out.append({
                "pair": pair_label, "spot": spot, "ppp": ppp, "overvaluation": overvaluation,
            })
        except Exception as exc:
            log.debug("PPP %s failed: %s", pair_label, exc)
            pairs_out.append({"pair": pair_label, "spot": None, "ppp": None, "overvaluation": None})

    return {"pairs": pairs_out, "asOf": str(date.today())}


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

    series_ids = (
        "USSLIND",            # Conference Board LEI
        "CFNAI",              # Chicago Fed National Activity Index
        "NAPM",               # ISM Manufacturing PMI
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

    return {
        "asOf": str(date.today()),
        "kpis": {
            "lei": _latest(data.get("USSLIND", [])),
            "cfnai": _latest(data.get("CFNAI", [])),
            "ismPmi": _latest(data.get("NAPM", [])),
            "gscpi": gscpi[-1]["value"] if gscpi else None,
        },
        "history": {
            "lei": data.get("USSLIND", []),
            "cfnai": data.get("CFNAI", []),
            "ismPmi": data.get("NAPM", []),
            "gscpi": gscpi,
        },
        "islmpc": islmpc,
        "baseYear": base_year,
    }


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
    ci_raw = data.get("BUSLOANS", data.get("TOTCI", []))
    ci_loans = [
        {"date": p["date"], "value": round(p["value"] / 1_000, 4)}
        for p in ci_raw if p.get("value") is not None
    ]

    return {
        "asOf": str(date.today()),
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
    return {
        "asOf": str(date.today()),
        "source": "BIS (Bank for International Settlements)",
        "note": "Credit-to-GDP gap = deviation from long-term trend. >10pp = elevated systemic risk.",
        "countries": countries_out,
    }


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

@router.get("/sentiment")
async def macro_sentiment():
    """Macro Sentiment Signals via Finnhub news."""
    from ..services.sentiment_service import get_macro_sentiment
    return await asyncio.to_thread(get_macro_sentiment)
