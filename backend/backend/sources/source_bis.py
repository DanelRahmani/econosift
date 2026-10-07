"""BIS (Bank for International Settlements) data source.

Uses the BIS bulk CSV ZIP downloads for historical data, with graceful
fallback.  All BIS exchange rates are reported as "units of foreign currency
per 1 USD" and are converted to standard FX conventions:
  - EUR/USD, GBP/USD, AUD/USD, NZD/USD → inverted (1 / BIS value)
  - USD/JPY, USD/CHF, USD/CAD, etc. → used directly (already correct)
"""
from __future__ import annotations

import asyncio
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
    """Download a BIS flat CSV ZIP and return as DataFrame.  Returns None on failure.

    Blocking for seconds (multi-MB download + parse): async callers must run it
    via ``asyncio.to_thread`` or every other request stalls meanwhile.
    """
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
    """Convert a BIS flat CSV to {iso2, year, value, period}.

    ``period`` is the BIS time label at its own resolution ("2024",
    "2024-Q4", "2024-03"), so sub-annual observations keep distinct dates
    (previously quarterly points were all labelled with the bare year, and
    monthly data had no ``year`` at all, so monthly requests always failed —
    audit D-24/D-25).

    Parameters
    ----------
    df : DataFrame from BIS flat CSV
    iso2_filter : if set, only return rows for this ISO2 code
    freq : 'A' for annual, 'Q' for quarterly, 'M' for monthly, 'D' for daily
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
        freq_prefix = {"A": "A:", "Q": "Q:", "M": "M:", "D": "D:"}[freq]
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
    elif freq in ("Q", "M", "D"):
        # Formats: 2024-Q4 (quarterly), 2024-03 (monthly), 2024-03-15 (daily)
        parts = time_val.astype(str).str.extract(r"^(\d{4})-(?:Q\d|\d{2}(?:-\d{2})?)$")
        df["year"] = pd.to_numeric(parts[0], errors="coerce")
        df = df[df["year"].notna()]
        df["year"] = df["year"].astype(int)
    df["period"] = df[col_time].astype(str)

    if iso2_filter:
        df = df[df["iso2"] == iso2_filter]

    return df[["iso2", "year", "value", "period"]].dropna().sort_values("period")


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

def cpi_yoy(iso2: str = "US", freq: str = "A") -> list[dict]:
    """CPI year-on-year % change for a country: [{date, value}] (synchronous)."""
    try:
        df = _fetch_bis_zip("cpi")
        if df is None:
            return []
        # Filter to YoY change measure (code 771)
        col_measure = next(c for c in df.columns if "MEASURE" in c.upper())
        df = df[df[col_measure].str.startswith("771:", na=False)]
        parsed = _parse_bis_flat(df, iso2_filter=iso2, freq=freq)
        return [
            {"date": str(r["period"]), "value": round(float(r["value"]), 4)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS CPI query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_cpi")
async def get_cpi(iso2: str = "US", freq: str = "A") -> list[dict]:
    """Get CPI year-on-year % change for a country.

    Returns list of {date, value} dicts where value is YoY % change.
    """
    return await asyncio.to_thread(cpi_yoy, iso2, freq)


def _parse_policy_rates(df: pd.DataFrame, iso2_list: list[str]) -> dict[str, dict]:
    """Per-country official policy-rate history from the BIS WS_CBPOL flat file.

    Uses the daily series when a country has one, else the monthly one (monthly
    periods are dated the 1st). Returns ``{iso2: {"points": [{date, value}],
    "compilation": str | None}}``; countries without data are omitted.
    """
    col_area = next(c for c in df.columns if "REF_AREA" in c)
    col_comp = next((c for c in df.columns if "COMPILATION" in c), None)
    # Cut the ~730k-row file down to the requested areas once: parsing the
    # whole frame per country took ~2 minutes and timed the tracker out.
    keep_cols = [c for c in df.columns
                 if any(k in c for k in ("REF_AREA", "FREQ", "TIME_PERIOD", "OBS_VALUE", "COMPILATION"))]
    area = df[col_area].astype(str).str[:2]
    df = df.loc[area.isin(set(iso2_list)), keep_cols]
    area = area[df.index]
    # Three years cover the 3m/12m changes and the staleness check; older daily
    # history only bloats the cached payload.
    since = (pd.Timestamp.today() - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    result: dict[str, dict] = {}
    for iso2 in iso2_list:
        own = df[area == iso2]
        for freq in ("D", "M"):
            parsed = _parse_bis_flat(own, iso2_filter=iso2, freq=freq)
            if parsed.empty:
                continue
            points = [
                {"date": d, "value": round(float(v), 4)}
                for d, v in ((p if len(p) == 10 else f"{p}-01", v) for p, v in zip(parsed["period"], parsed["value"]))
                if d >= since
            ]
            if not points:
                continue
            compilation = None
            if col_comp:
                notes = own[col_comp].dropna()
                compilation = str(notes.iloc[0]) if len(notes) else None
            result[iso2] = {"points": points, "compilation": compilation}
            break
    return result


@async_cached("bis_policy_rates")
async def get_policy_rates_bulk(iso2_tuple: tuple[str, ...]) -> dict[str, dict]:
    """Official central-bank policy rates for several countries from one BIS download.

    Returns ``{iso2: {"points": [{date, value}], "compilation": str | None}}``
    (daily series where available, else monthly); ``{}`` if BIS is unreachable.
    """
    try:
        df = await asyncio.to_thread(_fetch_bis_zip, "policy")
        if df is None or df.empty:
            return {}
        return await asyncio.to_thread(_parse_policy_rates, df, list(iso2_tuple))
    except Exception as exc:
        logger.warning("BIS policy rates bulk query failed: %s", exc)
        return {}


@async_cached("bis_policy")
async def get_policy_rate(iso2: str = "US") -> list[dict]:
    return await asyncio.to_thread(_get_policy_rate_sync, iso2)


def _get_policy_rate_sync(iso2: str = "US") -> list[dict]:
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
            {"date": str(r["period"]), "value": round(float(r["value"]), 4)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS policy rate query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_fx")
async def get_fx_rate(iso2: str, freq: str = "A") -> list[dict]:
    return await asyncio.to_thread(_get_fx_rate_sync, iso2, freq)


def _get_fx_rate_sync(iso2: str, freq: str = "A") -> list[dict]:
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
            {"date": str(r["period"]), "value": round(float(r["value"]), 6)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS FX query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_credit_gap")
async def get_credit_gap(iso2: str = "US") -> list[dict]:
    return await asyncio.to_thread(_get_credit_gap_sync, iso2)


def _get_credit_gap_sync(iso2: str = "US") -> list[dict]:
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
            {"date": str(r["period"]), "value": round(float(r["value"]), 4)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS credit gap query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_property")
async def get_property_prices(iso2: str = "US", real: bool = True) -> list[dict]:
    return await asyncio.to_thread(_get_property_prices_sync, iso2, real)


def _get_property_prices_sync(iso2: str = "US", real: bool = True) -> list[dict]:
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
            {"date": str(r["period"]), "value": round(float(r["value"]), 2)}
            for _, r in parsed.iterrows()
        ]
    except Exception as exc:
        logger.warning("BIS property price query failed for %s: %s", iso2, exc)
        return []


@async_cached("bis_property_bulk")
async def get_property_prices_bulk(iso2_tuple: tuple[str, ...], real: bool = True) -> dict[str, list[dict]]:
    return await asyncio.to_thread(_get_property_prices_bulk_sync, iso2_tuple, real)


def _get_property_prices_bulk_sync(iso2_tuple: tuple[str, ...], real: bool = True) -> dict[str, list[dict]]:
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
                {"date": str(r["period"]), "value": round(float(r["value"]), 2)}
                for _, r in parsed.iterrows()
            ]
        return result
    except Exception as exc:
        logger.warning("BIS property bulk query failed: %s", exc)
        return result


@async_cached("bis_credit_gap_bulk")
async def get_credit_gaps_bulk(iso2_tuple: tuple[str, ...]) -> dict[str, list[dict]]:
    return await asyncio.to_thread(_get_credit_gaps_bulk_sync, iso2_tuple)


def _get_credit_gaps_bulk_sync(iso2_tuple: tuple[str, ...]) -> dict[str, list[dict]]:
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
                {"date": str(r["period"]), "value": round(float(r["value"]), 4)}
                for _, r in parsed.iterrows()
            ]
        return result
    except Exception as exc:
        logger.warning("BIS credit gap bulk query failed: %s", exc)
        return result


# ---------------------------------------------------------------------------
# Cross-border banking claims (Locational Banking Statistics)
# ---------------------------------------------------------------------------

# Bilateral cross-border claims, latest observation per reporter/counterparty
# pair, from the BIS SDMX API. Key dimensions: quarterly, amounts outstanding
# (S), total claims (C), all instruments, all currencies (TO1), all parent
# countries (5J), all reporting banks, <reporting country>, all counterparty
# sectors, <counterparty country>, cross-border positions (N).
_LBS_URL = ("https://stats.bis.org/api/v1/data/WS_LBS_D_PUB/"
            "Q.S.C.A.TO1.A.5J.A..A..N/all?lastNObservations=1")
_LBS_ALL_REPORTERS, _LBS_ALL_COUNTRIES = "5A", "5J"


def _parse_lbs(csv_text: str, top: int = 60) -> dict:
    """Latest-quarter bilateral claims from a BIS LBS SDMX-CSV response."""
    df = pd.read_csv(io.StringIO(csv_text), dtype={"L_REP_CTY": str, "L_CP_COUNTRY": str})
    df["value"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df[df["value"].notna()]
    if df.empty:
        return {}
    # Each series reports its own last observation; discontinued pairs carry
    # years-old quarters, so keep only the latest one.
    period = df["TIME_PERIOD"].max()
    df = df[df["TIME_PERIOD"] == period]
    scale = 10.0 ** 6  # UNIT_MULT=6: values are USD millions

    total = df[(df["L_REP_CTY"] == _LBS_ALL_REPORTERS) & (df["L_CP_COUNTRY"] == _LBS_ALL_COUNTRIES)]
    # Two-letter alphabetic codes are countries; codes with a digit (5A, 5J,
    # 1C ...) are BIS aggregates and would double count their members.
    is_country = lambda col: df[col].str.fullmatch(r"[A-Z]{2}", na=False)  # noqa: E731
    pairs = df[is_country("L_REP_CTY") & is_country("L_CP_COUNTRY")].sort_values("value", ascending=False)
    return {
        "period": str(period),
        "totalUsd": float(total["value"].iloc[0]) * scale if len(total) else None,
        "pairCount": int(len(pairs)),
        "claims": [
            {"creditor": r.L_REP_CTY, "debtor": r.L_CP_COUNTRY, "value_usd": round(float(r.value) * scale)}
            for r in pairs.head(top).itertuples()
        ],
    }


@async_cached("bis_crossborder")
async def get_crossborder_claims() -> dict:
    """Largest bilateral cross-border bank claims (BIS Locational Banking Statistics).

    Returns ``{period, totalUsd, pairCount, claims: [{creditor, debtor,
    value_usd}]}`` (ISO2 codes, claims of banks located in ``creditor`` on
    residents of ``debtor``, in USD), or ``{}`` when BIS is unreachable.

    Queries the BIS SDMX API for exactly the total-claims series. The previous
    implementation downloaded a bulk file that no longer exists and summed
    every instrument/currency/sector breakdown of a pair together, counting
    each claim many times over (audit D-26).
    """
    import asyncio as _asyncio

    def _fetch() -> dict:
        resp = httpx.get(_LBS_URL, timeout=90,
                         headers={"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"})
        resp.raise_for_status()
        return _parse_lbs(resp.text)

    try:
        return await _asyncio.to_thread(_fetch)
    except Exception as exc:
        logger.warning("BIS cross-border claims query failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Effective exchange rates (real broad indices, 2020=100, monthly)
# ---------------------------------------------------------------------------

def _parse_eer(df: pd.DataFrame, iso2_list: list[str]) -> dict[str, list[dict]]:
    """Monthly real broad EER per country from the BIS WS_EER flat file."""
    col = lambda name: next(c for c in df.columns if c.startswith(name))  # noqa: E731
    # The file mixes nominal/real, narrow/broad and monthly/daily series for
    # every country; pick exactly one of each.
    df = df[df[col("EER_TYPE")].str.startswith("R:", na=False)
            & df[col("EER_BASKET")].str.startswith("B:", na=False)]
    result: dict[str, list[dict]] = {}
    for iso2 in iso2_list:
        parsed = _parse_bis_flat(df, iso2_filter=iso2, freq="M")
        if not parsed.empty:
            result[iso2] = [{"date": str(r.period), "value": round(float(r.value), 2)}
                            for r in parsed.itertuples()]
    return result


@async_cached("bis_effective_fx_bulk")
async def get_effective_fx_bulk(iso2_tuple: tuple[str, ...]) -> dict[str, list[dict]]:
    """BIS real effective exchange rate indices (broad basket) for several countries.

    A CPI-deflated, trade-weighted index (2020=100); higher = stronger in real
    terms, which is what an overvaluation signal needs. Monthly averages.

    Returns {iso2: [{date: "YYYY-MM", value}, ...]} sorted by date ascending.
    (Previously this filtered on a ``MEASURE`` column the file does not have
    and then on annual frequency, which the file does not contain either, so
    it always returned nothing — audit D-27.)
    """
    import asyncio as _asyncio

    try:
        df = await _asyncio.to_thread(_fetch_bis_zip, "fx_effective")
        if df is None or df.empty:
            return {}
        return await _asyncio.to_thread(_parse_eer, df, list(iso2_tuple))
    except Exception as exc:
        logger.warning("BIS effective FX bulk query failed: %s", exc)
        return {}
