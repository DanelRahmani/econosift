"""Portfolio aggregation: weighted performance, P&L, risk metrics, and optimisation."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .. import provenance as pv
from . import metrics
from .advanced_risk import (
    _series_to_points,
    rolling_sharpe,
    rolling_volatility,
    _rolling_beta_impl,
    _STRESS_SCENARIOS,
)
from .fama_french import load_ff_factors, _ols
from .discount_rates import risk_free_rate

TRADING_DAYS = 252


def _clean(x):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


# ---------------------------------------------------------------------------
# Core analysis (existing — unchanged)
# ---------------------------------------------------------------------------

def _portfolio_returns(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Daily portfolio *simple* returns: Σ wᵢ·rᵢ over the assets that traded.

    Simple returns aggregate across assets; log returns do not, so a weighted
    sum of log returns is not the portfolio's return (audit C-19). On days a
    holding has no return (before it listed, or a data gap) its weight is
    redistributed over the others instead of earning a fake 0% (C-20).
    """
    cols = list(weights)
    px = frame[cols].dropna(how="all").ffill()
    rets = px.pct_change().iloc[1:]
    w = pd.Series(weights, dtype=float)
    avail = rets.notna()
    w_eff = avail.mul(w, axis=1)
    denom = w_eff.sum(axis=1)
    port = rets.fillna(0.0).mul(w, axis=1).sum(axis=1) / denom.replace(0.0, np.nan)
    return port.dropna()


def _sortino(simple_ret: pd.Series, risk_free: float) -> float | None:
    """Sortino ratio: annualised excess return over downside deviation.

    Downside deviation is sqrt(mean(min(r − MAR, 0)²)) over *all* days with
    the daily risk-free rate as the MAR — not the standard deviation of the
    negative days around their own mean (audit C-17).
    """
    if len(simple_ret) < 2:
        return None
    mar = risk_free / TRADING_DAYS
    shortfall = np.minimum(simple_ret - mar, 0.0)
    dd = math.sqrt(float((shortfall ** 2).mean())) * math.sqrt(TRADING_DAYS)
    if dd <= 0:
        return None
    return (float(simple_ret.mean()) * TRADING_DAYS - risk_free) / dd


def analyze(frame: pd.DataFrame, holdings: list[dict], bench_series: pd.Series | None,
            risk_free: float) -> dict:
    """Aggregate a basket of holdings into a single portfolio.

    `holdings` is a list of {"ticker", "weight"} (weights need not sum to 1;
    they are normalised here). Returns a portfolio value series (base 100),
    headline metrics, and per-holding contribution.
    """
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present or frame.empty:
        return {"holdings": [], "series": [], "metrics": {}, "missing": [h["ticker"] for h in holdings]}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}

    cols = list(weights.keys())
    port_ret = _portfolio_returns(frame, weights)

    # Value series, base 100.
    value = (1.0 + port_ret).cumprod() * 100.0
    series = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
              for d, v in value.items()]

    # Headline metrics.
    log_ret = np.log1p(port_ret.clip(lower=-0.999))
    daily_mean = log_ret.mean()
    ann_return = daily_mean * TRADING_DAYS
    ann_vol = log_ret.std(ddof=1) * math.sqrt(TRADING_DAYS) if len(log_ret) > 1 else None
    sharpe = ((ann_return - risk_free) / ann_vol) if ann_vol and ann_vol > 0 else None

    sortino = _sortino(port_ret, risk_free)

    total_return = (float(value.iloc[-1]) / 100.0 - 1.0) if len(value) else None

    # Max drawdown.
    running_max = value.cummax()
    drawdown = (value / running_max - 1.0)
    max_dd = float(drawdown.min()) if len(drawdown) else None

    var95 = float(np.percentile(log_ret, 5)) if len(log_ret) else None

    # Portfolio beta vs benchmark (regression of portfolio returns on bench).
    beta = None
    if bench_series is not None and len(bench_series) > 2:
        br = metrics.log_returns(bench_series)
        joined = pd.concat([log_ret, br], axis=1, join="inner").dropna()
        if len(joined) > 2:
            a, b = joined.iloc[:, 0], joined.iloc[:, 1]
            var_b = b.var(ddof=1)
            if var_b and var_b > 0:
                beta = float(a.cov(b) / var_b)

    # Per-holding contribution: weight x its own total return.
    holding_rows = []
    for c in cols:
        hpx = frame[c].dropna()
        h_total = (float(hpx.iloc[-1]) / float(hpx.iloc[0]) - 1.0) if len(hpx) > 1 else None
        holding_rows.append({
            "ticker": c,
            "weight": _clean(weights[c]),
            "totalReturn": _clean(h_total),
            "contribution": _clean(weights[c] * h_total) if h_total is not None else None,
        })

    # Drawdown series for extended response — compounds *simple* returns, so
    # it matches maxDrawdown from the value series (audit C-18).
    dd_series = drawdown_series(port_ret)

    return {
        "holdings": holding_rows,
        "series": series,
        "drawdownSeries": dd_series,
        "metrics": {
            "totalReturn": _clean(total_return),
            "annReturn": _clean(ann_return),
            "annVolatility": _clean(ann_vol),
            "sharpe": _clean(sharpe),
            "sortino": _clean(sortino),
            "maxDrawdown": _clean(max_dd),
            "var95": _clean(var95),
            "beta": _clean(beta),
        },
        "missing": [h["ticker"] for h in holdings if h["ticker"] not in frame.columns],
    }


