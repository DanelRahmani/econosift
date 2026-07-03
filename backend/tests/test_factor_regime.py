"""Tests for the Factor Regime & Style Rotation Monitor (pure compute) — Phase 39."""
import pandas as pd
import pytest

from backend.services.fama_french import _compute_factor_regime


def _constant_monthly_df(n_months: int = 36) -> pd.DataFrame:
    """36 months of constant per-factor decimal returns, easy to hand-verify.

    Mkt-RF +1%/mo, SMB -1%/mo, HML +2%/mo, RMW +0.5%/mo, CMA +0.3%/mo, Mom +1.5%/mo.
    HML is the strongest performer at every horizon; SMB is the weakest (negative).
    """
    dates = pd.period_range("2021-01", periods=n_months, freq="M")
    return pd.DataFrame(
        {
            "Mkt-RF": 0.01,
            "SMB": -0.01,
            "HML": 0.02,
            "RMW": 0.005,
            "CMA": 0.003,
            "Mom": 0.015,
        },
        index=dates,
    )


def test_empty_dataframe_returns_empty():
    assert _compute_factor_regime(pd.DataFrame()) == {}


def test_3m_compounded_return_hand_verified():
    df = _constant_monthly_df()
    out = _compute_factor_regime(df)
    hml = next(f for f in out["factors"] if f["factor"] == "HML")
    expected_3m = (1.02 ** 3) - 1.0
    assert hml["ret3m"] == pytest.approx(expected_3m)
    expected_1m = 0.02
    assert hml["ret1m"] == pytest.approx(expected_1m)
    expected_12m = (1.02 ** 12) - 1.0
    assert hml["ret12m"] == pytest.approx(expected_12m)


def test_leading_factor_and_regime_label():
    df = _constant_monthly_df()
    out = _compute_factor_regime(df)
    # HML has the highest constant monthly return -> highest 3m return everywhere.
    assert out["kpis"]["leadingFactor"] == "HML"
    # Mkt-RF 3m > 0 -> Risk-On; best style-factor 3m is HML -> Value-led.
    assert out["kpis"]["regime"] == "Risk-On — Value-led"
    assert out["kpis"]["mkt3m"] == pytest.approx((1.01 ** 3) - 1.0)
    assert out["kpis"]["hml12m"] == pytest.approx((1.02 ** 12) - 1.0)
    assert out["kpis"]["smb12m"] == pytest.approx((0.99 ** 12) - 1.0)


def test_mom_rank_ordering():
    df = _constant_monthly_df()
    out = _compute_factor_regime(df)
    ranks = {f["factor"]: f["momRank"] for f in out["factors"]}
    # Ordered by 12m return, best (highest) = rank 1.
    assert ranks["HML"] == 1
    assert ranks["Mom"] == 2
    assert ranks["Mkt-RF"] == 3
    assert ranks["RMW"] == 4
    assert ranks["CMA"] == 5
    assert ranks["SMB"] == 6


def test_cumulative_rows_keyed_and_monotone():
    df = _constant_monthly_df()
    out = _compute_factor_regime(df)
    cumulative = out["cumulative"]
    assert len(cumulative) == 36
    first = cumulative[0]
    assert set(first.keys()) == {"date", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"}
    assert first["date"] == "2021-01"
    # A positive constant-return factor (HML) must be strictly increasing.
    hml_values = [row["HML"] for row in cumulative]
    assert all(b > a for a, b in zip(hml_values, hml_values[1:]))
    # A negative constant-return factor (SMB) must be strictly decreasing.
    smb_values = [row["SMB"] for row in cumulative]
    assert all(b < a for a, b in zip(smb_values, smb_values[1:]))


def test_short_history_yields_none_ret12m_without_crashing():
    # Only 6 months of history for every factor -> ret12m must be None, not a crash.
    df = _constant_monthly_df(n_months=6)
    out = _compute_factor_regime(df)
    for f in out["factors"]:
        assert f["ret12m"] is None
        assert f["ret1m"] is not None
        assert f["ret3m"] is not None
    # No factor has a 12m return, so momRank must be null for all.
    assert all(f["momRank"] is None for f in out["factors"])


def test_rf_column_excluded_from_factors():
    df = _constant_monthly_df()
    df["RF"] = 0.001
    out = _compute_factor_regime(df)
    factor_names = {f["factor"] for f in out["factors"]}
    assert "RF" not in factor_names
    assert "RF" not in out["cumulative"][0]
