"""Dividend analysis — hand-computed known values (audit C-01, C-02)."""
from __future__ import annotations

import pandas as pd
import pytest


class _FakeTicker:
    """Quarterly dividends: $0.40/qtr in 2019 … +$0.05/qtr each year; 2026 is
    partial (two payments). EPS $6.00, 1bn shares, FCF $3bn."""

    def __init__(self, _sym):
        dates, vals = [], []
        for year in range(2019, 2026):
            dps = 0.40 + 0.05 * (year - 2019)
            for month in (3, 6, 9, 12):
                dates.append(pd.Timestamp(year, month, 15))
                vals.append(dps)
        for month in (3, 6):
            dates.append(pd.Timestamp(2026, month, 15))
            vals.append(0.75)
        self.dividends = pd.Series(vals, index=pd.DatetimeIndex(dates))
        self.info = {"currentPrice": 100.0, "shortName": "Fake", "sector": "Utilities",
                     "dividendYield": 2.9, "sharesOutstanding": 1_000_000_000,
                     "trailingEps": 6.0, "freeCashflow": 3_000_000_000}
        self.cashflow = pd.DataFrame()


@pytest.fixture()
def analysis(monkeypatch):
    from backend.services import dividend_service, discount_rates
    monkeypatch.setattr(dividend_service.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(discount_rates, "risk_free_rate", lambda: 0.045)
    # Freeze "now" inside 2026 so 2026 is the running (partial) year.
    monkeypatch.setattr(dividend_service, "_now", lambda: pd.Timestamp(2026, 9, 30))
    return dividend_service.get_dividend_analysis("FAKE")


def test_partial_and_first_years_excluded(analysis):
    years = [int(y) for y in analysis["annualDividends"]]
    assert 2026 not in years          # running year is partial
    assert 2019 not in years          # first year of the record may be partial
    assert analysis["latestYear"] == 2025
    assert analysis["latestAnnualDividend"] == pytest.approx(4 * 0.70)


def test_growth_streak_not_reset_by_partial_year(analysis):
    # 2020→2025 all rise: 5 consecutive increases (2019 dropped).
    assert analysis["consecutiveGrowthYears"] == 5


def test_payout_ratio_is_per_share(analysis):
    # TTM from 2026-09-30: Dec-2025 (0.70) + Mar/Jun-2026 (0.75 each) = 2.20.
    assert analysis["ttmDividend"] == pytest.approx(2.20)
    assert analysis["payoutRatio"] == pytest.approx(2.20 / 6.0, abs=1e-4)


def test_fcf_payout_uses_total_dividends_over_fcf(analysis):
    # 2.20 × 1bn shares / 3bn FCF.
    assert analysis["fcfPayoutRatio"] == pytest.approx(2.20 / 3.0, abs=1e-4)


def test_cagr_5y_on_complete_years(analysis):
    # 2025 (2.80) vs 2020 (1.80) over 5 years.
    assert analysis["cagr5y"] == pytest.approx(((2.80 / 1.80) ** (1 / 5) - 1) * 100, abs=0.01)
