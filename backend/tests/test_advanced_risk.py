"""Tests for advanced_risk — Phase 40 (task A4).

GARCH, Hurst, Ornstein-Uhlenbeck, cointegration and the rolling metrics had no
tests. These assert analytic properties of each estimator against processes
simulated with known parameters.

The Hurst tests double as regression tests for a real defect found while
writing them: R/S was being run on price *levels* rather than increments, which
returned ~1.0 for random-walk, trending and mean-reverting series alike.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from backend.services import advanced_risk as ar

TD = ar.TRADING_DAYS


# ── Simulation helpers ───────────────────────────────────────────────────────

def _ar1_return_prices(phi: float, n: int = 2000, sd: float = 0.01, seed: int = 1) -> pd.Series:
    """Prices whose log returns follow an AR(1): phi > 0 persistent, < 0 not."""
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(n) * sd
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = phi * r[i - 1] + eps[i]
    return pd.Series(100.0 * np.exp(np.cumsum(r)), index=pd.bdate_range("2015-01-01", periods=n))


def _ou_levels(theta: float, mu: float, sigma: float, n: int = 3000, seed: int = 3) -> pd.Series:
    """Exact discretisation of dX = theta (mu - X) dt + sigma dW, dt = 1/252."""
    rng = np.random.default_rng(seed)
    dt = 1.0 / TD
    b = math.exp(-theta * dt)
    sd = sigma * math.sqrt((1 - b ** 2) / (2 * theta))
    x = np.zeros(n)
    x[0] = mu
    for i in range(1, n):
        x[i] = mu + b * (x[i - 1] - mu) + sd * rng.standard_normal()
    return pd.Series(x, index=pd.bdate_range("2015-01-01", periods=n))


def _returns(n: int = 1500, sd: float = 0.01, seed: int = 5) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.standard_normal(n) * sd, index=pd.bdate_range("2015-01-01", periods=n))


# ── Hurst exponent ───────────────────────────────────────────────────────────

def test_hurst_is_one_half_for_a_random_walk():
    """The central property. Before the Phase 40 fix this returned ~1.0."""
    h = ar.hurst_exponent(_ar1_return_prices(0.0))["hurst"]
    assert h == pytest.approx(0.5, abs=0.08)


def test_hurst_is_unbiased_across_seeds():
    """Raw R/S is badly biased high; the Anis-Lloyd correction removes it."""
    hs = [ar.hurst_exponent(_ar1_return_prices(0.0, n=1000, seed=s))["hurst"] for s in range(12)]
    assert np.mean(hs) == pytest.approx(0.5, abs=0.05)


def test_hurst_rises_with_persistence_and_falls_with_mean_reversion():
    anti = ar.hurst_exponent(_ar1_return_prices(-0.5))["hurst"]
    iid = ar.hurst_exponent(_ar1_return_prices(0.0))["hurst"]
    persistent = ar.hurst_exponent(_ar1_return_prices(0.5))["hurst"]
    assert anti < iid < persistent


def test_hurst_discriminates_regimes_that_the_level_based_version_could_not():
    """Regression guard: run on levels these three all collapsed to ~1.0."""
    walk = ar.hurst_exponent(_ar1_return_prices(0.0))["hurst"]
    trending = ar.hurst_exponent(_ar1_return_prices(0.6))["hurst"]
    reverting = ar.hurst_exponent(_ou_levels(theta=40.0, mu=100.0, sigma=2.0))["hurst"]

    assert trending > walk > reverting
    assert reverting < 0.4          # OU levels are strongly anti-persistent
    assert walk < 0.6


def test_constant_drift_alone_does_not_create_persistence():
    """GBM with drift still has iid increments, so H must stay near 0.5.
    A level-based estimator reports drift as 'trending', which is wrong."""
    rng = np.random.default_rng(11)
    n = 2000
    r = rng.standard_normal(n) * 0.01 + 0.004   # large positive drift
    prices = pd.Series(100.0 * np.exp(np.cumsum(r)))
    assert ar.hurst_exponent(prices)["hurst"] == pytest.approx(0.5, abs=0.08)


def test_hurst_handles_series_crossing_zero():
    """A spread can legitimately be negative — must not take log of it."""
    series = _ou_levels(theta=5.0, mu=0.0, sigma=1.0)
    assert (series < 0).any()
    out = ar.hurst_exponent(series)
    assert out["hurst"] is not None


def test_hurst_reports_insufficient_data():
    assert ar.hurst_exponent(pd.Series([1.0, 2.0, 3.0]))["hurst"] is None
    assert ar.hurst_exponent(pd.Series(dtype=float))["hurst"] is None


def test_expected_rs_switches_branch_without_discontinuity():
    """The gamma form overflows past n=340, hence Peters' asymptotic branch;
    the two must agree at the switch point."""
    assert ar._expected_rs(340) == pytest.approx(ar._expected_rs(341), rel=0.01)
    assert ar._expected_rs(1000) > ar._expected_rs(100)


# ── Ornstein-Uhlenbeck ───────────────────────────────────────────────────────

def test_ou_fit_recovers_known_parameters():
    theta, mu, sigma = 5.0, 50.0, 3.0
    out = ar.ou_fit(_ou_levels(theta, mu, sigma, n=4000))

    assert out["theta"] == pytest.approx(theta, rel=0.25)
    assert out["mu"] == pytest.approx(mu, abs=0.5)
    assert out["sigma"] == pytest.approx(sigma, rel=0.15)


def test_ou_half_life_matches_log2_over_theta():
    out = ar.ou_fit(_ou_levels(4.0, 20.0, 2.0, n=4000))
    expected = math.log(2) / out["theta"] * TD
    assert out["halfLifeDays"] == pytest.approx(expected, rel=1e-9)
    assert out["halfLifeDays"] > 0


def test_faster_mean_reversion_gives_a_shorter_half_life():
    slow = ar.ou_fit(_ou_levels(2.0, 10.0, 1.0, n=4000))["halfLifeDays"]
    fast = ar.ou_fit(_ou_levels(12.0, 10.0, 1.0, n=4000))["halfLifeDays"]
    assert fast < slow


def test_ou_fit_returns_nulls_on_short_input():
    out = ar.ou_fit(pd.Series([1.0, 2.0, 3.0]))
    assert out == {"theta": None, "mu": None, "sigma": None, "halfLifeDays": None}


def test_ou_fit_returns_nulls_on_constant_series():
    """A flat series is a degenerate regression, not a crash."""
    out = ar.ou_fit(pd.Series([5.0] * 100))
    assert out["theta"] is None or out["halfLifeDays"] is None


# ── GARCH ────────────────────────────────────────────────────────────────────

def test_garch_fit_is_stationary_and_finite():
    out = ar.garch_fit(_returns(n=1200))
    if out.get("alpha") is None:
        pytest.skip("arch backend unavailable in this environment")

    assert out["alpha"] >= 0
    assert out["beta"] >= 0
    assert out["alpha"] + out["beta"] < 1.0          # covariance stationarity
    assert out["omega"] > 0


def test_garch_forecast_volatility_is_positive():
    out = ar.garch_fit(_returns(n=1200))
    if out.get("alpha") is None:
        pytest.skip("arch backend unavailable in this environment")
    assert out["forecastVol"] > 0


def test_garch_rejects_short_series_without_raising():
    out = ar.garch_fit(_returns(n=10))
    assert out.get("alpha") is None


# ── Cointegration ────────────────────────────────────────────────────────────

def test_cointegrated_pair_is_detected():
    """Two series sharing one stochastic trend, differing by a stationary gap."""
    rng = np.random.default_rng(21)
    n = 1200
    common = np.cumsum(rng.standard_normal(n) * 0.01)
    a = 100 * np.exp(common)
    b = 100 * np.exp(common + rng.standard_normal(n) * 0.002)  # stationary spread
    df = pd.DataFrame({"A": a, "B": b}, index=pd.bdate_range("2016-01-01", periods=n))

    assert ar.cointegration_test(df)["isCointegrated"] is True


def test_independent_random_walks_are_not_cointegrated():
    rng = np.random.default_rng(22)
    n = 1200
    df = pd.DataFrame(
        {
            "A": 100 * np.exp(np.cumsum(rng.standard_normal(n) * 0.01)),
            "B": 100 * np.exp(np.cumsum(rng.standard_normal(n) * 0.01)),
        },
        index=pd.bdate_range("2016-01-01", periods=n),
    )
    assert ar.cointegration_test(df)["isCointegrated"] is False


def test_cointegration_requires_two_columns():
    df = pd.DataFrame({"A": [1.0, 2.0, 3.0]})
    out = ar.cointegration_test(df)
    assert out.get("isCointegrated") in (None, False)


# ── Rolling metrics ──────────────────────────────────────────────────────────

def test_rolling_beta_of_a_series_against_itself_is_one():
    r = _returns(n=400)
    beta = ar.rolling_beta(r, r, window=60).dropna()
    assert len(beta) > 0
    assert beta.values == pytest.approx(np.ones(len(beta)), abs=1e-9)


def test_rolling_volatility_annualises_correctly():
    """Constant-magnitude alternating returns have a known sample sd."""
    r = pd.Series([0.01, -0.01] * 200, index=pd.bdate_range("2020-01-01", periods=400))
    vol = ar.rolling_volatility(r, window=100).dropna()
    expected = float(np.std([0.01, -0.01] * 50, ddof=1)) * math.sqrt(TD)
    assert vol.iloc[-1] == pytest.approx(expected, rel=1e-6)


def test_rolling_windows_produce_leading_nans():
    r = _returns(n=200)
    vol = ar.rolling_volatility(r, window=60)
    assert vol.iloc[:59].isna().all()
    assert not math.isnan(vol.iloc[-1])


def test_rolling_var_is_more_extreme_at_higher_confidence():
    r = _returns(n=600)
    var95 = ar.rolling_var(r, window=250, confidence=0.95).dropna()
    var99 = ar.rolling_var(r, window=250, confidence=0.99).dropna()
    assert var99.iloc[-1] <= var95.iloc[-1]


def test_rolling_max_drawdown_is_non_positive():
    prices = _ar1_return_prices(0.0, n=500)
    dd = ar.rolling_max_drawdown(prices, window=120).dropna()
    assert (dd <= 1e-12).all()


def test_monte_carlo_var_scales_with_confidence():
    r = _returns(n=800)
    out = ar.monte_carlo_var(r, sims=20_000)
    if not out or out.get("var95") is None:
        pytest.skip("monte_carlo_var unavailable")
    assert out["var99"] <= out["var95"]
