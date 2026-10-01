"""Sovereign Default Probability service — Phase 31.

Fits a logistic regression model on historical sovereign default data
(Reinhart & Rogoff) using current macro predictors from World Bank data.
Outputs 1Y and 5Y default probabilities per country with traffic-light signals.

Uses scipy only (NO statsmodels) — follows econ_lab_service.py pattern:
scipy.optimize.minimize BFGS, scipy.special.expit, scipy.stats.t.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

import numpy as np
from scipy import optimize, special, stats

from .. import provenance as pv
from ..cache import async_cached

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bundled Reinhart & Rogoff training data
# Key columns: iso3, year, default (0/1 for external default)
# Sourced from: Reinhart & Rogoff "This Time Is Different" (2009, 2011 updates)
# Covers major default episodes 1970-2020
# ---------------------------------------------------------------------------
_TRAINING_DATA = [
    # Latin America debt crisis 1980s
    ("ARG", 1982, 1), ("ARG", 1989, 1), ("ARG", 2001, 1), ("ARG", 2014, 1),
    ("ARG", 2020, 1),
    ("BOL", 1980, 1), ("BOL", 1986, 1), ("BOL", 1989, 1),
    ("BRA", 1983, 1), ("BRA", 1986, 1), ("BRA", 1990, 1),
    ("CHL", 1983, 1),
    ("COL", 1980, 0),  # non-default
    ("CRI", 1981, 1), ("CRI", 1984, 1),
    ("DOM", 1982, 1), ("DOM", 2005, 1),
    ("ECU", 1982, 1), ("ECU", 1999, 1), ("ECU", 2008, 1), ("ECU", 2020, 1),
    ("MEX", 1982, 1), ("MEX", 1986, 1),
    ("PAN", 1983, 1), ("PAN", 1987, 1),
    ("PER", 1978, 1), ("PER", 1980, 1), ("PER", 1984, 1),
    ("URY", 1983, 1), ("URY", 1987, 1), ("URY", 1990, 1), ("URY", 2003, 1),
    ("VEN", 1983, 1), ("VEN", 1990, 1), ("VEN", 1995, 1), ("VEN", 1998, 1),
    ("VEN", 2004, 1), ("VEN", 2017, 1),

    # Asian crisis 1997-1998
    ("IDN", 1998, 1), ("IDN", 2000, 1), ("IDN", 2002, 1),
    ("KOR", 1980, 1),  # pre-crisis
    ("PAK", 1998, 1), ("PAK", 1999, 1),

    # Russian / Eastern Europe
    ("RUS", 1991, 1), ("RUS", 1998, 1),
    ("UKR", 1998, 1), ("UKR", 2000, 1), ("UKR", 2015, 1),
    ("MDA", 1998, 1), ("MDA", 2002, 1),

    # African defaults
    ("CIV", 1983, 1), ("CIV", 2000, 1), ("CIV", 2010, 1),
    ("NGA", 1982, 1), ("NGA", 1986, 1), ("NGA", 1992, 1), ("NGA", 2001, 1),
    ("NGA", 2004, 1),
    ("ZAF", 1985, 1), ("ZAF", 1989, 1), ("ZAF", 1993, 1),
    ("EGY", 1984, 1),
    ("KEN", 1994, 1), ("KEN", 2000, 1),
    ("MAR", 1983, 1), ("MAR", 1986, 1),
    ("ZMB", 1983, 1),
    ("TUN", 1980, 0),
    ("GHA", 1987, 1), ("GHA", 2000, 1),

    # Developed country defaults (rare but happen)
    ("GRC", 2012, 1),
    ("CYP", 2013, 1),

    # Non-default observations (balanced dataset)
    ("USA", 2010, 0), ("USA", 2015, 0), ("USA", 2020, 0),
    ("GBR", 2010, 0), ("GBR", 2015, 0), ("GBR", 2020, 0),
    ("DEU", 2010, 0), ("DEU", 2015, 0), ("DEU", 2020, 0),
    ("FRA", 2010, 0), ("FRA", 2015, 0), ("FRA", 2020, 0),
    ("JPN", 2010, 0), ("JPN", 2015, 0), ("JPN", 2020, 0),
    ("CAN", 2010, 0), ("CAN", 2015, 0), ("CAN", 2020, 0),
    ("AUS", 2010, 0), ("AUS", 2015, 0), ("AUS", 2020, 0),
    ("ITA", 2010, 0), ("ITA", 2015, 0),
    ("ESP", 2010, 0), ("ESP", 2015, 0),
    ("NLD", 2010, 0), ("NLD", 2015, 0),
    ("CHE", 2010, 0), ("CHE", 2015, 0),
    ("SWE", 2010, 0), ("SWE", 2015, 0),
    ("NOR", 2010, 0), ("NOR", 2015, 0),
    ("KOR", 2010, 0), ("KOR", 2015, 0), ("KOR", 2020, 0),
    ("CHN", 2010, 0), ("CHN", 2015, 0), ("CHN", 2020, 0),
    ("IND", 2010, 0), ("IND", 2015, 0), ("IND", 2020, 0),
    ("BRA", 2010, 0), ("BRA", 2015, 0),
    ("MEX", 2010, 0), ("MEX", 2015, 0),
    ("ZAF", 2010, 0), ("ZAF", 2015, 0),
    ("TUR", 2010, 0), ("TUR", 2015, 0),
    ("POL", 2010, 0), ("POL", 2015, 0),
    ("HUN", 2010, 0),
    ("CZE", 2010, 0), ("CZE", 2015, 0),
    ("CHL", 2010, 0), ("CHL", 2015, 0),
    ("COL", 2010, 0), ("COL", 2015, 0),
    ("PER", 2010, 0), ("PER", 2015, 0),
    ("PHL", 2010, 0), ("PHL", 2015, 0),
    ("THA", 2010, 0), ("THA", 2015, 0),
    ("MYS", 2010, 0), ("MYS", 2015, 0),
    ("VNM", 2010, 0), ("VNM", 2015, 0),
]

# Predictors: World Bank indicator keys used in the model
PREDICTORS = ["debt_gdp", "fiscal_balance", "current_account", "inflation", "gdp_growth"]

# Traffic-light thresholds for 1Y default probability
TL_GREEN = 0.05   # <5% = green
TL_RED = 0.20     # >20% = red, 5-20% = yellow


def _sigmoid(z):
    """Logistic sigmoid function."""
    return special.expit(z)


def _neg_log_likelihood(beta, X, y):
    """Negative log-likelihood for logistic regression."""
    z = X @ beta
    # Clip to avoid log(0)
    p = np.clip(_sigmoid(z), 1e-10, 1 - 1e-10)
    return -np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))


def _pseudo_r2(y, y_pred, beta, X):
    """McFadden's pseudo R-squared."""
    ll_model = -_neg_log_likelihood(beta, X, y)
    # Null model (intercept only)
    null_beta = np.array([np.log(np.mean(y) / (1 - np.mean(y) + 1e-10))])
    X_null = np.ones((len(y), 1))
    ll_null = -_neg_log_likelihood(null_beta, X_null, y)
    if ll_null == 0:
        return 1.0
    return 1.0 - ll_model / ll_null


