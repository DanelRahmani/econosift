"""Tests for the vectorized backtester — Phase 43 (task D1).

The critical tests are the two alignment sentinels. Writing them caught a real
defect: the engine originally shifted the signal an extra period on top of the
forward-return shift, so it modelled a trader who waits a full period after
seeing their own signal — understating every strategy rather than protecting
against look-ahead. Sentinel A pins that a signal equal to the next period's
return scores perfectly; Sentinel B pins that one equal to the last period's
does not.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services.backtest_engine import (
    LookaheadError,
    _performance,
    _quantile_weights,
    _rebalance_dates,
    _turnover,
    run_backtest,
)

TICKERS = [f"T{i:02d}" for i in range(20)]


def _price_frame(returns: np.ndarray, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Prices from a (dates x tickers) array of per-day simple returns."""
    return pd.DataFrame(
        100.0 * np.cumprod(1.0 + returns, axis=0), index=dates, columns=TICKERS
    )


@pytest.fixture
def daily_dates():
    return pd.bdate_range("2015-01-01", periods=1500)


# ── Helpers ──────────────────────────────────────────────────────────────────

def test_rebalance_dates_pick_the_last_trading_day_of_each_period(daily_dates):
    monthly = _rebalance_dates(daily_dates, "M")
    assert len(monthly) > 60
    assert monthly.is_monotonic_increasing
    # Consecutive gaps are roughly a month of business days.
    gaps = np.diff(monthly.values).astype("timedelta64[D]").astype(int)
    assert 25 <= np.median(gaps) <= 35


def test_rebalance_rejects_an_unknown_frequency(daily_dates):
    with pytest.raises(ValueError):
        _rebalance_dates(daily_dates, "hourly")


def test_quantile_weights_partition_the_cross_section():
    row = pd.Series(np.arange(20.0), index=TICKERS)
    buckets = _quantile_weights(row, 5)

    assert len(buckets) == 5
    members = [t for w in buckets.values() for t in w.index]
    assert len(members) == len(set(members)) == 20      # no overlap, full cover
    for w in buckets.values():
        assert w.sum() == pytest.approx(1.0)


def test_quantile_weights_put_the_highest_signal_in_the_top_bucket():
    row = pd.Series(np.arange(20.0), index=TICKERS)
    buckets = _quantile_weights(row, 5)
    assert TICKERS[-1] in buckets[5].index
    assert TICKERS[0] in buckets[1].index


def test_quantile_weights_survive_ties():
    """Ranking before qcut stops ties from collapsing a bucket."""
    row = pd.Series([1.0] * 20, index=TICKERS)
    assert len(_quantile_weights(row, 5)) == 5


def test_quantile_weights_skip_a_thin_cross_section():
    row = pd.Series([1.0, 2.0], index=TICKERS[:2])
    assert _quantile_weights(row, 5) == {}


def test_turnover_is_zero_when_weights_are_unchanged():
    w = pd.Series([0.5, 0.5], index=["A", "B"])
    assert _turnover(w, w) == pytest.approx(0.0)


def test_turnover_is_one_on_a_complete_switch():
    old = pd.Series([0.5, 0.5], index=["A", "B"])
    new = pd.Series([0.5, 0.5], index=["C", "D"])
    assert _turnover(old, new) == pytest.approx(1.0)


def test_first_period_turnover_is_half_the_gross_weight():
    """Opening a fully invested book is 1.0 of one-way turnover."""
    w = pd.Series([0.5, 0.5], index=["A", "B"])
    assert _turnover(None, w) == pytest.approx(0.5)


def test_performance_on_a_known_series():
    perf = _performance([0.10, -0.10, 0.10, -0.10], periods_per_year=12.0)
    expected_total = 1.10 * 0.90 * 1.10 * 0.90 - 1.0

    assert perf["totalReturn"] == pytest.approx(expected_total, abs=1e-9)
    assert perf["hitRate"] == pytest.approx(0.5)
    assert perf["maxDrawdown"] < 0
    assert perf["periods"] == 4


def test_performance_handles_an_empty_series():
    perf = _performance([], periods_per_year=12.0)
    assert perf["periods"] == 0 and perf["cagr"] is None


# ── The look-ahead sentinel ──────────────────────────────────────────────────

def test_alignment_signal_at_t_earns_the_return_from_t_to_t_plus_one(daily_dates):
    """Sentinel A — pins the alignment.

    A signal whose value at t IS the return from t to t+1 is look-ahead by
    construction, so it must produce a near-perfect spread. If someone adds an
    extra lag to the signal, this alignment breaks and the spread collapses.
    """
    rng = np.random.default_rng(0)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)

    rebal = _rebalance_dates(daily_dates, "M")
    fwd = prices.reindex(rebal, method="ffill").pct_change().shift(-1)
    oracle = fwd.reindex(prices.index, method="ffill")

    res = run_backtest(oracle, prices, rebalance="M", cost_bps=0.0)
    spread = res["longShort"]["gross"]

    # Perfect foresight over ~70 monthly periods: every period must be a win.
    assert spread["hitRate"] == pytest.approx(1.0, abs=1e-9)
    assert spread["totalReturn"] > 5.0


def test_alignment_a_past_return_signal_earns_no_edge(daily_dates):
    """Sentinel B — pins the other direction.

    The same construction shifted one period forward carries only information
    already public at t. It must NOT win. If someone removes the shift(-1) on
    returns, this signal becomes an oracle and starts winning, failing here.
    """
    rng = np.random.default_rng(0)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)

    rebal = _rebalance_dates(daily_dates, "M")
    fwd = prices.reindex(rebal, method="ffill").pct_change().shift(-1)
    stale = fwd.shift(1).reindex(prices.index, method="ffill")

    res = run_backtest(stale, prices, rebalance="M", cost_bps=0.0)
    spread = res["longShort"]["gross"]

    assert spread["hitRate"] < 0.9
    assert abs(spread["sharpe"] or 0.0) < 2.5