# ---------------------------------------------------------------------------
# New service functions (Phase 11)
# ---------------------------------------------------------------------------

def drawdown_series(port_ret: pd.Series) -> list[dict]:
    """Underwater drawdown curve from a daily return series.

    Accepts either log or simple returns; computes cumulative wealth then
    the percentage drawdown from the running peak at each point.
    """
    if port_ret is None or port_ret.empty:
        return []
    try:
        cum = (1.0 + port_ret).cumprod()
        dd = (cum / cum.cummax()) - 1.0
        return [
            {"date": str(idx)[:10], "value": _clean(float(v))}
            for idx, v in dd.items()
        ]
    except Exception:
        return []


def benchmark_series(frame: pd.DataFrame, period: str = "1y") -> dict:
    """Return base-100 cumulative return series for ^GSPC and AGG.

    Both columns are expected to already be present in *frame* (the caller
    should have loaded them alongside the portfolio tickers).
    """
    out: dict[str, list[dict]] = {"gspc": [], "agg": []}

    def _to_base100(col: str) -> list[dict]:
        if col not in frame.columns:
            return []
        px = frame[col].dropna().ffill()
        if px.empty:
            return []
        cum = (px / px.iloc[0]) * 100.0
        return [
            {"date": str(idx)[:10], "value": round(float(v), 2)}
            for idx, v in cum.items()
        ]

    out["gspc"] = _to_base100("^GSPC")
    out["agg"] = _to_base100("AGG")
    return out


def correlation_matrix(holdings: list[dict], frame: pd.DataFrame) -> dict:
    """Pairwise Pearson correlation from daily log returns."""
    tickers = [h["ticker"] for h in holdings if h["ticker"] in frame.columns]
    if len(tickers) < 2:
        return {"tickers": tickers, "matrix": []}

    px = frame[tickers].dropna(how="all").ffill()
    log_ret = np.log(px / px.shift(1)).dropna(how="all")

    corr = log_ret.corr()
    matrix = [
        [_clean(round(float(corr.loc[r, c]), 3)) if r in corr.index and c in corr.columns else None
         for c in tickers]
        for r in tickers
    ]
    return {"tickers": tickers, "matrix": matrix}


