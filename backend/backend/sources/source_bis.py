"""BIS (Bank for International Settlements) data source.

Uses the BIS bulk CSV ZIP downloads for historical data, with graceful
fallback.  All BIS exchange rates are reported as "units of foreign currency
per 1 USD" and are converted to standard FX conventions:
  - EUR/USD, GBP/USD, AUD/USD, NZD/USD → inverted (1 / BIS value)
  - USD/JPY, USD/CHF, USD/CAD, etc. → used directly (already correct)
"""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import date
from typing import Any

import httpx
import pandas as pd

from ..cache import async_cached

logger = logging.getLogger(__name__)

SOURCE_LABEL = "BIS (Bank for International Settlements)"

# BIS bulk ZIP URLs
BIS_ZIPS = {
    "cpi":       "https://data.bis.org/static/bulk/WS_LONG_CPI_csv_flat.zip",
    "policy":    "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip",
    "fx":        "https://data.bis.org/static/bulk/WS_XRU_csv_flat.zip",
    "fx_effective": "https://data.bis.org/static/bulk/WS_EER_csv_flat.zip",
    "credit_gap":   "https://data.bis.org/static/bulk/WS_CREDIT_GAP_csv_flat.zip",
    "property":     "https://data.bis.org/static/bulk/WS_SPP_csv_flat.zip",
    "crossborder":  "https://data.bis.org/static/bulk/WS_LBS_csv_flat.zip",
}

# Currencies where standard quote is "USD per unit" → need to invert BIS value
INVERT_CURRENCIES = {"XM", "GB", "AU", "NZ"}

# BIS ISO2 codes that need special handling
BIS_AREA_MAP = {
    "XM": "EA",  # Euro area → use EA
    "XU": "EA",
    "GB": "GB",
    "US": "US",
}

# ---------------------------------------------------------------------------
# Low-level: fetch and parse a BIS ZIP
# ---------------------------------------------------------------------------

def _fetch_bis_zip(dataset_key: str) -> pd.DataFrame | None:
    """Download a BIS flat CSV ZIP and return as DataFrame.  Returns None on failure."""
    url = BIS_ZIPS.get(dataset_key)
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=90)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
            return pd.read_csv(zf.open(csv_name), low_memory=False)
    except Exception as exc:
        logger.warning("BIS %s fetch failed: %s", dataset_key, exc)
        return None


def _parse_bis_flat(df: pd.DataFrame, iso2_filter: str | None = None,
                    freq: str = "A") -> pd.DataFrame:
    """Convert a BIS flat CSV to our standard {iso2, year, value} format.

    Parameters
    ----------
    df : DataFrame from BIS flat CSV
    iso2_filter : if set, only return rows for this ISO2 code
    freq : 'A' for annual, 'Q' for quarterly, 'M' for monthly
    """
    # Some BIS datasets use REF_AREA, others use BORROWERS_CTY for country
    col_area = next((c for c in df.columns if "REF_AREA" in c), None)
    if col_area is None:
        col_area = next((c for c in df.columns if "BORROWERS_CTY" in c), None)
    if col_area is None:
        raise KeyError("No REF_AREA or BORROWERS_CTY column found in BIS data")
    col_time = next(c for c in df.columns if "TIME_PERIOD" in c)
    col_val = next(c for c in df.columns if "OBS_VALUE" in c)
    col_freq = next((c for c in df.columns if "FREQ" in c), None)

    # Extract ISO2 code from "US: United States" format
    df = df.copy()
    df["iso2"] = df[col_area].str.extract(r"^([A-Z]{2}):")

    # Frequency filter
    if col_freq and freq:
        freq_prefix = {"A": "A:", "Q": "Q:", "M": "M:"}[freq]
        df = df[df[col_freq].str.startswith(freq_prefix, na=False)]

    # Parse value
    df["value"] = pd.to_numeric(df[col_val], errors="coerce")
    df = df[df["value"].notna()]

    # Parse time
    time_val = df[col_time]
    if freq == "A":
        df["year"] = pd.to_numeric(time_val, errors="coerce")
        df = df[df["year"].notna()]
        df["year"] = df["year"].astype(int)
    elif freq == "Q":
        # Format: 2024-Q4 → year + quarter
        parts = time_val.str.extract(r"^(\d{4})-Q(\d)$")
        df["year"] = pd.to_numeric(parts[0], errors="coerce")
        df = df[df["year"].notna()]
        df["year"] = df["year"].astype(int)

    if iso2_filter:
        df = df[df["iso2"] == iso2_filter]

    return df[["iso2", "year", "value"]].dropna()


