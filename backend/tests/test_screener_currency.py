"""Audit M-01 in the screener: ADR rows must not carry Yahoo's mixed-currency multiples.

Fixture: a USD-quoted ADR reporting in TWD, 1 TWD = 0.5 USD. No network: FX is patched.
"""
from __future__ import annotations

import pytest

from backend.services import dcf_engine
from backend.services.screener_service import _price_currency_multiples

YAHOO = {"pb": 2.5, "evEbitda": 15.0, "evFcf": 99.0, "fcfYield": 0.04, "psRatio": 5.0}


def _bundle(financial_currency: str) -> dict:
    return {
        "ticker": "ADR",
        "info": {
            "currency": "USD", "financialCurrency": financial_currency,
            "currentPrice": 100.0, "marketCap": 10_000.0,                     # USD
            "freeCashflow": 400.0, "ebitda": 600.0, "totalRevenue": 2_000.0,  # TWD
            "totalDebt": 1_000.0, "totalCash": 3_000.0,                       # TWD
        },
        "financials": {},
        "balance_sheet": {"Stockholders Equity": 4_000.0},                     # TWD
        "cashflow": {},
    }


def test_adr_multiples_rebuilt_in_price_currency(monkeypatch):
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: 0.5)
    m = _price_currency_multiples(_bundle("TWD"), YAHOO)
    # EV = 10_000 + (1_000 − 3_000) × 0.5 = 9_000 USD
    assert m["fcfYield"] == pytest.approx(0.02)   # 400 × 0.5 / 10_000
    assert m["evFcf"] == pytest.approx(45.0)      # 9_000 / (400 × 0.5)
    assert m["evEbitda"] == pytest.approx(30.0)   # 9_000 / (600 × 0.5)
    assert m["psRatio"] == pytest.approx(10.0)    # 10_000 / (2_000 × 0.5)
    assert m["pb"] == pytest.approx(5.0)          # 10_000 / (4_000 × 0.5)


def test_same_currency_keeps_values(monkeypatch):
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: 0.5)
    assert _price_currency_multiples(_bundle("USD"), YAHOO) == YAHOO


def test_missing_fx_gives_none_not_yahoo(monkeypatch):
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: None)
    m = _price_currency_multiples(_bundle("TWD"), YAHOO)
    assert all(v is None for v in m.values())