def risk_contribution(holdings: list[dict], frame: pd.DataFrame) -> list[dict]:
    """Marginal risk contribution per holding.

    RC_i = w_i * (Σ w)_i / σ_p
    where (Σ w)_i is the i-th component of the covariance-weight product vector.
    """
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present:
        return []

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights_list = [max(h["weight"], 0.0) / total_w for h in present]
    tickers = [h["ticker"] for h in present]

    px = frame[tickers].dropna(how="all").ffill()
    log_ret = np.log(px / px.shift(1)).dropna(how="all")

    w = np.array(weights_list)
    cov = log_ret.cov().values * TRADING_DAYS  # annualise

    port_var = float(w @ cov @ w)
    port_vol = math.sqrt(port_var) if port_var > 0 else None

    if port_vol is None or port_vol == 0:
        return [
            {"ticker": t, "weight": _clean(weights_list[i]),
             "marginalContrib": None, "pctContrib": None}
            for i, t in enumerate(tickers)
        ]

    sigma_w = cov @ w  # (Σ w) vector
    mrc = w * sigma_w / port_vol  # marginal risk contribution

    total_rc = mrc.sum() or 1.0
    result = []
    for i, t in enumerate(tickers):
        result.append({
            "ticker": t,
            "weight": _clean(weights_list[i]),
            "marginalContrib": _clean(float(mrc[i])),
            "pctContrib": _clean(float(mrc[i] / total_rc)),
        })
    return result


def capm_attribution(
    holdings: list[dict],
    frame: pd.DataFrame,
    bench_col: str,
    rf: float,
) -> dict:
    """OLS portfolio excess return ~ alpha + beta * bench_excess."""
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present or bench_col not in frame.columns:
        return {"error": "insufficient data"}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}
    port_log_ret = np.log1p(_portfolio_returns(frame, weights))

    bench_px = frame[bench_col].dropna().ffill()
    bench_log_ret = np.log(bench_px / bench_px.shift(1)).dropna()

    joined = pd.concat([port_log_ret, bench_log_ret], axis=1, join="inner").dropna()
    if len(joined) < 10:
        return {"error": "insufficient aligned data"}

    joined.columns = ["port", "bench"]
    rf_daily = rf / TRADING_DAYS
    port_excess = (joined["port"] - rf_daily).values
    bench_excess = (joined["bench"] - rf_daily).values

    # OLS
    X = bench_excess.reshape(-1, 1)
    ols = _ols(port_excess, X)

    alpha_daily = ols["alpha"]
    beta = ols["betas"][0] if ols["betas"] else None
    r_sq = ols["r_squared"]

    ann_alpha = alpha_daily * TRADING_DAYS if alpha_daily is not None else None

    # CAPM variance decomposition
    port_var = float(joined["port"].var(ddof=1))
    bench_var = float(joined["bench"].var(ddof=1))
    systematic_var_pct = None
    idiosyncratic_var_pct = None
    if beta is not None and port_var and port_var > 0 and bench_var and bench_var > 0:
        sys_var = (beta ** 2) * bench_var
        sys_pct = sys_var / port_var
        systematic_var_pct = _clean(sys_pct)
        idiosyncratic_var_pct = _clean(max(1.0 - sys_pct, 0.0))

    return {
        "alpha": _clean(alpha_daily),
        "annAlpha": _clean(ann_alpha),
        "beta": _clean(beta),
        "rSquared": _clean(r_sq),
        "systematicVarPct": systematic_var_pct,
        "idiosyncraticVarPct": idiosyncratic_var_pct,
        "nObs": len(joined),
    }


