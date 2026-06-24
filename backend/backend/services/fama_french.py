"""Fama-French 3-factor and 5-factor attribution service.

Downloads daily Ken French factor CSVs, aligns them with ticker returns, and
runs OLS regressions to produce per-ticker alpha / beta / R² attribution.

NOTE: The existing `backend.sources.source_datareader.fama_french()` fetches
*annual* FF factors for macro display via pandas-datareader; this module is a
separate, richer service that downloads the *daily* factor CSVs directly from
Ken French's data library and performs OLS regression. The two coexist without
conflict.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from typing import Literal

import numpy as np
import pandas as pd
import requests

from ..cache import cached
from .metrics import _clean

# ---------------------------------------------------------------------------
# Ken French data library URLs (daily factor CSVs)
# ---------------------------------------------------------------------------
_FF3_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_daily_CSV.zip"
)
_FF5_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AxiomFinance/1.0 (research use)"
    )
}
_TIMEOUT = 30  # seconds

# Column names after parsing
_FF3_COLS = ["Mkt-RF", "SMB", "HML", "RF"]
_FF5_COLS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Factor data loader
# ---------------------------------------------------------------------------

def _parse_ff_csv(raw_bytes: bytes, expected_cols: list[str]) -> pd.DataFrame:
    """Parse a Ken French daily CSV file from raw bytes.

    These CSVs have a text preamble (copyright notice, description) before
    the data table. We skip header rows until we find the first line whose
    first field is an 8-digit date (YYYYMMDD).

    Factor values are in percent; we divide by 100 to return decimals.
    """
    text = raw_bytes.decode("latin-1")
    lines = text.splitlines()

    # Find the first data row: a line where the first comma-delimited token is
    # an 8-digit integer (e.g. "19260701").
    data_start = None
    for i, line in enumerate(lines):
        token = line.split(",")[0].strip()
        if token.isdigit() and len(token) == 8:
            data_start = i
            break

    if data_start is None:
        raise ValueError("Could not locate data rows in Ken French CSV")

    # The header row is immediately before the first data row.
    header_idx = data_start - 1

    # Read just the relevant portion as CSV.
    csv_text = "\n".join(lines[header_idx:])
    df = pd.read_csv(
        io.StringIO(csv_text),
        header=0,
        index_col=0,
    )

    # Drop any trailing rows that are not 8-digit dates (annual averages etc.)
    df.index = df.index.astype(str).str.strip()
    mask = df.index.str.match(r"^\d{8}$")
    df = df.loc[mask].copy()

    # Parse index as dates.
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "Date"

    # Strip whitespace from column names.
    df.columns = [c.strip() for c in df.columns]

    # Keep only the expected columns (some CSVs include extra).
    available = [c for c in expected_cols if c in df.columns]
    df = df[available].copy()

    # Convert from percent to decimal.
    df = df.astype(float) / 100.0

    return df


@cached("ff_factors")
def load_ff_factors(model: Literal["3", "5"] = "3") -> pd.DataFrame | None:
    """Download and parse daily Ken French factor data.

    Parameters
    ----------
    model : "3" or "5"
        Which factor model to load.

    Returns
    -------
    pd.DataFrame | None
        DataFrame indexed by date with factor columns as decimals, or None if
        the download fails (caller handles None; we do NOT fabricate data).

    Columns
    -------
    3-factor: Mkt-RF, SMB, HML, RF
    5-factor: Mkt-RF, SMB, HML, RMW, CMA, RF
    """
    url = _FF5_URL if model == "5" else _FF3_URL
    expected_cols = _FF5_COLS if model == "5" else _FF3_COLS

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception:
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            # There is typically one CSV file inside the ZIP.
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                return None
            raw = zf.read(csv_names[0])
    except Exception:
        return None

    try:
        return _parse_ff_csv(raw, expected_cols)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# OLS regression helper
# ---------------------------------------------------------------------------

def _ols(y: np.ndarray, X: np.ndarray) -> dict:
    """Run OLS via numpy.linalg.lstsq and return coefficients + diagnostics.

    Parameters
    ----------
    y : (n,) excess returns
    X : (n, k) factor matrix (no constant — we prepend one internally)

    Returns
    -------
    dict with keys: alpha, betas (array), t_stats (array), r_squared
    """
    n = len(y)
    # Prepend intercept column.
    X_const = np.column_stack([np.ones(n), X])

    # OLS: coefficients
    coeffs, residuals_sum, rank, sv = np.linalg.lstsq(X_const, y, rcond=None)
    y_hat = X_const @ coeffs
    resid = y - y_hat

    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Standard errors via OLS variance-covariance matrix.
    dof = n - X_const.shape[1]
    if dof > 0 and ss_res > 0:
        s2 = ss_res / dof
        try:
            XtX_inv = np.linalg.inv(X_const.T @ X_const)
            se = np.sqrt(np.diag(s2 * XtX_inv))
        except np.linalg.LinAlgError:
            se = np.full(len(coeffs), np.nan)
    else:
        se = np.full(len(coeffs), np.nan)

    t_stats = coeffs / se

    return {
        "alpha": float(coeffs[0]),
        "betas": coeffs[1:].tolist(),
        "t_stats": t_stats.tolist(),
        "r_squared": float(r_squared),
    }


# ---------------------------------------------------------------------------
# Main attribution function
# ---------------------------------------------------------------------------

def factor_regression(
    ticker: str,
    model: Literal["3", "5"] = "3",
    period: str = "2y",
) -> dict:
    """Run a Fama-French factor regression for a single ticker.

    Parameters
    ----------
    ticker : str
        Ticker symbol (e.g. "AAPL").
    model : "3" or "5"
        3-factor (Mkt-RF, SMB, HML) or 5-factor (+RMW, CMA).
    period : str
        yfinance period string (e.g. "1y", "2y", "5y").

    Returns
    -------
    dict with keys:
        ticker, model, alpha (annualised), alphaDaily, betas (per-factor),
        rSquared, tStats, nObs, period, asOf
        — OR —
        ticker, model, error, period, asOf  (when factor data unavailable)
    """
    as_of = date.today().isoformat()
    base = {"ticker": ticker, "model": model, "period": period, "asOf": as_of}

    # ---- Load factor data ------------------------------------------------
    factors = load_ff_factors(model)
    if factors is None or factors.empty:
        return {**base, "error": "factor data unavailable"}

    factor_cols = _FF5_COLS[:-1] if model == "5" else _FF3_COLS[:-1]
    # Remove RF from factor_cols — RF is a regressor offset, not a beta factor.
    factor_cols = [c for c in factor_cols if c != "RF"]
    # Confirm all factor columns are present.
    missing = [c for c in factor_cols + ["RF"] if c not in factors.columns]
    if missing:
        return {**base, "error": f"factor data missing columns: {missing}"}

    # ---- Load ticker prices and compute daily simple returns --------------
    try:
        import yfinance as yf
        raw = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if raw is None or raw.empty:
            return {**base, "error": "price data unavailable"}

        # Handle MultiIndex columns (single ticker still sometimes gets one).
        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" in raw.columns.get_level_values(0):
                prices = raw["Close"].squeeze()
            else:
                prices = raw.xs("Close", axis=1, level=-1).squeeze()
        else:
            prices = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]

        prices = prices.dropna()
        if len(prices) < 30:
            return {**base, "error": "insufficient price history"}

        ticker_ret = prices.pct_change().dropna()
    except Exception as exc:
        return {**base, "error": f"price fetch failed: {exc}"}

    # ---- Align returns with factor dates ----------------------------------
    ticker_ret.index = pd.to_datetime(ticker_ret.index).tz_localize(None)
    factors.index = pd.to_datetime(factors.index).tz_localize(None)

    merged = pd.concat(
        [ticker_ret.rename("ret"), factors[factor_cols + ["RF"]]],
        axis=1,
        join="inner",
    ).dropna()

    if len(merged) < 30:
        return {**base, "error": "insufficient aligned observations"}

    # Excess return = ticker return - risk-free rate.
    excess_ret = (merged["ret"] - merged["RF"]).values
    factor_matrix = merged[factor_cols].values

    # ---- OLS regression --------------------------------------------------
    ols = _ols(excess_ret, factor_matrix)

    alpha_daily = ols["alpha"]
    alpha_annual = alpha_daily * TRADING_DAYS

    betas = dict(zip(
        [c.replace("-", "") for c in factor_cols],  # "Mkt-RF" → "MktRF"
        [_clean(b) for b in ols["betas"]],
    ))

    t_stats = dict(zip(
        ["alpha"] + [c.replace("-", "") for c in factor_cols],
        [_clean(t) for t in ols["t_stats"]],
    ))

    return {
        "ticker": ticker,
        "model": model,
        "alpha": _clean(alpha_annual),
        "alphaDaily": _clean(alpha_daily),
        "betas": betas,
        "rSquared": _clean(ols["r_squared"]),
        "tStats": t_stats,
        "nObs": int(len(merged)),
        "period": period,
        "asOf": as_of,
    }
