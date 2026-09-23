"""Tests for oil_shock_service (demand vs. oil-specific decomposition) — Phase 39."""
import numpy as np
import pandas as pd
import pytest

from backend.services import oil_shock_service as oss


def _months(n: int, start: str = "1995-01-31") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="ME")


def test_ols_recovers_known_coefficients():
    rng = np.random.default_rng(0)
    n = 400
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 1.5 + 2.0 * x1 - 0.5 * x2  # noiseless
    X = np.column_stack([np.ones(n), x1, x2])

    beta, se, r2 = oss._ols(y, X)

    assert beta == pytest.approx([1.5, 2.0, -0.5], abs=1e-8)
    assert r2 == pytest.approx(1.0, abs=1e-9)


def test_to_monthly_averages_within_month():
    pts = [
        {"date": "2020-01-05", "value": 10.0},
        {"date": "2020-01-20", "value": 20.0},
        {"date": "2020-02-10", "value": 30.0},
    ]
    s = oss._to_monthly(pts)
    assert len(s) == 2
    assert s.iloc[0] == pytest.approx(15.0)
    assert s.iloc[1] == pytest.approx(30.0)


def test_to_monthly_drops_nulls_and_handles_empty():
    assert oss._to_monthly([]).empty
    assert oss._to_monthly([{"date": "2020-01-05", "value": None}]).empty


def _synthetic(n=180, demand_beta=0.6, seed=1):
    """Oil returns generated as demand_beta * copper returns + an oil-only shock."""
    rng = np.random.default_rng(seed)
    idx = _months(n)
    cpi = pd.Series(100.0, index=idx)  # flat CPI -> real == nominal
    r_copper = rng.normal(0, 5, n)
    oil_specific = rng.normal(0, 8, n)
    r_oil = demand_beta * r_copper + oil_specific

    copper = pd.Series(100 * np.exp(np.cumsum(r_copper / 100)), index=idx)
    wti = pd.Series(50 * np.exp(np.cumsum(r_oil / 100)), index=idx)
    igrea = pd.Series(rng.normal(0, 10, n), index=idx)
    return wti, cpi, igrea, copper


def test_decompose_recovers_the_demand_beta():
    wti, cpi, igrea, copper = _synthetic(demand_beta=0.6)

    out = oss._decompose(wti, cpi, igrea, copper)

    assert out["available"] is True
    # Copper loading should recover the generating beta within sampling error.
    assert out["regression"]["beta_copper"] == pytest.approx(0.6, abs=0.15)
    assert out["regression"]["n"] > 150


def test_decompose_components_sum_to_total_less_intercept():
    """demand + supply must reconstruct the total return exactly."""
    wti, cpi, igrea, copper = _synthetic()
    out = oss._decompose(wti, cpi, igrea, copper)

    # The intercept is deliberately excluded from `demand`, so the identity is
    # total = intercept + demand + supply. Recover the intercept from any row
    # and check it is constant across all of them.
    residuals = [h["total"] - h["demand"] - h["supply"] for h in out["history"]]
    # Payload values are rounded to 3dp, so the recovered intercept can vary by
    # up to ~1.5e-3 across rows; anything beyond that would mean a real leak.
    assert max(residuals) - min(residuals) < 3e-3
    assert out["regression"]["n"] == len(out["history"])


def test_decompose_flags_demand_driven_month():
    """A month whose move is almost entirely explained by copper reads as demand."""
    n = 120
    idx = _months(n)
    cpi = pd.Series(100.0, index=idx)
    rng = np.random.default_rng(3)
    r_copper = rng.normal(0, 5, n)
    r_oil = 1.0 * r_copper  # perfectly demand-driven, no oil-specific noise
    copper = pd.Series(100 * np.exp(np.cumsum(r_copper / 100)), index=idx)
    wti = pd.Series(50 * np.exp(np.cumsum(r_oil / 100)), index=idx)
    igrea = pd.Series(rng.normal(0, 10, n), index=idx)

    out = oss._decompose(wti, cpi, igrea, copper)

    assert out["latest"]["dominant"] == "demand"
    assert out["regression"]["r2"] > 0.95


def test_interpretation_sign_logic():
    """Rising oil on demand is expansionary; rising oil on supply is not."""
    n = 120
    idx = _months(n)
    cpi = pd.Series(100.0, index=idx)
    rng = np.random.default_rng(5)
    r_copper = rng.normal(0, 5, n)
    copper = pd.Series(100 * np.exp(np.cumsum(r_copper / 100)), index=idx)
    igrea = pd.Series(rng.normal(0, 10, n), index=idx)

    # Final month: a large oil-only spike with copper flat -> supply-driven up.
    r_oil = 0.8 * r_copper
    r_oil[-1] = 40.0
    r_copper[-1] = 0.0
    copper = pd.Series(100 * np.exp(np.cumsum(r_copper / 100)), index=idx)
    wti = pd.Series(50 * np.exp(np.cumsum(r_oil / 100)), index=idx)

    out = oss._decompose(wti, cpi, igrea, copper)

    assert out["latest"]["dominant"] == "supply"
    assert out["latest"]["supply"] > 0
    assert out["latest"]["interpretation"] == "contractionary"


def test_decompose_refuses_short_samples():
    wti, cpi, igrea, copper = _synthetic(n=20)
    out = oss._decompose(wti, cpi, igrea, copper)
    assert out["available"] is False
    assert "observations" in out["reason"]


def test_is_empty_guard_blocks_caching_unavailable_results():
    assert oss._is_empty({"available": False, "reason": "x"})
    assert oss._is_empty({})
    assert not oss._is_empty({"available": True})
