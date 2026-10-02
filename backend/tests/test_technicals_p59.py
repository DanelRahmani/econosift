"""Phase 59 technicals: forward Ichimoku cloud, Chikou 26, daily pivot on completed session, Fibonacci direction."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services import technicals_service as ts


def _bars(index, high, low, close) -> pd.DataFrame:
    return pd.DataFrame({"Open": close, "High": high, "Low": low, "Close": close, "Volume": 1_000.0}, index=index)


def _frame(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    idx = pd.bdate_range(end="2026-09-30", periods=n)
    close = pd.Series(100.0 + np.cumsum(rng.standard_normal(n)), index=idx)
    return _bars(idx, close + 1.5, close - 1.5, close)


# ── P3-29: forward cloud ──

def test_forward_senkou_joins_history_without_gap_or_overlap():
    """span row j holds source bar n-25+j (25-bar displacement), last row NaN; bar 0 comes from the last bar."""
    dates = pd.bdate_range("2026-10-01", periods=26)
    a = [float(100 + j) for j in range(25)] + [np.nan]
    span = pd.DataFrame({"ISA_9": a, "ISB_26": [x * 2 for x in a]}, index=dates)

    fwd = ts._forward_senkou({"ISA_9": 90.0, "ISB_26": 180.0}, span)

    assert len(fwd) == 26 and list(fwd.index) == list(dates)
    assert fwd["ISA_9"].iloc[0] == 90.0        # the last bar's 25-displaced value, shifted one more bar
    assert fwd["ISA_9"].iloc[1] == 100.0       # span row 0 shifted one more bar
    assert fwd["ISA_9"].iloc[25] == 124.0      # span row 24
    assert fwd["ISB_26"].iloc[25] == 248.0
    assert fwd.notna().all().all()


def test_forward_senkou_without_a_span_frame_is_empty():
    assert ts._forward_senkou({"ISA_9": 1.0}, None).empty


def test_ichimoku_emits_26_forward_senkou_bars(monkeypatch):
    pytest.importorskip("pandas_ta")
    frame = _frame()
    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: frame)

    out = ts.get_technicals.__wrapped__("AAPL", "1y")
    last_price = out["prices"][-1]["date"]
    fut = [r for r in out["ichimoku"] if r["date"] > last_price]

    assert len(fut) == 26
    assert all(r["senkouA"] is not None and r["senkouB"] is not None for r in fut)
    assert all(r["tenkan"] is None and r["kijun"] is None and r["chikou"] is None for r in fut)
    assert fut[0]["date"] == str((frame.index[-1] + pd.offsets.BDay(1)).date())

    h, l = frame["High"], frame["Low"]
    mid = lambda n, i: (h.iloc[i - n + 1:i + 1].max() + l.iloc[i - n + 1:i + 1].min()) / 2  # noqa: E731
    n = len(frame)
    for k in (0, 1, 12, 25):                  # future bar k is drawn from source bar n + k - 26
        i = n + k - 26
        assert fut[k]["senkouA"] == pytest.approx((mid(9, i) + mid(26, i)) / 2, rel=1e-9)
        assert fut[k]["senkouB"] == pytest.approx(mid(52, i), rel=1e-9)
    # seam: the last historical bar is source n-27, the first forward bar is source n-26
    seam = next(r for r in out["ichimoku"] if r["date"] == last_price)
    i = n - 27
    assert seam["senkouA"] == pytest.approx((mid(9, i) + mid(26, i)) / 2, rel=1e-9)


# ── P3-30: Chikou ──

def test_chikou_at_t_is_the_close_26_bars_later(monkeypatch):
    pytest.importorskip("pandas_ta")
    frame = _frame()
    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: frame)

    out = ts.get_technicals.__wrapped__("AAPL", "1y")
    rows = {r["date"]: r for r in out["ichimoku"]}
    n = len(frame)
    for i in (n - 27, n - 60, n - 100):
        assert rows[str(frame.index[i].date())]["chikou"] == pytest.approx(frame["Close"].iloc[i + 26], rel=1e-12)
    # the last 26 bars have no future close to show
    assert rows[str(frame.index[n - 26].date())]["chikou"] is None


# ── P3-32: daily pivot from the last completed session ──

def _week() -> pd.DataFrame:
    idx = pd.bdate_range("2026-09-21", "2026-09-25")           # Mon..Fri
    # last bar: H 120, L 80, C 100 -> P = 100; previous bar: H 90, L 60, C 75 -> P = 75
    high = np.array([50, 50, 50, 90, 120.0])
    low = np.array([40, 40, 40, 60, 80.0])
    close = np.array([45, 45, 45, 75, 100.0])
    return _bars(idx, high, low, close)


@pytest.mark.parametrize("now, expected_p", [
    ("2026-09-25 17:00", 100.0),   # Fri after the close: the last bar is complete
    ("2026-09-25 11:00", 75.0),    # Fri mid-session: the last bar is still forming
    ("2026-09-25 16:00", 100.0),   # exactly the close
    ("2026-09-26 11:00", 100.0),   # Saturday: market closed
    ("2026-09-28 08:00", 100.0),   # Monday pre-market: Friday is the last completed session
])
def test_daily_pivot_uses_the_last_completed_session(now, expected_p):
    out = ts._pivot_points(_week(), pd.Timestamp(now).normalize(), now=pd.Timestamp(now, tz="America/New_York"))
    assert out["daily"]["p"] == pytest.approx(expected_p)


def test_daily_pivot_converts_other_timezones_to_new_york():
    # 2026-09-25 20:30 UTC = 16:30 New York (EDT) -> complete
    out = ts._pivot_points(_week(), pd.Timestamp("2026-09-25"), now=pd.Timestamp("2026-09-25 20:30", tz="UTC"))
    assert out["daily"]["p"] == pytest.approx(100.0)
    # 2026-09-25 19:30 UTC = 15:30 New York -> still forming
    out = ts._pivot_points(_week(), pd.Timestamp("2026-09-25"), now=pd.Timestamp("2026-09-25 19:30", tz="UTC"))
    assert out["daily"]["p"] == pytest.approx(75.0)


# ── P3-18: Fibonacci from intraday highs/lows, direction-aware ──

def _swing_frame(high_first: bool) -> pd.DataFrame:
    idx = pd.bdate_range("2026-01-01", periods=10)
    high = np.full(10, 150.0)
    low = np.full(10, 140.0)
    close = np.full(10, 145.0)
    first, last = 1, 8
    hi_i, lo_i = (first, last) if high_first else (last, first)
    high[hi_i] = 200.0      # intraday swing high (close stays 145)
    low[lo_i] = 100.0       # intraday swing low
    return _bars(idx, high, low, close)


def test_fib_swing_uses_intraday_highs_and_lows():
    sw = ts._fib_swing(_swing_frame(high_first=True))
    assert sw["high"] == 200.0 and sw["low"] == 100.0       # closes would give 145 / 145


def test_fib_downswing_when_the_low_comes_after_the_high():
    sw = ts._fib_swing(_swing_frame(high_first=True))
    assert sw["direction"] == "downswing"
    lv = {x["label"]: x["price"] for x in ts._fib_levels(sw["high"], sw["low"], sw["direction"])}
    # retraces up from the low: low + 100 * ratio
    assert lv["0%"] == 100.0 and lv["38.2%"] == pytest.approx(138.2) and lv["100%"] == 200.0


def test_fib_upswing_when_the_high_comes_after_the_low():
    sw = ts._fib_swing(_swing_frame(high_first=False))
    assert sw["direction"] == "upswing"
    lv = {x["label"]: x["price"] for x in ts._fib_levels(sw["high"], sw["low"], sw["direction"])}
    # retraces down from the high: high - 100 * ratio
    assert lv["0%"] == 200.0 and lv["38.2%"] == pytest.approx(161.8) and lv["100%"] == 100.0


def test_get_technicals_exposes_the_fib_direction(monkeypatch):
    frame = _frame()
    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: frame)
    out = ts.get_technicals.__wrapped__("AAPL", "1y")
    tail = frame.tail(126)
    expect = "downswing" if tail["Low"].values.argmin() > tail["High"].values.argmax() else "upswing"
    assert out["fibDirection"] == expect
    assert out["fibSwing"]["high"] == pytest.approx(tail["High"].max())
    assert out["fibSwing"]["low"] == pytest.approx(tail["Low"].min())


# â”€â”€ P3-19: one 52-week range definition (intraday, like Yahoo's fiftyTwoWeekHigh/Low) â”€â”€

def test_week52_range_uses_intraday_highs_and_lows(monkeypatch):
    """The fixture's High/Low are close Â± 1.5, so the intraday 52-week high is the
    highest close of the last 252 bars + 1.5 (and the low that close âˆ’ 1.5)."""
    frame = _frame()
    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: frame)
    s = ts.get_technicals.__wrapped__("AAPL", "1y")["summary"]
    last = frame.tail(252)
    assert s["week52High"] == pytest.approx(last["Close"].max() + 1.5)
    assert s["week52Low"] == pytest.approx(last["Close"].min() - 1.5)
