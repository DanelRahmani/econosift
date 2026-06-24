"""Shared discount-rate helpers: risk-free rate, ERP, WACC for valuation models."""
from __future__ import annotations

import json
import math
from pathlib import Path

from ..cache import cached
from .metrics import _clean

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
    "KSC": "South Korea",
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
    ("korea", "South Korea"),
    ("singapore", "Singapore"),
]


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _data_path(fname: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / fname


@cached("erp_json")
def load_erp() -> dict:
    """Load Damodaran ERP JSON (cached). Returns raw dict."""
    path = _data_path("damodaran_erp_2026.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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

def _fetch_dgs10() -> float:
    """Synchronously fetch the latest DGS10 from FRED via fredapi or pandas_datareader."""
    # Try fredapi first
    try:
        from ..config import FRED_API_KEY
        if FRED_API_KEY:
            from fredapi import Fred
            fred = Fred(api_key=FRED_API_KEY)
            s = fred.get_series("DGS10")
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
        df = web.DataReader("DGS10", "fred", start=start, end=end)
        s = df.iloc[:, 0].dropna()
        if len(s) > 0:
            val = _clean(float(s.iloc[-1]))
            if val is not None and 0 < val < 20:
                return val / 100.0
    except Exception:
        pass

    return 0.04  # Hard fallback: 4%


@cached("rf10y")
def risk_free_rate() -> float:
    """US 10-Year Treasury yield as a decimal. Cached 60 min. Falls back to 0.04."""
    return _fetch_dgs10()


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
