"""Tests for options_engine — Phase 40 (task A2).

Every assertion here is anchored to a closed-form property of Black-Scholes
rather than to output recorded from a previous run. Recorded-output tests only
prove the code still does what it did; they cannot tell you it was ever right.

Conventions this module must respect (see `bs_greeks`):
  * vega is per **1% IV** (raw vega x 0.01)
  * rho is per **1% rate** (raw rho x 0.01)
  * theta is per **calendar day** (annual theta / 365)
`crr_price` is always **American** — early exercise is checked at every node.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from backend.services.options_engine import (
    bs_greeks,
    bs_price,
    crr_price,
    iv_backsolve,
    mc_option_price,
)

# Reference contract used throughout: at-the-money, 1y, 5% rates, 20% vol.
S, K, T, R, SIGMA = 100.0, 100.0, 1.0, 0.05, 0.20

# Textbook Black-Scholes value for the reference call.
REF_CALL = 10.450583572185565


# ── Black-Scholes price ──────────────────────────────────────────────────────

def test_bs_price_matches_textbook_value():
    assert bs_price(S, K, T, R, SIGMA, "call") == pytest.approx(REF_CALL, abs=1e-9)


def test_put_call_parity():
    """C - P == S - K*exp(-rT). The defining arbitrage relation."""
    call = bs_price(S, K, T, R, SIGMA, "call")
    put = bs_price(S, K, T, R, SIGMA, "put")
    assert call - put == pytest.approx(S - K * math.exp(-R * T), abs=1e-9)


def test_put_call_parity_holds_away_from_the_money():
    for strike in (60.0, 85.0, 115.0, 140.0):
        call = bs_price(S, strike, T, R, SIGMA, "call")
        put = bs_price(S, strike, T, R, SIGMA, "put")
        assert call - put == pytest.approx(S - strike * math.exp(-R * T), abs=1e-9)


def test_price_is_monotonic_in_volatility():
    """Vega is positive everywhere, so price must rise with vol."""
    prices = [bs_price(S, K, T, R, s, "call") for s in (0.1, 0.2, 0.3, 0.4)]
    assert all(b > a for a, b in zip(prices, prices[1:]))


def test_price_respects_no_arbitrage_bounds():
    """max(S - K e^-rT, 0) <= C <= S for a European call."""
    call = bs_price(S, K, T, R, SIGMA, "call")
    assert max(S - K * math.exp(-R * T), 0.0) <= call <= S


def test_deep_itm_call_approaches_discounted_intrinsic():
    call = bs_price(1000.0, K, T, R, SIGMA, "call")
    assert call == pytest.approx(1000.0 - K * math.exp(-R * T), rel=1e-6)


def test_bs_price_returns_none_on_domain_errors():
    assert bs_price(S, K, 0.0, R, SIGMA, "call") is None      # expired
    assert bs_price(S, K, -1.0, R, SIGMA, "call") is None
    assert bs_price(S, K, T, R, 0.0, "call") is None          # zero vol
    assert bs_price(-1.0, K, T, R, SIGMA, "call") is None     # negative spot
    assert bs_price(S, 0.0, T, R, SIGMA, "call") is None      # zero strike


# ── Greeks ───────────────────────────────────────────────────────────────────

def test_delta_signs_and_ranges():
    call_d = bs_greeks(S, K, T, R, SIGMA, "call")["delta"]
    put_d = bs_greeks(S, K, T, R, SIGMA, "put")["delta"]
    assert 0.0 < call_d < 1.0
    assert -1.0 < put_d < 0.0


def test_delta_call_minus_delta_put_is_one():
    """N(d1) - (N(d1) - 1) == 1 for a non-dividend-paying underlying."""
    call_d = bs_greeks(S, K, T, R, SIGMA, "call")["delta"]
    put_d = bs_greeks(S, K, T, R, SIGMA, "put")["delta"]
    assert call_d - put_d == pytest.approx(1.0, abs=1e-12)


def test_gamma_and_vega_are_identical_for_call_and_put():
    call = bs_greeks(S, K, T, R, SIGMA, "call")
    put = bs_greeks(S, K, T, R, SIGMA, "put")
    assert call["gamma"] == pytest.approx(put["gamma"], abs=1e-12)
    assert call["vega"] == pytest.approx(put["vega"], abs=1e-12)
    assert call["gamma"] > 0
    assert call["vega"] > 0


def test_delta_saturates_deep_itm_and_otm():
    assert bs_greeks(10_000.0, K, T, R, SIGMA, "call")["delta"] == pytest.approx(1.0, abs=1e-6)
    assert bs_greeks(1.0, K, T, R, SIGMA, "call")["delta"] == pytest.approx(0.0, abs=1e-6)


def test_delta_numerically_matches_dPrice_dSpot():
    """Delta is dC/dS — verify against a central difference on the price."""
    h = 1e-4
    up = bs_price(S + h, K, T, R, SIGMA, "call")
    dn = bs_price(S - h, K, T, R, SIGMA, "call")
    numeric = (up - dn) / (2 * h)
    assert bs_greeks(S, K, T, R, SIGMA, "call")["delta"] == pytest.approx(numeric, abs=1e-6)


def test_vega_matches_dPrice_dVol_scaled_per_one_percent():
    """Vega is reported per 1% IV, so it equals dC/dsigma * 0.01."""
    h = 1e-6
    up = bs_price(S, K, T, R, SIGMA + h, "call")
    dn = bs_price(S, K, T, R, SIGMA - h, "call")
    numeric_raw = (up - dn) / (2 * h)
    assert bs_greeks(S, K, T, R, SIGMA, "call")["vega"] == pytest.approx(numeric_raw * 0.01, rel=1e-5)


def test_gamma_matches_second_derivative():
    h = 1e-3
    up = bs_price(S + h, K, T, R, SIGMA, "call")
    mid = bs_price(S, K, T, R, SIGMA, "call")
    dn = bs_price(S - h, K, T, R, SIGMA, "call")
    numeric = (up - 2 * mid + dn) / (h ** 2)
    assert bs_greeks(S, K, T, R, SIGMA, "call")["gamma"] == pytest.approx(numeric, rel=1e-3)


def test_rho_sign_differs_by_option_type():
    assert bs_greeks(S, K, T, R, SIGMA, "call")["rho"] > 0
    assert bs_greeks(S, K, T, R, SIGMA, "put")["rho"] < 0


def test_theta_is_negative_for_a_long_atm_call():
    """Time decay works against the holder of an at-the-money option."""
    assert bs_greeks(S, K, T, R, SIGMA, "call")["theta"] < 0


def test_greeks_return_all_none_on_domain_errors():
    for bad in (
        (S, K, 0.0, R, SIGMA),
        (S, K, T, R, 0.0),
        (-1.0, K, T, R, SIGMA),
    ):
        out = bs_greeks(*bad, "call")
        assert set(out) == {"delta", "gamma", "theta", "vega", "rho"}
        assert all(v is None for v in out.values())


# ── Implied volatility ───────────────────────────────────────────────────────

def test_iv_backsolve_round_trips():
    for true_sigma in (0.10, 0.25, 0.40, 0.85):
        price = bs_price(S, K, T, R, true_sigma, "call")
        assert iv_backsolve(price, S, K, T, R, "call") == pytest.approx(true_sigma, abs=1e-5)


def test_iv_backsolve_round_trips_for_puts_and_off_atm_strikes():
    price = bs_price(S, 120.0, T, R, 0.35, "put")
    assert iv_backsolve(price, S, 120.0, T, R, "put") == pytest.approx(0.35, abs=1e-5)


def test_iv_backsolve_returns_none_on_unreachable_price():
    """A price above the S bound is unattainable, so there is no root."""
    assert iv_backsolve(10_000.0, S, K, T, R, "call") is None


def test_iv_backsolve_returns_none_on_invalid_inputs():
    assert iv_backsolve(0.0, S, K, T, R, "call") is None
    assert iv_backsolve(5.0, S, K, 0.0, R, "call") is None


# ── CRR binomial tree (American) ─────────────────────────────────────────────

def test_crr_call_converges_to_black_scholes():
    """An American call on a non-dividend underlying is never exercised early
    (Merton), so the tree must converge to the European Black-Scholes value."""
    assert crr_price(S, K, T, R, SIGMA, "call", steps=2000) == pytest.approx(REF_CALL, abs=1e-2)


def test_crr_convergence_improves_with_steps():
    coarse = abs(crr_price(S, K, T, R, SIGMA, "call", steps=25) - REF_CALL)
    fine = abs(crr_price(S, K, T, R, SIGMA, "call", steps=2000) - REF_CALL)
    assert fine < coarse


def test_american_put_is_worth_at_least_european_put():
    """Early exercise is an extra right, so it can never reduce value."""
    european = bs_price(S, K, T, R, SIGMA, "put")
    american = crr_price(S, K, T, R, SIGMA, "put", steps=2000)
    assert american >= european - 1e-6


def test_american_put_strictly_exceeds_european_when_deep_itm():
    """Deep in the money with positive rates, early exercise has real value."""
    european = bs_price(60.0, 100.0, 1.0, 0.10, 0.20, "put")
    american = crr_price(60.0, 100.0, 1.0, 0.10, 0.20, "put", steps=1000)
    assert american > european


def test_crr_price_never_below_intrinsic():
    american = crr_price(120.0, 100.0, T, R, SIGMA, "call", steps=500)
    assert american >= 120.0 - 100.0 - 1e-9


def test_crr_returns_none_on_domain_errors():
    assert crr_price(S, K, 0.0, R, SIGMA, "call") is None
    assert crr_price(S, K, T, R, 0.0, "call") is None
    assert crr_price(S, K, T, R, SIGMA, "call", steps=0) is None


# ── Monte Carlo ──────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_rng(monkeypatch):
    """`mc_option_price` calls np.random.default_rng() with no seed argument,
    so determinism has to be imposed from outside rather than by parameter.

    The original factory must be captured before patching — referring to
    `np.random.default_rng` inside the replacement would resolve to the patch
    itself and recurse.
    """
    original = np.random.default_rng
    monkeypatch.setattr(np.random, "default_rng", lambda *a, **k: original(20260822))


def test_mc_converges_to_black_scholes(seeded_rng):
    out = mc_option_price(S, K, T, R, SIGMA, "call", sims=200_000)
    assert out["price"] == pytest.approx(REF_CALL, rel=0.02)


def test_mc_reports_the_black_scholes_reference_alongside_its_estimate(seeded_rng):
    out = mc_option_price(S, K, T, R, SIGMA, "call", sims=20_000)
    assert out["bsPrice"] == pytest.approx(REF_CALL, abs=1e-9)


def test_mc_standard_error_shrinks_with_more_paths(monkeypatch):
    """MC error falls as 1/sqrt(n). A single seed could get lucky, so compare
    mean absolute error across several seeds rather than one draw."""
    original = np.random.default_rng

    def mean_abs_error(sims: int) -> float:
        errors = []
        for seed in range(6):
            monkeypatch.setattr(np.random, "default_rng", lambda *a, _s=seed, **k: original(_s))
            price = mc_option_price(S, K, T, R, SIGMA, "call", sims=sims)["price"]
            errors.append(abs(price - REF_CALL))
        return sum(errors) / len(errors)

    assert mean_abs_error(200_000) < mean_abs_error(1_000)


def test_mc_payoffs_are_non_negative(seeded_rng):
    out = mc_option_price(S, K, T, R, SIGMA, "put", sims=10_000)
    assert out["price"] >= 0
    assert out["var95"] >= 0  # discounted payoffs are floored at zero
    assert all(b["count"] >= 0 for b in out["distribution"])


def test_mc_distribution_has_expected_shape(seeded_rng):
    out = mc_option_price(S, K, T, R, SIGMA, "call", sims=10_000)
    assert len(out["distribution"]) == 50
    assert set(out["distribution"][0]) == {"bin", "count"}


def test_merton_dividend_yield_put_call_parity():
    """Audit C-30: with a dividend yield q, C − P = S·e^(−qT) − K·e^(−rT)."""
    import math
    from backend.services.options_engine import bs_price
    S, K, T, r, q, sig = 100.0, 95.0, 0.5, 0.04, 0.03, 0.25
    c = bs_price(S, K, T, r, sig, "call", q)
    p = bs_price(S, K, T, r, sig, "put", q)
    assert c - p == pytest.approx(S * math.exp(-q * T) - K * math.exp(-r * T), abs=1e-9)
    # A dividend lowers the call and raises the put vs q = 0.
    assert c < bs_price(S, K, T, r, sig, "call") and p > bs_price(S, K, T, r, sig, "put")


def test_merton_delta_matches_finite_difference():
    from backend.services.options_engine import bs_price, bs_greeks
    S, K, T, r, q, sig, h = 100.0, 100.0, 0.75, 0.03, 0.02, 0.3, 1e-4
    fd = (bs_price(S + h, K, T, r, sig, "call", q) - bs_price(S - h, K, T, r, sig, "call", q)) / (2 * h)
    assert bs_greeks(S, K, T, r, sig, "call", q)["delta"] == pytest.approx(fd, abs=1e-6)