_PREDICTOR_TITLES = {
    "debt_gdp": ("Central government debt (% of GDP)", "% of GDP"),
    "fiscal_balance": ("Net lending (+) / net borrowing (-) (% of GDP)", "% of GDP"),
    "current_account": ("Current account balance (% of GDP)", "% of GDP"),
    "inflation": ("Inflation, consumer prices (annual %)", "% per year"),
    "gdp_growth": ("GDP growth (annual %)", "% per year"),
}


def _provenance(pred_data: dict, countries: list[dict], n_obs: int) -> dict:
    """Source map for the default-probability model (see provenance.py)."""
    from . import atlas_service

    prov: dict = {}
    for p in PREDICTORS:
        years = [max(pred_data[p][c["iso3"]]) for c in countries if pred_data[p].get(c["iso3"])]
        title, units = _PREDICTOR_TITLES[p]
        prov[f"predictors.{p}"] = pv.ref(
            "worldbank", atlas_service._WB_CODES[p], title, units=units, frequency="annual",
            observed=str(max(years)) if years else None,
            note="Each country uses its own latest available year; the World Bank series only, no IMF gap-fill.")
    prov["training_data"] = pv.ref(
        "econosift", None, "Bundled sovereign default episodes, 1970-2020",
        note="A hand-compiled list of (country, year, default 0/1) attributed to Reinhart & Rogoff's "
             "'This Time Is Different'; it ships with the app and is not fetched from a live source.")
    prov["*"] = pv.derived(
        "Logistic regression (BFGS) of the default flag on five standardised World Bank predictors, fitted on "
        f"the {n_obs} bundled default / non-default observations that have predictor data (nearest year within "
        "+/-2 accepted). prob1y = sigmoid(intercept + sum(coef x standardised latest predictor)).",
        [f"predictors.{p}" for p in PREDICTORS] + ["training_data"], title="Sovereign default probability model")
    prov["model"] = prov["*"]
    prov["countries"] = pv.derived(
        "prob1y = model probability from each country's latest predictors; prob5y = 1 - (1 - prob1y)^5 "
        "(constant annual hazard); signal green < 5%, yellow 5-20%, red > 20% on prob1y.",
        ["*"], title="Default probabilities")
    prov["asOf"] = pv.derived(
        "the date the model was run; the predictor data behind it is older (see predictors.*)",
        title="Model run date")
    return prov