def rolling_portfolio_metrics(
    holdings: list[dict],
    frame: pd.DataFrame,
    bench_col: str,
    rf: float,
    window: int,
) -> dict:
    """Rolling Sharpe, volatility, and beta for the portfolio."""
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present:
        return {"window": window, "sharpe": [], "volatility": [], "beta": []}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}
    port_log_ret = np.log1p(_portfolio_returns(frame, weights))

    roll_sharpe = rolling_sharpe(port_log_ret, rf, window)
    roll_vol = rolling_volatility(port_log_ret, window)

    roll_beta_series: pd.Series | None = None
    if bench_col in frame.columns:
        bench_px = frame[bench_col].dropna().ffill()
        bench_log_ret = np.log(bench_px / bench_px.shift(1)).dropna()
        joined = pd.DataFrame({"a": port_log_ret, "b": bench_log_ret}).dropna()
        if len(joined) > window:
            roll_beta_series = _rolling_beta_impl(joined, window)

    return {
        "window": window,
        "sharpe": _series_to_points(roll_sharpe.dropna()),
        "volatility": _series_to_points(roll_vol.dropna()),
        "beta": _series_to_points(roll_beta_series.dropna()) if roll_beta_series is not None else [],
    }


def kelly_criterion(holdings: list[dict], frame: pd.DataFrame, rf: float = 0.0) -> list[dict]:
    """Kelly fraction f* = (μ − r) / σ² for each holding (capped 0–1).

    μ is the *arithmetic* annual return of simple daily returns. Using the
    mean log return understated every fraction by ½ (μ_log = μ − σ²/2) and
    the risk-free rate was ignored (audit C-09).
    """
    result = []
    for h in holdings:
        ticker = h["ticker"]
        if ticker not in frame.columns:
            continue
        px = frame[ticker].dropna().ffill()
        if len(px) < 20:
            result.append({"ticker": ticker, "kellyFraction": None,
                           "annReturn": None, "annVolatility": None})
            continue

        simple = px.pct_change().dropna()
        mu = float(simple.mean()) * TRADING_DAYS
        sigma2 = float(simple.var(ddof=1)) * TRADING_DAYS

        kelly = max(0.0, min(1.0, (mu - rf) / sigma2)) if sigma2 > 0 else 0.0
        ann_vol = math.sqrt(sigma2) if sigma2 > 0 else None

        result.append({
            "ticker": ticker,
            "kellyFraction": _clean(kelly),
            "annReturn": _clean(mu),
            "annVolatility": _clean(ann_vol),
        })
    return result


