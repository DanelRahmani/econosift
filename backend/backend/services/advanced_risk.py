"""Advanced rolling risk metrics, tail-risk models, and stress testing."""
from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import gamma as gamma_fn

from .metrics import _clean, log_returns, TRADING_DAYS

# ──────────────────────────────────────────────────────────────────────────────
# Rolling helpers
# ──────────────────────────────────────────────────────────────────────────────

def _series_to_points(s: pd.Series) -> list[dict]:
    """Convert a pandas Series (DatetimeIndex or str index) to [{date, value}]."""
    out = []
    for idx, val in s.items():
        date = str(idx)[:10]
        v = _clean(val)
        out.append({"date": date, "value": v})
    return out


def _rf_daily(rf_annual: float) -> float:
    return rf_annual / TRADING_DAYS


def rolling_volatility(returns: pd.Series, window: int) -> pd.Series:
    """Annualised rolling volatility (std × √252)."""
    return returns.rolling(window).std(ddof=1) * math.sqrt(TRADING_DAYS)


def rolling_sharpe(returns: pd.Series, rf_annual: float, window: int) -> pd.Series:
    """Rolling annualised Sharpe ratio."""
    rf_d = _rf_daily(rf_annual)
    excess = returns - rf_d
    roll_mean = excess.rolling(window).mean() * TRADING_DAYS
    roll_std = returns.rolling(window).std(ddof=1) * math.sqrt(TRADING_DAYS)
    return (roll_mean / roll_std).where(roll_std > 0)


def rolling_sortino(returns: pd.Series, rf_annual: float, window: int) -> pd.Series:
    """Rolling annualised Sortino ratio (downside deviation denominator)."""
    rf_d = _rf_daily(rf_annual)
    excess = returns - rf_d
    roll_ann_excess = excess.rolling(window).mean() * TRADING_DAYS

    # Downside deviation vs the daily risk-free MAR over every day in the
    # window: sqrt(mean(min(r − MAR, 0)²)) — not the std of the negative raw
    # returns around their own mean (audit C-17).
    shortfall_sq = np.minimum(excess, 0.0) ** 2
    roll_dd = np.sqrt(shortfall_sq.rolling(window).mean()) * math.sqrt(TRADING_DAYS)
    return (roll_ann_excess / roll_dd).where(roll_dd > 0)


def rolling_beta(asset_ret: pd.Series, bench_ret: pd.Series, window: int) -> pd.Series:
    """Rolling beta of asset vs benchmark."""
    joined = pd.concat([asset_ret, bench_ret], axis=1, join="inner").dropna()
    joined.columns = ["a", "b"]

    def _beta(df: pd.DataFrame) -> float:
        var_b = df["b"].var(ddof=1)
        if var_b <= 0:
            return float("nan")
        return df["a"].cov(df["b"]) / var_b

    return joined.rolling(window).apply(lambda _: float("nan"), raw=False)["a"].combine(
        joined["a"],
        lambda _a, _: float("nan"),
    ).pipe(lambda _: _rolling_beta_impl(joined, window))


def _rolling_beta_impl(joined: pd.DataFrame, window: int) -> pd.Series:
    results = []
    for i in range(len(joined)):
        if i + 1 < window:
            results.append(float("nan"))
            continue
        chunk = joined.iloc[max(0, i + 1 - window): i + 1]
        var_b = chunk["b"].var(ddof=1)
        if var_b <= 0:
            results.append(float("nan"))
        else:
            results.append(chunk["a"].cov(chunk["b"]) / var_b)
    return pd.Series(results, index=joined.index)


def rolling_max_drawdown(prices: pd.Series, window: int) -> pd.Series:
    """Rolling maximum drawdown (most negative trough-to-peak) over a window."""
    def _mdd(p: pd.Series) -> float:
        cummax = p.expanding().max()
        dd = (p - cummax) / cummax
        return float(dd.min()) if len(dd) else float("nan")

    return prices.rolling(window).apply(_mdd, raw=False)


def rolling_var(returns: pd.Series, window: int, confidence: float = 0.95) -> pd.Series:
    """Rolling parametric VaR at given confidence (e.g. 0.95)."""
    percentile = (1 - confidence) * 100
    return returns.rolling(window).apply(
        lambda r: np.percentile(r, percentile), raw=True
    )


