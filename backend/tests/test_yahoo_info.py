"""Phase 68 item 5: Yahoo-only fields fetched by the fetcher, read only from the store."""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend import fetcher, store, yahoo_info
from backend.services import analyst_service

TABLES = ("fetch_queue", "security", "fundamental", "yahoo_doc", "source_health")


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    with store.connect() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")
    yield
    with store.connect() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")


INFO = {"quoteType": "EQUITY", "currentPrice": 100.0, "sector": "Technology", "industry": "Chips",
        "forwardEps": 5.0, "targetMeanPrice": 120.0, "financialCurrency": "EUR", "currency": "USD"}


def _ticker(info=INFO):
    t = MagicMock()
    t.get_info.return_value = dict(info)
    cols = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]
    t.financials = pd.DataFrame({cols[0]: [10.0, 2.0], cols[1]: [9.0, None]}, index=["Total Revenue", "Net Income"])
    t.quarterly_financials = pd.DataFrame({pd.Timestamp("2026-06-30"): [3.0]}, index=["Total Revenue"])
    t.balance_sheet = pd.DataFrame({cols[0]: [50.0]}, index=["Total Assets"])
    t.quarterly_balance_sheet = pd.DataFrame({cols[0]: [50.0], pd.Timestamp("2026-06-30"): [55.0]},
                                             index=["Total Assets"])
    t.cashflow = pd.DataFrame()
    t.quarterly_cashflow = pd.DataFrame()
    return t


def _queue():
    with store.connect() as conn:
        return conn.execute("SELECT kind, key FROM fetch_queue ORDER BY priority, id").fetchall()


def test_fetch_stores_info_and_statements_for_a_company_sec_lacks():
    with patch("yfinance.Ticker", return_value=_ticker()):
        fetcher.run_yahoo_info("ASML")
    info, fetched_at = yahoo_info.stored(["ASML"])["ASML"]
    assert info["forwardEps"] == 5.0 and fetched_at
    with store.connect() as conn:
        rows = conn.execute("SELECT concept, period_end, value, unit, form, source FROM fundamental "
                            "ORDER BY concept, period_end").fetchall()
    assert ("Total Revenue|Q", "2026-06-30", 3.0, "EUR", "yahoo:financials", "yahoo") in rows
    assert ("Total Revenue", "2025-12-31", 10.0, "EUR", "yahoo:financials", "yahoo") in rows
    assert [r for r in rows if r[0] == "Total Assets"] == [  # an instant is stored once per date
        ("Total Assets", "2025-12-31", 50.0, "EUR", "yahoo:balance_sheet", "yahoo"),
        ("Total Assets", "2026-06-30", 55.0, "EUR", "yahoo:balance_sheet", "yahoo")]
    assert not [r for r in rows if r[0] == "Net Income" and r[1] == "2024-12-31"]  # NaN is not stored


def test_a_company_with_sec_facts_gets_no_yahoo_statements():
    store.upsert("security", [dict(symbol="AAPL", facts_at="2026-10-15T00:00:00Z")], ("symbol",))
    with patch("yfinance.Ticker", return_value=_ticker()):
        fetcher.run_yahoo_info("AAPL")
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM fundamental").fetchone()[0] == 0
    assert "AAPL" in yahoo_info.stored(["AAPL"])


def test_info_without_a_price_is_not_stored(monkeypatch):
    monkeypatch.setattr(yahoo_info, "RETRY_DELAYS", (0.0,))
    with patch("yfinance.Ticker", return_value=_ticker({"quoteType": "EQUITY"})), pytest.raises(RuntimeError):
        fetcher.run_yahoo_info("ZZZ")
    assert yahoo_info.stored(["ZZZ"]) == {}


def test_rotation_takes_never_fetched_then_oldest_and_includes_extras():
    store.upsert("security", [dict(symbol=s) for s in ("AAA", "BBB", "CCC", "^GSPC")], ("symbol",))
    yahoo_info.put("info", "AAA", {}, "2026-10-01T00:00:00Z")
    yahoo_info.put("info", "BBB", {}, "2026-09-01T00:00:00Z")
    assert yahoo_info.rotation(extra=("XLK",), n=3) == ["CCC", "XLK", "BBB"]
    fetcher.queue_yahoo_rotation()
    assert {k for kind, k in _queue() if kind == "yahoo_info"} >= {"CCC", "BBB", "AAA", "XLK"}


def test_request_yahoo_info_queues_only_what_is_missing():
    yahoo_info.put("info", "AAA", {"currentPrice": 1.0})
    assert fetcher.request_yahoo_info(["AAA", "BBB"]) == ["BBB"]
    assert _queue() == [("yahoo_info", "BBB")]


def test_analyst_page_reads_only_the_store():
    with patch.object(analyst_service, "yf") as yf:
        result = analyst_service.analyst_data("msft")
        yf.Ticker.assert_not_called()
    assert result["status"] == "pending" and result["priceTarget"]["meanPrice"] is None
    assert _queue() == [("analyst", "MSFT")]

    doc = {**analyst_service._empty("MSFT"), "price": 400.0, "asOf": "2026-10-14"}
    yahoo_info.put("analyst", "MSFT", doc, "2026-10-14T21:00:00Z")
    with patch("backend.services.analyst_service.datetime") as dt:
        dt.now.return_value = pd.Timestamp("2026-10-15T10:00:00Z").to_pydatetime()
        dt.fromisoformat = __import__("datetime").datetime.fromisoformat
        got = analyst_service.analyst_data("MSFT")
    assert got["price"] == 400.0 and got["fetchedAt"] == "2026-10-14T21:00:00Z"
    prov = analyst_service.provenance(got)
    assert prov["analyst"]["fetchedAt"] == "2026-10-14T21:00:00Z"


def test_a_week_old_panel_is_served_and_refreshed():
    yahoo_info.put("analyst", "MSFT", {**analyst_service._empty("MSFT"), "price": 1.0}, "2026-01-01T00:00:00Z")
    assert analyst_service.analyst_data("MSFT")["price"] == 1.0
    assert _queue() == [("analyst", "MSFT")]


def test_run_analyst_never_stores_an_empty_panel():
    with patch.object(analyst_service, "fetch_analyst", return_value=analyst_service._empty("X")), \
         pytest.raises(RuntimeError):
        fetcher.run_analyst("X")
    full = {**analyst_service._empty("X"), "price": 10.0}
    with patch.object(analyst_service, "fetch_analyst", return_value=full):
        fetcher.run_analyst("X")
    assert yahoo_info.stored(["X"], "analyst")["X"][0]["price"] == 10.0


def test_sector_fundamentals_read_the_stored_etf_info():
    from backend import cache
    from backend.services import sector_service
    cache.clear_all("sector_fundamentals")
    yahoo_info.put("info", "XLK", {"totalAssets": 7.0e10, "trailingPE": 30.0, "yield": 0.006})
    with patch("backend.services.sector_service.yfs.get_close_frame", return_value=pd.DataFrame()):
        rows = sector_service.get_sector_fundamentals()
    xlk = next(r for r in rows if r["ticker"] == "XLK")
    assert xlk["aum"] == 7.0e10 and xlk["dividendYield"] == 0.6 and xlk["infoAsOf"]
    assert next(r for r in rows if r["ticker"] == "XLF")["aum"] is None
    assert ("yahoo_info", "XLF") in _queue()
    cache.clear_all("sector_fundamentals")
