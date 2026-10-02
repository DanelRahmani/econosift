"""Phase 54 (M-19, P3-16, P3-17): pivot-point period selection, Bollinger std, Ichimoku displacement.

All offline. Pivot tests hand-compute the expected levels from a small OHLC fixture.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services import technicals_service as ts


def _bars(index, high, low, close) -> pd.DataFrame:
    return pd.DataFrame({"High": high, "Low": low, "Close": close}, index=index)


# ── M-19: pivots come from the last COMPLETED period ─────────────────────────

def _three_weeks(last_bar: str) -> pd.DataFrame:
    """Three Mon-Fri weeks (2026-09-07, -14, -21); Mon-Thu bars sit inside the week's Friday bar.

    week 1: H 110 / L  90 / C 100
    week 2: H 120 / L 100 / C 110
    week 3: H 130 / L 105 / C 125
    """
    weeks = [(110.0, 90.0, 100.0), (120.0, 100.0, 110.0), (130.0, 105.0, 125.0)]
    idx = pd.bdate_range("2026-09-07", "2026-09-25")
    h, l, c = [], [], []
    for i, d in enumerate(idx):
        wh, wl, wc = weeks[i // 5]
        is_fri = d.weekday() == 4
        h.append(wh if is_fri else wh - 5)
        l.append(wl if is_fri else wl + 5)
        c.append(wc)
    return _bars(idx, h, l, c).loc[:last_bar]


def test_weekly_pivot_uses_the_just_completed_week_when_the_last_bar_is_friday():
    df = _three_weeks("2026-09-25")
    out = ts._pivot_points(df, today=pd.Timestamp("2026-09-25"))["weekly"]
    # week 3 is complete: P = (130 + 105 + 125) / 3 = 120 ; R1 = 2P - L = 135 ; S1 = 2P - H = 110
    assert out["p"] == pytest.approx(120.0)
    assert out["r1"] == pytest.approx(135.0)
    assert out["s1"] == pytest.approx(110.0)


def test_weekly_pivot_uses_the_previous_week_when_the_last_bar_is_mid_week():
    df = _three_weeks("2026-09-23")   # Wednesday of week 3: week 3 still open
    out = ts._pivot_points(df, today=pd.Timestamp("2026-09-23"))["weekly"]
    # week 2: P = (120 + 100 + 110) / 3 = 110
    assert out["p"] == pytest.approx(110.0)


def test_weekly_pivot_treats_a_holiday_shortened_week_as_complete_once_the_week_has_passed():
    """Last bar Thursday (Friday was a holiday): complete only because the reference date is past the week."""
    df = _three_weeks("2026-09-24")
    mid_week = ts._pivot_points(df, today=pd.Timestamp("2026-09-24"))["weekly"]["p"]
    after = ts._pivot_points(df, today=pd.Timestamp("2026-09-26"))["weekly"]["p"]
    assert mid_week == pytest.approx(110.0)   # week 3 may still get a Friday bar -> use week 2
    # week 3 through Thursday: H max = 125 (Thu bar = 130 - 5), L min = 110 (Mon bar = 105 + 5), C = 125
    # P = (125 + 110 + 125) / 3 = 120
    assert after == pytest.approx(120.0)


def _two_months(last_bar: str) -> pd.DataFrame:
    """Business days 2026-08-03 .. 2026-09-30.  Aug: H110/L90/C100 (P=100). Sep: H130/L100/C120."""
    idx = pd.bdate_range("2026-08-03", "2026-09-30")
    aug = idx.month == 8
    df = _bars(idx, np.where(aug, 110.0, 130.0), np.where(aug, 90.0, 100.0), np.where(aug, 100.0, 120.0))
    return df.loc[:last_bar]


def test_monthly_pivot_uses_the_just_completed_month_when_the_last_bar_is_the_last_session():
    df = _two_months("2026-09-30")    # Wednesday, last weekday of September
    out = ts._pivot_points(df, today=pd.Timestamp("2026-09-30"))["monthly"]
    # September complete: P = (130 + 100 + 120) / 3 = 116.6667 ; the stale (August) value would be 100
    assert out["p"] == pytest.approx(116.6667, abs=1e-4)
    assert out["r1"] == pytest.approx(133.3333, abs=1e-4)   # 2P - L = 233.3333 - 100
    assert out["s1"] == pytest.approx(103.3333, abs=1e-4)   # 2P - H = 233.3333 - 130


def test_monthly_pivot_uses_the_previous_month_when_the_last_bar_is_mid_month():
    df = _two_months("2026-09-29")
    out = ts._pivot_points(df, today=pd.Timestamp("2026-09-29"))["monthly"]
    # August: P = (110 + 90 + 100) / 3 = 100
    assert out["p"] == pytest.approx(100.0)


def test_monthly_pivot_is_complete_when_the_reference_date_is_past_month_end():
    df = _two_months("2026-09-29")    # feed lags by a day, but it is now October
    out = ts._pivot_points(df, today=pd.Timestamp("2026-10-02"))["monthly"]
    assert out["p"] == pytest.approx(116.6667, abs=1e-4)


def test_monthly_pivot_when_month_ends_on_a_weekend_completes_on_the_last_friday():
    """Aug 31 2025 is a Sunday: the last Friday bar (Aug 29) completes August."""
    idx = pd.bdate_range("2025-07-01", "2025-08-29")
    jul = idx.month == 7
    df = _bars(idx, np.where(jul, 110.0, 130.0), np.where(jul, 90.0, 100.0), np.where(jul, 100.0, 120.0))
    out = ts._pivot_points(df, today=pd.Timestamp("2025-08-29"))["monthly"]
    assert out["p"] == pytest.approx(116.6667, abs=1e-4)


def test_get_technicals_pivots_follow_the_last_completed_period(monkeypatch):
    """End to end: the fixture ends Wed 2026-09-30, the last session of September."""
    idx = pd.bdate_range(end="2026-09-30", periods=600)
    close = pd.Series(100.0 + np.arange(600) * 0.1, index=idx)
    frame = pd.DataFrame(
        {"Open": close, "High": close + 1.0, "Low": close - 1.0, "Close": close, "Volume": 1_000.0}, index=idx)
    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: frame)
    monkeypatch.setattr(ts, "_today", lambda: pd.Timestamp("2026-09-30"))

    pivots = ts.get_technicals.__wrapped__("AAPL", "1y")["pivotPoints"]

    # September bars are rows 578..599: H = 159.9 + 1 = 160.9, L = 157.8 - 1 = 156.8, C = 159.9
    # P = (160.9 + 156.8 + 159.9) / 3 = 159.2
    assert pivots["monthly"]["p"] == pytest.approx(159.2, abs=1e-3)
    # Last bar is Wed, so the week of 09-28 is open: week 09-21..09-25 = rows 592..596
    # H = 159.6 + 1 = 160.6, L = 159.2 - 1 = 158.2, C = 159.6 -> P = 478.4 / 3
    assert pivots["weekly"]["p"] == pytest.approx(478.4 / 3, abs=1e-3)


# ── P3-16 / P3-17: indicator conventions (need pandas-ta, which the Docker image ships) ──

def _trending_frame(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.bdate_range(end="2026-09-30", periods=n)
    close = pd.Series(100.0 + np.cumsum(rng.standard_normal(n)), index=idx)
    return pd.DataFrame(
        {"Open": close, "High": close + 1.5, "Low": close - 1.5, "Close": close, "Volume": 1_000.0}, index=idx)


def test_bollinger_bands_use_the_population_standard_deviation(monkeypatch):
    pytest.importorskip("pandas_ta")
    frame = _trending_frame()
    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: frame)

    out = ts.get_technicals.__wrapped__("AAPL", "1y")
    last = out["bollinger"][-1]

    w = frame["Close"].iloc[-20:]
    # upper = mean + 2 * sqrt(sum((x - mean)^2) / 20)   (divisor N, not N - 1)
    expected = w.mean() + 2 * np.sqrt(((w - w.mean()) ** 2).sum() / 20)
    assert last["upper"] == pytest.approx(expected, rel=1e-9)
    assert last["mid"] == pytest.approx(w.mean(), rel=1e-9)


def test_senkou_spans_are_displaced_twenty_six_periods(monkeypatch):
    pytest.importorskip("pandas_ta")
    frame = _trending_frame()
    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: frame)

    out = ts.get_technicals.__wrapped__("AAPL", "2y")
    rows = {r["date"]: r for r in out["ichimoku"]}
    dates = [p["date"] for p in out["prices"]]

    h, l = frame["High"], frame["Low"]
    mid = lambda n, i: (h.iloc[i - n + 1:i + 1].max() + l.iloc[i - n + 1:i + 1].min()) / 2  # noqa: E731
    i = len(frame) - 60                       # bar the cloud is computed from
    senkou_a = (mid(9, i) + mid(26, i)) / 2   # (Tenkan + Kijun) / 2
    senkou_b = mid(52, i)
    target = str(frame.index[i + 26].date())  # plotted 26 bars later

    assert target in dates
    assert rows[target]["senkouA"] == pytest.approx(senkou_a, rel=1e-9)
    assert rows[target]["senkouB"] == pytest.approx(senkou_b, rel=1e-9)


def test_displace_senkou_moves_both_spans_one_extra_period():
    """pandas-ta shifts the spans by kijun - 1 = 25; the standard displacement is 26."""
    idx = pd.bdate_range("2026-01-01", periods=40)
    raw = pd.Series(np.arange(40, dtype=float), index=idx)       # value i observed on bar i
    df = pd.DataFrame({"ISA_9": raw.shift(25), "ISB_26": raw.shift(25), "ITS_9": raw})

    ts._displace_senkou(df)

    assert df["ISA_9"].iloc[30] == pytest.approx(4.0)    # bar 30 shows the span computed on bar 30 - 26
    assert df["ISB_26"].iloc[39] == pytest.approx(13.0)
    assert df["ITS_9"].iloc[30] == 30.0                  # Tenkan untouched