# ---------------------------------------------------------------------------
# Exchange rate conversion
# ---------------------------------------------------------------------------

def _convert_fx(df: pd.DataFrame, iso2: str) -> pd.DataFrame:
    """Convert BIS exchange rates to standard FX convention.

    BIS reports ALL rates as "units of foreign currency per 1 USD".
    For EUR, GBP, AUD, NZD the standard quote is "USD per unit" → invert.
    For others (JPY, CHF, CAD, etc.) the standard is "units per USD" → keep as-is.
    """
    df = df.copy()
    if iso2 in INVERT_CURRENCIES:
        # Standard is USD/unit: e.g. EUR/USD = 1 / (EUR per USD)
        mask = df["value"] > 0
        df.loc[mask, "value"] = 1.0 / df.loc[mask, "value"]
    return df


# ---------------------------------------------------------------------------
# Public API — cached queries
# ---------------------------------------------------------------------------

@async_cached("bis_cpi")
async def get_cpi(iso2: str = "US", freq: str = "A") -> list[dict]:
    """Get CPI year-on-year % change for a country.

    Returns list of {date, value} dicts where value is YoY % change.
    """
    try:
        df = _fetch_bis_zip("cpi")
        if df is None:
            return []
        # Filter to YoY change measure (code 771)
        col_measure = next(c for c in df.columns if "MEASURE" in c.upper())
        df = df[df[col_measure].str.startswith("771:", na=False)]
        parsed = _parse_bis_flat(df, iso2_filter=iso2, freq=freq)
        return [
            {"date": str(int(r["year"])), "value": round(float(r["value"]), 4)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS CPI query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_policy")
async def get_policy_rate(iso2: str = "US") -> list[dict]:
    """Get central bank policy rate history for a country (monthly).

    Returns list of {date, value} dicts where value is % per year.
    """
    try:
        df = _fetch_bis_zip("policy")
        if df is None:
            return []
        parsed = _parse_bis_flat(df, iso2_filter=iso2, freq="M")
        # Keep monthly time format
        return [
            {"date": str(r["year"]), "value": round(float(r["value"]), 4)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS policy rate query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_fx")
async def get_fx_rate(iso2: str, freq: str = "A") -> list[dict]:
    """Get exchange rate vs USD for a currency (annual end-of-period).

    Returns list of {date, value} dicts in standard FX convention.
    BIS reports USD per foreign unit → converted to standard format.
    """
    try:
        df = _fetch_bis_zip("fx")
        if df is None:
            return []
        # End-of-period collection
        col_coll = next(c for c in df.columns if "COLLECTION" in c)
        df = df[df[col_coll].str.startswith("E:", na=False)]
        parsed = _parse_bis_flat(df, iso2_filter=iso2, freq=freq)
        parsed = _convert_fx(parsed, iso2)
        return [
            {"date": str(int(r["year"])), "value": round(float(r["value"]), 6)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS FX query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_credit_gap")
async def get_credit_gap(iso2: str = "US") -> list[dict]:
    """Get credit-to-GDP gap for a country (quarterly).

    Returns list of {date, value} dicts where value is % of GDP.
    """
    try:
        df = _fetch_bis_zip("credit_gap")
        if df is None:
            return []
        # Filter to credit-to-GDP gaps (C = gap: actual minus trend)
        col_type = next(c for c in df.columns if "CG_DTYPE" in c)
        df = df[df[col_type].str.startswith("C:", na=False)]
        # All sectors, private non-financial
        col_borrower = next(c for c in df.columns if "TC_BORROWERS" in c)
        df = df[df[col_borrower].str.startswith("P:", na=False)]
        parsed = _parse_bis_flat(df, iso2_filter=iso2, freq="Q")
        return [
            {"date": str(int(r["year"])), "value": round(float(r["value"]), 4)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS credit gap query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_property")
async def get_property_prices(iso2: str = "US", real: bool = True) -> list[dict]:
    """Get residential property price index for a country (quarterly, 2010=100).

    Returns list of {date, value} dicts.  Set real=False for nominal prices.
    BIS UNIT_MEASURE codes: 628 = index (2010=100), 771 = YoY% change.
    VALUE column: R = real, N = nominal.
    """
    try:
        df = _fetch_bis_zip("property")
        if df is None:
            return []
        # Filter to index measure (628), not YoY changes (771)
        col_measure = next(c for c in df.columns if "MEASURE" in c.upper())
        df = df[df[col_measure].str.startswith("628:", na=False)]
        # Filter real vs nominal via VALUE column
        col_value_type = next((c for c in df.columns if c.startswith("VALUE:")), None)
        if col_value_type:
            prefix = "R:" if real else "N:"
            df = df[df[col_value_type].str.startswith(prefix, na=False)]
        # Residential only (exclude commercial) via REF_SECTOR if present
        col_sector = next((c for c in df.columns if "REF_SECTOR" in c.upper()), None)
        if col_sector:
            df = df[df[col_sector].str.startswith("R:", na=False)]
        parsed = _parse_bis_flat(df, iso2_filter=iso2, freq="Q")
        return [
            {"date": str(r["year"]), "value": round(float(r["value"]), 2)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS property price query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_property_bulk")
async def get_property_prices_bulk(iso2_tuple: tuple[str, ...], real: bool = True) -> dict[str, list[dict]]:
    """Get residential property prices for multiple countries in one call.

    Returns {iso2: [{date, value}, ...]}.
    """
    iso2_list = list(iso2_tuple)
    result: dict[str, list[dict]] = {}
    try:
        df = _fetch_bis_zip("property")
        if df is None:
            return result
        # Filter to index measure (628), not YoY changes (771)
        col_measure = next(c for c in df.columns if "MEASURE" in c.upper())
        df = df[df[col_measure].str.startswith("628:", na=False)]
        # Filter real vs nominal via VALUE column
        col_value_type = next((c for c in df.columns if c.startswith("VALUE:")), None)
        if col_value_type:
            prefix = "R:" if real else "N:"
            df = df[df[col_value_type].str.startswith(prefix, na=False)]
        col_sector = next((c for c in df.columns if "REF_SECTOR" in c.upper()), None)
        if col_sector:
            df = df[df[col_sector].str.startswith("R:", na=False)]
        for iso2 in iso2_list:
            parsed = _parse_bis_flat(df, iso2_filter=iso2, freq="Q")
            if parsed.empty:
                continue
            result[iso2] = [
                {"date": str(r["year"]), "value": round(float(r["value"]), 2)}
                for _, r in parsed.iterrows()
            ]
        return result
    except Exception as exc:
        logger.warning("BIS property bulk query failed: %s", exc)
        return result


@async_cached("bis_credit_gap_bulk")
async def get_credit_gaps_bulk(iso2_tuple: tuple[str, ...]) -> dict[str, list[dict]]:
    """Get credit-to-GDP gaps for multiple countries in one call.

    Returns {iso2: [{date, value}, ...]} where value is gap in % of GDP.
    """
    iso2_list = list(iso2_tuple)
    result: dict[str, list[dict]] = {}
    try:
        df = _fetch_bis_zip("credit_gap")
        if df is None:
            return result
        # Filter to credit-to-GDP gaps (C = gap: actual minus trend)
        col_type = next(c for c in df.columns if "CG_DTYPE" in c)
        df = df[df[col_type].str.startswith("C:", na=False)]  # C = credit-to-GDP gaps
        # All sectors, private non-financial
        col_borrower = next(c for c in df.columns if "TC_BORROWERS" in c)
        df = df[df[col_borrower].str.startswith("P:", na=False)]
        for iso2 in iso2_list:
            parsed = _parse_bis_flat(df, iso2_filter=iso2, freq="Q")
            if parsed.empty:
                continue
            result[iso2] = [
                {"date": str(r["year"]), "value": round(float(r["value"]), 4)}
                for _, r in parsed.iterrows()
            ]
        return result
    except Exception as exc:
        logger.warning("BIS credit gap bulk query failed: %s", exc)
        return result


# ---------------------------------------------------------------------------
# Cross-border banking claims (Locational Banking Statistics)
# ---------------------------------------------------------------------------

@async_cached("bis_crossborder")
async def get_crossborder_claims() -> list[dict]:
    """Get top cross-border banking claims from BIS LBS data.

    Parses creditor (REF_AREA) → debtor (COUNTERPART_AREA) claims in USD.
    Filters to latest quarter, aggregates by country pair, returns top-20.

    Returns list of {creditor, debtor, value_usd} dicts sorted by value descending.
    """
    try:
        df = _fetch_bis_zip("crossborder")
        if df is None or df.empty:
            return []

        # Identify columns: creditor = REF_AREA, debtor = COUNTERPART_AREA
        col_creditor = next((c for c in df.columns if "REF_AREA" in c), None)
        col_debtor = next((c for c in df.columns if "COUNTERPART_AREA" in c), None)
        col_time = next((c for c in df.columns if "TIME_PERIOD" in c), None)
        col_val = next((c for c in df.columns if "OBS_VALUE" in c), None)
        col_freq = next((c for c in df.columns if "FREQ" in c), None)

        if not (col_creditor and col_debtor and col_time and col_val):
            logger.warning("BIS crossborder: missing required columns")
            return []

        df = df.copy()

        # Extract ISO2 codes from "US: United States" format
        df["creditor"] = df[col_creditor].str.extract(r"^([A-Z]{2}):")
        df["debtor"] = df[col_debtor].str.extract(r"^([A-Z]{2}):")

        # Filter to quarterly frequency
        if col_freq:
            df = df[df[col_freq].str.startswith("Q:", na=False)]

        # Parse value
        df["value"] = pd.to_numeric(df[col_val], errors="coerce")
        df = df[df["value"].notna()]

        # Parse time as proper quarterly for latest-quarter filtering
        parts = df[col_time].str.extract(r"^(\d{4})-Q(\d)$")
        df["year"] = pd.to_numeric(parts[0], errors="coerce")
        df["quarter"] = pd.to_numeric(parts[1], errors="coerce")
        df = df[df["year"].notna() & df["quarter"].notna()]
        df["year"] = df["year"].astype(int)
        df["quarter"] = df["quarter"].astype(int)

        if df.empty:
            return []

        # Get latest quarter
        max_row = df.loc[df["year"].idxmax()]
        latest_year = int(max_row["year"])
        latest_q = int(df[df["year"] == latest_year]["quarter"].max())
        df = df[(df["year"] == latest_year) & (df["quarter"] == latest_q)]

        # Aggregate by (creditor, debtor) pair
        grouped = df.groupby(["creditor", "debtor"])["value"].sum().reset_index()
        grouped = grouped.sort_values("value", ascending=False)

        # Return top-20
        claims = []
        for _, row in grouped.head(20).iterrows():
            claims.append({
                "creditor": str(row["creditor"]),
                "debtor": str(row["debtor"]),
                "value_usd": round(float(row["value"]), 1),
            })

        return claims
    except Exception as exc:
        logger.warning("BIS crossborder query failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Effective exchange rates (nominal broad indices, 2010=100)
# ---------------------------------------------------------------------------

@async_cached("bis_effective_fx_bulk")
async def get_effective_fx_bulk(iso2_tuple: tuple[str, ...]) -> dict[str, list[dict]]:
    """Get BIS nominal effective exchange rate indices for multiple countries.

    The BIS effective FX index is a trade-weighted basket (2010=100).
    Higher = stronger currency. Used to detect overvaluation vs long-term trend.

    Returns {iso2: [{date, value}, ...]} sorted by date ascending.
    Uses asyncio.to_thread to avoid blocking the event loop during HTTP fetch.
    """
    import asyncio as _asyncio

    iso2_list = list(iso2_tuple)
    result: dict[str, list[dict]] = {}
    try:
        df = await _asyncio.to_thread(_fetch_bis_zip, "fx_effective")
        if df is None or df.empty:
            return result

        # Filter to nominal broad index (measure N: Nominal, B: Broad)
        col_measure = next((c for c in df.columns if "MEASURE" in c.upper()), None)
        if col_measure:
            # EER nominal broad starts with "N:B:" in BIS data
            df = df[df[col_measure].str.startswith("N:B:", na=False)]

        for iso2 in iso2_list:
            parsed = _parse_bis_flat(df, iso2_filter=iso2, freq="A")
            if parsed.empty:
                continue
            pts = [
                {"date": str(int(r["year"])), "value": round(float(r["value"]), 2)}
                for _, r in parsed.iterrows()
            ]
            pts.sort(key=lambda p: p["date"])
            result[iso2] = pts
        return result
    except Exception as exc:
        logger.warning("BIS effective FX bulk query failed: %s", exc)
        return result
