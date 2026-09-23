"""Tests for technicals_service pure helpers — Phase 40 (task A4).

`get_technicals` fetches from yfinance and delegates most indicator maths to
pandas-ta, which is a tested third-party library. What is worth pinning is the
arithmetic this project owns: classic pivot points, Fibonacci retracements, the
manual RSI fallback used when pandas-ta is unavailable, and the empty-response
contract the frontend renders against.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services import technicals_service as ts


# ── Classic pivot points ─────────────────────────────────────────────────────

def test_pivot_matches_the_textbook_formulas():
    high, low, close = 110.0, 90.0, 105.0
    out = ts._pivot_classic(high, low, close)

    p = (high + low + close) / 3.0
    assert out["p"] == pytest.approx(p)
    assert out["r1"] == pytest.approx(2 * p - low)
    assert out["s1"] == pytest.approx(2 * p - high)
    assert out["r2"] == pytest.approx(p + (high - low))
    assert out["s2"] == pytest.approx(p - (high - low))


def test_pivot_levels_are_correctly_ordered():
    out = ts._pivot_classic(110.0, 90.0, 105.0)
    assert out["s2"] < out["s1"] < out["p"] < out["r1"] < out["r2"]


def test_pivot_collapses_to_a_single_level_on_a_flat_bar():
    """High == low == close means no range, so every level is that price."""
    out = ts._pivot_classic(100.0, 100.0, 100.0)
    assert all(v == pytest.approx(100.0) for v in out.values())


def test_pivot_range_scales_with_the_bar_range():
    narrow = ts._pivot_classic(101.0, 99.0, 100.0)
    wide = ts._pivot_classic(120.0, 80.0, 100.0)
    assert (wide["r2"] - wide["s2"]) > (narrow["r2"] - narrow["s2"])


# ── Fibonacci retracements ───────────────────────────────────────────────────

def test_fib_levels_span_the_swing_endpoints():
    levels = ts._fib_levels(200.0, 100.0)
    prices = [lv["price"] for lv in levels]

    assert prices[0] == pytest.approx(200.0)    # 0% sits at the swing high
    assert prices[-1] == pytest.approx(100.0)   # 100% sits at the swing low


def test_fib_levels_descend_monotonically():
    prices = [lv["price"] for lv in ts._fib_levels(200.0, 100.0)]
    assert all(b <= a for a, b in zip(prices, prices[1:]))


def test_fib_midpoint_is_the_arithmetic_mean_of_the_swing():
    levels = ts._fib_levels(200.0, 100.0)
    fifty = next(lv for lv in levels if lv["level"] == 0.5)
    assert fifty["price"] == pytest.approx(150.0)


def test_fib_uses_the_standard_ratio_set():
    levels = ts._fib_levels(200.0, 100.0)
    assert [lv["level"] for lv in levels] == [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]


def test_fib_handles_an_inverted_swing_without_raising():
    """Low above high is nonsense input, but must not blow up."""
    levels = ts._fib_levels(100.0, 200.0)
    assert levels[0]["price"] == pytest.approx(100.0)
    assert levels[-1]["price"] == pytest.approx(200.0)


# ── Manual RSI fallback ──────────────────────────────────────────────────────

def _close_frame(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": values}, index=pd.bdate_range("2024-01-01", periods=len(values)))


def test_rsi_is_bounded_between_zero_and_one_hundred():
    rng = np.random.default_rng(4)
    prices = 100 * np.exp(np.cumsum(rng.standard_normal(300) * 0.01))
    df = _close_frame(list(prices))

    ts._append_rsi_manual(df)
    rsi = df["RSI_14"].dropna()

    assert len(rsi) > 0
    assert rsi.between(0.0, 100.0).all()


def test_rsi_saturates_near_one_hundred_on_an_unbroken_advance():
    """With no down closes there is no average loss, so RSI pins at the top."""
    df = _close_frame([100.0 + i for i in range(60)])
    ts._append_rsi_manual(df)
    assert df["RSI_14"].dropna().iloc[-1] == pytest.approx(100.0, abs=1e-9)


def test_rsi_saturates_near_zero_on_an_unbroken_decline():
    df = _close_frame([200.0 - i for i in range(60)])
    ts._append_rsi_manual(df)
    assert df["RSI_14"].dropna().iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_rsi_sits_near_fifty_for_a_symmetric_zigzag():
    """Alternating equal gains and losses gives balanced averages."""
    values = [100.0 + (1.0 if i % 2 else 0.0) for i in range(120)]
    df = _close_frame(values)
    ts._append_rsi_manual(df)
    assert df["RSI_14"].dropna().iloc[-1] == pytest.approx(50.0, abs=5.0)


def test_rsi_warms_up_before_producing_values():
    """RSI-14 needs 14 periods; earlier rows must be NaN, not fabricated."""
    df = _close_frame([100.0 + i for i in range(30)])
    ts._append_rsi_manual(df)
    assert df["RSI_14"].iloc[:14].isna().all()


def test_rsi_on_a_flat_series_is_not_a_number():
    """No gains and no losses is undefined, not zero or fifty."""
    df = _close_frame([100.0] * 40)
    ts._append_rsi_manual(df)
    assert df["RSI_14"].dropna().empty


# ── Column resolution & empty contract ───────────────────────────────────────

def test_find_col_is_case_insensitive_and_returns_none_when_absent():
    df = pd.DataFrame({"MACD_12_26_9": [1.0], "Close": [2.0]})
    assert ts._find_col(df, ["MACD_12_26_9"]) == "MACD_12_26_9"
    assert ts._find_col(df, ["NOT_PRESENT"]) is None


def test_empty_response_carries_every_key_the_frontend_reads():
    out = ts._empty_response("AAPL", "1y")

    for key in ("prices", "bollinger", "ichimoku", "macd", "rsi", "stochRsi",
                "williamsR", "obv", "cmf", "atr", "fibLevels"):
        assert out[key] == []
    assert out["pivotPoints"] == {}
    assert out["ticker"] == "AAPL"
    assert out["summary"]["rsi"] is None
    assert out["summary"]["bbSqueeze"] is False
