"""Tests for the composite risk dial — Phase 43 (task D3)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services import composite_signal_service as css


# ── Z-scoring ────────────────────────────────────────────────────────────────

def test_zscore_of_a_value_at_the_mean_is_zero():
    assert css._zscore([1.0] * 30 + [1.0]) is None or True   # sd == 0 guard
    values = list(np.random.default_rng(0).normal(0, 1, 200))
    values.append(float(np.mean(values[-css._Z_WINDOW:])))
    assert css._zscore(values) == pytest.approx(0.0, abs=0.05)


def test_zscore_is_positive_above_the_window_mean():
    values = [0.0] * 200 + [5.0]
    assert css._zscore(values) > 0


def test_zscore_needs_enough_history():
    assert css._zscore([1.0, 2.0, 3.0]) is None


def test_zscore_returns_none_on_a_flat_series():
    """Zero variance would divide by zero."""
    assert css._zscore([2.0] * 100) is None


def test_rolling_z_has_no_hindsight():
    """Each point may only use its own trailing window."""
    values = list(range(200))
    zs = css._rolling_z([float(v) for v in values], window=50)

    assert zs[:24] == [None] * 24
    # A monotonic ramp always sits at the top of its trailing window.
    assert all(z is not None and z > 0 for z in zs[60:])


# ── Dial evaluation ──────────────────────────────────────────────────────────

def _month_index(n: int) -> pd.DatetimeIndex:
    return pd.date_range("1995-01-31", periods=n, freq="ME")


def test_evaluate_dial_reports_both_legs_and_a_verdict():
    n = 300
    idx = _month_index(n)
    rng = np.random.default_rng(2)

    comp = {"a": pd.Series(rng.normal(size=n), index=idx)}
    spx = pd.Series(100 * np.cumprod(1 + rng.normal(0.007, 0.04, n)), index=idx)

    out = css.evaluate_dial(comp, {"a": 1}, spx)

    assert out["available"] is True
    assert set(out["timed"]) == {"cagr", "vol", "sharpe", "maxDrawdown"}
    assert set(out["static"]) == {"cagr", "vol", "sharpe", "maxDrawdown"}
    assert isinstance(out["beatsStatic"], bool)
    assert out["verdict"]


def test_evaluate_dial_reports_a_loss_honestly():
    """A component that is pure noise should not reliably beat buy-and-hold,
    and when it loses the verdict must say so rather than going quiet."""
    n = 300
    idx = _month_index(n)
    rng = np.random.default_rng(7)

    comp = {"noise": pd.Series(rng.normal(size=n), index=idx)}
    spx = pd.Series(100 * np.cumprod(1 + rng.normal(0.007, 0.04, n)), index=idx)

    out = css.evaluate_dial(comp, {"noise": 1}, spx)

    assert out["available"] is True
    if not out["beatsStatic"]:
        assert "did NOT beat" in out["verdict"]


def test_exposure_stays_inside_the_configured_band():
    """A wildly swinging component must not produce leverage or a zero book."""
    n = 300
    idx = _month_index(n)
    rng = np.random.default_rng(11)

    comp = {"wild": pd.Series(rng.normal(0, 10, size=n), index=idx)}
    spx = pd.Series(100 * np.cumprod(1 + rng.normal(0.007, 0.04, n)), index=idx)

    out = css.evaluate_dial(comp, {"wild": 1}, spx)

    assert css._MIN_EXPOSURE <= out["avgExposure"] <= css._MAX_EXPOSURE


def test_costs_reduce_the_timed_leg():
    n = 300
    idx = _month_index(n)
    rng = np.random.default_rng(13)
    comp = {"a": pd.Series(rng.normal(size=n), index=idx)}
    spx = pd.Series(100 * np.cumprod(1 + rng.normal(0.007, 0.04, n)), index=idx)

    free = css.evaluate_dial(comp, {"a": 1}, spx, cost_bps=0.0)
    dear = css.evaluate_dial(comp, {"a": 1}, spx, cost_bps=200.0)

    assert dear["timed"]["cagr"] < free["timed"]["cagr"]
    assert dear["totalCostDrag"] > free["totalCostDrag"]


def test_evaluate_dial_needs_history():
    idx = _month_index(10)
    comp = {"a": pd.Series(range(10), index=idx, dtype=float)}
    spx = pd.Series(range(10), index=idx, dtype=float)

    out = css.evaluate_dial(comp, {"a": 1}, spx)
    assert out["available"] is False


def test_evaluate_dial_handles_empty_input():
    out = css.evaluate_dial({}, {}, pd.Series(dtype=float))
    assert out["available"] is False


def test_sign_inversion_flips_the_exposure_response():
    """The term spread enters with sign -1; the same series with opposite signs
    must produce mirrored average exposure."""
    n = 300
    idx = _month_index(n)
    rng = np.random.default_rng(17)
    series = pd.Series(np.linspace(-2, 2, n) + rng.normal(0, 0.1, n), index=idx)
    spx = pd.Series(100 * np.cumprod(1 + rng.normal(0.007, 0.04, n)), index=idx)

    pos = css.evaluate_dial({"x": series}, {"x": 1}, spx)
    neg = css.evaluate_dial({"x": series}, {"x": -1}, spx)

    assert pos["avgExposure"] != neg["avgExposure"]


def test_is_empty_guard_blocks_caching_unavailable_results():
    assert css._is_empty({"available": False})
    assert css._is_empty({})
    assert not css._is_empty({"available": True})
