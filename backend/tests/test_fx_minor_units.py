"""Minor-unit quote currencies (London GBp, Johannesburg ZAc, Tel Aviv ILA).

Yahoo quotes AZN.L in pence ("GBp") while its statements are in GBP or USD. A pence quote is
the same currency as GBP, so it needs a ×100 scale, not an FX pair ("GBPGBp=X" does not exist).
No network: the close-frame lookup is patched.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.services import dcf_engine, metrics
from backend.services import yfinance_service as yfs


def _frame(rates: dict):
    def get_close_frame(symbols, period):
        return pd.DataFrame({s: [rates[s]] for s in symbols if s in rates})
    return get_close_frame


def test_same_currency_minor_unit_needs_no_fx(monkeypatch):
    monkeypatch.setattr(yfs, "get_close_frame", _frame({}))
    assert dcf_engine._fx_rate("GBP", "GBp") == pytest.approx(100.0)   # £1 = 100p
    assert dcf_engine._fx_rate("GBp", "GBP") == pytest.approx(0.01)
    assert dcf_engine._fx_rate("ZAR", "ZAc") == pytest.approx(100.0)
    assert dcf_engine._fx_rate("ILS", "ILA") == pytest.approx(100.0)


def test_cross_currency_into_minor_unit(monkeypatch):
    monkeypatch.setattr(yfs, "get_close_frame", _frame({"USDGBP=X": 0.8}))
    # $1 = £0.80 = 80p
    assert dcf_engine._fx_rate("USD", "GBp") == pytest.approx(80.0)


def test_pence_quoted_ticker_keeps_its_multiples(monkeypatch):
    monkeypatch.setattr(yfs, "get_close_frame", _frame({}))
    bundle = {
        "info": {"currency": "GBp", "financialCurrency": "GBP",
                 "currentPrice": 10_000.0, "marketCap": 1_000_000.0,          # pence
                 "freeCashflow": 500.0, "ebitda": 1_000.0, "totalRevenue": 2_000.0,
                 "totalDebt": 1_000.0, "totalCash": 500.0},                   # GBP
        "financials": {}, "balance_sheet": {"Stockholders Equity": 2_500.0}, "cashflow": {},
    }
    m = metrics.market_multiples(bundle)
    assert m["unavailable"] == {}
    # FCF £500 = 50_000p; 50_000 / 1_000_000 = 0.05
    assert m["values"]["fcfYield"] == pytest.approx(0.05)
    # EV = 1_000_000 + (1_000 − 500) × 100 = 1_050_000p; EBITDA 100_000p → 10.5
    assert m["values"]["evEbitda"] == pytest.approx(10.5)
    # P/B = 1_000_000 / 250_000 = 4.0
    assert m["values"]["pbRatio"] == pytest.approx(4.0)
