"""A failed Ticker.info call must not be cached as a half-empty bundle.

Live, after a cache clear, a burst of requests made Yahoo fail some info calls; get_info kept
the statements, injected a few derived keys and cached the result for an hour (24 h stale), so
JPM showed no price and every model "Shares outstanding unavailable". No network: Ticker is faked.
"""
from __future__ import annotations

import pandas as pd

from backend.services import yfinance_service as yfs

GOOD = {"currentPrice": 330.83, "beta": 1.1, "forwardEps": 25.0, "trailingEps": 20.0}


class _FakeTicker:
    calls = 0

    def __init__(self, sym, fail_first: int):
        self._fail_first = fail_first
        self.financials = self.balance_sheet = self.cashflow = pd.DataFrame()

    def get_info(self):
        _FakeTicker.calls += 1
        if _FakeTicker.calls <= self._fail_first:
            raise RuntimeError("429 Too Many Requests")
        return dict(GOOD)


def _patch(monkeypatch, fail_first: int):
    _FakeTicker.calls = 0
    monkeypatch.setattr(yfs.yf, "Ticker", lambda sym: _FakeTicker(sym, fail_first))


def test_info_failure_is_retried_once(monkeypatch):
    _patch(monkeypatch, fail_first=1)
    b = yfs.get_info.__wrapped__("JPM")
    assert b["info"]["currentPrice"] == 330.83
    assert _FakeTicker.calls == 2


def test_bundle_without_price_is_not_cached():
    assert yfs._info_failed({"info": {"forwardEps": 24.0, "beta": 0.96}}) is True
    assert yfs._info_failed({"info": {"regularMarketPrice": 10.0}}) is False
    assert yfs._info_failed({"info": dict(GOOD)}) is False


def test_quote_only_equity_response_counts_as_failed():
    # Yahoo's profile/financials request failed: price and P/E present, sector/industry/revenue absent
    # (live AAPL/NVO/JPM after a burst; JPM then also escaped the bank lock, which reads industry).
    quote_only = {"quoteType": "EQUITY", "currentPrice": 333.02, "trailingPE": 38.1, "marketCap": 4.86e12}
    assert yfs._info_failed({"info": quote_only}) is True
    assert yfs._info_failed({"info": {**quote_only, "industry": "Consumer Electronics"}}) is False
    # ETFs/indices have no sector or revenue by nature; a price is enough for them.
    assert yfs._info_failed({"info": {"quoteType": "ETF", "regularMarketPrice": 95.0}}) is False


# ---------------------------------------------------------------------------
# P2-39 — spaced retry, and a degraded flag on /valuation/full
# ---------------------------------------------------------------------------

QUOTE_ONLY = {"quoteType": "EQUITY", "currentPrice": 1186.0, "trailingPE": 38.0}
FULL = {**QUOTE_ONLY, "sector": "Technology", "industry": "Semiconductor Equipment", "totalRevenue": 3.2e10}


class _SeqTicker:
    """Returns the queued info dicts in order (the last one repeats)."""
    seq: list = []
    calls = 0

    def __init__(self, sym):
        self.financials = self.balance_sheet = self.cashflow = pd.DataFrame()

    def get_info(self):
        _SeqTicker.calls += 1
        return dict(_SeqTicker.seq[min(_SeqTicker.calls, len(_SeqTicker.seq)) - 1])


def _seq(monkeypatch, seq):
    _SeqTicker.seq, _SeqTicker.calls = seq, 0
    slept: list[float] = []
    monkeypatch.setattr(yfs.yf, "Ticker", _SeqTicker)
    monkeypatch.setattr(yfs.time, "sleep", slept.append)
    return slept


def test_quote_only_bundle_gets_a_spaced_third_attempt(monkeypatch):
    # Two quote-only answers in a row (the Phase 54 ASML case), the third, after a pause, is complete.
    slept = _seq(monkeypatch, [QUOTE_ONLY, QUOTE_ONLY, FULL])
    b = yfs.get_info.__wrapped__("ASML.AS")
    assert b["info"]["sector"] == "Technology"
    assert _SeqTicker.calls == 3
    assert slept and all(s > 0 for s in slept)


def test_full_marks_a_still_partial_bundle_degraded(monkeypatch):
    import asyncio
    from backend.routers import valuation as vr
    _seq(monkeypatch, [QUOTE_ONLY])
    monkeypatch.setattr(vr, "_beta_for", lambda sym: None)
    monkeypatch.setattr(vr, "analyst_data", lambda sym: {})
    out = asyncio.run(vr.full("ASML.AS"))
    assert out["degraded"] is True
    assert "partial company data" in out["degradedReason"]


def test_full_is_not_degraded_for_a_complete_bundle(monkeypatch):
    import asyncio
    from backend.routers import valuation as vr
    _seq(monkeypatch, [FULL])
    monkeypatch.setattr(vr, "_beta_for", lambda sym: None)
    monkeypatch.setattr(vr, "analyst_data", lambda sym: {})
    out = asyncio.run(vr.full("ASML.AS"))
    assert out["degraded"] is False and out["degradedReason"] is None
