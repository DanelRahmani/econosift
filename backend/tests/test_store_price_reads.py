"""Store-backed price readers in yfinance_service (Phase 67)."""
import contextvars
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from backend import cache, fetcher, store
from backend.services import yfinance_service as ys

SYMS = ("ZZPA", "ZZPB", "ZZPC")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    def boom(*a, **k):
        pytest.fail("network call")
    monkeypatch.setattr("yfinance.download", boom)
    monkeypatch.setattr("yfinance.Ticker", boom)

    def wipe():
        with store.connect() as conn:
            for s in SYMS:
                conn.execute("DELETE FROM price_daily WHERE symbol = ?", (s,))
                conn.execute("DELETE FROM security WHERE symbol = ?", (s,))
                conn.execute("DELETE FROM fetch_queue WHERE key = ?", (s,))
    store.init_schema()
    wipe()
    yield
    wipe()


def _days(n=8):
    return pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=n)


def _stock(sym, days, close=100.0, adj=None, vol=1000.0, step=1.0):
    store.upsert("security", [{"symbol": sym, "history_at": "x"}], ["symbol"])
    rows = [{"symbol": sym, "date": d.date().isoformat(), "open": close + i * step - 1, "high": close + i * step + 2,
             "low": close + i * step - 2, "close": close + i * step,
             "adj_close": (adj if adj is not None else close) + i * step, "volume": vol + i}
            for i, d in enumerate(days)]
    store.upsert("price_daily", rows, ["symbol", "date"])


def _queued(sym):
    with store.connect() as conn:
        return conn.execute("SELECT kind, priority FROM fetch_queue WHERE key = ?", (sym,)).fetchall()


def test_period_start():
    today = pd.Timestamp.today().normalize()
    assert ys._period_start("1y") == ((today - pd.DateOffset(years=1)).date().isoformat(), None)
    assert ys._period_start("5d")[1] == 5
    assert ys._period_start("ytd") == (f"{today.year}-01-01", None)
    assert ys._period_start("max") == (None, None)
    with pytest.raises(ValueError):
        ys._period_start("bogus")


def test_close_frame_wide_ordered_and_limited():
    days = _days()
    _stock("ZZPA", days, close=100)
    _stock("ZZPB", days, close=50)
    df = ys.get_close_frame(("ZZPB", "ZZPA", "ZZPC"), "1mo")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.columns) == ["ZZPB", "ZZPA"]
    assert len(df) == 8
    assert df["ZZPA"].iloc[0] == 100 and df["ZZPB"].iloc[-1] == 57
    assert len(ys.get_close_frame(("ZZPA",), "5d")) == 5
    assert df.index[-1] == days[-1]


def test_missing_symbol_is_queued_and_marks_result_incomplete():
    _stock("ZZPA", _days())
    with cache._Computing() as c:
        df = ys.get_close_frame(("ZZPA", "ZZPC"), "1mo")
    assert list(df.columns) == ["ZZPA"]
    assert c.used_stale is True
    assert _queued("ZZPC") == [("history", fetcher.PRIORITY_ON_DEMAND)]
    assert _queued("ZZPA") == []
    with cache._Computing() as c:
        ys.get_close_frame(("ZZPA",), "1mo")
    assert c.used_stale is False


def test_volume_frame():
    _stock("ZZPA", _days(), vol=500)
    df = ys.get_volume_frame(("ZZPA",), "1mo")
    assert list(df["ZZPA"]) == [500 + i for i in range(8)]


def test_ohlc_frame_adjust_and_raw():
    _stock("ZZPA", _days(3), close=100, adj=50, step=0)
    out = ys.get_ohlc_frame(("ZZPA", "ZZPC"), "1mo")
    assert list(out) == ["ZZPA"]
    assert list(out["ZZPA"].columns) == ["Open", "High", "Low", "Close"]
    assert list(out["ZZPA"].iloc[0]) == [49.5, 51.0, 49.0, 50.0]
    raw = ys.get_ohlc_frame(("ZZPA",), "1mo", adjust=False)["ZZPA"]
    assert list(raw.columns) == ["Open", "High", "Low", "Close"]
    assert list(raw.iloc[0]) == [99.0, 102.0, 98.0, 100.0]


def test_daily_bars_adjusted_and_unknown_symbol():
    days = _days(4)
    _stock("ZZPA", days, close=100, adj=50, step=0, vol=700)
    bars = ys.get_daily_bars("ZZPA", days[1].date().isoformat())
    assert list(bars.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(bars) == 3
    assert list(bars.iloc[0]) == [49.5, 51.0, 49.0, 50.0, 701.0]
    empty = ys.get_daily_bars("ZZPC", days[0].date().isoformat())
    assert empty.empty and list(empty.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert _queued("ZZPC") == [("history", fetcher.PRIORITY_ON_DEMAND)]


def test_as_of_is_the_oldest_last_bar():
    _stock("ZZPA", [pd.Timestamp("2026-10-12"), pd.Timestamp("2026-10-13")])
    _stock("ZZPB", [pd.Timestamp("2026-10-13"), pd.Timestamp("2026-10-14")])

    def read():
        cache.start_fetch_log()
        ys.get_close_frame(("ZZPA", "ZZPB"), "max")
        return cache.oldest_fetch()
    got = contextvars.copy_context().run(read)
    assert got == datetime(2026, 10, 13, 16, 0, tzinfo=ZoneInfo("America/New_York")).timestamp()
