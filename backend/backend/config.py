"""Static configuration: countries, indicators, ISO mappings."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY") or None
# Optional free-tier key; features that use it degrade gracefully when absent.
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") or None
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or None
# Optional Google Gemini API key (free tier); used for AI-powered summaries.

# ISO2 -> ISO3 for sources that need 3-letter codes (DBnomics OECD/BIS etc.)
ISO2_TO_ISO3: dict[str, str] = {
    "US": "USA", "DE": "DEU", "FR": "FRA", "GB": "GBR", "JP": "JPN",
    "CN": "CHN", "NL": "NLD", "IT": "ITA", "ES": "ESP", "CA": "CAN",
    "AU": "AUS", "KR": "KOR", "IN": "IND", "BR": "BRA", "MX": "MEX",
    "SE": "SWE", "NO": "NOR", "DK": "DNK", "PL": "POL", "CH": "CHE",
}

# Eurozone members (for ECB routing).
EUROZONE = {
    "AT", "BE", "CY", "EE", "FI", "FR", "DE", "GR", "IE", "IT",
    "LV", "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES", "HR",
}

# Country catalogue for /api/macro/countries.
COUNTRIES: list[dict[str, str]] = [
    {"iso2": "US", "name": "United States", "region": "North America"},
    {"iso2": "CA", "name": "Canada", "region": "North America"},
    {"iso2": "MX", "name": "Mexico", "region": "North America"},
    {"iso2": "BR", "name": "Brazil", "region": "South America"},
    {"iso2": "DE", "name": "Germany", "region": "Europe"},
    {"iso2": "FR", "name": "France", "region": "Europe"},
    {"iso2": "GB", "name": "United Kingdom", "region": "Europe"},
    {"iso2": "IT", "name": "Italy", "region": "Europe"},
    {"iso2": "ES", "name": "Spain", "region": "Europe"},
    {"iso2": "NL", "name": "Netherlands", "region": "Europe"},
    {"iso2": "SE", "name": "Sweden", "region": "Europe"},
    {"iso2": "NO", "name": "Norway", "region": "Europe"},
    {"iso2": "DK", "name": "Denmark", "region": "Europe"},
    {"iso2": "PL", "name": "Poland", "region": "Europe"},
    {"iso2": "CH", "name": "Switzerland", "region": "Europe"},
    {"iso2": "JP", "name": "Japan", "region": "Asia"},
    {"iso2": "CN", "name": "China", "region": "Asia"},
    {"iso2": "KR", "name": "South Korea", "region": "Asia"},
    {"iso2": "IN", "name": "India", "region": "Asia"},
    {"iso2": "AU", "name": "Australia", "region": "Oceania"},
]

COUNTRY_NAMES: dict[str, str] = {c["iso2"]: c["name"] for c in COUNTRIES}

# ── dynamic ISO2 → ISO3 lookup ──────────────────────────────────────────

def iso2_to_iso3(iso2: str) -> str:
    """Convert an ISO2 country code to ISO3.

    Uses the static mapping first (20 predefined countries, instant).
    Falls back to pycountry for any other World Bank economy (e.g. AR→ARG).
    If pycountry is unavailable or the code is unrecognised, returns the
    original value so data sources can attempt a direct lookup.
    """
    iso2 = iso2.upper()
    if iso2 in ISO2_TO_ISO3:
        return ISO2_TO_ISO3[iso2]
    try:
        import pycountry
        pc = pycountry.countries.get(alpha_2=iso2)
        if pc:
            return pc.alpha_3
    except Exception:
        pass
    return iso2  # last resort — let the data source try with the ISO2 code

# Indicator catalogue for /api/macro/indicators.
INDICATORS: list[dict] = [
    {"id": "gdp_growth", "label": "GDP Growth (annual %)", "unit": "%",
     "availableSources": ["World Bank", "IMF", "FRED", "DB.nomics"]},
    {"id": "inflation", "label": "Inflation, CPI (annual %)", "unit": "%",
     "availableSources": ["World Bank", "IMF", "FRED", "ECB", "DB.nomics"]},
    {"id": "unemployment", "label": "Unemployment Rate", "unit": "%",
     "availableSources": ["World Bank", "IMF", "FRED", "DB.nomics"]},
    {"id": "interest_rate", "label": "Policy Interest Rate", "unit": "%",
     "availableSources": ["FRED", "ECB", "DB.nomics"]},
    {"id": "debt_gdp", "label": "Government Debt (% of GDP)", "unit": "%",
     "availableSources": ["World Bank", "IMF", "FRED"]},
    {"id": "current_account", "label": "Current Account (% of GDP)", "unit": "%",
     "availableSources": ["World Bank", "IMF"]},
    {"id": "trade_gdp", "label": "Trade (% of GDP)", "unit": "%",
     "availableSources": ["World Bank"]},
    {"id": "gdp_per_capita", "label": "GDP per Capita (constant US$)", "unit": "US$",
     "availableSources": ["World Bank", "IMF"]},
    {"id": "yield_10y", "label": "10-Year Govt Bond Yield", "unit": "%",
     "availableSources": ["FRED"]},
    {"id": "exchange_rates", "label": "Exchange Rate (vs USD)", "unit": "FX",
     "availableSources": ["Frankfurter"]},
]

INDICATOR_UNITS: dict[str, str] = {i["id"]: i["unit"] for i in INDICATORS}
