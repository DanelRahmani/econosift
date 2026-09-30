"""Recession Probability Model — NY-Fed-style 12-month-ahead yield-curve probit.

P(USREC_{t+12} = 1) = Phi(alpha + beta * spread_t), fit by maximum likelihood
over the 10y-3m Treasury spread (T10Y3M), using monthly means aligned against
the NBER recession indicator (USREC) shifted 12 months forward. Also surfaces
the FRED-published smoothed recession probability (RECPROUSM156N) and the
real-time Sahm rule indicator (SAHMREALTIME) for context.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import optimize
from scipy.stats import norm

from .. import provenance as pv
from ..cache import async_cached
from ..config import FRED_API_KEY
from . import macro_expansion_service as mes

log = logging.getLogger(__name__)

_SERIES = ("T10Y3M", "USREC", "RECPROUSM156N", "SAHMREALTIME")
_START = "1985-01-01"
_MIN_OBS = 24


def _latest(pts: list[dict]) -> float | None:
    for pt in reversed(pts):
        v = pt.get("value")
        if v is not None:
            try:
                return round(float(v), 4)
            except (TypeError, ValueError):
                continue
    return None


def _monthly_mean(pts: list[dict]) -> list[dict]:
    """[{date, value}] (any frequency) -> monthly-mean [{date: YYYY-MM, value}]."""
    clean = [(p["date"], p["value"]) for p in pts if p.get("value") is not None]
    if not clean:
        return []
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in clean}).sort_index()
    monthly = s.resample("MS").mean()
    return [
        {"date": idx.strftime("%Y-%m"), "value": round(float(v), 4)}
        for idx, v in monthly.dropna().items()
    ]


def _fit_probit(spread: list[float], y: list[int]) -> tuple[float | None, float | None]:
    """MLE probit fit: P(y=1) = Phi(alpha + beta*spread). (None, None) if degenerate."""
    n = len(spread)
    if n < _MIN_OBS or n != len(y):
        return None, None
    y_arr = np.asarray(y, dtype=float)
    if y_arr.sum() == 0 or y_arr.sum() == n:
        return None, None
    x_arr = np.asarray(spread, dtype=float)

    def _neg_log_lik(params: np.ndarray) -> float:
        alpha, beta = params
        z = np.clip(alpha + beta * x_arr, -30.0, 30.0)
        ll = y_arr * norm.logcdf(z) + (1.0 - y_arr) * norm.logcdf(-z)
        return -float(np.sum(ll))

    result = optimize.minimize(_neg_log_lik, x0=np.array([0.0, -0.5]), method="Nelder-Mead")
    if not result.success:
        result = optimize.minimize(_neg_log_lik, x0=np.array([0.0, -0.5]), method="BFGS")
    if not result.success:
        return None, None
    alpha, beta = result.x
    return float(alpha), float(beta)


def _extract_recessions(usrec_pts: list[dict]) -> list[dict]:
    """USREC points -> [{start, end}] episodes (YYYY-MM); end = last month with value 1."""
    episodes: list[dict] = []
    in_rec = False
    start: str | None = None
    end: str | None = None
    for p in usrec_pts:
        v = p.get("value")
        if v is None:
            continue
        ym = p["date"][:7]
        if int(v) == 1:
            if not in_rec:
                in_rec = True
                start = ym
            end = ym
        elif in_rec:
            episodes.append({"start": start, "end": end})
            in_rec = False
    if in_rec and start is not None:
        episodes.append({"start": start, "end": end})
    return episodes


def _walk_forward_probit(
    monthly_spread: list[dict],
    usrec_map: dict[str, float],
    min_train: int = 120,
) -> list[dict]:
    """Out-of-sample recession probability using only data available at the time.

    The in-sample path fits one probit over the whole history and then applies
    those coefficients back across it, so every point is informed by recessions
    that had not happened yet. This refits at each month on the observations
    whose 12-month-ahead outcome was already known by then, and predicts one
    step out — what the model would actually have printed at the time.

    Note the remaining, irreducible look-ahead: NBER dates recessions with a lag
    of months, so even a walk-forward fit uses labels nobody had contemporaneously.
    This is the standard caveat on every yield-curve recession model, not a
    defect that can be engineered away with free data.
    """
    if not monthly_spread:
        return []

    def _add_months(ym: str, n: int) -> str:
        return str(pd.Period(ym, freq="M") + n)

    out: list[dict] = []
    alpha = beta = None
    for i, pt in enumerate(monthly_spread):
        now = pt["date"]
        # Training pairs whose outcome month is already in the past at `now`.
        xs: list[float] = []
        ys: list[int] = []
        for prev in monthly_spread[:i]:
            target_month = _add_months(prev["date"], 12)
            if target_month > now:
                continue
            target = usrec_map.get(target_month)
            if target is not None:
                xs.append(prev["value"])
                ys.append(int(target))

        if len(xs) >= min_train:
            fitted_a, fitted_b = _fit_probit(xs, ys)
            if fitted_a is not None and fitted_b is not None:
                alpha, beta = fitted_a, fitted_b

        if alpha is not None and beta is not None:
            p = float(norm.cdf(alpha + beta * pt["value"])) * 100.0
            out.append({"date": now, "value": round(p, 2)})

    return out


def _compute_recession(data: dict[str, list[dict]]) -> dict:
    """Pure computation over already-fetched FRED points; unit-testable."""
    if not data:
        return {}

    spread_pts = data.get("T10Y3M", [])
    usrec_pts = data.get("USREC", [])
    smoothed_pts = data.get("RECPROUSM156N", [])
    sahm_pts = data.get("SAHMREALTIME", [])

    monthly_spread = _monthly_mean(spread_pts)
    if not monthly_spread:
        return {}

    usrec_map = {p["date"][:7]: p["value"] for p in usrec_pts if p.get("value") is not None}

    def _add_months(ym: str, n: int) -> str:
        return str(pd.Period(ym, freq="M") + n)

    train_x: list[float] = []
    train_y: list[int] = []
    for pt in monthly_spread:
        target_val = usrec_map.get(_add_months(pt["date"], 12))
        if target_val is not None:
            train_x.append(pt["value"])
            train_y.append(int(target_val))

    alpha, beta = _fit_probit(train_x, train_y)

    prob_history: list[dict] = []
    if alpha is not None and beta is not None:
        for pt in monthly_spread:
            p = float(norm.cdf(alpha + beta * pt["value"])) * 100.0
            prob_history.append({"date": pt["date"], "value": round(p, 2)})

    # Out-of-sample path: what the model would have printed at the time.
    realtime_history = _walk_forward_probit(monthly_spread, usrec_map)

    months_inverted = 0
    for pt in reversed(monthly_spread):
        if pt["value"] < 0:
            months_inverted += 1
        else:
            break

    recessions = _extract_recessions(usrec_pts)

    prob12m = prob_history[-1]["value"] if prob_history else None

    return {
        "asOf": prob_history[-1]["date"] if prob_history else None,
        "kpis": {
            "prob12m": prob12m,
            "sahm": _latest(sahm_pts),
            "spreadPct": _latest(spread_pts),
            "monthsInverted": months_inverted,
            "smoothedProb": _latest(smoothed_pts),
            "prob12mRealtime": _latest(realtime_history),
        },
        "history": {
            "probability": prob_history,
            "probabilityRealtime": realtime_history,
            "spread": monthly_spread,
            "sahm": sahm_pts,
            "smoothedProb": smoothed_pts,
        },
        "recessions": recessions,
        "model": {
            "alpha": round(alpha, 6) if alpha is not None else None,
            "beta": round(beta, 6) if beta is not None else None,
            "nObs": len(train_x),
            "note": (
                "`probability` is in-sample: one probit fitted over the whole "
                "history and applied back across it, so every point is informed "
                "by recessions that had not happened yet. `probabilityRealtime` "
                "refits each month on data available at the time. NBER dates "
                "recessions with a lag, so even the real-time path uses labels "
                "nobody had contemporaneously."
            ),
        },
    }


def _provenance(data: dict[str, list[dict]], result: dict) -> dict:
    def last(sid: str) -> str | None:
        pts = [p for p in data.get(sid, []) if p.get("value") is not None]
        return pts[-1]["date"] if pts else None

    spread = pv.fred("T10Y3M", "10-year minus 3-month Treasury constant maturity spread", units="%",
                     frequency="daily", observed=last("T10Y3M"))
    usrec = pv.fred("USREC", "NBER recession indicator (1 = recession)", frequency="monthly",
                    observed=last("USREC"))
    smoothed = pv.fred("RECPROUSM156N", "Smoothed US recession probabilities", units="%", frequency="monthly",
                       observed=last("RECPROUSM156N"))
    sahm = pv.fred("SAHMREALTIME", "Real-time Sahm rule recession indicator", units="percentage points",
                   frequency="monthly", observed=last("SAHMREALTIME"))
    monthly_spread = pv.derived("monthly mean of daily T10Y3M", [spread], title="10y-3m spread, monthly mean",
                                observed=(result.get("history", {}).get("spread") or [{}])[-1].get("date"))
    prob = pv.derived(
        "Phi(alpha + beta x spread) x 100, spread = monthly mean of T10Y3M; alpha, beta fitted once by maximum-"
        "likelihood probit over the whole sample against USREC shifted 12 months ahead (in-sample)",
        [monthly_spread, usrec], title="12-month-ahead recession probability (in-sample)",
        observed=result.get("asOf"))
    realtime = pv.derived(
        "same probit, refitted each month using only observations whose 12-month-ahead outcome was already "
        "known, then applied to that month's spread (walk-forward)", [monthly_spread, usrec],
        title="12-month-ahead recession probability (real-time refit)",
        observed=((result.get("history", {}).get("probabilityRealtime") or [{}])[-1]).get("date"))
    return {
        "*": prob,
        "kpis.prob12m": prob, "history.probability": prob,
        "kpis.prob12mRealtime": realtime, "history.probabilityRealtime": realtime,
        "kpis.sahm": sahm, "history.sahm": sahm,
        "kpis.spreadPct": spread,
        "history.spread": monthly_spread,
        "kpis.monthsInverted": pv.derived("count of consecutive most recent months whose monthly mean spread "
                                          "is below 0", [monthly_spread], title="Months inverted",
                                          observed=result.get("asOf")),
        "kpis.smoothedProb": smoothed, "history.smoothedProb": smoothed,
        "recessions": pv.derived("months where USREC = 1, grouped into start/end episodes", [usrec],
                                 title="NBER recession episodes"),
        "model": pv.derived("maximum-likelihood probit fit of USREC (12 months ahead) on the monthly mean "
                            "10y-3m spread; nObs = months used", [monthly_spread, usrec],
                            title="Probit coefficients"),
    }


@async_cached("recession_probability")
async def get_recession_probability() -> dict:
    """NY-Fed-style 12-month-ahead recession probability from the 10y-3m spread."""
    if not FRED_API_KEY:
        return {"error": "FRED API key required"}

    data = await mes.fetch_fred_series(_SERIES, start=_START)
    result = _compute_recession(data)
    return pv.attach(result, _provenance(data, result)) if result else result
