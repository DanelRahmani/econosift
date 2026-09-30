"""Risk Parity service — Phase 14.

Provides three functions:
  - inverse_vol_weights  : inverse-volatility weighting
  - erc_weights          : Equal Risk Contribution (SLSQP)
  - risk_parity_backtest : monthly-rebalanced backtest vs 60/40 SPY+AGG
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import yfinance_service as yfs
from ..cache import cached

TRADING_DAYS = 252
_MIN_OBS = 60          # minimum rows required to fit weights
_BENCH_60_40 = ("SPY", "AGG")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _clean(x) -> Optional[float]:
    """Convert to Python float; map NaN/inf/None → None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _log_returns(px: pd.DataFrame) -> pd.DataFrame:
    """Daily log-returns, dropping rows where ALL values are NaN."""
    return np.log(px / px.shift(1)).dropna(how="all")


def _annual_vols(log_ret: pd.DataFrame) -> pd.Series:
    """Annualised per-asset volatility."""
    return log_ret.std(ddof=1) * math.sqrt(TRADING_DAYS)


def _rc_from_weights(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Risk contribution vector RC_i = w_i * (cov @ w)_i (un-normalised)."""
    sigma_w = cov @ w
    return w * sigma_w


def _inv_vol_w(vols: np.ndarray) -> np.ndarray:
    """Inverse-vol weights; returns zeros if any vol is zero/nan."""
    if np.any(~np.isfinite(vols)) or np.any(vols <= 0):
        return np.full(len(vols), 1.0 / len(vols))
    inv = 1.0 / vols
    return inv / inv.sum()


def _erc_optimize(vols: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """SLSQP minimisation of Σ_i Σ_j (RC_i - RC_j)^2 s.t. Σw=1, w≥0."""
    n = len(vols)
    w0 = _inv_vol_w(vols)   # warm-start from inverse-vol

    def objective(w: np.ndarray) -> float:
        rc = _rc_from_weights(w, cov)
        total = 0.0
        for i in range(n):
            for j in range(n):
                total += (rc[i] - rc[j]) ** 2
        return total

    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bounds = [(0.0, 1.0)] * n

    result = minimize(
        objective, w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 1000},
    )

    if result.success:
        w = np.clip(result.x, 0.0, None)
        s = w.sum()
        return w / s if s > 0 else w0
    return w0   # fallback


def _build_risk_contrib_rows(
    tickers: list[str],
    w: np.ndarray,
    cov: np.ndarray,
) -> list[dict]:
    """Build riskContrib list with pctContrib normalised to sum 1."""
    rc = _rc_from_weights(w, cov)
    port_var = float(w @ cov @ w)
    port_vol = math.sqrt(port_var) if port_var > 0 else None

    if port_vol is None or port_vol == 0:
        # fallback: equal contrib
        return [
            {"ticker": t, "weight": _clean(float(w[i])), "pctContrib": _clean(1.0 / len(tickers))}
            for i, t in enumerate(tickers)
        ]

    mrc = w * (cov @ w) / port_vol   # marginal risk contributions
    total_mrc = mrc.sum() or 1.0

    return [
        {
            "ticker": t,
            "weight": _clean(float(w[i])),
            "pctContrib": _clean(float(mrc[i] / total_mrc)),
        }
        for i, t in enumerate(tickers)
    ]


def _weights_rows(tickers: list[str], w: np.ndarray) -> list[dict]:
    return [{"ticker": t, "weight": _clean(float(w[i]))} for i, t in enumerate(tickers)]


def _portfolio_metrics(daily_ret: pd.Series) -> dict:
    """Compute CAGR, annualised vol, Sharpe (rf=0), and max-drawdown."""
    if daily_ret.empty or len(daily_ret) < 2:
        return {"cagr": None, "vol": None, "sharpe": None, "maxDrawdown": None}

    log_r = np.log1p(daily_ret.clip(lower=-0.999))
    n_years = len(log_r) / TRADING_DAYS
    # Compounded annual growth — total return ÷ years is an arithmetic
    # average, not a CAGR (audit C-04).
    total = float(np.exp(log_r.sum()))
    cagr = total ** (1.0 / n_years) - 1.0 if n_years > 0 and total > 0 else None
    vol = float(log_r.std(ddof=1) * math.sqrt(TRADING_DAYS)) if len(log_r) > 1 else None
    # Sharpe (rf = 0): annualised mean daily return over annualised vol.
    ann_mean = float(daily_ret.mean()) * TRADING_DAYS
    sharpe = (ann_mean / vol) if (vol and vol > 0) else None

    cum = (1.0 + daily_ret).cumprod()
    max_dd = float((cum / cum.cummax() - 1.0).min()) if len(cum) else None

    return {
        "cagr": _clean(cagr),
        "vol": _clean(vol),
        "sharpe": _clean(sharpe),
        "maxDrawdown": _clean(max_dd),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("rp_weights")
def inverse_vol_weights(tickers: tuple[str, ...], period: str = "3y") -> dict:
    """Inverse-volatility weights.

    Returns::

        {
          "weights":     [{"ticker": str, "weight": float}, ...],
          "riskContrib": [{"ticker": str, "weight": float, "pctContrib": float}, ...],
          "missing":     [str, ...]
        }
    """
    px = yfs.get_close_frame(tickers, period)
    if px.empty:
        return {"error": "insufficient data", "weights": [], "riskContrib": [], "missing": list(tickers)}

    valid_cols = [c for c in px.columns if px[c].notna().sum() >= _MIN_OBS]
    missing = [t for t in tickers if t not in valid_cols]

    if len(valid_cols) < 2:
        return {"error": "insufficient data", "weights": [], "riskContrib": [], "missing": list(tickers)}

    px_clean = px[valid_cols].ffill().dropna(how="all")
    log_ret = _log_returns(px_clean).dropna()

    vols = _annual_vols(log_ret).values
    w = _inv_vol_w(vols)

    cov = log_ret.cov().values * TRADING_DAYS

    return {
        "weights": _weights_rows(valid_cols, w),
        "riskContrib": _build_risk_contrib_rows(valid_cols, w, cov),
        "missing": missing,
    }


@cached("rp_erc")
def erc_weights(tickers: tuple[str, ...], period: str = "3y") -> dict:
    """Equal Risk Contribution weights via SLSQP.

    Returns the same shape as ``inverse_vol_weights``.
    """
    px = yfs.get_close_frame(tickers, period)
    if px.empty:
        return {"error": "insufficient data", "weights": [], "riskContrib": [], "missing": list(tickers)}

    valid_cols = [c for c in px.columns if px[c].notna().sum() >= _MIN_OBS]
    missing = [t for t in tickers if t not in valid_cols]

    if len(valid_cols) < 2:
        return {"error": "insufficient data", "weights": [], "riskContrib": [], "missing": list(tickers)}

    px_clean = px[valid_cols].ffill().dropna(how="all")
    log_ret = _log_returns(px_clean).dropna()

    vols = _annual_vols(log_ret).values
    cov = log_ret.cov().values * TRADING_DAYS

    w = _erc_optimize(vols, cov)

    return {
        "weights": _weights_rows(valid_cols, w),
        "riskContrib": _build_risk_contrib_rows(valid_cols, w, cov),
        "missing": missing,
    }


@cached("rp_backtest")
def risk_parity_backtest(
    tickers: tuple[str, ...],
    period: str = "3y",
    mode: str = "erc",
) -> dict:
    """Monthly-rebalanced Risk Parity backtest vs 60/40 (SPY+AGG).

    Returns::

        {
          "series": [{"date": "YYYY-MM-DD", "strategy": float, "benchmark": float}, ...],
          "finalWeights": [{"ticker": str, "weight": float}, ...],
          "metrics": {
              "strategy": {"cagr", "vol", "sharpe", "maxDrawdown"},
              "benchmark": {"cagr", "vol", "sharpe", "maxDrawdown"},
          },
          "missing": [str, ...]
        }
    """
    # ---- fetch all needed price data ----------------------------------------
    all_tickers = tuple(dict.fromkeys(list(tickers) + list(_BENCH_60_40)))
    px_all = yfs.get_close_frame(all_tickers, period)

    asset_cols = [t for t in tickers if t in px_all.columns and px_all[t].notna().sum() >= _MIN_OBS]
    missing = [t for t in tickers if t not in asset_cols]

    if len(asset_cols) < 2:
        return {
            "error": "insufficient data",
            "series": [],
            "finalWeights": [],
            "metrics": {"strategy": {}, "benchmark": {}},
            "missing": list(tickers),
        }

    # ---- align dates for strategy -------------------------------------------
    px_assets = px_all[asset_cols].ffill().dropna(how="all")
    dates = px_assets.index

    # ---- identify month-start boundaries ------------------------------------
    month_starts: list[int] = []
    prev_month = None
    for i, d in enumerate(dates):
        m = (d.year, d.month)
        if m != prev_month:
            month_starts.append(i)
            prev_month = m

    # ---- walk forward: recompute weights at each month boundary -------------
    strategy_returns: list[float] = []
    strategy_dates: list[str] = []
    current_w: Optional[np.ndarray] = None
    final_w: Optional[np.ndarray] = None

    # Daily returns computed once over the whole history, so the return from
    # the last close of one month to the first close of the next is kept.
    # (Computing pct_change inside each monthly segment dropped ~12 sessions
    # a year from the strategy but not from the 60/40 benchmark — C-05.)
    all_ret = px_assets.ffill().pct_change()

    for seg_idx, seg_start in enumerate(month_starts):
        seg_end = month_starts[seg_idx + 1] if seg_idx + 1 < len(month_starts) else len(dates)

        # Recompute weights from data UP TO seg_start (trailing window)
        if seg_start >= _MIN_OBS:
            hist = px_assets.iloc[:seg_start]
            log_ret_hist = _log_returns(hist.ffill()).dropna()
            if len(log_ret_hist) >= _MIN_OBS:
                vols_h = _annual_vols(log_ret_hist).values
                cov_h = log_ret_hist.cov().values * TRADING_DAYS
                if mode == "erc":
                    current_w = _erc_optimize(vols_h, cov_h)
                else:
                    current_w = _inv_vol_w(vols_h)
                final_w = current_w.copy()

        if current_w is None:
            # Not enough history yet — use equal weights
            n = len(asset_cols)
            current_w = np.full(n, 1.0 / n)

        # Forward returns for this segment
        seg_ret = all_ret.iloc[seg_start:seg_end].dropna(how="all").fillna(0.0)
        if seg_ret.empty:
            continue
        port_ret = seg_ret.values @ current_w
        for i, d in enumerate(seg_ret.index):
            strategy_returns.append(float(port_ret[i]))
            # Keep as Timestamp so we can align with the benchmark DatetimeIndex
            strategy_dates.append(d)

    strategy_ret_series = pd.Series(strategy_returns, index=strategy_dates)

    # ---- 60/40 benchmark ----------------------------------------------------
    bench_px = pd.DataFrame()
    if "SPY" in px_all.columns and "AGG" in px_all.columns:
        bench_px = px_all[["SPY", "AGG"]].reindex(px_assets.index).ffill().dropna(how="all")

    if bench_px.empty or len(bench_px) < 2:
        # Fallback: use SPY alone
        bench_ret_series = pd.Series(dtype=float)
        if "SPY" in px_all.columns:
            s = px_all["SPY"].reindex(px_assets.index).ffill().dropna()
            bench_ret_series = s.pct_change().dropna()
    else:
        b_ret = bench_px.pct_change().dropna(how="all").fillna(0.0)
        bench_w = np.array([0.6, 0.4])
        bench_ret_series = pd.Series(
            b_ret.values @ bench_w,
            index=b_ret.index,
        )

    # ---- build cumulative base-100 series -----------------------------------
    strat_cum = (1.0 + strategy_ret_series).cumprod() * 100.0
    bench_cum = (1.0 + bench_ret_series).cumprod() * 100.0

    # Align both to the same index
    aligned = pd.DataFrame({"strategy": strat_cum, "benchmark": bench_cum}).dropna(how="any")

    series_out = [
        {
            "date": pd.Timestamp(d).strftime("%Y-%m-%d"),
            "strategy": round(float(aligned.loc[d, "strategy"]), 4),
            "benchmark": round(float(aligned.loc[d, "benchmark"]), 4),
        }
        for d in aligned.index
    ]

    # ---- metrics per stream -------------------------------------------------
    strat_simple = strategy_ret_series.reindex(aligned.index)
    bench_simple = bench_ret_series.reindex(aligned.index)

    return {
        "series": series_out,
        "finalWeights": (
            [{"ticker": asset_cols[i], "weight": _clean(float(final_w[i]))} for i in range(len(asset_cols))]
            if final_w is not None
            else [{"ticker": t, "weight": _clean(1.0 / len(asset_cols))} for t in asset_cols]
        ),
        "metrics": {
            "strategy": _portfolio_metrics(strat_simple),
            "benchmark": _portfolio_metrics(bench_simple),
        },
        "missing": missing,
    }