def ff_attribution_portfolio(
    holdings: list[dict],
    frame: pd.DataFrame,
    model: str,
    rf: float,
) -> dict:
    """Fama-French attribution for the portfolio (simple returns, matching
    the Ken French factor files)."""
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present:
        return {"error": "no holdings found in price data"}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}
    port_ret = _portfolio_returns(frame, weights)

    factors = load_ff_factors(model)
    if factors is None or factors.empty:
        return {"error": "factor data unavailable"}

    from .fama_french import _FF3_COLS, _FF5_COLS, _FF3_URL, _FF5_URL
    factor_cols_all = _FF5_COLS if model == "5" else _FF3_COLS
    factor_cols = [c for c in factor_cols_all if c != "RF"]
    if not all(c in factors.columns for c in factor_cols + ["RF"]):
        return {"error": "factor data missing expected columns"}

    port_ret.index = pd.to_datetime(port_ret.index).tz_localize(None)
    factors.index = pd.to_datetime(factors.index).tz_localize(None)

    merged = pd.concat(
        [port_ret.rename("ret"), factors[factor_cols + ["RF"]]],
        axis=1, join="inner"
    ).dropna()

    if len(merged) < 20:
        return {"error": "insufficient aligned observations"}

    excess_ret = (merged["ret"] - merged["RF"]).values
    factor_matrix = merged[factor_cols].values

    ols = _ols(excess_ret, factor_matrix)

    alpha_daily = ols["alpha"]
    ann_alpha = alpha_daily * TRADING_DAYS

    factor_names = [c.replace("-", "") for c in factor_cols]
    factors_out = [
        {
            "name": name,
            "loading": _clean(ols["betas"][i]) if i < len(ols["betas"]) else None,
            "tStat": _clean(ols["t_stats"][i + 1]) if i + 1 < len(ols["t_stats"]) else None,
        }
        for i, name in enumerate(factor_names)
    ]

    obs = pv.last_date(merged)
    px = pv.ref("yahoo", None, "Daily adjusted close of the requested tickers",
                units="price (split/dividend adjusted)", frequency="daily", observed=pv.last_date(port_ret))
    kf = pv.ref("kenfrench",
                "F-F_Research_Data_5_Factors_2x3_daily" if model == "5" else "F-F_Research_Data_Factors_daily",
                f"Fama/French {model}-factor daily returns and the one-month T-bill rate (RF)",
                units="decimal daily return (the source file is in percent; divided by 100)", frequency="daily",
                url=_FF5_URL if model == "5" else _FF3_URL)
    reg = ("OLS of the portfolio's daily simple return minus Ken French RF on the daily factor returns, with an "
           f"intercept, over the {len(merged)} dates both series share")
    prov: dict = {
        "*": pv.derived(f"Fama-French {model}-factor regression of the portfolio: " + reg, [px, kf],
                        title="Fama-French attribution", observed=obs),
        "alpha": pv.derived("intercept of the regression (daily)", ["*"], title="Alpha (daily)", observed=obs),
        "annAlpha": pv.derived("daily alpha × 252", ["alpha"], title="Alpha (annualised)", observed=obs),
        "rSquared": pv.derived("1 − residual sum of squares ÷ total sum of squares", ["*"], title="R²", observed=obs),
        "nObs": pv.derived("count of dates shared by the portfolio and factor series", ["*"], title="Observations",
                           observed=obs),
    }
    for f in factors_out:
        prov[f"factors.{f['name']}.loading"] = pv.derived("regression coefficient on this factor", ["*"],
                                                          title=f"{f['name']} loading", observed=obs)
        prov[f"factors.{f['name']}.tStat"] = pv.derived("coefficient ÷ its OLS standard error", ["*"],
                                                        title=f"{f['name']} t-statistic", observed=obs)
    return pv.attach({
        "model": model,
        "alpha": _clean(alpha_daily),
        "annAlpha": _clean(ann_alpha),
        "factors": factors_out,
        "rSquared": _clean(ols["r_squared"]),
        "nObs": int(len(merged)),
    }, prov)


