"""Macro Regime Classifier — 2×2 Goldilocks matrix.

Classifies quarterly macro regime for a given country based on:
  - GDP growth (YoY %) vs threshold (default 2.0 %)
  - CPI inflation (YoY %) vs threshold (default 2.5 %)

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

from ..config import FRED_API_KEY

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

def _fetch_eurozone(start_year: int) -> tuple[pd.Series, pd.Series, str]:
    """
    Returns (gdp_yoy_quarterly, cpi_yoy_quarterly, source_label).
    Returns empty series with a note on failure.
    """
    try:
        import eurostat  # type: ignore[import]
    except ImportError:
        return pd.Series(dtype=float), pd.Series(dtype=float), "eurostat lib not installed"

    gdp_q = pd.Series(dtype=float)
    cpi_q = pd.Series(dtype=float)
    source_parts: list[str] = []

    # GDP: namq_10_gdp — quarterly real GDP, chain-linked volumes, seasonally adjusted
    try:
        df_gdp = eurostat.get_data_df("namq_10_gdp")
        if df_gdp is not None and not df_gdp.empty:
            # Filter: unit=CLV10_MEUR, s_adj=SCA, na_item=B1GQ, geo=EA20 or EA19
            mask = (
                (df_gdp.get("unit", pd.Series()) == "CLV10_MEUR") &
                (df_gdp.get("s_adj", pd.Series()).isin(["SCA", "SA"])) &
                (df_gdp.get("na_item", pd.Series()) == "B1GQ") &
                (df_gdp.get("geo\\TIME_PERIOD", df_gdp.get("geo", pd.Series())).isin(["EA20", "EA19", "EA"]))
            )
            row = df_gdp[mask]
            if row.empty:
                raise ValueError("no matching EA GDP row")
            # Time columns are like "2024-Q1"
            time_cols = [c for c in row.columns if c and str(c)[0].isdigit()]
            vals: dict[pd.Timestamp, float] = {}
            for col in time_cols:
                try:
                    ts = pd.Period(col, freq="Q").to_timestamp(how="end")
                    v = float(row[col].iloc[0])
                    if not math.isnan(v):
                        vals[ts] = v
                except Exception:
                    continue
            if vals:
                gdp_levels = pd.Series(vals).sort_index()
                gdp_yoy = (gdp_levels / gdp_levels.shift(4) - 1.0) * 100.0
                gdp_q = gdp_yoy.dropna()
                source_parts.append("Eurostat namq_10_gdp")
    except Exception:
        pass

    # CPI: prc_hicp_midx — HICP monthly index, all items (CP00), EA
    try:
        df_cpi = eurostat.get_data_df("prc_hicp_midx")
        if df_cpi is not None and not df_cpi.empty:
            coicop_col = "coicop" if "coicop" in df_cpi.columns else None
            geo_col = next((c for c in df_cpi.columns if "geo" in c.lower()), None)
            unit_col = "unit" if "unit" in df_cpi.columns else None

            mask_cpi = pd.Series([True] * len(df_cpi), index=df_cpi.index)
            if coicop_col:
                mask_cpi &= df_cpi[coicop_col] == "CP00"
            if unit_col:
                mask_cpi &= df_cpi[unit_col] == "I15"
            if geo_col:
                mask_cpi &= df_cpi[geo_col].isin(["EA20", "EA19", "EA"])
            row_cpi = df_cpi[mask_cpi]
            if row_cpi.empty:
                raise ValueError("no matching EA CPI row")
            time_cols_c = [c for c in row_cpi.columns if c and str(c)[0].isdigit()]
            cpi_vals: dict[pd.Timestamp, float] = {}
            for col in time_cols_c:
                try:
                    ts = pd.Period(col, freq="M").to_timestamp(how="end")
                    v = float(row_cpi[col].iloc[0])
                    if not math.isnan(v):
                        cpi_vals[ts] = v
                except Exception:
                    continue
            if cpi_vals:
                cpi_levels = pd.Series(cpi_vals).sort_index()
                cpi_yoy = (cpi_levels / cpi_levels.shift(12) - 1.0) * 100.0
                cpi_q = cpi_yoy.resample("QE").last().dropna()
                source_parts.append("Eurostat prc_hicp_midx")
    except Exception:
        pass

    source = "; ".join(source_parts) if source_parts else "Eurostat (no data retrieved)"
    return gdp_q, cpi_q, source


# ---------------------------------------------------------------------------
# Japan best-effort via pandas-datareader / OECD.
# ---------------------------------------------------------------------------

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

    # CPI: FRED JPNCPIALLMINMEI (Japan CPI, monthly)
    try:
        import pandas_datareader.data as web
        df_cpi = web.DataReader(
            "JPNCPIALLMINMEI",
            "fred",
            start=datetime(start_year - 1, 1, 1),
            end=datetime.today(),
        )
        s_cpi = df_cpi.iloc[:, 0].dropna()
        if len(s_cpi) > 12:
            s_cpi.index = pd.to_datetime(s_cpi.index)
            yoy = (s_cpi / s_cpi.shift(12) - 1.0) * 100.0
            cpi_q = yoy.resample("QE").last().dropna()
            source_parts.append("FRED JPNCPIALLMINMEI")
    except Exception:
        pass

    source = "; ".join(source_parts) if source_parts else "FRED/OECD (Japan data unavailable)"
    return gdp_q, cpi_q, source


# ---------------------------------------------------------------------------
# Main public function.
# ---------------------------------------------------------------------------

def regime_series(
    country: str = "US",
    start_year: int = 2000,
    gdp_thr: float = GDP_THRESHOLD,
    cpi_thr: float = CPI_THRESHOLD,
) -> dict:
    """
    Return a time series classifying quarterly macro regime for *country*
    from *start_year* to today.

    Supported: US (FRED), EZ (Eurozone, Eurostat), JP (Japan, FRED/OECD).
    All other codes return empty series with a note.
    """
    today_str = date.today().isoformat()
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
        return {
            "country": country,
            "thresholds": {"gdp": gdp_thr, "cpi": cpi_thr},
            "series": [],
            "current": None,
            "source": "N/A",
            "asOf": today_str,
            "note": f"Country '{country}' not supported. Supported: US, EZ, JP.",
        }

    # --- Align to common quarterly index ------------------------------------
    if not gdp_q.empty:
        gdp_q.index = pd.to_datetime(gdp_q.index).normalize()
    if not cpi_q.empty:
        cpi_q.index = pd.to_datetime(cpi_q.index).normalize()

    # Outer join on quarter-end dates; include only dates >= start_year
    start_ts = pd.Timestamp(f"{start_year}-01-01")
    df = pd.DataFrame({"gdpGrowth": gdp_q, "cpiInflation": cpi_q})
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        df = df.reindex(pd.DatetimeIndex([]))
    df = df[df.index >= start_ts].sort_index()

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

    current = series[-1] if series else None

    return {
        "country": country,
        "thresholds": {"gdp": gdp_thr, "cpi": cpi_thr},
        "series": series,
        "current": current,
        "source": source_label,
        "asOf": today_str,
        "note": note,
    }
