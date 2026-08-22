"""Tests for treasury_noise_service (Nelson-Siegel curve-fit noise) — Phase 39."""
import numpy as np
import pandas as pd
import pytest

from backend.services import treasury_noise_service as tns


_MATS = [1 / 12, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]


def _ns_curve(b0: float, b1: float, b2: float, mats=None) -> np.ndarray:
    mats = np.array(mats if mats is not None else _MATS, dtype=float)
    X = tns._ns_loadings(mats)
    return X @ np.array([b0, b1, b2])


def test_ns_loadings_shape_and_limits():
    tau = np.array([1e-9, 1.0, 30.0])
    X = tns._ns_loadings(tau)

    assert X.shape == (3, 3)
    assert np.allclose(X[:, 0], 1.0)          # level loads 1 everywhere
    assert X[0, 1] == pytest.approx(1.0)      # slope -> 1 as tau -> 0
    assert X[0, 2] == pytest.approx(0.0, abs=1e-6)  # curvature -> 0 as tau -> 0
    assert X[2, 1] < X[1, 1]                  # slope loading decays with maturity


def test_exact_nelson_siegel_curve_has_zero_noise():
    """A curve that IS Nelson-Siegel must fit with ~0 residual."""
    yields = _ns_curve(4.0, -1.5, 2.0)
    curve = pd.DataFrame([yields], index=[pd.Timestamp("2024-01-02")], columns=_MATS)

    out = tns._compute_noise(curve)

    assert len(out) == 1
    assert out[0]["value"] == pytest.approx(0.0, abs=1e-6)
    assert out[0]["date"] == "2024-01-02"


def test_known_perturbation_produces_expected_rmse():
    """A +10bp bump on one tenor of an otherwise perfect curve raises RMSE."""
    yields = _ns_curve(4.0, -1.5, 2.0)
    bumped = yields.copy()
    bumped[5] += 0.10  # +10bp on the 3y point (yields are in percent)
    curve = pd.DataFrame([bumped], index=[pd.Timestamp("2024-01-02")], columns=_MATS)

    out = tns._compute_noise(curve)

    # The fit absorbs part of the bump, so RMSE lands below the 10bp shock but
    # is unambiguously non-zero.
    assert 0.5 < out[0]["value"] < 10.0


def test_noise_increases_with_dispersion():
    base = _ns_curve(4.0, -1.5, 2.0)
    rng = np.random.default_rng(0)
    small = base + rng.normal(0, 0.02, len(base))
    large = base + rng.normal(0, 0.20, len(base))

    idx = [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]
    curve = pd.DataFrame([small, large], index=idx, columns=_MATS)

    out = tns._compute_noise(curve)

    assert out[1]["value"] > out[0]["value"]


def test_days_with_too_few_tenors_are_skipped():
    """Fewer than _MIN_TENORS observations cannot support a 3-factor fit."""
    row = [np.nan] * len(_MATS)
    row[0], row[1], row[2] = 4.0, 4.1, 4.2  # only 3 tenors
    curve = pd.DataFrame([row], index=[pd.Timestamp("2024-01-02")], columns=_MATS)

    assert tns._compute_noise(curve) == []


def test_partial_tenor_coverage_still_fits():
    yields = _ns_curve(4.0, -1.5, 2.0)
    row = list(yields)
    row[0] = np.nan
    row[-1] = np.nan  # 9 tenors remain
    curve = pd.DataFrame([row], index=[pd.Timestamp("2024-01-02")], columns=_MATS)

    out = tns._compute_noise(curve)

    assert len(out) == 1
    assert out[0]["value"] == pytest.approx(0.0, abs=1e-6)


def test_compute_noise_handles_empty_frame():
    assert tns._compute_noise(pd.DataFrame()) == []


def test_percentile_rank():
    hist = [{"date": f"2024-01-{i:02d}", "value": float(i)} for i in range(1, 11)]
    assert tns._percentile_rank(hist, 10.0) == 100.0
    assert tns._percentile_rank(hist, 5.0) == 50.0
    assert tns._percentile_rank(hist, None) is None
    assert tns._percentile_rank([], 1.0) is None


def test_is_empty_guard_blocks_caching_of_empty_history():
    assert tns._is_empty({"error": "FRED API key required", "history": []})
    assert tns._is_empty({})
    assert not tns._is_empty({"history": [{"date": "2024-01-02", "value": 8.0}]})
