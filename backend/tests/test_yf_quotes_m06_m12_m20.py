"""M-06 quote change %, M-12 forward-EPS fallback, M-20 dual-class market caps. No network.

Since Phase 67 quotes and caps are read from econosift.db (the snapshot), never from Yahoo.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.services import yfinance_service as yfs


# ── M-06 (Phase 67: quotes come from the store) ─────────────────────────────
SYMS = ("ACME", "GOOGL", "GOOG", "BRK-B", "BRK-A", "AAPL", "BF-B", "BF-A")


@pytest.fixture(autouse=True)
def _store():
    from backend import store
    store.init_schema()

    def clean():
        with store.connect() as conn:
            for t in ("quote_latest", "price_daily", "security", "fetch_queue"):
                conn.execute(f"DELETE FROM {t} WHERE {'key' if t == 'fetch_queue' else 'symbol'} IN "
                             f"({','.join('?' * len(SYMS))})", SYMS)
    clean()
    yield store
    clean()


def _bars(store, closes):
    days = pd.bdate_range("2026-09-28", periods=len(closes))
    store.upsert("price_daily", [dict(symbol="ACME", date=d.date().isoformat(), open=c, high=c, low=c, close=c,
                                      adj_close=c, volume=1.0) for d, c in zip(days, closes)], ("symbol", "date"))
    store.upsert("security", [dict(symbol="ACME", name="Acme", history_at="2026-10-01T00:00:00Z")], ("symbol",))


def test_quote_comes_from_the_latest_snapshot(_store, monkeypatch):
    monkeypatch.setattr(yfs.yf, "Ticker", lambda s: pytest.fail("a quote must not call Yahoo"))
    _bars(_store, [100.0, 110.0])
    _store.upsert("quote_latest", [dict(symbol="ACME", ts=1792008001, price=111.0, change_pct=0.909091,
                                        currency="USD", name="Acme Corp")], ("symbol",))
    q = yfs.get_quote("ACME")
    assert q == {"symbol": "ACME", "price": 111.0, "changePercent": 0.909091, "currency": "USD",
                 "name": "Acme Corp"}


def test_quote_without_a_snapshot_uses_the_last_two_daily_closes(_store):
    # closes 100, 110, 111 -> (111 / 110 - 1) * 100 = +0.909091 %.
    _bars(_store, [100.0, 110.0, 111.0])
    q = yfs.get_quote("ACME")
    assert q["price"] == 111.0
    assert q["changePercent"] == pytest.approx(0.909091, abs=1e-5)
    assert q["name"] == "Acme" and q["currency"] is None


def test_quote_with_a_single_bar_has_no_change(_store):
    _bars(_store, [50.0])
    q = yfs.get_quote("ACME")
    assert q["price"] == 50.0 and q["changePercent"] is None


def test_unknown_symbol_is_queued_and_pending(_store):
    q = yfs.get_quote("ACME")
    assert q["status"] == "pending" and q["price"] is None
    with _store.connect() as conn:
        assert conn.execute("SELECT kind FROM fetch_queue WHERE key = 'ACME'").fetchone() == ("history",)


# ── M-12 ────────────────────────────────────────────────────────────────────
class _EpsTicker:
    def __init__(self, sym):
        self.financials = self.balance_sheet = self.cashflow = pd.DataFrame()
        self.earnings_estimate = pd.DataFrame(
            {"avg": [47965.375, 71030.125]}, index=["0y", "+1y"])

    def get_info(self):
        return {"currentPrice": 276000.0, "forwardPE": 3.8856752, "quoteType": "EQUITY",
                "sector": "Technology", "trailingEps": 1.0}


def test_forward_eps_fallback_uses_next_year_estimate(monkeypatch):
    # Samsung: price 276 000 / forwardPE 3.8856752 = 71 030 = the +1y estimate (not the 0y 47 965).
    monkeypatch.setattr(yfs.yf, "Ticker", _EpsTicker)
    info = yfs.get_info.__wrapped__("005930.KS")["info"]
    assert info["forwardEps"] == pytest.approx(71030.125)
    assert info["currentPrice"] / info["forwardPE"] == pytest.approx(info["forwardEps"], rel=1e-4)


# ── M-20 ────────────────────────────────────────────────────────────────────
_FAST = {
    # Yahoo reports the whole-company cap at each class's price (live: GOOGL 4.19T, GOOG 4.15T).
    "GOOGL": {"market_cap": 4.19e12, "shares": 12.2e9},
    "GOOG": {"market_cap": 4.15e12, "shares": 12.2e9},
    "BRK-B": {"market_cap": 1.064e12, "shares": 2.14e9},
    "BRK-A": {"market_cap": 1.066e12, "shares": 1.427e6},
    "AAPL": {"market_cap": 3.5e12, "shares": 14.9e9},
    "BF-B": {"market_cap": 15.0e9, "shares": 470e6},   # separate per-class caps: both kept
    "BF-A": {"market_cap": 3.0e9, "shares": 90e6},
}


def _caps(store, syms, **kw):
    store.upsert("quote_latest", [dict(symbol=sym, ts=1792008001, market_cap=v["market_cap"], shares=v["shares"])
                                  for sym, v in _FAST.items()], ("symbol",))
    return yfs.get_market_caps(tuple(syms), **kw)


def test_dual_class_issuer_counted_once(_store):
    # GOOGL + GOOG would add to 4.19e12 + 4.15e12 = 8.34e12; one area = 4.19e12 (GOOGL, the preferred class).
    caps = _caps(_store, ["AAPL", "GOOG", "GOOGL"])
    assert caps == {"AAPL": 3.5e12, "GOOGL": 4.19e12}
    assert sum(caps.values()) == pytest.approx(7.69e12)


def test_berkshire_classes_with_different_share_counts_are_merged(_store):
    caps = _caps(_store, ["BRK-A", "BRK-B"])
    assert caps == {"BRK-B": 1.064e12}


def test_classes_with_distinct_caps_are_both_kept(_store):
    # 15.0e9 vs 3.0e9: Yahoo gives per-class caps (ratio 5x), summing them is right.
    caps = _caps(_store, ["BF-B", "BF-A"])
    assert caps == {"BF-B": 15.0e9, "BF-A": 3.0e9}


def test_single_class_requested_is_unchanged(_store):
    assert _caps(_store, ["GOOG"]) == {"GOOG": 4.15e12}


def test_one_per_issuer_can_be_switched_off(_store):
    caps = _caps(_store, ["GOOG", "GOOGL"], one_per_issuer=False)
    assert set(caps) == {"GOOG", "GOOGL"}
