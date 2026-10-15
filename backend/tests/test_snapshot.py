"""Phase 66: the 15-minute yf.screen snapshot and the daily bar it writes."""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from backend import fetcher, snapshot, store

ET = ZoneInfo("America/New_York")
TS = int(datetime(2026, 10, 14, 16, 0, tzinfo=ET).timestamp())


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    with store.connect() as conn:
        for t in ("fetch_queue", "security", "price_daily", "quote_latest", "quote_intraday"):
            conn.execute(f"DELETE FROM {t}")
        conn.executemany("INSERT INTO security (symbol) VALUES (?)", [("AAA",), ("BBB",), ("CCC",)])
    yield


def _quote(sym, price, prev=None):
    return {"symbol": sym, "regularMarketPrice": price, "regularMarketOpen": price - 1,
            "regularMarketDayHigh": price + 1, "regularMarketDayLow": price - 2,
            "regularMarketVolume": 1000, "regularMarketPreviousClose": prev,
            "regularMarketTime": TS, "sharesOutstanding": 5e6, "trailingPE": None,
            "marketState": "POST"}


def _fake_screen(pages):
    calls = []

    def screen(query, offset, size, sortField, sortAsc):
        calls.append(offset)
        return {"quotes": pages[offset // size], "total": sum(map(len, pages)) * 0 + 1000}
    return screen, calls


def test_screen_pages_until_the_universe_is_covered():
    fake, calls = _fake_screen([[_quote("AAA", 10), _quote("ZZZ", 1)], [_quote("BBB", 20)],
                                [_quote("CCC", 30)], [_quote("DDD", 40)]])
    with patch("yfinance.screen", side_effect=fake):
        got = snapshot.screen({"AAA", "BBB", "CCC"})
    assert set(got) == {"AAA", "BBB", "CCC"}  # non-members dropped
    assert calls == [0, 250, 500]  # stopped once covered


def test_close_snapshot_writes_quotes_intraday_bar_and_fills_missing_members():
    fake, _ = _fake_screen([[_quote("AAA", 10), _quote("BBB", 20)], []])
    filled = [dict({c: None for c in snapshot.FIELDS}, symbol="CCC", price=30.0, open=29.0,
                   high=31.0, low=28.0, volume=500.0, ts=TS, market_state=None, source="yahoo_chart")]
    with patch("yfinance.screen", side_effect=fake), \
         patch.object(snapshot, "download_quotes", return_value=filled) as dl:
        assert snapshot.run("close") == 3
    dl.assert_called_once_with(["CCC"])
    with store.connect() as conn:
        assert conn.execute("SELECT symbol, price, source FROM quote_latest ORDER BY symbol").fetchall() == [
            ("AAA", 10.0, "yahoo_screen"), ("BBB", 20.0, "yahoo_screen"), ("CCC", 30.0, "yahoo_chart")]
        assert conn.execute("SELECT COUNT(*) FROM quote_intraday").fetchone()[0] == 3
        assert conn.execute("SELECT shares_outstanding FROM security WHERE symbol='AAA'").fetchone()[0] == 5e6
    bars = store.prices(["AAA", "CCC"], field="close")
    assert bars.index.tolist() == [pd.Timestamp("2026-10-14")]
    assert bars.iloc[0].tolist() == [10.0, 30.0]


def test_intraday_snapshot_does_not_write_a_daily_bar():
    fake, _ = _fake_screen([[_quote("AAA", 10), _quote("BBB", 20), _quote("CCC", 30)]])
    with patch("yfinance.screen", side_effect=fake):
        snapshot.run("intraday")
    assert store.prices(["AAA"]).empty


def test_a_failed_screen_falls_back_to_chart_downloads_for_everyone():
    with patch("yfinance.screen", side_effect=ValueError("schema changed")), \
         patch.object(snapshot, "download_quotes", return_value=[]) as dl, \
         pytest.raises(RuntimeError):
        snapshot.run("intraday")
    dl.assert_called_once_with(["AAA", "BBB", "CCC"])
    with store.connect() as conn:  # nothing stored from an empty result
        assert conn.execute("SELECT COUNT(*) FROM quote_latest").fetchone()[0] == 0


def test_a_previous_close_that_disagrees_with_history_queues_a_refetch():
    store.upsert("price_daily", [dict(symbol="AAA", date="2026-10-13", open=40, high=40, low=40,
                                      close=40.0, adj_close=40.0, volume=1)], ("symbol", "date"))
    store.upsert("price_daily", [dict(symbol="BBB", date="2026-10-13", open=20, high=20, low=20,
                                      close=20.0, adj_close=20.0, volume=1)], ("symbol", "date"))
    # AAA split 4:1 overnight (prev close 10 vs stored 40); BBB matches.
    fake, _ = _fake_screen([[_quote("AAA", 10, prev=10.0), _quote("BBB", 20, prev=20.1),
                             _quote("CCC", 30)]])
    with patch("yfinance.screen", side_effect=fake):
        snapshot.run("close")
    with store.connect() as conn:
        assert conn.execute("SELECT kind, key, priority FROM fetch_queue").fetchall() == [
            ("history", "AAA", fetcher.PRIORITY_REFETCH)]
    # The split symbol's bar waits for the re-fetched history.
    assert store.prices(["AAA"], start="2026-10-14").empty


@pytest.mark.parametrize("when, open_", [
    (datetime(2026, 10, 14, 9, 29, tzinfo=ET), False),
    (datetime(2026, 10, 14, 9, 30, tzinfo=ET), True),
    (datetime(2026, 10, 14, 16, 0, tzinfo=ET), True),
    (datetime(2026, 10, 14, 16, 15, tzinfo=ET), False),
    (datetime(2026, 10, 17, 12, 0, tzinfo=ET), False),  # Saturday
])
def test_market_hours_gate_the_intraday_snapshot(when, open_):
    assert snapshot.in_market_hours(when) is open_
    fetcher.queue_snapshot(when)
    with store.connect() as conn:
        assert bool(conn.execute("SELECT COUNT(*) FROM fetch_queue").fetchone()[0]) is open_


def test_download_quotes_reduces_15m_bars_per_symbol():
    idx = pd.DatetimeIndex(["2026-10-14 09:30", "2026-10-14 09:45"], tz=ET)
    cols = pd.MultiIndex.from_product([["AAA", "BBB"], ["Open", "High", "Low", "Close", "Volume"]])
    df = pd.DataFrame([[10, 11, 9, 10.5, 100, None, None, None, None, None],
                       [10.5, 12, 10, 11.5, 200, None, None, None, None, None]], index=idx, columns=cols)
    with patch("yfinance.download", return_value=df):
        rows = snapshot.download_quotes(["AAA", "BBB"])
    assert len(rows) == 1  # BBB had no bars
    r = rows[0]
    assert (r["symbol"], r["price"], r["open"], r["high"], r["low"], r["volume"]) == (
        "AAA", 11.5, 10.0, 12.0, 9.0, 300.0)
    assert r["ts"] == int(idx[-1].timestamp()) and r["prev_close"] is None