def _with_provenance(result: dict, pred_data: dict, countries: list[dict], n_obs: int) -> dict:
    # A module-level wrapper: get_default_probabilities() has a local named ``pv`` (a p-value).
    return pv.attach(result, _provenance(pred_data, countries, n_obs))


@async_cached("sovereign_default")
async def get_default_probabilities() -> dict:
    """Fit logistic regression and compute 1Y/5Y default probabilities.

    Returns {model: {...}, countries: [{iso3, name, prob1y, prob5y, signal}], asOf, source}.
    """
    from . import atlas_service
    from ..config import ISO2_TO_ISO3, COUNTRY_NAMES

    as_of = str(date.today())

    # Build training DataFrame from bundled data
    train_rows = []
    for iso3, year, default in _TRAINING_DATA:
        train_rows.append({"iso3": iso3, "year": year, "default": default})
    train_df = None
    import pandas as pd
    train_df = pd.DataFrame(train_rows)

    # Fetch predictors from World Bank
    start, end = 2000, date.today().year - 1
    all_predictors = await asyncio.gather(*[
        atlas_service._wb_timeline(p, start, end) for p in PREDICTORS
    ])
    pred_data = dict(zip(PREDICTORS, all_predictors))

    # Build long-format dataset: ({iso3, year, predictor values})
    # Collect all unique (iso3, year) from predictors
    all_years = set()
    for pname, pdata in pred_data.items():
        for iso3, years in pdata.items():
            all_years.update(years.keys())

    # Build feature matrix for training
    X_rows = []
    y_rows = []
    country_year_pairs = []

    for _, row in train_df.iterrows():
        iso3 = row["iso3"]
        year = int(row["year"])
        default = int(row["default"])

        features = []
        valid = True
        for pname in PREDICTORS:
            val = pred_data[pname].get(iso3, {}).get(year)
            if val is None:
                # Try nearby years
                for offset in [-1, -2, 1, 2]:
                    val = pred_data[pname].get(iso3, {}).get(year + offset)
                    if val is not None:
                        break
            if val is None:
                valid = False
                break
            features.append(val)

        if valid:
            X_rows.append(features)
            y_rows.append(default)
            country_year_pairs.append((iso3, year))

    if len(X_rows) < 10:
        return {
            "model": None,
            "countries": [],
            "asOf": as_of,
            "source": "Reinhart & Rogoff (bundled) + World Bank",
            "error": "Insufficient training data (need >= 10 observations)",
        }

    X_train = np.array(X_rows)
    y_train = np.array(y_rows)

    # Normalize features
    X_mean = X_train.mean(axis=0)
    X_std = X_train.std(axis=0)
    X_std[X_std == 0] = 1.0
    X_norm = (X_train - X_mean) / X_std

    # Add intercept
    X_norm = np.column_stack([np.ones(X_norm.shape[0]), X_norm])
    n, k = X_norm.shape

    # Fit logistic regression via BFGS
    beta_init = np.zeros(k)
    try:
        result = optimize.minimize(
            _neg_log_likelihood, beta_init,
            args=(X_norm, y_train),
            method="BFGS",
            options={"maxiter": 500},
        )
        beta = result.x
        converged = result.success
    except Exception as exc:
        logger.warning("Logistic regression optimization failed: %s", exc)
        return {
            "model": None,
            "countries": [],
            "asOf": as_of,
            "source": "Reinhart & Rogoff (bundled) + World Bank",
            "error": f"Model fitting failed: {exc}",
        }

    # Compute standard errors via Hessian
    p_train = _sigmoid(X_norm @ beta)
    W = np.diag(p_train * (1 - p_train))
    try:
        H = X_norm.T @ W @ X_norm
        H_inv = np.linalg.inv(H)
        se = np.sqrt(np.diag(H_inv))
    except np.linalg.LinAlgError:
        se = np.full(k, np.nan)

    t_stats = beta / se
    dof = n - k
    p_values = 2 * stats.t.sf(np.abs(t_stats), dof) if dof > 0 else np.full(k, np.nan)

    # Pseudo R²
    y_pred = p_train
    pseudo_r2 = _pseudo_r2(y_train, y_pred, beta, X_norm)

    # Coefficients table
    coef_names = ["const"] + PREDICTORS
    coefficients = []
    for i, name in enumerate(coef_names):
        pv = float(p_values[i]) if not np.isnan(p_values[i]) else None
        stars = ""
        if pv is not None:
            if pv < 0.01:
                stars = "***"
            elif pv < 0.05:
                stars = "**"
            elif pv < 0.10:
                stars = "*"
        coefficients.append({
            "name": name,
            "coef": round(float(beta[i]), 6),
            "stdErr": round(float(se[i]), 6) if not np.isnan(se[i]) else None,
            "tStat": round(float(t_stats[i]), 4) if not np.isnan(t_stats[i]) else None,
            "pValue": round(pv, 4) if pv is not None else None,
            "stars": stars,
        })

    model = {
        "pseudoR2": round(float(pseudo_r2), 4) if pseudo_r2 is not None else None,
        "nObs": n,
        "converged": converged,
        "coefficients": coefficients,
    }

    # Compute current 1Y and 5Y probabilities for all countries with predictor data
    countries_out = []
    # Get country universe from atlas
    universe = atlas_service._country_universe()
    iso3_to_name = {c["iso3"]: c["name"] for c in universe}

    for iso3 in sorted(set(row["iso3"] for row in train_rows)):
        # Get latest predictor values
        features = []
        valid = True
        for pname in PREDICTORS:
            pdata = pred_data[pname].get(iso3, {})
            if not pdata:
                valid = False
                break
            latest_year = max(pdata.keys())
            val = pdata[latest_year]
            if val is None:
                valid = False
                break
            features.append(val)

        if not valid:
            continue

        # Normalize and predict
        x_norm = (np.array(features) - X_mean) / X_std
        x_norm = np.insert(x_norm, 0, 1.0)  # intercept
        prob1y = float(_sigmoid(x_norm @ beta))

        # 5Y probability: cumulative probability of default over 5 years
        # Assumes constant annual hazard: P(5Y) = 1 - (1-P)^5
        prob5y = 1.0 - (1.0 - prob1y) ** 5

        # Traffic light
        if prob1y < TL_GREEN:
            signal = "green"
        elif prob1y < TL_RED:
            signal = "yellow"
        else:
            signal = "red"

        name = iso3_to_name.get(iso3, iso3)
        countries_out.append({
            "iso3": iso3,
            "name": name,
            "prob1y": round(prob1y, 4),
            "prob5y": round(prob5y, 4),
            "signal": signal,
        })

    countries_out.sort(key=lambda c: c["prob5y"], reverse=True)

    return _with_provenance({
        "model": model,
        "countries": countries_out,
        "asOf": as_of,
        "source": "Reinhart & Rogoff (bundled training data) + World Bank predictors",
    }, pred_data, countries_out, n)