def rolling_correlation_matrix(
    returns_df: pd.DataFrame, window: int, step: int = 21
) -> list[dict]:
    """
    Rolling pairwise correlation matrix, sampled every `step` days.
    Returns a list of {date, matrix: {tickerA: {tickerB: corr}}}.
    """
    tickers = list(returns_df.columns)
    results = []
    for i in range(window, len(returns_df) + 1, step):
        chunk = returns_df.iloc[max(0, i - window): i]
        date = str(returns_df.index[i - 1])[:10]
        corr = chunk.corr()
        matrix: dict[str, dict[str, Any]] = {}
        for t1 in tickers:
            matrix[t1] = {}
            for t2 in tickers:
                v = corr.loc[t1, t2] if t1 in corr.index and t2 in corr.columns else None
                matrix[t1][t2] = _clean(v)
        results.append({"date": date, "matrix": matrix})
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Extended (point-in-time) metrics
# ──────────────────────────────────────────────────────────────────────────────

def extended_metrics(
    returns: pd.Series,
    bench_returns: pd.Series | None,
    rf_annual: float,
    prices: pd.Series,
) -> dict:
    """
    Compute extended risk metrics over the full return history.
    All returns are daily log returns.
    """
    if returns.empty:
        return {}

    ann_ret = returns.mean() * TRADING_DAYS
    ann_vol = returns.std(ddof=1) * math.sqrt(TRADING_DAYS)

    # Max drawdown (full period)
    cummax = prices.expanding().max()
    dd = (prices - cummax) / cummax
    max_dd = float(dd.min()) if len(dd) else None

    # Calmar ratio
    calmar = None
    if max_dd and max_dd != 0:
        calmar = ann_ret / abs(max_dd)

    # Omega ratio: E[max(r-rf,0)] / E[max(rf-r,0)]
    rf_d = _rf_daily(rf_annual)
    gains = np.maximum(returns - rf_d, 0)
    losses = np.maximum(rf_d - returns, 0)
    omega = float(gains.mean() / losses.mean()) if losses.mean() > 0 else None

    # Beta and Jensen's Alpha
    beta, alpha, treynor = None, None, None
    if bench_returns is not None and not bench_returns.empty:
        joined = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
        if len(joined) > 2:
            a_ret = joined.iloc[:, 0]
            b_ret = joined.iloc[:, 1]
            var_b = b_ret.var(ddof=1)
            if var_b and var_b > 0:
                beta = a_ret.cov(b_ret) / var_b
                bench_ann = b_ret.mean() * TRADING_DAYS
                alpha = ann_ret - (rf_annual + beta * (bench_ann - rf_annual))
                if beta != 0:
                    treynor = (ann_ret - rf_annual) / beta

    # CAPM decomposition
    systematic_var, idio_var, r_squared = None, None, None
    if beta is not None and bench_returns is not None:
        joined = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
        b_ret = joined.iloc[:, 1]
        total_var = returns.var(ddof=1)
        bench_var = b_ret.var(ddof=1)
        if total_var and total_var > 0 and bench_var and bench_var > 0:
            systematic_var = (beta ** 2) * bench_var
            idio_var = max(total_var - systematic_var, 0)
            r_squared = systematic_var / total_var

    # VaR 99 (Historical)
    var99_hist = float(np.percentile(returns, 1)) if len(returns) >= 20 else None
    var95_hist = float(np.percentile(returns, 5)) if len(returns) >= 20 else None

    # CVaR / Expected Shortfall
    cvar95, cvar99 = None, None
    if var95_hist is not None:
        tail = returns[returns <= var95_hist]
        cvar95 = float(tail.mean()) if len(tail) else None
    if var99_hist is not None:
        tail99 = returns[returns <= var99_hist]
        cvar99 = float(tail99.mean()) if len(tail99) else None

    return {
        "annReturn": _clean(ann_ret),
        "annVolatility": _clean(ann_vol),
        "maxDrawdown": _clean(max_dd),
        "calmar": _clean(calmar),
        "omega": _clean(omega),
        "beta": _clean(beta),
        "alpha": _clean(alpha),
        "treynor": _clean(treynor),
        "systematicVar": _clean(systematic_var),
        "idiosyncraticVar": _clean(idio_var),
        "rSquared": _clean(r_squared),
        "var95Historical": _clean(var95_hist),
        "var99Historical": _clean(var99_hist),
        "cvar95": _clean(cvar95),
        "cvar99": _clean(cvar99),
    }


# ──────────────────────────────────────────────────────────────────────────────
# On-demand models (🟡)
# ──────────────────────────────────────────────────────────────────────────────

