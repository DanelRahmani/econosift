"""Econometric Lab service: pooled OLS regression across World Bank panel data."""
from __future__ import annotations

import asyncio
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats

from ..cache import async_cached
from ..config import ISO2_TO_ISO3, COUNTRY_NAMES
from ..sources import source_worldbank as wb

_VALID: set[str] = set(wb.INDICATOR_MAP)


def _min_obs(nindep: int) -> int:
    return max(nindep + 2, 10)


def _clean(x):
    """Convert NaN/inf/None to None, otherwise return float."""
    if x is None:
        return None
    try:
        f = float(x)
        if not np.isfinite(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _stars(p) -> str:
    if p is None:
        return ""
    try:
        pv = float(p)
        if pv < 0.01:
            return "***"
        if pv < 0.05:
            return "**"
        if pv < 0.10:
            return "*"
        return ""
    except (TypeError, ValueError):
        return ""


def _pooled_ols(y: np.ndarray, X: np.ndarray, names: list[str]) -> dict:
    """Run pooled OLS and return coefficients + diagnostics.

    Parameters
    ----------
    y : (n,) dependent variable
    X : (n, k) independent variables (no constant — prepended internally)
    names : list of k independent-variable labels
    """
    n = len(y)
    X_const = np.column_stack([np.ones(n), X])
    k = X_const.shape[1]

    coeffs, *_ = np.linalg.lstsq(X_const, y, rcond=None)
    resid = y - X_const @ coeffs
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    dof = n - k
    if dof > 0 and ss_res > 0:
        s2 = ss_res / dof
        try:
            XtX_inv = np.linalg.inv(X_const.T @ X_const)
            se = np.sqrt(np.diag(s2 * XtX_inv))
        except np.linalg.LinAlgError:
            se = np.full(k, np.nan)
    else:
        se = np.full(k, np.nan)

    with np.errstate(divide="ignore", invalid="ignore"):
        t = coeffs / se

    if dof > 0:
        p = 2 * stats.t.sf(np.abs(t), dof)
    else:
        p = np.full(k, np.nan)

    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - k) if n > k else None

    if ss_res > 0:
        ll = n * np.log(ss_res / n)
        aic = ll + 2 * k
        bic = ll + k * np.log(n)
    else:
        aic = bic = None

    all_names = ["const"] + list(names)
    coefficients = []
    for i, name in enumerate(all_names):
        pi = _clean(p[i]) if i < len(p) else None
        coefficients.append({
            "name": name,
            "coef": _clean(coeffs[i]),
            "stdErr": _clean(se[i]),
            "tStat": _clean(t[i]),
            "pValue": pi,
            "stars": _stars(pi),
        })

    return {
        "coefficients": coefficients,
        "rSquared": _clean(r2),
        "adjRSquared": _clean(adj_r2),
        "aic": _clean(aic),
        "bic": _clean(bic),
        "_coeffs": coeffs,
    }


async def regress(
    dep: str,
    indep: list[str],
    countries: list[str],
    start: int,
    end: int,
) -> dict:
    """Public entry point: converts lists to tuples so the cached inner fn works."""
    # Dedupe indep preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for v in indep:
        if v not in seen:
            seen.add(v)
            deduped.append(v)
    return await _regress_cached(dep, tuple(deduped), tuple(countries), start, end)


@async_cached("econ_regress")
async def _regress_cached(
    dep: str,
    indep: tuple[str, ...],
    countries: tuple[str, ...],
    start: int,
    end: int,
) -> dict:
    """Cached implementation. All args must be hashable (tuples, not lists)."""
    as_of = date.today().isoformat()
    indep_list = list(indep)
    countries_list = list(countries)

    def _err(msg: str) -> dict:
        return {
            "dep": dep,
            "indep": indep_list,
            "countries": countries_list,
            "start": start,
            "end": end,
            "asOf": as_of,
            "error": msg,
            "coefficients": [],
            "residuals": [],
            "nObs": 0,
        }

    # Validation
    if dep not in _VALID:
        return _err(f"invalid dependent variable: {dep!r}")
    for v in indep_list:
        if v not in _VALID:
            return _err(f"invalid independent variable: {v!r}")
    if dep in indep:
        return _err("dependent variable must not appear in independent variables")
    if not (1 <= len(indep_list) <= 5):
        return _err("between 1 and 5 independent variables required")
    if not countries_list:
        return _err("at least one country required")
    if start > end:
        start, end = end, start

    # Fetch all series concurrently.
    all_keys = [dep] + indep_list
    fetched = await asyncio.gather(
        *[wb.fetch(key, countries, start, end) for key in all_keys]
    )

    # Reshape each SeriesResult list into a long DataFrame keyed by (country, year).
    frames: list[pd.DataFrame] = []
    for key, series_list in zip(all_keys, fetched):
        rows = []
        for sr in series_list:
            c_code = sr["country"]
            for dp in sr["data"]:
                try:
                    rows.append({
                        "country": c_code,
                        "year": int(dp["year"]),
                        key: pd.to_numeric(dp["value"], errors="coerce"),
                    })
                except (KeyError, TypeError, ValueError):
                    continue
        if rows:
            frames.append(pd.DataFrame(rows).set_index(["country", "year"]))
        else:
            frames.append(pd.DataFrame(columns=[key]).rename_axis(["country", "year"]))

    # Inner-join all series on (country, year).
    if not frames:
        return _err("no data returned for the selected countries/indicators")

    panel = frames[0]
    for df in frames[1:]:
        panel = panel.join(df, how="inner")

    for col in panel.columns:
        panel[col] = pd.to_numeric(panel[col], errors="coerce")
    panel = panel.dropna()
    panel = panel.reset_index()

    n = len(panel)
    min_needed = _min_obs(len(indep_list))
    if n < min_needed:
        return _err(f"insufficient observations (n={n}, need >= {min_needed})")

    y = panel[dep].to_numpy(float)
    X = panel[indep_list].to_numpy(float)

    # Rank check.
    X_const = np.column_stack([np.ones(n), X])
    warning = None
    if np.linalg.matrix_rank(X_const) < X_const.shape[1]:
        warning = "near-singular design matrix"

    ols = _pooled_ols(y, X, indep_list)
    coeffs_arr = ols.pop("_coeffs")

    fitted_vals = X_const @ coeffs_arr
    residuals = [
        {
            "country": str(row["country"]),
            "year": int(row["year"]),
            "fitted": _clean(fitted_vals[i]),
            "residual": _clean(float(y[i]) - float(fitted_vals[i])),
        }
        for i, row in enumerate(panel.to_dict("records"))
    ]

    return {
        "dep": dep,
        "indep": indep_list,
        "countries": countries_list,
        "start": start,
        "end": end,
        "asOf": as_of,
        "nObs": int(n),
        "rSquared": ols["rSquared"],
        "adjRSquared": ols["adjRSquared"],
        "aic": ols["aic"],
        "bic": ols["bic"],
        "coefficients": ols["coefficients"],
        "residuals": residuals,
        "warning": warning,
    }
