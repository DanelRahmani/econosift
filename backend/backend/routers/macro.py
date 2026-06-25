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


@router.get("/regime")
async def regime(country: str = "US", start: int = 2000):
    """2×2 Goldilocks regime classifier: quarterly GDP growth vs CPI inflation."""
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


@router.get("/inflation")
async def inflation():
    """CPI, Core CPI, PCE, Core PCE, PPI, breakevens, M2, Quantity Theory."""
    from ..services.macro_expansion_service import fetch_fred_series

    series_ids = (
        "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "PPIFIS",
        "T5YIE", "T5YIFR", "T10YIE", "M2SL", "GDP",
    )
    data = await fetch_fred_series(series_ids, start="2000-01-01")

    cpi_yoy = _yoy(data.get("CPIAUCSL", []))
    core_cpi_yoy = _yoy(data.get("CPILFESL", []))
    pce_yoy = _yoy(data.get("PCEPI", []))
    core_pce_yoy = _yoy(data.get("PCEPILFE", []))
    ppi_yoy = _yoy(data.get("PPIFIS", []))
    m2_yoy = _yoy(data.get("M2SL", []))

    return {
        "asOf": cpi_yoy[-1]["date"] if cpi_yoy else None,
        "kpis": {
            "cpiYoY": _latest(cpi_yoy),
            "coreCpiYoY": _latest(core_cpi_yoy),
            "pceYoY": _latest(pce_yoy),
            "corePceYoY": _latest(core_pce_yoy),
            "breakeven5y": _latest(data.get("T5YIE", [])),
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
            "m2": data.get("M2SL", []),
            "m2Yoy": m2_yoy,
        },
        "quantityTheory": {
            "nominalGdp": data.get("GDP", []),
            "m2": data.get("M2SL", []),
        },
    }


@router.get("/employment")
async def employment():
    """GDP growth, unemployment, NFP, jobless claims, JOLTS, Sahm Rule, industrial production."""
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
async def housing():
    """Case-Shiller, housing starts, mortgage rate, existing home sales, recession periods."""
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


# Commodity futures tickers and display names
_COMMODITY_TICKERS = [
    ("CL=F", "WTI Crude Oil", "Energy"),
    ("BZ=F", "Brent Crude", "Energy"),
    ("RB=F", "RBOB Gasoline", "Energy"),
    ("HO=F", "Heating Oil", "Energy"),
    ("NG=F", "Natural Gas", "Energy"),
    ("GC=F", "Gold", "Metals"),
    ("SI=F", "Silver", "Metals"),
    ("HG=F", "Copper", "Metals"),
    ("PA=F", "Palladium", "Metals"),
    ("PL=F", "Platinum", "Metals"),
    ("ZW=F", "Wheat", "Agriculture"),
    ("ZC=F", "Corn", "Agriculture"),
    ("ZS=F", "Soybeans", "Agriculture"),
    ("LE=F", "Live Cattle", "Agriculture"),
    ("LBS=F", "Lumber", "Agriculture"),
]

_AXIOM_BASKET = ["CL=F", "GC=F", "NG=F", "HG=F", "ZW=F"]


