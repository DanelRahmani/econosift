"""M-06 quote change %, M-12 forward-EPS fallback, M-20 dual-class market caps. No network."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.services import yfinance_service as yfs


# ── M-06 ────────────────────────────────────────────────────────────────────
class _QuoteTicker:
    def __init__(self, closes, fast, meta=None):
        self._closes, self.fast_info, self._meta = closes, fast, meta or {"shortName": "Acme"}

    def history(self, **kw):
        idx = pd.bdate_range("2026-09-28", periods=len(self._closes))
        return pd.DataFrame({"Close": self._closes}, index=idx)

    def get_info(self):
        return self._meta


def _quote(monkeypatch, closes, fast):
    monkeypatch.setattr(yfs.yf, "Ticker", lambda s: _QuoteTicker(closes, fast))
    return yfs.get_quote.__wrapped__("ACME")


def test_quote_change_uses_last_two_daily_closes_not_fast_info_prev_close(monkeypatch):
    # closes 100, 110, 111 -> (111 / 110 - 1) * 100 = +0.909091 %.
    # fast_info.previous_close is stale (the audit's AAPL +0.85 % vs +1.10 %): 111 / 110.06 would differ.
    q = _quote(monkeypatch, [100.0, 110.0, 111.0],
               {"last_price": 111.0, "previous_close": 100.0, "currency": "USD"})
    assert q["changePercent"] == pytest.approx(0.909091, abs=1e-5)
    assert q["price"] == 111.0


def test_quote_price_and_change_come_from_the_same_bars(monkeypatch):
    # fast_info last_price (112) is a tick ahead of the last daily bar (111): price follows the bar,
    # so price/change agree with each other and with the treemap (last bar vs the one before).
    q = _quote(monkeypatch, [100.0, 110.0, 111.0], {"last_price": 112.0, "previous_close": 90.0})
    assert q["price"] == 111.0
    assert q["changePercent"] == pytest.approx((111.0 / 110.0 - 1) * 100, abs=1e-9)


def test_quote_falls_back_to_fast_info_with_a_single_bar(monkeypatch):
    # New listing, one bar: (50 - 40) / 40 = +25 %.
    q = _quote(monkeypatch, [50.0], {"last_price": 50.0, "previous_close": 40.0})
    assert q["changePercent"] == pytest.approx(25.0)


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


class _CapTicker:
    def __init__(self, sym):
        self.fast_info = _FAST[sym]


def _caps(monkeypatch, syms):
    monkeypatch.setattr(yfs.yf, "Ticker", _CapTicker)
    monkeypatch.setattr(yfs.time, "sleep", lambda s: None)
    return yfs.get_market_caps.__wrapped__(tuple(syms))


def test_dual_class_issuer_counted_once(monkeypatch):
    # GOOGL + GOOG would add to 4.19e12 + 4.15e12 = 8.34e12; one area = 4.19e12 (GOOGL, the preferred class).
    caps = _caps(monkeypatch, ["AAPL", "GOOG", "GOOGL"])
    assert caps == {"AAPL": 3.5e12, "GOOGL": 4.19e12}
    assert sum(caps.values()) == pytest.approx(7.69e12)


def test_berkshire_classes_with_different_share_counts_are_merged(monkeypatch):
    caps = _caps(monkeypatch, ["BRK-A", "BRK-B"])
    assert caps == {"BRK-B": 1.064e12}


def test_classes_with_distinct_caps_are_both_kept(monkeypatch):
    # 15.0e9 vs 3.0e9: Yahoo gives per-class caps (ratio 5x), summing them is right.
    caps = _caps(monkeypatch, ["BF-B", "BF-A"])
    assert caps == {"BF-B": 15.0e9, "BF-A": 3.0e9}


def test_single_class_requested_is_unchanged(monkeypatch):
    assert _caps(monkeypatch, ["GOOG"]) == {"GOOG": 4.15e12}


def test_one_per_issuer_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(yfs.yf, "Ticker", _CapTicker)
    monkeypatch.setattr(yfs.time, "sleep", lambda s: None)
    caps = yfs.get_market_caps.__wrapped__(("GOOG", "GOOGL"), one_per_issuer=False)
    assert set(caps) == {"GOOG", "GOOGL"}
