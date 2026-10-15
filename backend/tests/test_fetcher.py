"""Phase 66: the fetcher thread's queue, backfill and universe tasks."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from backend import fetcher, store

TABLES = ("fetch_queue", "security", "price_daily", "corporate_action", "index_membership",
          "source_health")


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    with store.connect() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")
    yield


def _queue():
    with store.connect() as conn:
        return conn.execute("SELECT kind, key, attempts FROM fetch_queue ORDER BY priority, id").fetchall()


def _history_frame():
    idx = pd.DatetimeIndex(["2020-08-28", "2020-08-31"], tz="America/New_York")
    return pd.DataFrame({
        "Open": [500.0, 127.0], "High": [510.0, 131.0], "Low": [495.0, 126.0],
        "Close": [499.2, 129.0], "Adj Close": [120.0, 126.5], "Volume": [4.6e7, 2.2e8],
        "Dividends": [0.0, 0.0], "Stock Splits": [0.0, 4.0],
    }, index=idx)


def test_membership_intervals_walk_the_change_log_back_from_today():
    changes = [  # newest first
        {"date": date(2025, 6, 1), "added": "NEW", "removed": "OLD"},
        {"date": date(2020, 1, 1), "added": "OLD", "removed": "GONE"},
    ]
    got = set(fetcher.membership_intervals(["NEW", "KEEP"], changes))
    assert got == {
        ("NEW", "2025-06-01", None),
        ("OLD", "2020-01-01", "2025-06-01"),
        ("GONE", "", "2020-01-01"),
        ("KEEP", "", None),
    }


def test_history_stores_bars_actions_and_marks_the_symbol_done():
    t = MagicMock()
    t.history.return_value = _history_frame()
    with patch("yfinance.Ticker", return_value=t):
        assert fetcher.run_history("ZZF") == 2
    t.history.assert_called_once_with(period="max", auto_adjust=False, actions=True)
    df = store.prices(["ZZF"], field="close")
    assert df["ZZF"].tolist() == [499.2, 129.0]
    assert store.prices(["ZZF"])["ZZF"].tolist() == [120.0, 126.5]  # adj_close is the default
    with store.connect() as conn:
        assert conn.execute("SELECT date, type, value FROM corporate_action").fetchall() == [
            ("2020-08-31", "split", 4.0)]
        assert conn.execute("SELECT history_at FROM security WHERE symbol='ZZF'").fetchone()[0]


def test_empty_history_stores_nothing_and_fails():
    t = MagicMock()
    t.history.return_value = pd.DataFrame()
    with patch("yfinance.Ticker", return_value=t), pytest.raises(RuntimeError):
        fetcher.run_history("ZZF")
    assert store.prices(["ZZF"]).empty


def test_enqueue_is_idempotent_and_failed_tasks_stop_after_max_attempts():
    fetcher.enqueue("history", "ZZF")
    fetcher.enqueue("history", "ZZF")
    assert _queue() == [("history", "ZZF", 0)]
    with patch.dict(fetcher.HANDLERS, {"history": MagicMock(side_effect=ValueError("boom"))}):
        for _ in range(fetcher.MAX_ATTEMPTS):
            assert fetcher.run_one()
        assert not fetcher.run_one()  # failed: no longer picked
    assert _queue() == [("history", "ZZF", fetcher.MAX_ATTEMPTS)]
    st = fetcher.status()
    assert st["queue"] == {"pending": 0, "failed": 1,
                           "errors": [{"kind": "history", "key": "ZZF", "error": "ValueError: boom"}]}
    fetcher.enqueue("history", "ZZF")  # re-queueing gives it fresh attempts
    assert _queue() == [("history", "ZZF", 0)]


def test_a_finished_task_leaves_the_queue_and_runs_in_the_bulk_lane():
    from backend import rate_limit
    seen = []
    fetcher.enqueue("history", "ZZF")
    with patch.dict(fetcher.HANDLERS, {"history": lambda key: seen.append(rate_limit.is_bulk()) or 1}):
        assert fetcher.run_one()
    assert seen == [True] and _queue() == []


def test_rate_limit_pauses_without_spending_attempts():
    fetcher.enqueue("history", "ZZF")
    with patch.dict(fetcher.HANDLERS, {"history": MagicMock(side_effect=YFRateLimitError())}), \
         patch.object(fetcher._stop, "wait") as wait:
        fetcher.run_one()
    wait.assert_called_once()
    assert _queue() == [("history", "ZZF", 0)]


def test_universe_stores_rosters_and_queues_missing_history():
    members = {
        "sp500": [{"symbol": "AAA", "name": "A Inc", "sector": "Tech", "industry": "Chips"},
                  {"symbol": "BBB", "name": "B Inc", "sector": "Energy", "industry": None}],
        "ndx": [{"symbol": "AAA", "name": "A Inc", "sector": None, "industry": None}],
        "dow": [{"symbol": "CCC", "name": "C Inc", "sector": "Health", "industry": None}],
    }
    with store.connect() as conn:  # BBB already has its history
        conn.execute("INSERT INTO security (symbol, history_at) VALUES ('BBB', '2026-10-01T00:00:00Z')")
    with patch("backend.services.constituents.get_constituents", side_effect=lambda i: members[i]), \
         patch("backend.services.constituents.get_membership_changes", return_value=[]):
        assert fetcher.run_universe("all") == 3
    with store.connect() as conn:
        assert conn.execute("SELECT symbol, sector FROM security ORDER BY symbol").fetchall() == [
            ("AAA", "Tech"), ("BBB", "Energy"), ("CCC", "Health")]
        assert conn.execute("SELECT COUNT(*) FROM index_membership").fetchone()[0] == 4
    assert [k for _, k, _ in _queue()] == ["AAA", "CCC"]
    assert fetcher.status()["backfill"] == {"total": 3, "done": 1}
    assert fetcher._last_success("constituents") is not None


def test_universe_with_a_missing_roster_fails_instead_of_storing_a_partial_one():
    with patch("backend.services.constituents.get_constituents", return_value=[]), \
         pytest.raises(RuntimeError):
        fetcher.run_universe("all")
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM security").fetchone()[0] == 0


def test_history_rotation_queues_one_fifth_per_weekday():
    with store.connect() as conn:
        conn.executemany("INSERT INTO security (symbol, history_at) VALUES (?, 'x')",
                         [(f"S{i:02d}",) for i in range(10)])
    fetcher.queue_history_rotation(datetime(2026, 10, 13, tzinfo=timezone.utc))  # Tuesday
    assert [k for _, k, _ in _queue()] == ["S01", "S06"]
    with store.connect() as conn:
        conn.execute("DELETE FROM fetch_queue")
    fetcher.queue_history_rotation(datetime(2026, 10, 17, tzinfo=timezone.utc))  # Saturday
    assert _queue() == []


def test_source_health_counts_todays_yahoo_requests():
    from backend import rate_limit
    fetcher._seen_requests.clear()
    base = rate_limit.status()
    fake = {name: {**st, "requests": st["requests"] + 3} for name, st in base.items()}
    with patch.object(rate_limit, "status", return_value=base):
        fetcher.record_source_health()
    with patch.object(rate_limit, "status", return_value=fake):
        fetcher.record_source_health()
    with store.connect() as conn:
        rows = dict(conn.execute("SELECT source, requests_today FROM source_health").fetchall())
    for name, st in base.items():
        assert rows[name] == st["requests"] + 3


def test_admin_health_reports_store_progress(client):
    fetcher.enqueue("history", "ZZF")
    body = client.get("/api/admin/health").json()
    assert body["store"]["backfill"] == {"total": 0, "done": 0}
    assert body["store"]["queue"]["pending"] == 1
