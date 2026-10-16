"""Phase 70 item 2: signal backtests read the store over the point-in-time universe, never Yahoo."""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend import fetcher, store
from backend.services import backtest_signals

TABLES = ("index_membership", "price_daily", "corporate_action", "fetch_queue")
DAYS = pd.bdate_range("2023-01-02", "2025-12-31")


@pytest.fixture(autouse=True)
def _store():
    def wipe():
        with store.connect() as conn:
            for t in TABLES:
                conn.execute(f"DELETE FROM {t}")
    store.init_schema()
    wipe()
    syms = [f"S{i:02d}" for i in range(10)]
    membership = [(s, "", None) for s in syms] + [("GONE", "", "2024-06-03"), ("LATE", "2025-03-03", None),
                                                  ("NOHIST", "", None)]
    store.upsert("index_membership", [dict(index_name="sp500", symbol=s, start=a, end=e) for s, a, e in membership],
                 ("index_name", "symbol", "start"))
    rng = np.random.default_rng(7)
    bars = []
    for sym in [*syms, "GONE", "LATE"]:
        px = 100 * np.cumprod(1 + rng.normal(0.0004, 0.015, len(DAYS)))
        for d, p in zip(DAYS, px):
            if sym == "GONE" and d > pd.Timestamp("2024-06-10"):
                break  # acquired: its history ends
            bars.append(dict(symbol=sym, date=d.date().isoformat(), open=p, high=p, low=p, close=p,
                             adj_close=p, volume=1e6))
    store.upsert("price_daily", bars, ("symbol", "date"))
    with store.connect() as conn:
        conn.execute("INSERT INTO fetch_queue (kind, key, priority, created_at, attempts) VALUES "
                     "('history', 'NOHIST', 6, 'x', ?)", (fetcher.MAX_ATTEMPTS,))
    yield
    wipe()


def test_the_universe_on_each_date_is_its_members_including_former_ones():
    with patch("backend.services.yfinance_service.get_close_frame", side_effect=AssertionError("no downloads")):
        _sig, prices, meta, universe_as_of = backtest_signals.build_signal("momentum_12_1", "sp500", "2y")
    assert {"GONE", "LATE"} <= set(prices.columns) and meta["dataSource"] == "store"
    assert "GONE" in universe_as_of(pd.Timestamp("2024-05-31")) and "LATE" not in universe_as_of(pd.Timestamp("2024-05-31"))
    assert "GONE" not in universe_as_of(pd.Timestamp("2025-06-30")) and "LATE" in universe_as_of(pd.Timestamp("2025-06-30"))
    assert meta["excluded"] == {"NOHIST": "Yahoo has no history for this symbol"}


def test_switching_point_in_time_off_keeps_only_todays_members():
    _sig, _px, meta, universe_as_of = backtest_signals.build_signal("momentum_12_1", "sp500", "2y", point_in_time=False)
    assert "GONE" not in universe_as_of(pd.Timestamp("2024-05-31"))
    assert "survivorship" in meta["universeSampling"]


def test_the_endpoint_keeps_its_shape_and_lists_the_gaps(client):
    with patch("backend.services.yfinance_service.get_close_frame", side_effect=AssertionError("no downloads")):
        r = client.post("/api/research/backtest", json={"signal": "momentum_12_1", "universe": "sp500",
                                                        "period": "2y", "nQuantiles": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True and set(body["quantiles"]) == {"1", "2"} and "longShort" in body
    assert body["settings"]["universePointInTime"] is True
    assert body["meta"]["excluded"] == [{"symbol": "NOHIST", "reason": "Yahoo has no history for this symbol"}]
    assert body["meta"]["tickersWithData"] == 12 and body["meta"]["snapshot"]["priceMaxDate"] == "2025-12-31"
