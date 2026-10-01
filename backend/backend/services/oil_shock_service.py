"""Oil shock decomposition — Phase 39.

Kilian (2009, AER) showed that the *level* of the oil price is not an
interpretable signal: a rise driven by global demand is expansionary for
equities, while one driven by a supply disruption or precautionary hoarding is
contractionary. Kilian & Park (2009, IER) find US stock returns respond with
opposite signs depending on which shock dominates.

**What this implements — and what it does not.** This is a *reduced-form*
decomposition, not Kilian's structural VAR. We regress monthly real WTI returns
on two observable global-demand proxies — the change in Kilian's own Index of
Global Real Economic Activity (FRED ``IGREA``) and real copper returns — and
split the return into a fitted "demand-driven" component and a residual
"oil-specific (supply / precautionary)" component. It requires no sign
restrictions and no world oil-production series, but it also does not identify
structural shocks: the residual bundles genuine supply news with everything the
two proxies fail to span. Read it as a decomposition of *comovement*, not as
Kilian's SVAR.
"""
from __future__ import annotations

import asyncio

import logging

import numpy as np
import pandas as pd

from .. import provenance as pv
from ..cache import async_cached
from ..config import FRED_API_KEY
from . import macro_expansion_service as mes

log = logging.getLogger(__name__)

_SERIES = ("DCOILWTICO", "CPIAUCSL", "IGREA", "PCOPPUSDM")
_START = "1990-01-01"
_MIN_OBS = 60  # 5 years of monthly data before a regression is worth reporting


def _to_monthly(pts: list[dict]) -> pd.Series:
    """[{date, value}] -> month-end-indexed float Series (mean within month)."""
    rows = [(p["date"], p["value"]) for p in pts if p.get("value") is not None]
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in rows}).sort_index()
    return s.resample("ME").mean().dropna()


