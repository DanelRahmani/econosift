"""Tests for the portfolio engine — Phase 40 (task A3).

`portfolio.py` carries the efficient frontier, Black-Litterman, Kelly, risk
contribution and drawdown maths and had no tests. A sign error or a stray
annualisation factor here produces a plausible-looking number that nobody
notices, so these assertions are anchored to analytic identities.

The `_price_frame` helper below constructs prices whose observed log returns
have **exactly** the requested annualised mean and covariance — the sample is
standardised before the target Cholesky factor is applied, and a flat base row
is prepended so the first difference is not lost. That turns what would be
approximate statistical checks into exact algebraic ones.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from backend.services import portfolio as pf

TD = pf.TRADING_DAYS  # 252


# ── Synthetic data helper ────────────────────────────────────────────────────

def _price_frame(
    tickers: list[str],
    ann_mu: list[float],
    ann_cov: list[list[float]],
    n: int = 500,
    seed: int = 7,
) -> pd.DataFrame:
    """Prices whose log returns have exactly the given annualised mu and cov."""
    k = len(tickers)
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n, k))

    # Force the sample to zero mean and identity covariance exactly.
    # Whitening needs inv(L) where C = L L'; cholesky(inv(C)) is a *different*
    # factorisation and does not satisfy A C A' = I.
    Z = Z - Z.mean(axis=0)
    C = np.atleast_2d(np.cov(Z, rowvar=False, ddof=1))
    Z = Z @ np.linalg.inv(np.linalg.cholesky(C)).T

    daily_cov = np.asarray(ann_cov, dtype=float) / TD
    daily_mu = np.asarray(ann_mu, dtype=float) / TD
    R = Z @ np.linalg.cholesky(daily_cov).T + daily_mu

    # Flat base row so log(px/px.shift(1)).dropna() reproduces R exactly.
    levels = np.vstack([np.full(k, 100.0), 100.0 * np.exp(np.cumsum(R, axis=0))])
    idx = pd.bdate_range("2020-01-02", periods=n + 1)
    return pd.DataFrame(levels, index=idx, columns=tickers)


def _holdings(tickers: list[str], weights: list[float]) -> list[dict]:
    return [{"ticker": t, "weight": w} for t, w in zip(tickers, weights)]


def test_price_frame_helper_recovers_its_inputs_exactly():
    """Meta-test: if this drifts, every assertion built on it is meaningless."""
    mu = [0.10, 0.04]
    cov = [[0.04, 0.006], [0.006, 0.0225]]
    frame = _price_frame(["A", "B"], mu, cov)

    log_ret = np.log(frame / frame.shift(1)).dropna()

    assert log_ret.mean().values * TD == pytest.approx(mu, abs=1e-12)
    assert log_ret.cov().values * TD == pytest.approx(np.array(cov), abs=1e-12)


# ── Kelly criterion ──────────────────────────────────────────────────────────

def test_kelly_fraction_uses_arithmetic_excess_return():
    """Audit C-09: f* = (mu_arith - r) / sigma^2 on simple returns.

    The generator's log drift 0.02 with variance 0.16 is an arithmetic drift
    of 0.02 + 0.16/2 = 0.10, so f* = (0.10 - 0.02) / 0.16 = 0.5 (the old
    log-mean formula gave 0.125). Checked against the frame's own simple
    returns, independently of the production code path.
    """
    mu_log, var, rf = 0.02, 0.16, 0.02
    frame = _price_frame(["A"], [mu_log], [[var]])
    simple = frame["A"].pct_change().dropna()
    expected = (simple.mean() * TD - rf) / (simple.var(ddof=1) * TD)

    row = pf.kelly_criterion(_holdings(["A"], [1.0]), frame, rf=rf)[0]

    assert row["kellyFraction"] == pytest.approx(expected, abs=1e-9)
    assert row["kellyFraction"] == pytest.approx((mu_log + var / 2 - rf) / var, abs=0.03)


def test_kelly_is_capped_at_one_and_floored_at_zero():
    hot = _price_frame(["A"], [0.60], [[0.04]])       # mu/sigma^2 = 15
    assert pf.kelly_criterion(_holdings(["A"], [1.0]), hot)[0]["kellyFraction"] == 1.0

    cold = _price_frame(["A"], [-0.20], [[0.04]])     # negative drift
    assert pf.kelly_criterion(_holdings(["A"], [1.0]), cold)[0]["kellyFraction"] == 0.0


def test_kelly_reports_nulls_for_insufficient_history():
    frame = _price_frame(["A"], [0.08], [[0.04]], n=10)
    row = pf.kelly_criterion(_holdings(["A"], [1.0]), frame)[0]
    assert row["kellyFraction"] is None


def test_kelly_skips_tickers_absent_from_the_frame():
    frame = _price_frame(["A"], [0.08], [[0.04]])
    out = pf.kelly_criterion(_holdings(["A", "MISSING"], [0.5, 0.5]), frame)
    assert [r["ticker"] for r in out] == ["A"]


# ── Risk contribution ────────────────────────────────────────────────────────

def test_risk_contributions_sum_to_portfolio_volatility():
    """Euler decomposition: sum_i w_i (Sigma w)_i / sigma_p == sigma_p."""
    cov = [[0.04, 0.010, 0.005],
           [0.010, 0.09, 0.012],
           [0.005, 0.012, 0.0625]]
    tickers = ["A", "B", "C"]
    weights = np.array([0.5, 0.3, 0.2])
    frame = _price_frame(tickers, [0.05, 0.07, 0.06], cov)

    rows = pf.risk_contribution(_holdings(tickers, list(weights)), frame)

    expected_vol = math.sqrt(float(weights @ np.array(cov) @ weights))
    assert sum(r["marginalContrib"] for r in rows) == pytest.approx(expected_vol, abs=1e-9)


def test_percent_contributions_sum_to_one():
    tickers = ["A", "B", "C"]
    frame = _price_frame(tickers, [0.05, 0.07, 0.06],
                         [[0.04, 0.01, 0.005], [0.01, 0.09, 0.012], [0.005, 0.012, 0.0625]])
    rows = pf.risk_contribution(_holdings(tickers, [0.5, 0.3, 0.2]), frame)
    assert sum(r["pctContrib"] for r in rows) == pytest.approx(1.0, abs=1e-9)


def test_equal_weight_uncorrelated_equal_vol_assets_contribute_equally():
    tickers = ["A", "B", "C"]
    cov = np.diag([0.04, 0.04, 0.04]).tolist()
    frame = _price_frame(tickers, [0.05, 0.05, 0.05], cov)

    rows = pf.risk_contribution(_holdings(tickers, [1 / 3, 1 / 3, 1 / 3]), frame)

    contribs = [r["pctContrib"] for r in rows]
    assert contribs == pytest.approx([1 / 3, 1 / 3, 1 / 3], abs=1e-9)


def test_risk_contribution_normalises_weights_that_do_not_sum_to_one():
    """Weights of 2 and 2 must behave identically to 0.5 and 0.5."""
    tickers = ["A", "B"]
    frame = _price_frame(tickers, [0.05, 0.06], [[0.04, 0.01], [0.01, 0.09]])

    a = pf.risk_contribution(_holdings(tickers, [2.0, 2.0]), frame)
    b = pf.risk_contribution(_holdings(tickers, [0.5, 0.5]), frame)

    assert [r["pctContrib"] for r in a] == pytest.approx([r["pctContrib"] for r in b], abs=1e-12)


def test_risk_contribution_empty_when_no_ticker_matches():
    frame = _price_frame(["A"], [0.05], [[0.04]])
    assert pf.risk_contribution(_holdings(["ZZZ"], [1.0]), frame) == []


# ── Correlation matrix ───────────────────────────────────────────────────────

def test_correlation_matrix_recovers_known_correlation():
    # cov 0.012 with vols 0.2 and 0.3 -> rho = 0.012 / (0.2*0.3) = 0.2
    frame = _price_frame(["A", "B"], [0.05, 0.05], [[0.04, 0.012], [0.012, 0.09]])

    out = pf.correlation_matrix(_holdings(["A", "B"], [0.5, 0.5]), frame)

    assert out["tickers"] == ["A", "B"]
    assert out["matrix"][0][0] == pytest.approx(1.0, abs=1e-9)
    assert out["matrix"][1][1] == pytest.approx(1.0, abs=1e-9)
    assert out["matrix"][0][1] == pytest.approx(0.2, abs=1e-3)   # rounded to 3dp
    assert out["matrix"][0][1] == out["matrix"][1][0]            # symmetric


def test_correlation_matrix_needs_two_tickers():
    frame = _price_frame(["A"], [0.05], [[0.04]])
    assert pf.correlation_matrix(_holdings(["A"], [1.0]), frame) == {"tickers": ["A"], "matrix": []}


# ── Efficient frontier ───────────────────────────────────────────────────────

@pytest.fixture
def fixed_rf(monkeypatch):
    """`efficient_frontier` calls risk_free_rate(), which reaches FRED."""
    monkeypatch.setattr(pf, "risk_free_rate", lambda: 0.03)
    return 0.03


@pytest.fixture
def three_asset_frame():
    return _price_frame(
        ["A", "B", "C"],
        [0.12, 0.08, 0.05],
        [[0.0625, 0.010, 0.004], [0.010, 0.040, 0.006], [0.004, 0.006, 0.0225]],
    )


def test_frontier_returns_are_non_decreasing(fixed_rf, three_asset_frame):
    """Targets are swept low to high, so the return axis must be ordered."""
    pts = pf.efficient_frontier(_holdings(["A", "B", "C"], [0.4, 0.4, 0.2]), three_asset_frame)["frontier"]
    assert len(pts) > 10
    rets = [p["ret"] for p in pts]
    assert all(b >= a - 1e-9 for a, b in zip(rets, rets[1:]))


def test_frontier_volatility_is_valley_shaped(fixed_rf, three_asset_frame):
    """The mean-variance frontier falls to the global minimum-variance point
    and rises after it. Anything else is not a frontier."""
    pts = pf.efficient_frontier(_holdings(["A", "B", "C"], [0.4, 0.4, 0.2]), three_asset_frame)["frontier"]
    vols = [p["vol"] for p in pts]
    argmin = vols.index(min(vols))

    assert all(b <= a + 1e-6 for a, b in zip(vols[:argmin], vols[1:argmin + 1]))
    assert all(b >= a - 1e-6 for a, b in zip(vols[argmin:], vols[argmin + 1:]))


def test_frontier_minimum_variance_beats_the_equal_weight_portfolio(fixed_rf, three_asset_frame):
    holdings = _holdings(["A", "B", "C"], [1 / 3, 1 / 3, 1 / 3])
    out = pf.efficient_frontier(holdings, three_asset_frame)

    best = min(p["vol"] for p in out["frontier"])
    assert best <= out["currentPortfolio"]["vol"] + 1e-9


def test_max_sharpe_portfolio_is_at_least_as_good_as_every_frontier_point(fixed_rf, three_asset_frame):
    out = pf.efficient_frontier(_holdings(["A", "B", "C"], [0.4, 0.4, 0.2]), three_asset_frame)
    best_on_curve = max(p["sharpe"] for p in out["frontier"] if p["sharpe"] is not None)
    assert out["maxSharpe"]["sharpe"] >= best_on_curve - 1e-6


def test_max_sharpe_weights_are_long_only_and_sum_to_one(fixed_rf, three_asset_frame):
    out = pf.efficient_frontier(_holdings(["A", "B", "C"], [0.4, 0.4, 0.2]), three_asset_frame)
    ws = [w["weight"] for w in out["maxSharpe"]["weights"]]
    assert sum(ws) == pytest.approx(1.0, abs=1e-6)
    assert all(-1e-9 <= w <= 1.0 + 1e-9 for w in ws)


def test_frontier_rejects_single_holding(fixed_rf):
    frame = _price_frame(["A"], [0.05], [[0.04]])
    out = pf.efficient_frontier(_holdings(["A"], [1.0]), frame)
    assert out["frontier"] == []
    assert "at least 2" in out["error"]


def test_frontier_rejects_short_history(fixed_rf):
    frame = _price_frame(["A", "B"], [0.05, 0.06], [[0.04, 0.01], [0.01, 0.09]], n=20)
    out = pf.efficient_frontier(_holdings(["A", "B"], [0.5, 0.5]), frame)
    assert out["error"] == "insufficient price history"


# ── Black-Litterman ──────────────────────────────────────────────────────────

BL_TICKERS = ["A", "B", "C"]
BL_COV = [[0.0625, 0.010, 0.004],
          [0.010, 0.040, 0.006],
          [0.004, 0.006, 0.0225]]


@pytest.fixture
def bl_frame():
    return _price_frame(BL_TICKERS, [0.10, 0.07, 0.04], BL_COV)


def test_with_no_views_posterior_equals_the_equilibrium_prior(bl_frame):
    """The defining property: absent views, Black-Litterman returns the prior."""
    out = pf.black_litterman(_holdings(BL_TICKERS, [0.5, 0.3, 0.2]), bl_frame, views=[], rf=0.03)

    for row in out["blReturns"]:
        assert row["blReturn"] == pytest.approx(row["equilibriumReturn"], abs=1e-12)

    weights = [w["weight"] for w in out["optimalWeights"]]
    assert weights == pytest.approx([0.5, 0.3, 0.2], abs=1e-12)


def test_equilibrium_returns_match_reverse_optimisation_formula(bl_frame):
    """pi = delta * Sigma * w_mkt with delta = 2.5."""
    w = np.array([0.5, 0.3, 0.2])
    # pi is an excess return; the response reports total return (pi + rf).
    expected = 2.5 * np.array(BL_COV) @ w + 0.03

    out = pf.black_litterman(_holdings(BL_TICKERS, list(w)), bl_frame, views=[], rf=0.03)
    got = [r["equilibriumReturn"] for r in out["blReturns"]]

    assert got == pytest.approx(expected, abs=1e-9)


def test_views_naming_unknown_tickers_are_ignored(bl_frame):
    """An unusable view must fall back to equilibrium, not corrupt the posterior."""
    out = pf.black_litterman(
        _holdings(BL_TICKERS, [0.5, 0.3, 0.2]), bl_frame,
        views=[{"ticker": "NOT_HELD", "expectedReturn": 0.5}], rf=0.03,
    )
    for row in out["blReturns"]:
        assert row["blReturn"] == pytest.approx(row["equilibriumReturn"], abs=1e-12)


def test_a_bullish_view_raises_that_assets_posterior_return(bl_frame):
    holdings = _holdings(BL_TICKERS, [0.5, 0.3, 0.2])
    base = pf.black_litterman(holdings, bl_frame, views=[], rf=0.03)
    eq_a = next(r["equilibriumReturn"] for r in base["blReturns"] if r["ticker"] == "A")

    out = pf.black_litterman(
        holdings, bl_frame,
        views=[{"ticker": "A", "expectedReturn": eq_a + 0.25}], rf=0.03,
    )
    bl_a = next(r["blReturn"] for r in out["blReturns"] if r["ticker"] == "A")

    assert bl_a > eq_a


def test_a_view_equal_to_equilibrium_leaves_the_posterior_unchanged(bl_frame):
    """Agreeing with the prior should move nothing — a sharp check on the
    posterior blend, which a sign error in the P/Omega terms would break."""
    holdings = _holdings(BL_TICKERS, [0.5, 0.3, 0.2])
    base = pf.black_litterman(holdings, bl_frame, views=[], rf=0.03)
    eq_a = next(r["equilibriumReturn"] for r in base["blReturns"] if r["ticker"] == "A")

    out = pf.black_litterman(
        holdings, bl_frame, views=[{"ticker": "A", "expectedReturn": eq_a}], rf=0.03,
    )

    for row, prior in zip(out["blReturns"], base["blReturns"]):
        assert row["blReturn"] == pytest.approx(prior["equilibriumReturn"], abs=1e-9)


def test_bearish_view_pushes_posterior_below_equilibrium(bl_frame):
    holdings = _holdings(BL_TICKERS, [0.5, 0.3, 0.2])
    base = pf.black_litterman(holdings, bl_frame, views=[], rf=0.03)
    eq_b = next(r["equilibriumReturn"] for r in base["blReturns"] if r["ticker"] == "B")

    out = pf.black_litterman(
        holdings, bl_frame, views=[{"ticker": "B", "expectedReturn": eq_b - 0.20}], rf=0.03,
    )
    bl_b = next(r["blReturn"] for r in out["blReturns"] if r["ticker"] == "B")

    assert bl_b < eq_b


def test_black_litterman_optimal_weights_are_long_only_and_normalised(bl_frame):
    out = pf.black_litterman(
        _holdings(BL_TICKERS, [0.5, 0.3, 0.2]), bl_frame,
        views=[{"ticker": "A", "expectedReturn": 0.30}], rf=0.03,
    )
    ws = [w["weight"] for w in out["optimalWeights"]]
    assert sum(ws) == pytest.approx(1.0, abs=1e-9)
    assert all(w >= -1e-12 for w in ws)


def test_black_litterman_rejects_single_holding(bl_frame):
    out = pf.black_litterman(_holdings(["A"], [1.0]), bl_frame, views=[], rf=0.03)
    assert "at least 2" in out["error"]


# ── Drawdown ─────────────────────────────────────────────────────────────────

def test_monotonically_rising_series_never_draws_down():
    rets = pd.Series([0.01] * 50, index=pd.bdate_range("2024-01-01", periods=50))
    assert all(p["value"] == pytest.approx(0.0, abs=1e-12) for p in pf.drawdown_series(rets))


def test_drawdown_matches_a_hand_computed_peak_to_trough():
    # +25%, then -20%, -20%: wealth 1.25 -> 1.0 -> 0.8; trough is 0.8/1.25 - 1
    rets = pd.Series([0.25, -0.20, -0.20], index=pd.bdate_range("2024-01-01", periods=3))
    values = [p["value"] for p in pf.drawdown_series(rets)]

    assert values[0] == pytest.approx(0.0, abs=1e-12)
    assert values[1] == pytest.approx(1.0 / 1.25 - 1.0, abs=1e-12)
    assert values[2] == pytest.approx(0.8 / 1.25 - 1.0, abs=1e-12)


def test_drawdown_recovers_to_zero_at_a_new_high():
    rets = pd.Series([0.5, -0.5, 2.0], index=pd.bdate_range("2024-01-01", periods=3))
    assert pf.drawdown_series(rets)[-1]["value"] == pytest.approx(0.0, abs=1e-12)


def test_drawdown_handles_empty_input():
    assert pf.drawdown_series(pd.Series(dtype=float)) == []
    assert pf.drawdown_series(None) == []


# ── Monte Carlo weights & stress test ────────────────────────────────────────

def test_monte_carlo_weights_returns_points_and_a_best_sharpe(three_asset_frame):
    out = pf.monte_carlo_weights(_holdings(["A", "B", "C"], [0.4, 0.4, 0.2]), three_asset_frame, n_sim=500)

    assert len(out["points"]) > 0
    assert out["maxSharpe"]
    assert all(p["vol"] > 0 for p in out["points"])


def test_monte_carlo_weights_rejects_single_holding():
    frame = _price_frame(["A"], [0.05], [[0.04]])
    out = pf.monte_carlo_weights(_holdings(["A"], [1.0]), frame, n_sim=100)
    assert out["points"] == []
    assert "at least 2" in out["error"]


def test_stress_test_returns_empty_when_no_holding_is_present():
    frame = _price_frame(["A"], [0.05], [[0.04]])
    assert pf.stress_test_portfolio(_holdings(["ZZZ"], [1.0]), frame, "^GSPC") == []


def test_stress_test_does_not_raise_on_a_normal_portfolio(three_asset_frame):
    out = pf.stress_test_portfolio(_holdings(["A", "B", "C"], [0.4, 0.4, 0.2]), three_asset_frame, "^GSPC")
    assert isinstance(out, list)


def test_bl_prior_uses_market_caps_when_available(bl_frame):
    """Audit C-08: the equilibrium prior is the market-cap portfolio."""
    caps = {"A": 600.0, "B": 300.0, "C": 100.0}
    out = pf.black_litterman(_holdings(BL_TICKERS, [0.2, 0.2, 0.6]), bl_frame,
                             views=[], rf=0.03, market_caps=caps)
    assert out["priorWeights"] == "marketCap"
    expected = 2.5 * np.array(BL_COV) @ np.array([0.6, 0.3, 0.1]) + 0.03
    assert [r["equilibriumReturn"] for r in out["blReturns"]] == pytest.approx(expected, abs=1e-9)
    # No views: optimal = market weights; current = the user's weights.
    assert [w["weight"] for w in out["optimalWeights"]] == pytest.approx([0.6, 0.3, 0.1], abs=1e-9)
    assert [w["weight"] for w in out["currentWeights"]] == pytest.approx([0.2, 0.2, 0.6], abs=1e-9)


def test_sortino_downside_deviation_over_all_days():
    """Audit C-17, by hand: r = [+2%, −1%, +1%, −3%], MAR 0.
    shortfall² = [0, 1e-4, 0, 9e-4] → mean 2.5e-4 → DD = 0.015811·√252;
    mean r = −0.25% → numerator −0.0025·252."""
    r = pd.Series([0.02, -0.01, 0.01, -0.03])
    expected = (-0.0025 * TD) / (math.sqrt(2.5e-4) * math.sqrt(TD))
    assert pf._sortino(r, 0.0) == pytest.approx(expected, abs=1e-12)


def test_portfolio_returns_reweight_before_a_holding_lists():
    """Audit C-20: a holding with no price yet must not earn a fake 0%."""
    idx = pd.bdate_range("2024-01-01", periods=4)
    frame = pd.DataFrame({"A": [100.0, 110.0, 121.0, 133.1],
                          "B": [np.nan, np.nan, 50.0, 55.0]}, index=idx)
    port = pf._portfolio_returns(frame, {"A": 0.5, "B": 0.5})
    # Days 2–3: only A trades → 100% A (+10%); day 4: both +10%.
    assert list(port.round(10)) == [0.1, 0.1, 0.1]
