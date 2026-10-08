"""EDGAR Form 4 parsing against the edgartools 5.x object shape.

The fake filing mirrors a real one: AAPL, Jennifer Newstead, filed
2026-09-24 — an open-market sale (code S) of 2,399 shares at $340.06 on
2026-09-22. edgartools 5 exposes trades as ``Form4.market_trades`` (a
DataFrame, or None when the filing has no open-market trades); the old
``non_derivative_table.iterrows()`` path no longer exists.
"""
from __future__ import annotations

import sys
import types
from datetime import date, timedelta

import pandas as pd
import pytest

from backend.services import edgar_service


class _Form4:
    def __init__(self, name, position, trades):
        self.insider_name = name
        self.position = position
        self.market_trades = trades


class _Filing:
    def __init__(self, filed: date, form4):
        self.filing_date = filed
        self._form4 = form4

    def obj(self):
        return self._form4


def _trades(rows):
    return pd.DataFrame(rows, columns=["Security", "Date", "Shares", "Remaining", "Price",
                                       "AcquiredDisposed", "DirectIndirect", "Code", "TransactionType"])


@pytest.fixture
def fake_edgar(monkeypatch):
    today = date.today()
    filings = [
        # Newest first, as EDGAR returns them. No open-market trades: None.
        _Filing(today - timedelta(days=2), _Form4("Timothy D Cook", "CEO", None)),
        _Filing(today - timedelta(days=7), _Form4(
            "Jennifer Newstead", "SVP, GC and Government Affairs",
            _trades([["Common Stock", "2026-09-22", 2399, 44391, 340.06, "D", "D", "S", "Sale"]]))),
        _Filing(today - timedelta(days=30), _Form4(
            "Arthur Levinson", "Director",
            _trades([["Common Stock", "2026-08-30", 1000, 5000, 220.5, "A", "D", "P", "Purchase"],
                     ["Common Stock", "2026-08-30", 300, 4700, None, "D", "D", "F", "Tax Withholding"]]))),
        _Filing(today - timedelta(days=120), _Form4(
            "Old Filer", "Director",
            _trades([["Common Stock", "2026-05-01", 10, 0, 100.0, "D", "D", "S", "Sale"]]))),
    ]

    class Company:
        def __init__(self, ticker):
            self.ticker = ticker

        def get_filings(self, form):
            assert form == "4"
            return filings

    fake = types.ModuleType("edgar")
    fake.Company = Company
    fake.set_identity = lambda identity: None
    monkeypatch.setitem(sys.modules, "edgar", fake)
    monkeypatch.setattr("backend.config.EDGAR_IDENTITY", "Test Person test@example.com")


def test_form4_reads_open_market_trades(fake_edgar):
    out = edgar_service._fetch_form4_sync("AAPL")

    assert out["error"] is None
    assert out["transactions"] == [
        {"insiderName": "Jennifer Newstead", "title": "SVP, GC and Government Affairs",
         "transactionType": "Sell", "shares": 2399.0, "pricePerShare": 340.06,
         "totalValue": round(2399 * 340.06, 2), "date": "2026-09-22"},
        {"insiderName": "Arthur Levinson", "title": "Director",
         "transactionType": "Buy", "shares": 1000.0, "pricePerShare": 220.5,
         "totalValue": 220500.0, "date": "2026-08-30"},
    ]
    assert out["truncated"] is False


def test_form4_cap_marks_truncated(fake_edgar):
    out = edgar_service._fetch_form4_sync("AAPL", max_transactions=1)
    assert len(out["transactions"]) == 1
    assert out["truncated"] is True


def test_insider_aggregate_does_not_block_the_event_loop(monkeypatch):
    """The aggregate fetches Form 4s for ~500 tickers synchronously; run on the
    event loop it froze every other request until it finished."""
    import asyncio
    import time as _time

    import httpx
    from backend.main import app
    from backend.services import insider_aggregator

    def slow_aggregate():
        _time.sleep(1.0)
        return {"asOf": "2026-10-01"}

    monkeypatch.setattr(insider_aggregator, "get_insider_aggregate", slow_aggregate)

    async def main():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            done = {}

            async def call(path):
                await client.get(path)
                done[path] = _time.perf_counter()

            t0 = _time.perf_counter()
            agg = asyncio.create_task(call("/api/insider/aggregate"))
            await asyncio.sleep(0.05)
            await call("/api/health")
            await agg
            return done["/api/health"] - t0, done["/api/insider/aggregate"] - t0

    health_s, agg_s = asyncio.run(main())
    # Relative, not absolute (P3-38): a blocked loop would answer /health only after the 1 s
    # aggregate, i.e. health_s >= agg_s. A busy container made the old "< 0.5 s" bound flaky (0.50-0.67 s).
    assert agg_s > 0.9
    assert health_s < agg_s - 0.3