def _expected_rs(n: int) -> float:
    """Anis & Lloyd (1976) expected R/S for an iid series of length n.

    Raw R/S is biased upward badly at the sample sizes we work with — an iid
    series returns ~0.63 rather than 0.5 — so the estimate is de-biased against
    this expectation. Peters' large-n form avoids the gamma overflow above 340.
    """
    s = sum(math.sqrt((n - i) / i) for i in range(1, n))
    if n <= 340:
        return (gamma_fn((n - 1) / 2.0) / (math.sqrt(math.pi) * gamma_fn(n / 2.0))) * s
    return (1.0 / math.sqrt(n * math.pi / 2.0)) * s


def hurst_exponent(prices: pd.Series) -> dict:
    """
    Hurst exponent via corrected R/S analysis on log returns.
    H < 0.5 → mean-reverting, H ≈ 0.5 → random walk, H > 0.5 → trending.

    Takes a *price* series and differences it internally. R/S must be applied to
    the increments, not the levels: run on prices directly it returns ~1.0 for
    a random walk, a trending series and a mean-reverting series alike, i.e. it
    cannot distinguish the three regimes it exists to classify.

    A constant drift does not make H exceed 0.5 — GBM with drift still has iid
    increments. Only genuine autocorrelation in the returns moves it.

    The 0.4 / 0.6 interpretation bands are roughly the 95% interval of this
    estimator under the null: measured on iid data it has mean ~0.50 and sd
    ~0.045 at the default 3y window. A reading inside the band is not evidence
    of memory.
    """
    p = prices.dropna()
    if len(p) < 20:
        return {"hurst": None, "interpretation": "Insufficient data"}

    vals = p.values.astype(float)
    # Log returns where the series is a positive price level; plain first
    # differences otherwise (e.g. a spread that legitimately crosses zero).
    if np.all(vals > 0):
        x = np.diff(np.log(vals))
    else:
        x = np.diff(vals)

    n = len(x)
    if n < 20:
        return {"hurst": None, "interpretation": "Insufficient data"}

    rs_list = []
    lag_list = []
    # Lags below ~8 give unstable R/S regardless of the correction.
    for lag in range(8, min(n // 2, 200)):
        rs_vals = []
        for i in range(0, n - lag + 1, lag):
            chunk = x[i: i + lag]
            if len(chunk) < 2:
                continue
            dev = chunk - np.mean(chunk)
            cumdev = np.cumsum(dev)
            r = np.max(cumdev) - np.min(cumdev)
            s = np.std(chunk, ddof=1)
            if s > 0:
                rs_vals.append(r / s)
        if rs_vals:
            rs_list.append(np.mean(rs_vals))
            lag_list.append(lag)

    if len(lag_list) < 3:
        return {"hurst": None, "interpretation": "Insufficient data"}

    log_lags = np.log(lag_list)
    log_rs = np.log(rs_list)
    expected = np.array([math.log(_expected_rs(l)) for l in lag_list])
    # Regressing the de-biased ratio recovers H - 0.5.
    h = 0.5 + float(np.polyfit(log_lags, log_rs - expected, 1)[0])
    h = _clean(h)

    if h is None:
        interp = "Unknown"
    elif h < 0.4:
        interp = "Mean-reverting (H < 0.4)"
    elif h < 0.6:
        interp = "Random walk (H ≈ 0.5)"
    else:
        interp = "Trending (H > 0.6)"

    return {"hurst": h, "interpretation": interp}


def ou_fit(prices: pd.Series) -> dict:
    """
    Ornstein-Uhlenbeck fit via OLS on discrete analogue.
    Returns theta (mean-reversion speed), mu (long-run mean),
    sigma (vol), half-life in calendar days.
    """
    p = prices.dropna()
    if len(p) < 10:
        return {"theta": None, "mu": None, "sigma": None, "halfLifeDays": None}

    try:
        x = p.values[:-1]
        y = p.values[1:]
        n = len(x)
        sx = np.sum(x)
        sy = np.sum(y)
        sxx = np.sum(x * x)
        sxy = np.sum(x * y)
        syy = np.sum(y * y)

        denom = n * sxx - sx * sx
        if abs(denom) < 1e-10:
            raise ValueError("Degenerate matrix")

        b = (n * sxy - sx * sy) / denom
        a = (sy - b * sx) / n

        # b = exp(-theta * dt), dt = 1/252
        dt = 1.0 / TRADING_DAYS
        if b <= 0:
            return {"theta": None, "mu": None, "sigma": None, "halfLifeDays": None}

        theta = -math.log(b) / dt
        mu = a / (1 - b)

        residuals = y - (a + b * x)
        sigma_dt = residuals.std(ddof=2)
        sigma = sigma_dt / math.sqrt(dt)

        half_life_days = math.log(2) / theta * TRADING_DAYS if theta > 0 else None

        return {
            "theta": _clean(theta),
            "mu": _clean(mu),
            "sigma": _clean(sigma),
            "halfLifeDays": _clean(half_life_days),
        }
    except Exception:
        return {"theta": None, "mu": None, "sigma": None, "halfLifeDays": None}


def garch_fit(returns: pd.Series) -> dict:
    """
    GARCH(1,1) via arch library. Returns omega, alpha, beta,
    1-step-ahead forecast volatility (daily and annualised).
    """
    r = returns.dropna()
    if len(r) < 50:
        return {"omega": None, "alpha": None, "beta": None,
                "forecastVol": None, "annForecastVol": None}
    try:
        from arch import arch_model  # type: ignore
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            am = arch_model(r * 100, vol="Garch", p=1, q=1, dist="Normal")
            res = am.fit(disp="off", show_warning=False)
        params = res.params
        omega = _clean(float(params.get("omega", 0.0)))
        alpha = _clean(float(params.get("alpha[1]", 0.0)))
        beta = _clean(float(params.get("beta[1]", 0.0)))

        fc = res.forecast(horizon=1)
        var_1step = float(fc.variance.iloc[-1, 0])
        forecast_vol = _clean(math.sqrt(max(var_1step, 0)) / 100)
        ann_forecast_vol = _clean(forecast_vol * math.sqrt(TRADING_DAYS)) if forecast_vol else None

        return {
            "omega": omega,
            "alpha": alpha,
            "beta": beta,
            "forecastVol": forecast_vol,
            "annForecastVol": ann_forecast_vol,
        }
    except Exception as exc:
        return {"omega": None, "alpha": None, "beta": None,
                "forecastVol": None, "annForecastVol": None,
                "error": str(exc)}


def cointegration_test(prices_df: pd.DataFrame) -> dict:
    """
    Engle-Granger cointegration test on the first two columns.
    Returns p-value, hedge ratio, and the spread series.
    """
    if prices_df.shape[1] < 2:
        return {"pValue": None, "isCointegrated": None,
                "hedgeRatio": None, "spread": []}
    try:
        from statsmodels.tsa.stattools import coint  # type: ignore
        p = prices_df.dropna()
        y1 = p.iloc[:, 0].values
        y2 = p.iloc[:, 1].values

        _score, pvalue, _crit = coint(y1, y2)

        # OLS hedge ratio
        n = len(y1)
        sx = np.sum(y2)
        sy = np.sum(y1)
        sxx = np.sum(y2 * y2)
        sxy = np.sum(y2 * y1)
        denom = n * sxx - sx * sx
        hedge_ratio = (n * sxy - sx * sy) / denom if abs(denom) > 1e-10 else 1.0

        spread_vals = y1 - hedge_ratio * y2
        spread_series = pd.Series(spread_vals, index=p.index)

        return {
            "pValue": _clean(float(pvalue)),
            "isCointegrated": bool(pvalue < 0.05),
            "hedgeRatio": _clean(float(hedge_ratio)),
            "spread": _series_to_points(spread_series),
        }
    except ImportError:
        return {"pValue": None, "isCointegrated": None,
                "hedgeRatio": None, "spread": [],
                "error": "statsmodels not installed"}
    except Exception as exc:
        return {"pValue": None, "isCointegrated": None,
                "hedgeRatio": None, "spread": [], "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# User-triggered models (🔴)
# ──────────────────────────────────────────────────────────────────────────────

_STRESS_SCENARIOS: dict[str, tuple[str, str, str]] = {
    "gfc":    ("2007-10-01", "2009-03-09",  "2008 Global Financial Crisis"),
    "covid":  ("2020-02-19", "2020-03-23",  "2020 COVID Crash"),
    "rates":  ("2022-01-03", "2022-10-13",  "2022 Rate Shock"),
    "dotcom": ("2000-03-10", "2002-10-09",  "2000 Dot-com Bust"),
}


def monte_carlo_var(
    returns: pd.Series,
    sims: int = 10_000,
    horizon: int = 1,
) -> dict:
    """
    GBM Monte Carlo VaR.
    Draws `sims` random daily returns from a normal distribution
    parameterised by the historical mean/std, then applies them
    for `horizon` days. Returns VaR95, VaR99, expected, worst.
    """
    r = returns.dropna()
    if len(r) < 20:
        return {"var95": None, "var99": None, "expected": None,
                "worstCase": None, "distribution": []}

    mu = float(r.mean())
    sigma = float(r.std(ddof=1))
    rng = np.random.default_rng(seed=42)
    sim_returns = rng.normal(loc=mu, scale=sigma, size=(sims, horizon)).sum(axis=1)

    var95 = _clean(float(np.percentile(sim_returns, 5)))
    var99 = _clean(float(np.percentile(sim_returns, 1)))
    expected = _clean(float(sim_returns.mean()))
    worst = _clean(float(sim_returns.min()))

    # Histogram bins for distribution chart (100 buckets)
    hist, edges = np.histogram(sim_returns, bins=100)
    distribution = [
        {"bin": _clean(float(edges[i])), "count": int(hist[i])}
        for i in range(len(hist))
    ]

    return {
        "var95": var95,
        "var99": var99,
        "expected": expected,
        "worstCase": worst,
        "distribution": distribution,
        "sims": sims,
        "horizon": horizon,
    }


def stress_test_returns(
    prices: pd.Series,
    scenario_key: str,
    benchmark_prices: pd.Series | None = None,
) -> dict:
    """
    Stress test: apply historical scenario return sequence to the ticker.
    The scenario period returns are applied to the full price series start,
    and we report total return, max drawdown, and the daily return series.
    """
    if scenario_key not in _STRESS_SCENARIOS:
        return {"error": f"Unknown scenario: {scenario_key}"}

    start, end, label = _STRESS_SCENARIOS[scenario_key]
    p = prices.dropna()

    # Slice scenario window from the ticker's own history
    p.index = pd.to_datetime(p.index)
    scenario_prices = p.loc[start:end]

    if len(scenario_prices) < 5:
        return {
            "scenario": scenario_key,
            "label": label,
            "error": "Insufficient historical data for this scenario period",
            "returnsTimeSeries": [],
        }

    scenario_returns = log_returns(scenario_prices)
    total_return = float(np.exp(scenario_returns.sum()) - 1)

    cummax = scenario_prices.expanding().max()
    dd = (scenario_prices - cummax) / cummax
    max_dd = float(dd.min())

    cum_ret = (np.exp(scenario_returns.cumsum()) - 1)
    cum_ret.index = pd.to_datetime(cum_ret.index)

    bench_data = None
    if benchmark_prices is not None:
        bp = benchmark_prices.dropna()
        bp.index = pd.to_datetime(bp.index)
        bench_scenario = bp.loc[start:end]
        if len(bench_scenario) >= 5:
            bench_ret = log_returns(bench_scenario)
            bench_cum = np.exp(bench_ret.cumsum()) - 1
            bench_data = _series_to_points(bench_cum)

    return {
        "scenario": scenario_key,
        "label": label,
        "start": start,
        "end": end,
        "totalReturn": _clean(total_return),
        "maxDrawdown": _clean(max_dd),
        "returnsTimeSeries": _series_to_points(cum_ret),
        "benchmark": bench_data,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Aggregator: full rolling payload for a single ticker
# ──────────────────────────────────────────────────────────────────────────────

def rolling_metrics_for_ticker(
    prices: pd.Series,
    bench_prices: pd.Series | None,
    rf_annual: float,
    window: int,
) -> dict:
    """
    Build the complete rolling metrics payload for one ticker.
    Returns dict with all rolling series as [{date, value}] lists.
    """
    r = log_returns(prices)
    if r.empty:
        return {}

    roll_vol = rolling_volatility(r, window)
    roll_sharpe = rolling_sharpe(r, rf_annual, window)
    roll_sortino = rolling_sortino(r, rf_annual, window)
    roll_mdd = rolling_max_drawdown(prices, window)
    roll_var95 = rolling_var(r, window, 0.95)
    roll_var99 = rolling_var(r, window, 0.99)

    roll_beta = None
    if bench_prices is not None and not bench_prices.empty:
        br = log_returns(bench_prices)
        joined_idx = r.index.intersection(br.index)
        if len(joined_idx) > window:
            ra = r.loc[joined_idx]
            rb = br.loc[joined_idx]
            joined = pd.DataFrame({"a": ra, "b": rb}).dropna()
            roll_beta = _rolling_beta_impl(joined, window)

    return {
        "window": window,
        "volatility": _series_to_points(roll_vol.dropna()),
        "sharpe": _series_to_points(roll_sharpe.dropna()),
        "sortino": _series_to_points(roll_sortino.dropna()),
        "maxDrawdown": _series_to_points(roll_mdd.dropna()),
        "var95": _series_to_points(roll_var95.dropna()),
        "var99": _series_to_points(roll_var99.dropna()),
        "beta": _series_to_points(roll_beta.dropna()) if roll_beta is not None else [],
    }
