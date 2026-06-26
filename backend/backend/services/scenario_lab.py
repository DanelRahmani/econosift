"""Scenario Lab service for evaluating historical and custom macro shocks."""
from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime

from .advanced_risk import _STRESS_SCENARIOS
from .portfolio import analyze, _clean

# Predefined shocks for historical episodes (simplified estimates for macro variables)
HISTORICAL_SHOCKS = {
    "1987_crash": {"equities": -0.20, "rates": -0.50, "credit": 1.50},
    "1998_ltcm": {"equities": -0.15, "rates": -0.75, "credit": 2.00},
    "2001_dotcom": {"equities": -0.40, "rates": -2.00, "credit": 3.00},
    "2008_gfc": {"equities": -0.50, "rates": -4.00, "credit": 8.00},
    "2020_covid": {"equities": -0.30, "rates": -1.50, "credit": 5.00},
    "2022_inflation": {"equities": -0.20, "rates": 3.00, "credit": 1.50},
    "2023_regional_banks": {"equities": -0.10, "rates": -0.50, "credit": 1.00},
}

def get_historical_episodes() -> list[dict]:
    """Return available historical episodes and their metadata."""
    episodes = []
    for key, (start, end, label) in _STRESS_SCENARIOS.items():
        episodes.append({
            "id": key,
            "label": label,
            "start": start,
            "end": end,
            "shocks": HISTORICAL_SHOCKS.get(key, {})
        })
    return episodes

def simulate_custom_shock(
    holdings: list[dict],
    frame: pd.DataFrame,
    shocks: dict[str, float]
) -> dict:
    """
    Simulate a custom macro shock on a portfolio using simple beta exposure.
    Shocks: {"equities": pct_change, "rates": bps_change, "credit": bps_change}
    
    Uses ^GSPC for equity beta, TLT for rates beta, HYG for credit beta.
    """
    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present:
        return {"error": "no valid holdings"}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}
    
    px = frame.dropna(how="all").ffill()
    rets = px.pct_change().dropna(how="all").fillna(0.0)

    # Calculate portfolio return
    cols = list(weights.keys())
    w_vec = np.array([weights[c] for c in cols])
    port_ret = rets[cols].to_numpy() @ w_vec
    port_ret_series = pd.Series(port_ret, index=rets.index)

    impacts = []
    total_impact = 0.0

    # Equity shock (pct)
    if "equities" in shocks and "^GSPC" in rets.columns:
        spy_ret = rets["^GSPC"]
        cov = port_ret_series.cov(spy_ret)
        var = spy_ret.var()
        beta_eq = cov / var if var > 0 else 0
        eq_impact = beta_eq * shocks["equities"]
        impacts.append({"factor": "Equities", "beta": _clean(beta_eq), "impact": _clean(eq_impact)})
        total_impact += eq_impact

    # Rates shock (bps -> pct roughly)
    # Using TLT as proxy: a 100bps rate increase ~ -17% TLT drop (assuming 17y duration)
    if "rates" in shocks and "TLT" in rets.columns:
        tlt_ret = rets["TLT"]
        cov = port_ret_series.cov(tlt_ret)
        var = tlt_ret.var()
        beta_rates = cov / var if var > 0 else 0
        tlt_shock = -(shocks["rates"] / 100.0) * 0.17
        rate_impact = beta_rates * tlt_shock
        impacts.append({"factor": "Rates", "beta": _clean(beta_rates), "impact": _clean(rate_impact)})
        total_impact += rate_impact

    # Credit shock (bps -> pct roughly)
    # Using HYG as proxy: a 100bps spread widening ~ -4% HYG drop (assuming 4y spread duration)
    if "credit" in shocks and "HYG" in rets.columns:
        hyg_ret = rets["HYG"]
        cov = port_ret_series.cov(hyg_ret)
        var = hyg_ret.var()
        beta_credit = cov / var if var > 0 else 0
        hyg_shock = -(shocks["credit"] / 100.0) * 0.04
        credit_impact = beta_credit * hyg_shock
        impacts.append({"factor": "Credit", "beta": _clean(beta_credit), "impact": _clean(credit_impact)})
        total_impact += credit_impact

    return {
        "shocks": shocks,
        "impacts": impacts,
        "totalImpactPct": _clean(total_impact),
    }