def efficient_frontier(
    holdings: list[dict],
    frame: pd.DataFrame,
    n_points: int = 50,
) -> dict:
    """Trace the mean-variance efficient frontier (long-only, SLSQP)."""
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if len(present) < 2:
        return {"error": "need at least 2 holdings with price data", "frontier": []}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    current_weights = np.array([max(h["weight"], 0.0) / total_w for h in present])
    tickers = [h["ticker"] for h in present]

    px = frame[tickers].dropna(how="all").ffill()
    log_ret = np.log(px / px.shift(1)).dropna(how="all")
    if len(log_ret) < 30:
        return {"error": "insufficient price history", "frontier": []}

    mu = log_ret.mean().values * TRADING_DAYS
    cov = log_ret.cov().values * TRADING_DAYS
    n = len(tickers)

    warning = None
    if n > 20:
        warning = "Efficient frontier computation may be slow for >20 holdings"

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
    ]
    bounds = [(0.0, 1.0)] * n
    w0 = np.full(n, 1.0 / n)

    def port_vol(w):
        return math.sqrt(max(float(w @ cov @ w), 0.0))

    def port_ret_fn(w):
        return float(mu @ w)

    # Current portfolio stats
    cur_vol = port_vol(current_weights)
    cur_ret = port_ret_fn(current_weights)
    rf = risk_free_rate()
    cur_sharpe = (cur_ret - rf) / cur_vol if cur_vol > 0 else None

    # Sweep target returns
    min_ret_result = minimize(
        lambda w: float(mu @ w),
        w0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 500},
    )
    max_ret_result = minimize(
        lambda w: -float(mu @ w),
        w0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 500},
    )

    if not min_ret_result.success or not max_ret_result.success:
        return {"warning": warning, "frontier": [], "error": "optimisation failed"}

    ret_min = float(mu @ min_ret_result.x)
    ret_max = float(mu @ max_ret_result.x)

    target_rets = np.linspace(ret_min, ret_max, n_points)
    frontier_points = []

    for target in target_rets:
        cons = constraints + [
            {"type": "eq", "fun": lambda w, t=target: float(mu @ w) - t},
        ]
        res = minimize(
            lambda w: float(w @ cov @ w),
            w0, method="SLSQP", bounds=bounds, constraints=cons,
            options={"ftol": 1e-9, "maxiter": 500},
        )
        if res.success:
            vol = port_vol(res.x)
            ret = float(mu @ res.x)
            sh = (ret - rf) / vol if vol > 0 else None
            frontier_points.append({
                "vol": _clean(vol),
                "ret": _clean(ret),
                "sharpe": _clean(sh),
            })

    # Max Sharpe portfolio
    def neg_sharpe(w):
        v = math.sqrt(max(float(w @ cov @ w), 1e-12))
        return -(float(mu @ w) - rf) / v

    ms_res = minimize(
        neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 500},
    )
    max_sharpe = {}
    if ms_res.success:
        ms_w = ms_res.x
        ms_vol = port_vol(ms_w)
        ms_ret = float(mu @ ms_w)
        ms_sh = (ms_ret - rf) / ms_vol if ms_vol > 0 else None
        max_sharpe = {
            "vol": _clean(ms_vol),
            "ret": _clean(ms_ret),
            "sharpe": _clean(ms_sh),
            "weights": [{"ticker": tickers[i], "weight": _clean(float(ms_w[i]))} for i in range(n)],
        }

    result = {
        "frontier": frontier_points,
        "maxSharpe": max_sharpe,
        "currentPortfolio": {
            "vol": _clean(cur_vol),
            "ret": _clean(cur_ret),
            "sharpe": _clean(cur_sharpe),
        },
    }
    if warning:
        result["warning"] = warning
    return result


def monte_carlo_weights(
    holdings: list[dict],
    frame: pd.DataFrame,
    n_sim: int = 10_000,
) -> dict:
    """Random Dirichlet weight vectors mapped to (return, vol, Sharpe) space."""
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if len(present) < 2:
        return {"error": "need at least 2 holdings", "points": [], "maxSharpe": {}}

    tickers = [h["ticker"] for h in present]
    px = frame[tickers].dropna(how="all").ffill()
    log_ret = np.log(px / px.shift(1)).dropna(how="all")
    if len(log_ret) < 20:
        return {"error": "insufficient price history", "points": [], "maxSharpe": {}}

    mu = log_ret.mean().values * TRADING_DAYS
    cov = log_ret.cov().values * TRADING_DAYS
    n = len(tickers)
    rf = risk_free_rate()

    rng = np.random.default_rng(seed=42)
    # Dirichlet(1, …, 1) = uniform on the simplex
    weights_matrix = rng.dirichlet(np.ones(n), size=n_sim)

    rets = weights_matrix @ mu
    vols = np.sqrt(np.einsum("ij,jk,ik->i", weights_matrix, cov, weights_matrix))
    sharpes = np.where(vols > 0, (rets - rf) / vols, np.nan)

    best_idx = int(np.nanargmax(sharpes))
    best_weights = weights_matrix[best_idx]

    # Sample to max 5000 points for response size
    MAX_POINTS = 5000
    if n_sim > MAX_POINTS:
        idx = rng.choice(n_sim, size=MAX_POINTS, replace=False)
    else:
        idx = np.arange(n_sim)

    points = [
        {
            "vol": _clean(float(vols[i])),
            "ret": _clean(float(rets[i])),
            "sharpe": _clean(float(sharpes[i])),
        }
        for i in idx
    ]

    return {
        "points": points,
        "maxSharpe": {
            "vol": _clean(float(vols[best_idx])),
            "ret": _clean(float(rets[best_idx])),
            "sharpe": _clean(float(sharpes[best_idx])),
            "weights": [
                {"ticker": tickers[i], "weight": _clean(float(best_weights[i]))}
                for i in range(n)
            ],
        },
    }


