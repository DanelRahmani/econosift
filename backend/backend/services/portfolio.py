"""Portfolio aggregation: weighted performance, P&L, and risk metrics."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from . import metrics

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

    # Daily simple returns per holding, aligned.
    cols = list(weights.keys())
    px = frame[cols].dropna(how="all").ffill()
    rets = px.pct_change().dropna(how="all").fillna(0.0)

    # Weighted portfolio simple return series.
    w_vec = np.array([weights[c] for c in cols])
    port_ret = rets[cols].to_numpy() @ w_vec
    port_ret = pd.Series(port_ret, index=rets.index)

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

    downside = log_ret[log_ret < 0]
    downside_dev = downside.std(ddof=1) * math.sqrt(TRADING_DAYS) if len(downside) > 1 else None
    sortino = ((ann_return - risk_free) / downside_dev) if downside_dev and downside_dev > 0 else None

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

    return {
        "holdings": holding_rows,
        "series": series,
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