def test_a_pure_noise_signal_earns_roughly_nothing(daily_dates):
    rng = np.random.default_rng(3)
    rets = rng.normal(0.0004, 0.012, size=(len(daily_dates), len(TICKERS)))
    prices = _price_frame(rets, daily_dates)
    noise = pd.DataFrame(
        rng.normal(size=(len(daily_dates), len(TICKERS))), index=daily_dates, columns=TICKERS
    )

    res = run_backtest(noise, prices, rebalance="M", cost_bps=0.0)
    spread = res["longShort"]["gross"]

    # Over ~70 monthly periods a noise signal should not produce a large Sharpe.
    assert abs(spread["sharpe"] or 0.0) < 1.0


# ── Costs ────────────────────────────────────────────────────────────────────

def test_net_equals_gross_minus_costs_exactly(daily_dates):
    rng = np.random.default_rng(5)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(rng.normal(size=(len(daily_dates), len(TICKERS))), index=daily_dates, columns=TICKERS)

    free = run_backtest(sig, prices, rebalance="M", cost_bps=0.0)
    charged = run_backtest(sig, prices, rebalance="M", cost_bps=50.0)

    # With zero cost, gross and net must be identical.
    assert free["quantiles"]["5"]["gross"]["totalReturn"] == pytest.approx(
        free["quantiles"]["5"]["net"]["totalReturn"], abs=1e-9
    )
    # With cost, gross is unchanged but net is strictly worse.
    assert charged["quantiles"]["5"]["gross"]["totalReturn"] == pytest.approx(
        free["quantiles"]["5"]["gross"]["totalReturn"], abs=1e-9
    )
    assert charged["quantiles"]["5"]["net"]["totalReturn"] < charged["quantiles"]["5"]["gross"]["totalReturn"]
    assert charged["quantiles"]["5"]["totalCostDrag"] > 0


def test_higher_costs_hurt_more(daily_dates):
    rng = np.random.default_rng(7)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(rng.normal(size=(len(daily_dates), len(TICKERS))), index=daily_dates, columns=TICKERS)

    cheap = run_backtest(sig, prices, cost_bps=5.0)["quantiles"]["5"]["net"]["totalReturn"]
    dear = run_backtest(sig, prices, cost_bps=100.0)["quantiles"]["5"]["net"]["totalReturn"]
    assert dear < cheap


def test_a_constant_signal_produces_near_zero_turnover(daily_dates):
    """Same ranking every period means the book barely moves after it is built."""
    rng = np.random.default_rng(11)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)
    constant = pd.DataFrame(
        np.tile(np.arange(len(TICKERS), dtype=float), (len(daily_dates), 1)),
        index=daily_dates, columns=TICKERS,
    )

    res = run_backtest(constant, prices, rebalance="M", cost_bps=10.0)
    assert res["avgTurnover"] < 0.05


# ── Guards & contracts ───────────────────────────────────────────────────────

def test_fundamental_signals_are_refused_without_opt_in(daily_dates):
    prices = _price_frame(np.zeros((len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(1.0, index=daily_dates, columns=TICKERS)

    with pytest.raises(LookaheadError, match="restatement"):
        run_backtest(sig, prices, is_fundamental=True)


def test_fundamental_signals_run_with_opt_in_and_carry_a_warning(daily_dates):
    rng = np.random.default_rng(13)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(rng.normal(size=(len(daily_dates), len(TICKERS))), index=daily_dates, columns=TICKERS)

    res = run_backtest(sig, prices, is_fundamental=True, allow_lookahead=True)
    assert res["available"] is True
    assert "upper bound" in res["warning"]


def test_point_in_time_universe_restricts_the_tradable_set(daily_dates):
    rng = np.random.default_rng(17)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(rng.normal(size=(len(daily_dates), len(TICKERS))), index=daily_dates, columns=TICKERS)

    half = TICKERS[:10]
    res = run_backtest(sig, prices, universe_as_of=lambda d: half, n_quantiles=5)

    assert res["available"] is True
    assert res["settings"]["universePointInTime"] is True


def test_a_failing_universe_lookup_does_not_kill_the_run(daily_dates):
    rng = np.random.default_rng(19)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(rng.normal(size=(len(daily_dates), len(TICKERS))), index=daily_dates, columns=TICKERS)

    def boom(_d):
        raise RuntimeError("wikipedia down")

    res = run_backtest(sig, prices, universe_as_of=boom)
    assert res["available"] is True


def test_empty_inputs_degrade_rather_than_raise():
    assert run_backtest(pd.DataFrame(), pd.DataFrame())["available"] is False


def test_too_few_shared_tickers_is_reported(daily_dates):
    prices = _price_frame(np.zeros((len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(1.0, index=daily_dates, columns=TICKERS[:2])
    out = run_backtest(sig, prices, n_quantiles=5)

    assert out["available"] is False
    assert "common to signal and prices" in out["reason"]


def test_quantiles_and_equity_curves_line_up(daily_dates):
    rng = np.random.default_rng(23)
    prices = _price_frame(rng.normal(0.0004, 0.012, (len(daily_dates), len(TICKERS))), daily_dates)
    sig = pd.DataFrame(rng.normal(size=(len(daily_dates), len(TICKERS))), index=daily_dates, columns=TICKERS)

    res = run_backtest(sig, prices, n_quantiles=4)

    assert set(res["quantiles"]) == {"1", "2", "3", "4"}
    for q in res["quantiles"].values():
        assert len(q["equityCurve"]) == res["periods"]
    assert res["caveat"]