def black_litterman(
    holdings: list[dict],
    frame: pd.DataFrame,
    views: list[dict],
    rf: float,
    market_caps: dict[str, float] | None = None,
) -> dict:
    """Black-Litterman posterior returns + optimal weights.

    views = [{"ticker": ..., "expectedReturn": ...}] — absolute (total) return
    views. Internally everything is in *excess* returns: the equilibrium
    π = δΣw is an excess return, so views are converted with q − rf and the
    optimal weights are (δΣ)⁻¹μ_BL with no second rf subtraction. Reported
    returns are total (excess + rf). Previously excess π was blended with
    absolute views and rf was subtracted again from the posterior (C-08).

    The prior is market-cap weighted when ``market_caps`` covers every
    holding (the model's intended "market" portfolio), else the portfolio's
    own weights — ``priorWeights`` in the response says which.
    """
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if len(present) < 2:
        return {"error": "need at least 2 holdings for Black-Litterman"}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    w_cur = np.array([max(h["weight"], 0.0) / total_w for h in present])
    tickers = [h["ticker"] for h in present]
    n = len(tickers)
    caps = [(market_caps or {}).get(t) for t in tickers]
    if all(c and c > 0 for c in caps):
        w_mkt = np.array(caps, dtype=float) / float(sum(caps))
        prior_basis = "marketCap"
    else:
        w_mkt = w_cur
        prior_basis = "portfolio"

    px = frame[tickers].dropna(how="all").ffill()
    log_ret = np.log(px / px.shift(1)).dropna(how="all")
    if len(log_ret) < 20:
        return {"error": "insufficient price history"}

    cov = log_ret.cov().values * TRADING_DAYS

    # Reverse optimisation: equilibrium returns π = δ Σ w_mkt
    delta = 2.5
    pi = delta * cov @ w_mkt

    tau = 0.05

    # Build view matrices P, q, Ω
    valid_views = [v for v in views if v.get("ticker") in tickers]
    if not valid_views:
        # No views: return equilibrium weights
        eq_returns = [
            {"ticker": tickers[i], "equilibriumReturn": _clean(float(pi[i] + rf)),
             "blReturn": _clean(float(pi[i] + rf))}
            for i in range(n)
        ]
        return {
            "blReturns": eq_returns,
            "optimalWeights": [{"ticker": tickers[i], "weight": _clean(float(w_mkt[i]))} for i in range(n)],
            "currentWeights": [{"ticker": tickers[i], "weight": _clean(float(w_cur[i]))} for i in range(n)],
            "priorWeights": prior_basis,
        }

    k = len(valid_views)
    P = np.zeros((k, n))
    q = np.zeros(k)
    for i, v in enumerate(valid_views):
        j = tickers.index(v["ticker"])
        P[i, j] = 1.0
        q[i] = float(v["expectedReturn"]) - rf  # absolute view → excess

    # Ω = τ * P Σ P'  (proportional uncertainty)
    omega = tau * P @ cov @ P.T

    # BL posterior mean:
    # μ_BL = [(τΣ)⁻¹ + P'Ω⁻¹P]⁻¹ [(τΣ)⁻¹π + P'Ω⁻¹q]
    tau_cov = tau * cov
    try:
        tau_cov_inv = np.linalg.inv(tau_cov)
    except np.linalg.LinAlgError:
        tau_cov_inv = np.linalg.pinv(tau_cov)

    try:
        omega_inv = np.linalg.inv(omega)
    except np.linalg.LinAlgError:
        omega_inv = np.linalg.pinv(omega)

    M_inv = tau_cov_inv + P.T @ omega_inv @ P
    try:
        M = np.linalg.inv(M_inv)
    except np.linalg.LinAlgError:
        M = np.linalg.pinv(M_inv)

    mu_bl = M @ (tau_cov_inv @ pi + P.T @ omega_inv @ q)

    # Optimal weights via unconstrained MV: w* = (δΣ)⁻¹ μ_BL, then normalise
    try:
        cov_inv = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        cov_inv = np.linalg.pinv(cov)

    w_opt_raw = cov_inv @ mu_bl / delta  # μ_BL is already an excess return
    # Long-only: floor at 0 and renormalise
    w_opt = np.maximum(w_opt_raw, 0.0)
    w_sum = w_opt.sum()
    if w_sum > 0:
        w_opt = w_opt / w_sum
    else:
        w_opt = w_mkt.copy()

    bl_returns = [
        {
            "ticker": tickers[i],
            "equilibriumReturn": _clean(float(pi[i] + rf)),
            "blReturn": _clean(float(mu_bl[i] + rf)),
        }
        for i in range(n)
    ]

    return {
        "blReturns": bl_returns,
        "optimalWeights": [
            {"ticker": tickers[i], "weight": _clean(float(w_opt[i]))}
            for i in range(n)
        ],
        "currentWeights": [
            {"ticker": tickers[i], "weight": _clean(float(w_cur[i]))}
            for i in range(n)
        ],
        "priorWeights": prior_basis,
    }