def _get_commodities_sync() -> dict:
    import yfinance as yf
    from datetime import datetime

    tickers = [t[0] for t in _COMMODITY_TICKERS]
    try:
        raw = yf.download(
            tickers,
            period="1y",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
    except Exception as exc:
        log.warning("yfinance commodities download failed: %s", exc)
        return {"kpis": {}, "table": [], "ratios": {"goldOilRatio": []}, "axiomIndex": [], "asOf": str(date.today())}

    today = str(date.today())
    table_rows = []

    for ticker, name, sector in _COMMODITY_TICKERS:
        try:
            if len(tickers) == 1:
                closes = raw["Close"]
            else:
                closes = raw["Close"][ticker] if ticker in raw["Close"].columns else raw[ticker]["Close"]

            closes = closes.dropna()
            if closes.empty:
                continue

            price = round(float(closes.iloc[-1]), 4)

            def pct(n: int) -> float | None:
                if len(closes) > n:
                    return round((float(closes.iloc[-1]) / float(closes.iloc[-n - 1]) - 1) * 100, 2)
                return None

            # YTD: from first trading day of current year
            year_start = str(date.today().year) + "-01-01"
            ytd_closes = closes[closes.index >= year_start]
            ytd = None
            if len(ytd_closes) > 1:
                ytd = round((float(ytd_closes.iloc[-1]) / float(ytd_closes.iloc[0]) - 1) * 100, 2)

            table_rows.append({
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "price": price,
                "change1d": pct(1),
                "change1w": pct(5),
                "change1m": pct(21),
                "changeYtd": ytd,
            })
        except Exception as exc:
            log.debug("Commodity %s parse error: %s", ticker, exc)
            continue

    # KPIs
    def row_val(t: str, field: str = "price") -> float | None:
        for r in table_rows:
            if r["ticker"] == t:
                return r.get(field)
        return None

    kpis = {
        "wti": row_val("CL=F"),
        "gold": row_val("GC=F"),
        "natGas": row_val("NG=F"),
        "copper": row_val("HG=F"),
        "wheat": row_val("ZW=F"),
        "wtiChange1d": row_val("CL=F", "change1d"),
        "goldChange1d": row_val("GC=F", "change1d"),
    }

    # Gold/Oil ratio (5Y history)
    gold_oil_ratio: list[dict] = []
    try:
        hist_tickers = ["GC=F", "CL=F"]
        hist_raw = yf.download(
            hist_tickers,
            period="5y",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
        gc = hist_raw["Close"]["GC=F"].dropna() if "GC=F" in hist_raw["Close"].columns else pd.Series(dtype=float)
        cl = hist_raw["Close"]["CL=F"].dropna() if "CL=F" in hist_raw["Close"].columns else pd.Series(dtype=float)
        if not gc.empty and not cl.empty:
            ratio = (gc / cl).dropna()
            gold_oil_ratio = [
                {"date": str(d.date()), "value": round(float(v), 4)}
                for d, v in ratio.items()
            ]
    except Exception as exc:
        log.debug("Gold/Oil ratio failed: %s", exc)

    # Axiom Commodity Index: equal-weighted normalized from 2020-01-01
    axiom_index: list[dict] = []
    try:
        ax_raw = yf.download(
            _AXIOM_BASKET,
            start="2020-01-01",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
        closes_basket: dict[str, pd.Series] = {}
        for t in _AXIOM_BASKET:
            s = ax_raw["Close"][t].dropna() if t in ax_raw["Close"].columns else pd.Series(dtype=float)
            if not s.empty:
                closes_basket[t] = s / float(s.iloc[0])  # normalize to 1.0 at start

        if closes_basket:
            idx_df = pd.DataFrame(closes_basket).mean(axis=1) * 100  # scale to 100 at start
            axiom_index = [
                {"date": str(d.date()), "value": round(float(v), 4)}
                for d, v in idx_df.dropna().items()
            ]
    except Exception as exc:
        log.debug("Axiom commodity index failed: %s", exc)

    return {
        "asOf": today,
        "kpis": kpis,
        "table": table_rows,
        "ratios": {"goldOilRatio": gold_oil_ratio},
        "axiomIndex": axiom_index,
    }


@router.get("/commodities")
async def commodities():
    """Commodity futures prices, changes, Gold/Oil ratio, Axiom Commodity Index."""
    return await asyncio.to_thread(_get_commodities_sync)


# FX pairs for heatmap
_FX_PAIRS = [
    ("EURUSD=X", "EUR/USD"),
    ("GBPUSD=X", "GBP/USD"),
    ("USDJPY=X", "USD/JPY"),
    ("USDCNH=X", "USD/CNH"),
    ("USDCHF=X", "USD/CHF"),
    ("AUDUSD=X", "AUD/USD"),
    ("NZDUSD=X", "NZD/USD"),
    ("USDCAD=X", "USD/CAD"),
    ("USDSEK=X", "USD/SEK"),
    ("USDNOK=X", "USD/NOK"),
    ("USDMXN=X", "USD/MXN"),
    ("USDBRL=X", "USD/BRL"),
]


def _get_fx_heatmap_sync() -> dict:
    import yfinance as yf

    tickers = [t[0] for t in _FX_PAIRS]
    try:
        raw = yf.download(
            tickers,
            period="5d",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
    except Exception as exc:
        log.warning("FX heatmap download failed: %s", exc)
        return {"crosses": [], "asOf": str(date.today())}

    crosses = []
    for ticker, pair in _FX_PAIRS:
        try:
            if len(tickers) == 1:
                s = raw["Close"].dropna()
            else:
                s = raw["Close"][ticker].dropna() if ticker in raw["Close"].columns else pd.Series(dtype=float)
            if len(s) >= 2:
                change1d = round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 4)
            else:
                change1d = None
            price = round(float(s.iloc[-1]), 6) if not s.empty else None
            crosses.append({"pair": pair, "ticker": ticker, "price": price, "change1d": change1d})
        except Exception:
            crosses.append({"pair": pair, "ticker": ticker, "price": None, "change1d": None})

    return {"crosses": crosses, "asOf": str(date.today())}


@router.get("/fx/heatmap")
async def fx_heatmap():
    """1D % change for major currency crosses (FX heatmap)."""
    return await asyncio.to_thread(_get_fx_heatmap_sync)


# G10 PPP pairs: (pair_label, yf_ticker, us_cpi_series, foreign_cpi_series)
_PPP_PAIRS = [
    ("EUR/USD", "EURUSD=X", "CPIAUCSL", "CP0000EZ19M086NEST"),
    ("GBP/USD", "GBPUSD=X", "CPIAUCSL", "GBPCPIALLMINMEI"),
    ("USD/JPY", "USDJPY=X", "CPIAUCSL", "JPNCPIALLMINMEI"),
    ("USD/CHF", "USDCHF=X", "CPIAUCSL", "CHECPIALLMINMEI"),
    ("AUD/USD", "AUDUSD=X", "CPIAUCSL", "AUSCPIALLMINMEI"),
    ("NZD/USD", "NZDUSD=X", "CPIAUCSL", "NZLCPIALLMINMEI"),
    ("USD/CAD", "USDCAD=X", "CPIAUCSL", "CANCPIALLMINMEI"),
    ("USD/SEK", "USDSEK=X", "CPIAUCSL", "SWECPIALLMINMEI"),
    ("USD/NOK", "USDNOK=X", "CPIAUCSL", "NORCPIALLMINMEI"),
]


def _get_fx_ppp_sync() -> dict:
    """Compute PPP-implied exchange rates vs spot for G10 pairs."""
    import yfinance as yf

    if not __import__("os").environ.get("FRED_API_KEY"):
        return {"pairs": [], "note": "FRED_API_KEY required for PPP calculation"}

    from fredapi import Fred
    from ..config import FRED_API_KEY
    fred = Fred(api_key=FRED_API_KEY)

    # Fetch US CPI once
    try:
        us_cpi = fred.get_series("CPIAUCSL", observation_start="2000-01-01").dropna()
    except Exception as exc:
        log.warning("PPP: US CPI fetch failed: %s", exc)
        return {"pairs": [], "error": str(exc)}

    # Base year: earliest common date = 2000-01-01; use Jan 2000 levels as base
    base_date = pd.Timestamp("2000-01-01")

    pairs_out = []
    for pair_label, yf_ticker, _, foreign_cpi_id in _PPP_PAIRS:
        try:
            # Spot rate
            spot_df = yf.download(yf_ticker, period="5d", auto_adjust=True, progress=False)
            spot = None
            if not spot_df.empty:
                spot = round(float(spot_df["Close"].dropna().iloc[-1]), 6)

            # Foreign CPI from FRED
            try:
                foreign_cpi = fred.get_series(foreign_cpi_id, observation_start="2000-01-01").dropna()
            except Exception:
                pairs_out.append({"pair": pair_label, "spot": spot, "ppp": None, "overvaluation": None})
                continue

            # PPP = base_spot * (US_CPI_now / US_CPI_base) / (foreign_CPI_now / foreign_CPI_base)
            # Use Jan 2000 as base; forward-fill to align
            us_base = float(us_cpi.asof(base_date)) if not us_cpi.asof(base_date) is None else float(us_cpi.iloc[0])
            us_now = float(us_cpi.iloc[-1])
            f_base = float(foreign_cpi.asof(base_date)) if not foreign_cpi.asof(base_date) is None else float(foreign_cpi.iloc[0])
            f_now = float(foreign_cpi.iloc[-1])

            if f_base == 0 or f_now == 0 or us_base == 0:
                continue

            # We need a base spot rate; use yfinance historical for Jan 2000
            hist = yf.download(yf_ticker, start="2000-01-01", end="2000-03-01", auto_adjust=True, progress=False)
            if hist.empty:
                continue
            base_spot = float(hist["Close"].dropna().iloc[0])

            ppp = round(base_spot * (us_now / us_base) / (f_now / f_base), 6)
            overvaluation = round((spot / ppp - 1) * 100, 2) if spot and ppp else None

            pairs_out.append({
                "pair": pair_label,
                "spot": spot,
                "ppp": ppp,
                "overvaluation": overvaluation,
            })
        except Exception as exc:
            log.debug("PPP %s failed: %s", pair_label, exc)
            continue

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
async def leading():
    """Leading Economic Indicators: LEI, CFNAI, ISM PMI, GSCPI, IS-LM-PC framework data."""
    from ..services.macro_expansion_service import fetch_fred_series

    series_ids = (
        "USSLIND",            # Conference Board LEI
        "CFNAI",              # Chicago Fed National Activity Index
        "NAPM",               # ISM Manufacturing PMI (legacy; use MANEMP if unavailable)
        "GDPC1",              # Real GDP (quarterly)
        "GDPPOT",             # Potential GDP (quarterly)
        "FEDFUNDS",           # Federal Funds Rate
        "M2SL",               # M2 Money Supply
        "UNRATE",             # Unemployment rate
        "CPIAUCSL",           # CPI
    )
    data, gscpi = await asyncio.gather(
        fetch_fred_series(series_ids, start="2000-01-01"),
        asyncio.to_thread(_download_gscpi_sync),
    )

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
        "islmpc": {
            "gdp": data.get("GDPC1", []),
            "gdpPot": data.get("GDPPOT", []),
            "fedFunds": data.get("FEDFUNDS", []),
            "m2": data.get("M2SL", []),
            "unrate": data.get("UNRATE", []),
            "cpi": data.get("CPIAUCSL", []),
        },
    }


@router.get("/financial-conditions")
async def financial_conditions():
    """NFCI, STLFSI, Fed balance sheet, credit card delinquency, C&I loans, EPU."""
    from ..services.macro_expansion_service import fetch_fred_series

    series_ids = (
        "NFCI",           # Chicago Fed National Financial Conditions Index
        "STLFSI4",        # St. Louis Fed Financial Stress Index
        "WALCL",          # Fed balance sheet (total assets)
        "DRCCLACBS",      # Credit card delinquency rate
        "TOTCI",          # Total C&I loans
        "USEPUINDXD",     # Economic Policy Uncertainty Index (daily → monthly available)
    )
    data = await fetch_fred_series(series_ids, start="2000-01-01")

    fed_bs = data.get("WALCL", [])

    return {
        "asOf": str(date.today()),
        "kpis": {
            "nfci": _latest(data.get("NFCI", [])),
            "stlfsi": _latest(data.get("STLFSI4", [])),
            "fedBalanceSheet": _latest(fed_bs),
        },
        "history": {
            "nfci": data.get("NFCI", []),
            "stlfsi": data.get("STLFSI4", []),
            "fedBalanceSheet": fed_bs,
            "creditCardDelinquency": data.get("DRCCLACBS", []),
            "ciLoans": data.get("TOTCI", []),
            "economicPolicyUncertainty": data.get("USEPUINDXD", []),
        },
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
