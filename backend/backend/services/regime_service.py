"""Macro Regime Classifier — 2×2 Goldilocks matrix.

Classifies quarterly macro regime for a given country based on:
  - GDP growth (YoY %) vs threshold (default 2.0 %)
  - CPI inflation (YoY %) vs threshold (default 2.5 %)

Primary data source: World Bank (wb_gdp_growth.parquet, wb_inflation.parquet)
   — covers ~200 countries, annual, 1960–2024.
Augmented: FRED for US quarterly, Eurostat for EZ quarterly, FRED for JP quarterly.
   — these provide higher-frequency quarterly data when available.

Quadrants:
  Goldilocks  — growth >= gdp_thr AND inflation <  cpi_thr
  Overheating — growth >= gdp_thr AND inflation >= cpi_thr
  Slowdown    — growth <  gdp_thr AND inflation <  cpi_thr
  Stagflation — growth <  gdp_thr AND inflation >= cpi_thr
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import pandas as pd

from ..cache import cached
from ..config import FRED_API_KEY
from .bulk_data_service import DATA_DIR as _BULK_DIR

GDP_THRESHOLD = 2.0   # % YoY real GDP growth
CPI_THRESHOLD = 2.5   # % YoY CPI inflation


# ---------------------------------------------------------------------------
# Pure helper — tested independently; no I/O.
# ---------------------------------------------------------------------------

def classify_quadrant(
    gdp: float | None,
    cpi: float | None,
    gdp_thr: float = GDP_THRESHOLD,
    cpi_thr: float = CPI_THRESHOLD,
) -> str | None:
    """Return regime label or None if either input is missing."""
    if gdp is None or cpi is None:
        return None
    if gdp >= gdp_thr and cpi < cpi_thr:
        return "Goldilocks"
    if gdp >= gdp_thr and cpi >= cpi_thr:
        return "Overheating"
    if gdp < gdp_thr and cpi < cpi_thr:
        return "Slowdown"
    return "Stagflation"


# ---------------------------------------------------------------------------
# Numeric cleaner (mirrors services/metrics.py _clean).
# ---------------------------------------------------------------------------

def _clean(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)


# ---------------------------------------------------------------------------
# FRED fetchers (US).
# ---------------------------------------------------------------------------

def _fetch_fred_series(series_id: str, start_year: int) -> pd.Series:
    """Fetch a FRED series via fredapi or fall back to pandas-datareader."""
    start = f"{start_year}-01-01"
    # Primary: fredapi (faster, supports optional key)
    if FRED_API_KEY:
        try:
            from fredapi import Fred
            fred = Fred(api_key=FRED_API_KEY)
            s = fred.get_series(series_id, observation_start=start)
            if s is not None and len(s) > 0:
                return s
        except Exception:
            pass
    # Fallback: pandas-datareader (no key needed for FRED)
    try:
        import pandas_datareader.data as web
        df = web.DataReader(
            series_id, "fred",
            start=datetime(start_year, 1, 1),
            end=datetime.today(),
        )
        col = series_id if series_id in df.columns else df.columns[0]
        return df[col]
    except Exception:
        return pd.Series(dtype=float)


def _gdp_yoy_quarterly(start_year: int) -> pd.Series:
    """Real GDP (GDPC1) → quarterly YoY % change, indexed to quarter-end."""
    s = _fetch_fred_series("GDPC1", start_year - 1)  # extra year for YoY
    if s.empty:
        return pd.Series(dtype=float)
    s.index = pd.to_datetime(s.index)
    s = s.resample("QE").last().dropna()
    yoy = (s / s.shift(4) - 1.0) * 100.0
    return yoy.dropna()


def _cpi_yoy_quarterly(start_year: int) -> pd.Series:
    """CPI (CPIAUCSL, monthly) → YoY % change resampled to quarter-end."""
    s = _fetch_fred_series("CPIAUCSL", start_year - 1)
    if s.empty:
        return pd.Series(dtype=float)
    s.index = pd.to_datetime(s.index)
    # Monthly YoY first, then quarter-end
    monthly_yoy = (s / s.shift(12) - 1.0) * 100.0
    quarterly = monthly_yoy.resample("QE").last().dropna()
    return quarterly


# ---------------------------------------------------------------------------
# Eurozone best-effort via eurostat lib.
# ---------------------------------------------------------------------------

def _eurostat_row(code: str, filters: dict) -> pd.Series:
    """One series from the Eurostat API as {period label: value}.

    Filtered queries return a single row in a few seconds; the unfiltered
    tables are hundreds of megabytes and took ~2 minutes, longer than the
    proxy timeout, so the euro-area regime never loaded (audit D-42).
    """
    import eurostat  # type: ignore[import]

    df = eurostat.get_data_df(code, filter_pars=filters)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    row = df.iloc[0]
    vals = {str(c): float(row[c]) for c in df.columns
            if str(c)[:1].isdigit() and pd.notna(row[c])}
    return pd.Series(vals, dtype=float)


def _fetch_eurozone(start_year: int) -> tuple[pd.Series, pd.Series, str]:
    """
    Returns (gdp_yoy_quarterly, cpi_yoy_quarterly, source_label).
    Returns empty series with a note on failure.
    """
    gdp_q = pd.Series(dtype=float)
    cpi_q = pd.Series(dtype=float)
    source_parts: list[str] = []
    since = str(start_year - 1)

    # GDP: namq_10_gdp — quarterly real GDP, chain-linked volumes, seasonally
    # and calendar adjusted, euro area (20 countries).
    try:
        levels = _eurostat_row("namq_10_gdp", {
            "geo": ["EA20"], "unit": ["CLV10_MEUR"], "s_adj": ["SCA"], "na_item": ["B1GQ"],
            "startPeriod": f"{since}-Q1"})
        if not levels.empty:
            levels.index = [pd.Period(q, freq="Q").to_timestamp(how="end").normalize() for q in levels.index]
            levels = levels.sort_index()
            gdp_q = ((levels / levels.shift(4) - 1.0) * 100.0).dropna()
            source_parts.append("Eurostat namq_10_gdp (EA20, B1GQ, CLV10_MEUR, SCA)")
    except Exception:
        pass

    # CPI: prc_hicp_minr — HICP all items, annual rate of change, euro area.
    # (prc_hicp_midx, the previous dataset, stopped at 2025-12 when Eurostat
    # moved HICP to the 2018 COICOP classification.)
    try:
        yoy = _eurostat_row("prc_hicp_minr", {
            "geo": ["EA"], "coicop18": ["TOTAL"], "unit": ["RCH_A"], "startPeriod": f"{since}-01"})
        if not yoy.empty:
            yoy.index = [pd.Period(m, freq="M").to_timestamp(how="end").normalize() for m in yoy.index]
            cpi_q = yoy.sort_index().resample("QE").last().dropna()
            source_parts.append("Eurostat prc_hicp_minr (EA, TOTAL, RCH_A)")
    except Exception:
        pass

    source = "; ".join(source_parts) if source_parts else "Eurostat (no data retrieved)"
    return gdp_q, cpi_q, source


# ---------------------------------------------------------------------------
# World Bank bulk-data fallback — covers ~200 countries (annual)
# ---------------------------------------------------------------------------

# The bulk directory differs between Docker and the desktop build; a
# hard-coded container path left every non-US regime empty on desktop.
_WB_GDP_PATH = _BULK_DIR / "wb_gdp_growth.parquet"
_WB_CPI_PATH = _BULK_DIR / "wb_inflation.parquet"


def _fetch_wb_country(iso2: str, start_year: int) -> tuple[pd.Series, pd.Series, str]:
    """Read annual GDP growth and CPI inflation from World Bank parquet files."""
    gdp_s = pd.Series(dtype=float)
    cpi_s = pd.Series(dtype=float)
    source = "World Bank (bulk)"

    # Convert iso2 → iso3 (World Bank uses 3-letter codes)
    try:
        import pycountry
        c = pycountry.countries.get(alpha_2=iso2)
        iso3 = c.alpha_3 if c else iso2
    except Exception:
        iso3 = iso2

    try:
        if _WB_GDP_PATH.exists():
            wb_gdp = pd.read_parquet(_WB_GDP_PATH)
            mask = (wb_gdp["iso3"] == iso3) & (wb_gdp["year"] >= start_year)
            gdp_rows = wb_gdp[mask][["year", "value"]].dropna()
            if not gdp_rows.empty:
                gdp_s = pd.Series(gdp_rows["value"].values, index=gdp_rows["year"].values)
                gdp_s.index = pd.to_datetime(gdp_s.index.astype(str) + "-12-31")
        if _WB_CPI_PATH.exists():
            wb_cpi = pd.read_parquet(_WB_CPI_PATH)
            mask = (wb_cpi["iso3"] == iso3) & (wb_cpi["year"] >= start_year)
            cpi_rows = wb_cpi[mask][["year", "value"]].dropna()
            if not cpi_rows.empty:
                cpi_s = pd.Series(cpi_rows["value"].values, index=cpi_rows["year"].values)
                cpi_s.index = pd.to_datetime(cpi_s.index.astype(str) + "-12-31")
    except Exception:
        source = "World Bank (error reading parquet)"
    return gdp_s, cpi_s, source

def _fetch_japan(start_year: int) -> tuple[pd.Series, pd.Series, str]:
    """
    Returns (gdp_yoy_quarterly, cpi_yoy_quarterly, source_label).
    Uses OECD QNA (quarterly national accounts) + CPI via pandas-datareader.
    Returns empty series with a note on failure.
    """
    gdp_q = pd.Series(dtype=float)
    cpi_q = pd.Series(dtype=float)
    source_parts: list[str] = []

    # GDP: OECD via pandas-datareader
    try:
        import pandas_datareader.data as web
        # OECD QNA — Japan real GDP, quarterly growth
        df = web.DataReader(
            "JPNRGDPEXP",
            "fred",
            start=datetime(start_year - 1, 1, 1),
            end=datetime.today(),
        )
        s = df.iloc[:, 0].dropna()
        if len(s) > 4:
            s.index = pd.to_datetime(s.index)
            s = s.resample("QE").last().dropna()
            gdp_q = ((s / s.shift(4) - 1.0) * 100.0).dropna()
            source_parts.append("FRED JPNRGDPEXP")
    except Exception:
        pass

    # CPI: BIS consumer prices, year-on-year, monthly. (FRED's OECD series
    # JPNCPIALLMINMEI stopped in June 2021, which left Japan with no regime.)
    try:
        from ..sources import source_bis
        pts = source_bis.cpi_yoy("JP", "M")
        if pts:
            yoy = pd.Series({pd.Period(p["date"], freq="M").to_timestamp(how="end").normalize(): p["value"]
                             for p in pts}).sort_index()
            cpi_q = yoy[yoy.index.year >= start_year - 1].resample("QE").last().dropna()
            source_parts.append("BIS WS_LONG_CPI (JP, year-on-year)")
    except Exception:
        pass

    source = "; ".join(source_parts) if source_parts else "FRED/OECD (Japan data unavailable)"
    return gdp_q, cpi_q, source


# ---------------------------------------------------------------------------
# Main public function.
# ---------------------------------------------------------------------------

@cached("regime_series", skip_if=lambda r: not r.get("series"))
def regime_series(
    country: str = "US",
    start_year: int = 2000,
    gdp_thr: float = GDP_THRESHOLD,
    cpi_thr: float = CPI_THRESHOLD,
) -> dict:
    """
    Return a time series classifying quarterly macro regime for *country*
    from *start_year* to today.

    Data sources (best available per country):
      US — FRED quarterly (GDPC1, CPIAUCSL)
      EZ/EA — Eurostat quarterly (namq_10_gdp, prc_hicp_minr)
      JP — FRED quarterly GDP (JPNRGDPEXP), BIS monthly CPI
      ALL OTHERS — World Bank annual (wb_gdp_growth, wb_inflation parquet)
    """
    note: str | None = None
    source_label = ""

    country = country.upper()

    # --- Fetch raw series ---------------------------------------------------
    if country == "US":
        gdp_q = _gdp_yoy_quarterly(start_year)
        cpi_q = _cpi_yoy_quarterly(start_year)
        source_label = "FRED (GDPC1, CPIAUCSL)"
    elif country in ("EZ", "EA"):
        gdp_q, cpi_q, source_label = _fetch_eurozone(start_year)
        if gdp_q.empty and cpi_q.empty:
            note = f"Eurozone data unavailable: {source_label}"
    elif country == "JP":
        gdp_q, cpi_q, source_label = _fetch_japan(start_year)
        if gdp_q.empty and cpi_q.empty:
            note = f"Japan data unavailable: {source_label}"
    else:
        # World Bank annual data — works for ~200 countries
        gdp_q, cpi_q, source_label = _fetch_wb_country(country, start_year)
        if gdp_q.empty and cpi_q.empty:
            return {
                "country": country,
                "thresholds": {"gdp": gdp_thr, "cpi": cpi_thr},
                "series": [],
                "current": None,
                "source": source_label,
                "asOf": None,
                "note": f"No World Bank data for {country}.",
            }

    # --- Align to common quarterly index ------------------------------------
    def _dated(x: pd.Series) -> pd.Series:
        # An empty series has a non-datetime index; joining it with a dated
        # one produced an object index and wiped the whole frame.
        x = x.copy()
        x.index = pd.to_datetime(x.index).normalize() if len(x) else pd.DatetimeIndex([])
        return x

    start_ts = pd.Timestamp(f"{start_year}-01-01")
    df = pd.concat([_dated(gdp_q).rename("gdpGrowth"), _dated(cpi_q).rename("cpiInflation")], axis=1)
    # Periods that have not ended yet are dropped: the in-progress quarter
    # carried a quarter-end date for what was really a mid-quarter CPI print.
    df = df[(df.index >= start_ts) & (df.index < pd.Timestamp(date.today()))].sort_index()

    # Drop rows where BOTH are NaN
    df = df.dropna(how="all")

    # Build series list
    series: list[dict] = []
    for ts, row in df.iterrows():
        gdp_val = _clean(row["gdpGrowth"])
        cpi_val = _clean(row["cpiInflation"])
        quadrant = classify_quadrant(gdp_val, cpi_val, gdp_thr, cpi_thr)
        series.append({
            "date": ts.strftime("%Y-%m-%d"),  # type: ignore[union-attr]
            "gdpGrowth": gdp_val,
            "cpiInflation": cpi_val,
            "quadrant": quadrant,
        })

    # The current regime is the latest period with both readings. GDP is
    # published later than CPI, so the very last row is usually CPI-only and
    # unclassified; reporting it as "current" showed no regime at all.
    current = next((p for p in reversed(series) if p["quadrant"] is not None), None)

    return {
        "country": country,
        "thresholds": {"gdp": gdp_thr, "cpi": cpi_thr},
        "series": series,
        "current": current,
        "source": source_label,
        "asOf": current["date"] if current else None,
        "note": note,
    }