def stress_test_portfolio(
    holdings: list[dict],
    frame: pd.DataFrame,
    bench_col: str,
) -> list[dict]:
    """Replay historical stress scenarios on the portfolio."""
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present:
        return []

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}
    cols = list(weights.keys())

    px = frame[cols].dropna(how="all").ffill()
    px.index = pd.to_datetime(px.index)

    bench_px = frame[bench_col].dropna().ffill() if bench_col in frame.columns else None
    if bench_px is not None:
        bench_px.index = pd.to_datetime(bench_px.index)

    results = []
    for key, (start, end, label) in _STRESS_SCENARIOS.items():
        scenario_px = px.loc[start:end]
        if len(scenario_px) < 5:
            results.append({
                "scenario": key,
                "label": label,
                "start": start,
                "end": end,
                "error": "insufficient historical data for this scenario period",
                "totalReturn": None,
                "maxDrawdown": None,
                "returnsTimeSeries": [],
                "benchmark": [],
            })
            continue

        # Weighted simple returns (holdings that had not listed yet are
        # excluded that day rather than counted as flat).
        port_log_ret = np.log1p(_portfolio_returns(scenario_px, weights))

        cum_ret = np.exp(port_log_ret.cumsum()) - 1.0
        total_return = float(cum_ret.iloc[-1]) if len(cum_ret) else None

        # Max drawdown within scenario
        cum_value = np.exp(port_log_ret.cumsum())
        cum_max = cum_value.cummax()
        dd = (cum_value / cum_max) - 1.0
        max_dd = float(dd.min()) if len(dd) else None

        bench_series_out: list[dict] = []
        if bench_px is not None:
            bench_scenario = bench_px.loc[start:end]
            if len(bench_scenario) >= 5:
                bench_log_ret = np.log(bench_scenario / bench_scenario.shift(1)).dropna()
                bench_cum = np.exp(bench_log_ret.cumsum()) - 1.0
                bench_series_out = _series_to_points(bench_cum)

        results.append({
            "scenario": key,
            "label": label,
            "start": start,
            "end": end,
            "totalReturn": _clean(total_return),
            "maxDrawdown": _clean(max_dd),
            "returnsTimeSeries": _series_to_points(cum_ret),
            "benchmark": bench_series_out,
        })

    return results
