"""P2-38: /corporate Altman Z and /dividends FCF payout put statement-currency figures in the price
currency (via dcf_engine.to_price_currency's FX path) before dividing them by USD values. No network."""
from __future__ import annotations

import pandas as pd
import pytest

_COL = [pd.Timestamp(2025, 12, 31)]


def _bs(**rows) -> pd.DataFrame:
    return pd.DataFrame({_COL[0]: rows}).rename_axis(None)


def test_altman_x4_converts_liabilities_to_the_price_currency():
    # TWD-reporting ADR quoted in USD, 1 TWD = 0.03125 USD.
    #   liabilities TWD 3,200,000 -> USD 100,000;  market cap USD 1,000,000
    #   x4 = 1,000,000 / 100,000 = 10   (unconverted: 1,000,000 / 3,200,000 = 0.3125)
    #   other ratios are within one statement: x1 = (400-200)/1000 = 0.2, x2 = 0.3, x3 = 0.1, x5 = 0.5
    #   Z = 1.2*0.2 + 1.4*0.3 + 3.3*0.1 + 0.6*10 + 1.0*0.5 = 0.24 + 0.42 + 0.33 + 6 + 0.5 = 7.49
    from backend.services.corporate_health_service import _altman_z
    bs = _bs(**{"Total Assets": 1000.0 * 3200, "Total Liabilities Net Minority Interest": 3_200_000.0,
                "Current Assets": 400.0 * 3200, "Current Liabilities": 200.0 * 3200,
                "Retained Earnings": 300.0 * 3200})
    fin = _bs(**{"EBIT": 100.0 * 3200, "Total Revenue": 500.0 * 3200})
    z = _altman_z(fin, bs, {"marketCap": 1_000_000.0}, fx_rate=0.03125)
    assert z["components"]["x4_marketValueToLiabilities"] == pytest.approx(10.0)
    assert z["zScore"] == pytest.approx(7.49, abs=1e-4)


def test_altman_without_fx_rate_is_null_not_mixed():
    from backend.services.corporate_health_service import _altman_z
    bs = _bs(**{"Total Assets": 1000.0, "Total Liabilities Net Minority Interest": 500.0,
                "Current Assets": 400.0, "Current Liabilities": 200.0, "Retained Earnings": 300.0})
    fin = _bs(**{"EBIT": 100.0, "Total Revenue": 500.0})
    z = _altman_z(fin, bs, {"marketCap": 1000.0}, fx_rate=None)
    assert z["zScore"] is None


class _NvoTicker:
    """DKK-reporting ADR quoted in USD. TTM dividend: 2 × $1.00 in the last 12 months.
    FCF DKK 70bn, 4.4bn ADR-equivalent shares, 1 DKK = 0.15 USD."""

    def __init__(self, _sym):
        self.dividends = pd.Series([1.0, 1.0, 1.0, 1.0], index=pd.DatetimeIndex(
            [pd.Timestamp(2025, 3, 30), pd.Timestamp(2025, 8, 20), pd.Timestamp(2026, 3, 30),
             pd.Timestamp(2026, 8, 20)]))
        self.info = {"currentPrice": 60.0, "currency": "USD", "financialCurrency": "DKK",
                     "shortName": "NVO", "sector": "Healthcare", "sharesOutstanding": 4_400_000_000,
                     "trailingEps": 3.5, "freeCashflow": 70_000_000_000}
        self.cashflow = pd.DataFrame()


def test_dividend_fcf_payout_uses_fcf_in_the_price_currency(monkeypatch):
    # TTM dividend $2.00 × 4.4bn shares = $8.8bn; FCF DKK 70bn × 0.15 = $10.5bn
    #   payout = 8.8 / 10.5 = 0.8381   (unconverted: 8.8 / 70 = 0.1257, looks "very safe")
    from backend.services import dcf_engine, discount_rates, dividend_service
    monkeypatch.setattr(dividend_service.yf, "Ticker", _NvoTicker)
    monkeypatch.setattr(discount_rates, "risk_free_rate", lambda: 0.045)
    monkeypatch.setattr(dividend_service, "_now", lambda: pd.Timestamp(2026, 9, 30))
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda f, t: 0.15 if (f, t) == ("DKK", "USD") else None)
    out = dividend_service.get_dividend_analysis("NVO")
    assert out["fcfPayoutRatio"] == pytest.approx(0.8381, abs=1e-4)


def test_dividend_fcf_payout_none_when_fx_unavailable(monkeypatch):
    from backend.services import dcf_engine, discount_rates, dividend_service
    monkeypatch.setattr(dividend_service.yf, "Ticker", _NvoTicker)
    monkeypatch.setattr(discount_rates, "risk_free_rate", lambda: 0.045)
    monkeypatch.setattr(dividend_service, "_now", lambda: pd.Timestamp(2026, 9, 30))
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda f, t: None)
    assert dividend_service.get_dividend_analysis("NVO")["fcfPayoutRatio"] is None