def _ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Least squares with heteroskedasticity-naive standard errors.

    Returns (coefficients, standard errors, R-squared). X must already include
    an intercept column.
    """
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = max(n - k, 1)
    sigma2 = float(resid @ resid) / dof
    try:
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    except np.linalg.LinAlgError:
        se = np.full(k, np.nan)
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(resid @ resid) / tss if tss > 0 else 0.0
    return beta, se, r2


def _decompose(
    wti: pd.Series, cpi: pd.Series, igrea: pd.Series, copper: pd.Series
) -> dict:
    """Split real oil returns into demand-driven and oil-specific components.

    Pure compute — no network — so it can be unit-tested against synthetic data.
    """
    df = pd.DataFrame({"wti": wti, "cpi": cpi, "igrea": igrea, "copper": copper}).dropna()
    if len(df) < _MIN_OBS + 1:
        return {"available": False, "reason": f"only {len(df)} aligned monthly observations"}

    # Deflate to real terms, then log returns in percent.
    real_oil = df["wti"] / df["cpi"] * 100.0
    real_copper = df["copper"] / df["cpi"] * 100.0
    r_oil = np.log(real_oil).diff() * 100.0
    r_copper = np.log(real_copper).diff() * 100.0
    d_igrea = df["igrea"].diff()

    reg = pd.DataFrame(
        {"r_oil": r_oil, "d_igrea": d_igrea, "r_copper": r_copper}
    ).dropna()
    if len(reg) < _MIN_OBS:
        return {"available": False, "reason": f"only {len(reg)} usable return observations"}

    y = reg["r_oil"].to_numpy(dtype=float)
    X = np.column_stack([
        np.ones(len(reg)),
        reg["d_igrea"].to_numpy(dtype=float),
        reg["r_copper"].to_numpy(dtype=float),
    ])
    beta, se, r2 = _ols(y, X)

    # Demand component excludes the intercept: it is the part of each month's
    # move that the global-demand proxies actually explain.
    demand = X[:, 1:] @ beta[1:]
    supply = y - beta[0] - demand

    dates = [str(d.date()) for d in reg.index]
    history = [
        {
            "date": d,
            "total": round(float(t), 3),
            "demand": round(float(dm), 3),
            "supply": round(float(sp), 3),
        }
        for d, t, dm, sp in zip(dates, y, demand, supply)
    ]

    def _t(i: int) -> float | None:
        if se[i] == 0 or np.isnan(se[i]):
            return None
        return round(float(beta[i] / se[i]), 2)

    last = history[-1]
    dominant = "demand" if abs(last["demand"]) >= abs(last["supply"]) else "supply"
    # Sign of the dominant driver decides the equity read-through.
    driver_val = last[dominant]
    if dominant == "demand":
        interpretation = "expansionary" if driver_val > 0 else "contractionary"
    else:
        interpretation = "contractionary" if driver_val > 0 else "expansionary"

    # Trailing-12-month cumulative attribution.
    tail = history[-12:]
    cum = {
        "total": round(sum(h["total"] for h in tail), 2),
        "demand": round(sum(h["demand"] for h in tail), 2),
        "supply": round(sum(h["supply"] for h in tail), 2),
        "months": len(tail),
    }

    return {
        "available": True,
        "latest": {
            "date": last["date"],
            "total": last["total"],
            "demand": last["demand"],
            "supply": last["supply"],
            "dominant": dominant,
            "interpretation": interpretation,
        },
        "trailing12m": cum,
        "regression": {
            "n": int(len(reg)),
            "r2": round(r2, 4),
            "beta_igrea": round(float(beta[1]), 4),
            "beta_copper": round(float(beta[2]), 4),
            "t_igrea": _t(1),
            "t_copper": _t(2),
            "sampleStart": dates[0],
            "sampleEnd": dates[-1],
        },
        "history": history,
    }


def _is_empty(result: dict) -> bool:
    return not result or not result.get("available")


def _provenance(data: dict[str, list[dict]], result: dict) -> dict:
    def fred(sid: str, title: str, freq: str, units: str) -> dict:
        pts = [p for p in data.get(sid, []) if p.get("value") is not None]
        return pv.fred(sid, title, units=units, frequency=freq, observed=pts[-1]["date"] if pts else None)

    inputs = [
        fred("DCOILWTICO", "Crude oil prices: West Texas Intermediate (WTI), Cushing", "daily", "USD per barrel"),
        fred("CPIAUCSL", "Consumer price index for all urban consumers, all items", "monthly", "index"),
        fred("IGREA", "Kilian index of global real economic activity", "monthly", "index"),
        fred("PCOPPUSDM", "Global price of copper", "monthly", "USD per metric ton"),
    ]
    latest_date = (result.get("latest") or {}).get("date")
    decomposition = pv.derived(
        "monthly means of each series; real WTI and real copper = price / CPI x 100; r_oil and r_copper = "
        "100 x monthly log change; OLS r_oil = b0 + b1 x change in IGREA + b2 x r_copper; demand = "
        "b1 x change in IGREA + b2 x r_copper; supply (oil-specific) = r_oil - b0 - demand",
        inputs, title="Demand vs oil-specific decomposition of real WTI returns", observed=latest_date)
    return {
        "*": decomposition, "history": decomposition,
        "latest": pv.derived("the last month of `history` (percent, log returns); dominant = the larger of "
                             "|demand| and |supply|", ["history"], title="Latest month", observed=latest_date),
        "trailing12m": pv.derived("sum of the last 12 months of `history` (percent, log returns)", ["history"],
                                  title="Trailing 12-month attribution", observed=latest_date),
        "regression": pv.derived(
            "OLS coefficients, classical standard errors (no heteroskedasticity correction) and R-squared of the "
            "regression above over the aligned monthly sample", inputs, title="Regression diagnostics",
            observed=(result.get("regression") or {}).get("sampleEnd")),
    }


@async_cached("oil_shocks", skip_if=_is_empty)
async def get_oil_shocks() -> dict:
    """Demand vs. oil-specific decomposition of real WTI returns."""
    if not FRED_API_KEY:
        return {"available": False, "reason": "FRED API key required"}

    data = await mes.fetch_fred_series(_SERIES, start=_START)
    result = await asyncio.to_thread(lambda: _decompose(  # pandas work: off the loop
        _to_monthly(data.get("DCOILWTICO", [])),
        _to_monthly(data.get("CPIAUCSL", [])),
        _to_monthly(data.get("IGREA", [])),
        _to_monthly(data.get("PCOPPUSDM", [])),
    ))
    result["method"] = (
        "Reduced-form OLS of real WTI monthly log returns on the change in "
        "Kilian's Index of Global Real Economic Activity and real copper "
        "returns. Fitted values = demand-driven; residual = oil-specific "
        "(supply / precautionary). This is a proxy for the Kilian (2009) "
        "decomposition, not the structural VAR — the residual bundles supply "
        "news with anything the demand proxies do not span."
    )
    result["sources"] = "FRED: DCOILWTICO, CPIAUCSL, IGREA, PCOPPUSDM"
    return pv.attach(result, _provenance(data, result)) if result.get("available") else result
