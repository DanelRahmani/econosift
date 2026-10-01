"""Treasury curve-fit noise — Phase 39.

Hu, Pan & Wang (2013, JF), *"Noise as Information for Illiquidity"*, show that
the dispersion of individual Treasury yields around a smooth fitted curve is a
good gauge of how much arbitrage capital is deployed in fixed income. When
intermediaries are well capitalised, relative-value desks iron out the curve;
when they are constrained, bonds drift off it. The measure spikes in every
funding crisis and predicts hedge-fund returns.

**Scope caveat — read this before trusting the level.** HPW fit a Svensson
curve to *individual off-the-run bond prices*. We only have the daily CMT
constant-maturity series, which is itself already the Treasury's own smoothed
spline through the curve. Fitting Nelson-Siegel to CMT therefore measures how
far Treasury's spline departs from a three-factor shape — a genuine
curve-dislocation signal, but a materially weaker and lower-amplitude one than
HPW's bond-level measure. It is labelled "curve-fit noise" rather than "the HPW
noise measure" for that reason, and the levels are not comparable to the
published HPW series.
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

# (FRED series, maturity in years) — the CMT curve.
_TENORS: list[tuple[str, float]] = [
    ("DGS1MO", 1 / 12),
    ("DGS3MO", 0.25),
    ("DGS6MO", 0.5),
    ("DGS1", 1.0),
    ("DGS2", 2.0),
    ("DGS3", 3.0),
    ("DGS5", 5.0),
    ("DGS7", 7.0),
    ("DGS10", 10.0),
    ("DGS20", 20.0),
    ("DGS30", 30.0),
]
_START = "2000-01-01"

# Nelson-Siegel decay. In years, lambda = 0.7308 puts peak curvature loading at
# ~2.45y, the Diebold & Li (2006) convention.
_LAMBDA = 0.7308
_MIN_TENORS = 6  # need meaningfully more points than the 3 fitted factors


def _ns_loadings(tau: np.ndarray) -> np.ndarray:
    """Nelson-Siegel design matrix [level, slope, curvature] for maturities tau."""
    lt = _LAMBDA * tau
    # (1 - e^-lt) / lt, with the lt -> 0 limit of 1 handled explicitly.
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(lt > 1e-8, (1.0 - np.exp(-lt)) / lt, 1.0)
    curve = slope - np.exp(-lt)
    return np.column_stack([np.ones_like(tau), slope, curve])


def _compute_noise(curve: pd.DataFrame) -> list[dict]:
    """Per-date RMSE (bps) of CMT yields around a fitted Nelson-Siegel curve.

    ``curve`` is a DataFrame indexed by date with one column per maturity (in
    years). Pure compute — no network — so it is unit-testable offline.
    """
    if curve.empty:
        return []
    maturities = np.array([float(c) for c in curve.columns], dtype=float)
    out: list[dict] = []
    for date, row in curve.iterrows():
        vals = row.to_numpy(dtype=float)
        mask = ~np.isnan(vals)
        if int(mask.sum()) < _MIN_TENORS:
            continue
        y = vals[mask]
        X = _ns_loadings(maturities[mask])
        try:
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        resid = y - X @ beta
        # Yields are in percent; x100 -> basis points.
        rmse_bps = float(np.sqrt(np.mean(resid ** 2)) * 100.0)
        out.append({"date": str(pd.Timestamp(date).date()), "value": round(rmse_bps, 3)})
    return out


def _percentile_rank(series: list[dict], value: float | None) -> float | None:
    if value is None or not series:
        return None
    vals = np.array([p["value"] for p in series], dtype=float)
    return round(float((vals <= value).mean() * 100.0), 1)


def _provenance(observed: str) -> dict:
    """Source map for the curve-fit noise payload (see provenance.py)."""
    ids = ", ".join(sid for sid, _ in _TENORS)
    return {
        "*": pv.derived(
            "RMSE (in bp) of the residuals from a daily Nelson-Siegel fit (lambda=0.7308) "
            "to the Treasury constant-maturity yields",
            ["cmt_yields"], title="Treasury curve-fit noise", observed=observed,
            note="Fitted to CMT yields, which are already Treasury's smoothed curve, so levels are not "
                 "comparable to the Hu-Pan-Wang bond-level measure."),
        "cmt_yields": pv.ref("fred", None, f"Treasury constant-maturity yields ({ids})", units="percent",
                             frequency="daily", observed=observed),
        "kpis.ma20": pv.derived("mean of the last 20 daily noise values", ["*"],
                                title="20-day average noise", observed=observed),
        "kpis.percentile": pv.derived("share of all daily noise values since 2000 that are <= the latest, x100",
                                      ["*"], title="Percentile of latest noise", observed=observed),
        "kpis.median": pv.derived("median of all daily noise values since 2000", ["*"],
                                  title="Median noise", observed=observed),
        "kpis.max": pv.derived("maximum of all daily noise values since 2000", ["*"],
                               title="Maximum noise", observed=observed),
    }


def _is_empty(result: dict) -> bool:
    return not result or not result.get("history")


@async_cached("treasury_noise", skip_if=_is_empty)
async def get_treasury_noise() -> dict:
    """Daily Nelson-Siegel curve-fit noise across the CMT tenors, in bps."""
    if not FRED_API_KEY:
        return {"error": "FRED API key required", "history": []}

    data = await mes.fetch_fred_series(tuple(sid for sid, _ in _TENORS), start=_START)

    cols: dict[float, pd.Series] = {}
    for sid, years in _TENORS:
        pts = [(p["date"], p["value"]) for p in data.get(sid, []) if p.get("value") is not None]
        if pts:
            cols[years] = pd.Series({pd.Timestamp(d): float(v) for d, v in pts})
    if not cols:
        return {"error": "no Treasury curve data available", "history": []}

    curve = pd.DataFrame(cols).sort_index()
    history = await asyncio.to_thread(_compute_noise, curve)  # daily curve fits: CPU-bound
    if not history:
        return {"error": "insufficient tenor coverage to fit a curve", "history": []}

    latest = history[-1]["value"]
    vals = np.array([p["value"] for p in history], dtype=float)
    recent = [p for p in history if p["date"] >= "2020-01-01"]
    ma20 = float(np.mean(vals[-20:])) if len(vals) >= 20 else float(np.mean(vals))

    return pv.attach({
        "kpis": {
            "latest": latest,
            "asOf": history[-1]["date"],
            "ma20": round(ma20, 3),
            "percentile": _percentile_rank(history, latest),
            "median": round(float(np.median(vals)), 3),
            "max": round(float(vals.max()), 3),
        },
        "history": history,
        "recent": recent,
        "method": (
            "Nelson-Siegel (lambda=0.7308, Diebold-Li convention) fitted daily by "
            "least squares to the CMT tenors; the reported value is the RMSE of "
            "the fit in basis points. This approximates the Hu-Pan-Wang (2013) "
            "noise measure in spirit, but HPW fit individual off-the-run bond "
            "prices whereas CMT is already a smoothed official curve — so levels "
            "are lower and not comparable to the published HPW series."
        ),
        "limitation": (
            "Measured on this data, the series rose to ~20bps through the 2008 "
            "crisis against ~7bps in calm 2017, but stayed near ~10bps in March "
            "2020 — the worst Treasury dislocation on record. CMT is an official "
            "smoothed curve, so it cannot show the on-the-run/off-the-run "
            "dislocation that defined 2020. Read this as a curve-SHAPE stress "
            "gauge, not a market-liquidity gauge; it will miss dash-for-cash "
            "events."
        ),
        "sources": "FRED constant-maturity Treasury series (DGS1MO..DGS30)",
    }, _provenance(history[-1]["date"]))
