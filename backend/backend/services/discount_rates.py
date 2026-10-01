"""Shared discount-rate helpers: risk-free rate, ERP, WACC for valuation models."""
from __future__ import annotations

import io
import json
import logging
import math
from pathlib import Path

from ..cache import cached
from .metrics import _clean

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exchange code → Damodaran country name
# ---------------------------------------------------------------------------
EXCHANGE_COUNTRY: dict[str, str] = {
    # United States
    "NMS": "United States",
    "NYQ": "United States",
    "NGM": "United States",
    "ASE": "United States",
    "PCX": "United States",
    "BTS": "United States",
    "OBB": "United States",
    # Europe
    "GER": "Germany",
    "FRA": "Germany",
    "PAR": "France",
    "AMS": "Netherlands",
    "BRU": "Belgium",
    "LSE": "United Kingdom",
    "MIL": "Italy",
    "MCE": "Spain",
    "SWX": "Switzerland",
    "VIE": "Austria",
    # Americas
    "TOR": "Canada",
    "MEX": "Mexico",
    "SAO": "Brazil",
    # Asia / Pacific
    "TYO": "Japan",
    "HKG": "Hong Kong",
    "SHG": "China",
    "SHE": "China",
    "KSC": "Korea",
    "BSE": "India",
    "NSE": "India",
    "ASX": "Australia",
    # Other
    "SGX": "Singapore",
    "TAI": "Taiwan",
}

# Heuristic substrings in fullExchangeName → country
_EXCHANGE_NAME_HINTS: list[tuple[str, str]] = [
    ("nasdaq", "United States"),
    ("new york", "United States"),
    ("nyse", "United States"),
    ("toronto", "Canada"),
    ("london", "United Kingdom"),
    ("frankfurt", "Germany"),
    ("paris", "France"),
    ("tokyo", "Japan"),
    ("hong kong", "Hong Kong"),
    ("shanghai", "China"),
    ("shenzhen", "China"),
    ("sydney", "Australia"),
    ("asx", "Australia"),
    ("bombay", "India"),
    ("national stock exchange of india", "India"),
    ("korea", "Korea"),
    ("singapore", "Singapore"),
]

# yfinance's info["country"] spellings that differ from Damodaran's table keys.
_COUNTRY_ALIASES: dict[str, str] = {
    "South Korea": "Korea",
}


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

DAMODARAN_URL = (
    "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
)

