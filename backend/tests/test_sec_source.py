"""Phase 68 item 1: SEC guard, User-Agent from EDGAR_IDENTITY, ticker -> CIK map."""
from unittest.mock import MagicMock, patch

import pytest
from yfinance.exceptions import YFRateLimitError

from backend import config, fetcher, rate_limit, store
from backend.sources import source_sec


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    with store.connect() as conn:
        for t in ("fetch_queue", "security", "source_health"):
            conn.execute(f"DELETE FROM {t}")
    yield
    with store.connect() as conn:
        for t in ("fetch_queue", "security", "source_health"):
            conn.execute(f"DELETE FROM {t}")


def _resp(status=200, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


def test_sec_guard_runs_at_five_per_second_and_reports_its_status():
    assert rate_limit.SEC.rate == 5.0
    assert "sec" in rate_limit.status()


def test_no_identity_means_no_request(monkeypatch):
    monkeypatch.setattr(config, "EDGAR_IDENTITY", None)
    with patch("requests.get") as get, pytest.raises(source_sec.SecUnavailable):
        source_sec.get_json(source_sec.TICKERS_URL)
    get.assert_not_called()
    assert fetcher.sec_status()["identity"] is False
    fetcher.queue_ciks()
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM fetch_queue").fetchone()[0] == 0


def test_user_agent_names_the_caller(monkeypatch):
    monkeypatch.setattr(config, "EDGAR_IDENTITY", "Jane Doe jane@example.com")
    with patch("requests.get", return_value=_resp(payload={"ok": 1})) as get:
        assert source_sec.get_json("https://data.sec.gov/x.json") == {"ok": 1}
    assert get.call_args.kwargs["headers"]["User-Agent"] == "EconoSift Jane Doe jane@example.com"


def test_404_is_none_and_429_raises_rate_limit(monkeypatch):
    monkeypatch.setattr(config, "EDGAR_IDENTITY", "Jane Doe jane@example.com")
    with patch("requests.get", return_value=_resp(404)):
        assert source_sec.get_json("https://data.sec.gov/x.json") is None
    with patch("requests.get", return_value=_resp(429)), pytest.raises(YFRateLimitError):
        source_sec.get_json("https://data.sec.gov/x.json")
    rate_limit.SEC._open_until = 0.0  # don't leak an open circuit into other tests
    rate_limit.SEC._consecutive_429 = 0


def test_run_ciks_maps_stored_symbols(monkeypatch):
    monkeypatch.setattr(config, "EDGAR_IDENTITY", "Jane Doe jane@example.com")
    store.upsert("security", [dict(symbol="AAPL"), dict(symbol="BRK-B"), dict(symbol="^GSPC")], ("symbol",))
    payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"},
               "1": {"cik_str": 1067983, "ticker": "BRK.B", "title": "Berkshire"},
               "2": {"cik_str": 999, "ticker": "ZZZZ", "title": "Not tracked"}}
    with patch("requests.get", return_value=_resp(payload=payload)):
        assert fetcher.run_ciks("all") == 2
    with store.connect() as conn:
        got = dict(conn.execute("SELECT symbol, cik FROM security"))
    assert got == {"AAPL": "0000320193", "BRK-B": "0001067983", "^GSPC": None}
    status = fetcher.sec_status()
    assert status["identity"] is True and status["ciks"] == 2 and status["ciksAt"]


def test_empty_ticker_file_stores_nothing(monkeypatch):
    monkeypatch.setattr(config, "EDGAR_IDENTITY", "Jane Doe jane@example.com")
    with patch("requests.get", return_value=_resp(payload={})), pytest.raises(RuntimeError):
        fetcher.run_ciks("all")
