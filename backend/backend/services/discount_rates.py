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

DAMODARAN_URL = (
    "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
)

def _data_path(fname: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / fname


@cached("erp_json")
def load_erp() -> dict:
    """Load Damodaran ERP data — live Excel download with static JSON fallback."""
    import pandas as pd
    import tempfile
    import urllib.request

    try:
        # Download the latest ctryprem.xlsx from Damodaran's site
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            urllib.request.urlretrieve(DAMODARAN_URL, tmp.name)
            xl = pd.ExcelFile(tmp.name)

        # Find the regional breakdown sheet
        sheet_name = None
        for s in xl.sheet_names:
            if "regional" in s.lower() or "country" in s.lower():
                sheet_name = s
                break
        if sheet_name is None:
            sheet_name = xl.sheet_names[1] if len(xl.sheet_names) > 1 else xl.sheet_names[0]

        df = xl.parse(sheet_name, header=0)
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Detect column names (Damodaran uses different column names across years)
        country_col = erp_col = crp_col = tax_col = None
        for c in df.columns:
            c_clean = c.lower().strip()
            if c_clean in ("country", "region"):
                country_col = c
            elif "risk premium" in c_clean or "total erp" in c_clean or c_clean == "erp":
                if erp_col is None:
                    erp_col = c
            elif "country risk" in c_clean or "crp" in c_clean or "premium" in c_clean:
                if crp_col is None and erp_col is not None:
                    crp_col = c
            elif "tax" in c_clean:
                tax_col = c

        countries: dict[str, dict] = {}
        mature_erp = None
        for _, row in df.iterrows():
            name = str(row.get(country_col, "")).strip()
            if not name or name.lower() in ("nan", "none", "", "total"):
                continue
            erp_val = _clean(row.get(erp_col)) if erp_col else None
            crp_val = _clean(row.get(crp_col)) if crp_col else None
            tax_val = _clean(row.get(tax_col)) if tax_col else None

            if erp_val is None:
                continue

            countries[name] = {
                "erp": round(erp_val, 4),
                "crp": round(crp_val, 4) if crp_val is not None else None,
                "taxRate": round(tax_val, 4) if tax_val is not None else None,
            }
            if name == "United States" or mature_erp is None:
                mature_erp = erp_val

        if countries:
            log.info("Loaded %d countries from live Damodaran Excel (%s sheet)", len(countries), sheet_name)
            return {
                "asOf": "live",
                "source": "Aswath Damodaran — ctryprem.xlsx (live download)",
                "sourceUrl": DAMODARAN_URL,
                "matureMarketERP": round(mature_erp or 4.46, 2),
                "countries": countries,
            }
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

def _fetch_dgs10() -> float | None:
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

    return None


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
