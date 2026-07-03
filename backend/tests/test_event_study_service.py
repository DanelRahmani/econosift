"""Tests for event_study_service — pure market-model event study logic."""
import numpy as np
import pandas as pd

from backend.services.event_study_service import _event_study

TICKER = "TEST"
MKT = "^GSPC"


def _make_synthetic_frame(n=520, jump_positions=(150, 400), jump=0.05):
    """Build a deterministic (zero-noise) price frame where stock == market
    except for an injected ``jump`` return on ``jump_positions`` (0-based
    positions into the *returns* series, i.e. into ``px.index[1:]``).

    Returns (px, event_dates) where event_dates are the trading-day
    timestamps corresponding to each jump position.
    """
    dates = pd.bdate_range("2019-01-02", periods=n)
    i = np.arange(1, n)
    mkt_ret = 0.001 * np.sin(i / 7.0)  # deterministic, non-constant -> well-posed OLS
    stock_ret = mkt_ret.copy()
    for p in jump_positions:
        stock_ret[p] += jump

    mkt_price = 100.0 * np.concatenate([[1.0], np.cumprod(1 + mkt_ret)])
    stock_price = 50.0 * np.concatenate([[1.0], np.cumprod(1 + stock_ret)])

    px = pd.DataFrame({TICKER: stock_price, MKT: mkt_price}, index=dates)
    # trading_days inside _event_study == px.pct_change().dropna().index == dates[1:]
    event_dates = [dates[p + 1] for p in jump_positions]
    return px, event_dates


def test_car_matches_injected_jump():
    window = 5
    est_window = 120
    px, event_dates = _make_synthetic_frame(jump_positions=(150, 400))

    out = _event_study(px, event_dates, TICKER, MKT, window, est_window)

    assert out["nEvents"] == 2
    for ev in out["events"]:
        assert abs(ev["car"] - 0.05) < 1e-6

    assert len(out["carPath"]) == 2 * window + 1
    assert out["kpis"]["hitRate"] == 100.0
    assert abs(out["kpis"]["meanCar"] - 0.05) < 1e-6


def test_early_event_skipped_for_insufficient_estimation_window():
    window = 5
    est_window = 120
    # Position 5 is too early: est_start = 5 - 10 - 120 < 0 -> must be skipped.
    # (Kept well clear of the other events' own estimation windows so it
    # doesn't contaminate their regressions.)
    px, event_dates = _make_synthetic_frame(jump_positions=(5, 150, 400))

    out = _event_study(px, event_dates, TICKER, MKT, window, est_window)

    assert out["nEvents"] == 2
    dates_out = {e["date"] for e in out["events"]}
    early_date = event_dates[0].strftime("%Y-%m-%d")
    assert early_date not in dates_out


def test_empty_events_returns_error():
    px, _ = _make_synthetic_frame()
    out = _event_study(px, [], TICKER, MKT, 5, 120)
    assert "error" in out


def test_flat_price_series_does_not_crash():
    n = 200
    dates = pd.bdate_range("2019-01-02", periods=n)
    flat_stock = np.full(n, 50.0)
    flat_mkt = np.full(n, 100.0)
    px = pd.DataFrame({TICKER: flat_stock, MKT: flat_mkt}, index=dates)
    event_dates = [dates[100]]

    out = _event_study(px, event_dates, TICKER, MKT, 5, 60)

    assert isinstance(out, dict)  # must not raise