def _data_path(fname: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / fname


# Damodaran's data lives on this sheet (header in row 1; values are decimals, e.g. 0.0446). The
# first sheets whose names contain "country" ('Country Lookup', 'ERPs by country') are a calculator
# and a header-offset copy, not this table.
_ERP_SHEET = "regional breakdown"


def _download_damodaran_xlsx() -> bytes:
    """Download ctryprem.xlsx and return its bytes (separate so tests can stub the network)."""
    import urllib.request

    req = urllib.request.Request(DAMODARAN_URL, headers={"User-Agent": "Mozilla/5.0 (Axiom Finance)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _parse_damodaran_xlsx(blob: bytes) -> dict:
    """Parse the 'Regional breakdown' sheet into the static-JSON shape (erp/crp/taxRate in percent).

    Raises ValueError when the sheet, its columns or the United States row are missing, so the
    caller serves the static file instead of a half-parsed table.
    """
    import pandas as pd

    xl = pd.ExcelFile(io.BytesIO(blob))
    sheet = next((s for s in xl.sheet_names if s.strip().lower() == _ERP_SHEET), None)
    if sheet is None:
        raise ValueError(f"no '{_ERP_SHEET}' sheet in {xl.sheet_names}")

    df = xl.parse(sheet, header=0)
    df.columns = [str(c).strip().lower() for c in df.columns]
    wanted = {"country": "country", "erp": "equity risk premium",
              "crp": "country risk premium", "tax": "corporate tax rate"}
    missing = [w for w in wanted.values() if w not in df.columns]
    if missing:
        raise ValueError(f"'{sheet}' sheet lacks columns {missing}")

    def pct(v) -> float | None:
        """Sheet decimal (0.0446) -> percent (4.46), None for 'NA'/blank."""
        try:
            val = _clean(float(v))
        except (TypeError, ValueError):
            return None
        return None if val is None else round(val * 100.0, 4)

    countries: dict[str, dict] = {}
    for _, row in df.iterrows():
        name = str(row[wanted["country"]]).strip()
        if not name or name.lower() in ("nan", "none", "total"):
            continue
        erp_val = pct(row[wanted["erp"]])
        if erp_val is None:
            continue
        countries[name] = {
            "erp": erp_val,
            "crp": pct(row[wanted["crp"]]),
            "taxRate": pct(row[wanted["tax"]]),
        }

    us = countries.get("United States")
    if us is None or not 1.0 < us["erp"] < 15.0:
        raise ValueError("no plausible United States row in the parsed table")
    return {
        "asOf": "live",
        "source": "Aswath Damodaran — ctryprem.xlsx (live download)",
        "sourceUrl": DAMODARAN_URL,
        "matureMarketERP": round(us["erp"], 2),
        "countries": countries,
    }


@cached("erp_json")
def load_erp() -> dict:
    """Load Damodaran ERP data — live Excel download with static JSON fallback."""
    try:
        data = _parse_damodaran_xlsx(_download_damodaran_xlsx())
        log.info("Loaded %d countries from live Damodaran Excel", len(data["countries"]))
        return data
    except Exception as exc:
        log.warning("Failed to download/parse Damodaran Excel, falling back to JSON: %s", exc)

    # Fall back to static JSON
    path = _data_path("damodaran_erp_2026.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"matureMarketERP": 4.46, "countries": {}}


@cached("sector_multiples_json")
def load_sector_multiples() -> dict:
    """Load Damodaran sector EV/EBITDA multiples (cached)."""
    path = _data_path("sector_multiples.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Country detection
# ---------------------------------------------------------------------------

def detect_country(info: dict) -> str:
    """Best-effort: return a Damodaran country name from yfinance info dict."""
    erp_data = load_erp()
    country_table: dict = erp_data.get("countries", {})

    # 1. Direct exchange code lookup
    exchange = (info.get("exchange") or "").strip()
    if exchange in EXCHANGE_COUNTRY:
        return EXCHANGE_COUNTRY[exchange]

    # 2. Heuristic on fullExchangeName
    full_name = (info.get("fullExchangeName") or "").lower()
    for hint, country in _EXCHANGE_NAME_HINTS:
        if hint in full_name:
            return country

    # 3. info["country"] if it matches the ERP table directly
    info_country = (info.get("country") or "").strip()
    info_country = _COUNTRY_ALIASES.get(info_country, info_country)
    if info_country and info_country in country_table:
        return info_country

    # 4. Default
    return "United States"


# ---------------------------------------------------------------------------
# ERP / tax helpers
# ---------------------------------------------------------------------------

def erp_for_country(country: str) -> float:
    """Total ERP for *country* as a decimal (e.g. 0.0446 for US)."""
    erp_data = load_erp()
    countries: dict = erp_data.get("countries", {})

    entry = countries.get(country)
    if entry is not None:
        val = _clean(entry.get("erp"))
        if val is not None:
            return val / 100.0

    # Fallback to mature market ERP
    mm = _clean(erp_data.get("matureMarketERP"))
    if mm is not None:
        return mm / 100.0

    return 0.05  # last-resort


def tax_rate_for(info: dict, country: str) -> float:
    """Effective tax rate as a decimal."""
    # Prefer yfinance reported effective tax rate
    etr = _clean(info.get("effectiveTaxRate"))
    if etr is not None and 0.0 < etr < 0.6:
        return etr

    # Fall back to Damodaran country statutory rate
    erp_data = load_erp()
    countries: dict = erp_data.get("countries", {})
    entry = countries.get(country)
    if entry is not None:
        tr = _clean(entry.get("taxRate"))
        if tr is not None:
            return tr / 100.0

    return 0.21  # US federal statutory fallback


# ---------------------------------------------------------------------------
# Risk-free rate (US 10Y Treasury)
# ---------------------------------------------------------------------------

def _fetch_fred_latest(series_id: str) -> float | None:
    """Synchronously fetch the latest observation of a FRED yield series (percent) as a decimal.

    Uses fredapi, then pandas_datareader; None when both fail or the value is implausible.
    """
    # Try fredapi first
    try:
        from ..config import FRED_API_KEY
        if FRED_API_KEY:
            from fredapi import Fred
            fred = Fred(api_key=FRED_API_KEY)
            s = fred.get_series(series_id)
            s = s.dropna()
            if len(s) > 0:
                val = _clean(float(s.iloc[-1]))
                if val is not None and 0 < val < 20:
                    return val / 100.0
    except Exception:
        pass

    # Try pandas_datareader (no API key required)
    try:
        from datetime import datetime, timedelta
        import pandas_datareader.data as web
        end = datetime.today()
        start = end - timedelta(days=30)
        df = web.DataReader(series_id, "fred", start=start, end=end)
        s = df.iloc[:, 0].dropna()
        if len(s) > 0:
            val = _clean(float(s.iloc[-1]))
            if val is not None and 0 < val < 20:
                return val / 100.0
    except Exception:
        pass

    return None


def _fetch_dgs10() -> float | None:
    """Latest US 10-year Treasury yield (FRED DGS10) as a decimal."""
    return _fetch_fred_latest("DGS10")


RISK_FREE_FALLBACK = 0.04


@cached("rf10y")
def _risk_free_rate_live() -> float | None:
    """Live DGS10 as a decimal, or None — a failure is never cached."""
    return _fetch_dgs10()


def risk_free_rate_is_fallback() -> bool:
    """True when :func:`risk_free_rate` is serving the hard-coded fallback."""
    return _risk_free_rate_live() is None


def risk_free_rate() -> float:
    """US 10-Year Treasury yield as a decimal. Cached 60 min.

    Falls back to 4% when FRED is unreachable; the fallback is not cached, so
    the live rate is retried on the next call instead of being pinned for an
    hour (and persisted) as if it were real.
    """
    live = _risk_free_rate_live()
    return live if live is not None else RISK_FREE_FALLBACK


@cached("rf3m")
def _short_risk_free_rate_live() -> float | None:
    """Live DGS3MO as a decimal, or None — a failure is never cached."""
    return _fetch_fred_latest("DGS3MO")


def short_risk_free_rate_is_fallback() -> bool:
    """True when :func:`short_risk_free_rate` is serving the hard-coded fallback."""
    return _short_risk_free_rate_live() is None


def short_risk_free_rate() -> float:
    """US 3-month Treasury bill yield (FRED DGS3MO) as a decimal. Cached 60 min.

    Falls back to :data:`RISK_FREE_FALLBACK` when FRED is unreachable; like the 10-year
    rate, the fallback is not cached.
    """
    live = _short_risk_free_rate_live()
    return live if live is not None else RISK_FREE_FALLBACK


def short_risk_free_rate_with_source() -> tuple[float, str]:
    """(short rate, its label) from one lookup, so the label always describes the rate used."""
    live = _short_risk_free_rate_live()
    return (live, "FRED DGS3MO") if live is not None else (RISK_FREE_FALLBACK, "fallback 4%")


# ---------------------------------------------------------------------------
# Cost of equity (CAPM)
# ---------------------------------------------------------------------------

def cost_of_equity(beta: float | None, country: str, rf: float | None = None) -> float | None:
    """CAPM: ke = rf + β × ERP_country. Uses β=1.0 if None."""
    if rf is None:
        rf = risk_free_rate()
    b = beta if beta is not None else 1.0
    erp = erp_for_country(country)
    return _clean(rf + b * erp)


# ---------------------------------------------------------------------------
# WACC bundle
# ---------------------------------------------------------------------------

def wacc(bundle: dict, beta: float | None) -> dict:
    """
    Compute WACC and its components from a yfinance bundle.

    Returns
    -------
    dict with keys:
        wacc, costOfEquity, costOfDebt, taxRate, beta, country,
        riskFree, erp, weightEquity, weightDebt
    All monetary values as decimals; None where unavailable.
    """
    info: dict = bundle.get("info") or {}
    fin: dict = bundle.get("financials") or {}
    bs: dict = bundle.get("balance_sheet") or {}

    country = detect_country(info)
    rf = risk_free_rate()
    ke = cost_of_equity(beta, country, rf)
    erp = erp_for_country(country)
    tax = tax_rate_for(info, country)

    # --- Cost of debt ---
    interest_exp_raw = (
        info.get("interestExpense")
        or fin.get("Interest Expense")
        or fin.get("Interest Expense Non Operating")
    )
    total_debt_raw = (
        info.get("totalDebt")
        or bs.get("Total Debt")
        or bs.get("Long Term Debt And Capital Lease Obligation")
    )
    interest_exp = _clean(interest_exp_raw)
    total_debt_val = _clean(total_debt_raw)

    kd: float | None = None
    if (
        interest_exp is not None
        and total_debt_val is not None
        and total_debt_val > 0
    ):
        raw_kd = abs(interest_exp) / total_debt_val
        if 0.01 <= raw_kd <= 0.15:
            kd = raw_kd

    if kd is None:
        kd = (rf or 0.04) + 0.02  # rf + credit spread default

    # --- Capital structure weights ---
    market_cap = _clean(info.get("marketCap"))
    debt = _clean(total_debt_raw) or 0.0

    if market_cap is None:
        # Can't weight: WACC = ke (unlevered proxy)
        wacc_val = ke
        we = 1.0
        wd = 0.0
    else:
        total_cap = market_cap + debt
        if total_cap <= 0:
            wacc_val = ke
            we = 1.0
            wd = 0.0
        else:
            we = market_cap / total_cap
            wd = debt / total_cap
            if ke is not None:
                wacc_val = we * ke + wd * kd * (1.0 - tax)
            else:
                wacc_val = None

    # Clamp to sane floor (must exceed a reasonable terminal growth rate)
    TERMINAL_GROWTH_FLOOR = 0.025
    MIN_WACC = max(TERMINAL_GROWTH_FLOOR + 0.005, 0.05)
    if wacc_val is not None:
        wacc_val = max(wacc_val, MIN_WACC)
        wacc_val = _clean(wacc_val)

    return {
        "wacc": wacc_val,
        "costOfEquity": ke,
        "costOfDebt": _clean(kd),
        "taxRate": _clean(tax),
        "beta": _clean(beta) if beta is not None else None,
        "country": country,
        "riskFree": _clean(rf),
        "erp": _clean(erp),
        "weightEquity": _clean(we),
        "weightDebt": _clean(wd),
    }
