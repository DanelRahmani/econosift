"""Audit M-01: ADR / cross-listing multiples must not mix statement and price currency.

Fixture: a USD-quoted ADR that reports in TWD, with 1 TWD = 0.5 USD so every
expected value below is hand-computable. No network: the FX lookup is patched.
"""
from __future__ import annotations

import pytest

from backend.routers.valuation import _kpis
from backend.services import dcf_engine, metrics

RATE = 0.5  # USD per TWD


def _info(**over) -> dict:
    info = {
        "currency": "USD", "financialCurrency": "TWD",
        "currentPrice": 100.0, "marketCap": 10_000.0,          # USD
        "enterpriseValue": 9_999.0,                              # Yahoo's mixed-currency value, must be ignored
        "freeCashflow": 400.0, "ebitda": 600.0, "totalRevenue": 2_000.0,   # TWD
        "totalDebt": 1_000.0, "totalCash": 3_000.0,              # TWD
        # Yahoo's pass-through multiples are wrong for an ADR
        "priceToSalesTrailing12Months": 5.0, "enterpriseToEbitda": 15.0,
        "enterpriseToRevenue": 5.0, "priceToBook": 2.5,
    }
    info.update(over)
    return info


def _bundle(info: dict | None = None) -> dict:
    return {
        "ticker": "ADR",
        "info": info if info is not None else _info(),
        "financials": {"EBIT": 1_000.0, "Total Revenue": 8_000.0},
        "balance_sheet": {
            "Total Assets": 10_000.0, "Current Assets": 5_000.0, "Current Liabilities": 2_000.0,
            "Retained Earnings": 3_000.0, "Total Liabilities Net Minority Interest": 4_000.0,
            "Stockholders Equity": 4_000.0,
        },
        "cashflow": {},
    }


@pytest.fixture
def fx_half(monkeypatch):
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: RATE)


@pytest.fixture
def fx_missing(monkeypatch):
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: None)


class TestKpisCrossCurrency:
    def test_fcf_yield_converts_fcf(self, fx_half):
        # FCF 400 TWD * 0.5 = 200 USD; 200 / 10_000 mcap = 0.02 (unconverted would be 0.04)
        k = _kpis(_info())
        assert k["fcfYield"] == pytest.approx(0.02)

    def test_ev_to_fcf_rebuilds_ev(self, fx_half):
        # EV = 10_000 + 1_000*0.5 - 3_000*0.5 = 9_000 USD; / FCF 200 = 45 (Yahoo's EV 9_999 ignored)
        k = _kpis(_info())
        assert k["evToFcf"] == pytest.approx(45.0)

    def test_no_rate_returns_null_with_reason(self, fx_missing):
        k = _kpis(_info())
        assert k["fcfYield"] is None and k["evToFcf"] is None
        assert "TWD/USD" in k["unavailable"]["fcfYield"]
        assert "TWD/USD" in k["unavailable"]["evToFcf"]

    def test_book_value_from_converted_equity(self, fx_half):
        # equity 4_000 TWD * 0.5 = 2_000 USD; * price 100 / mcap 10_000 = 20 per ADR (Yahoo's 3.0 ignored)
        b = _bundle(_info(bookValue=3.0))
        k = _kpis(b["info"], b)
        assert k["bookValue"] == pytest.approx(20.0)
        assert "bookValue" not in k["unavailable"]

    def test_book_value_missing_equity_is_null_with_reason(self, fx_half):
        k = _kpis(_info(bookValue=3.0))  # no statements and no info equity
        assert k["bookValue"] is None
        assert "stockholdersEquity" in k["unavailable"]["bookValue"]

    def test_book_value_no_rate_is_null_with_reason(self, fx_missing):
        b = _bundle(_info(bookValue=3.0))
        k = _kpis(b["info"], b)
        assert k["bookValue"] is None
        assert "TWD/USD" in k["unavailable"]["bookValue"]

    def test_book_value_same_currency_unchanged(self, monkeypatch):
        monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: pytest.fail("no FX lookup expected"))
        k = _kpis(_info(financialCurrency="USD", bookValue=3.0))
        assert k["bookValue"] == 3.0

    def test_same_currency_unchanged(self, monkeypatch):
        monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: pytest.fail("no FX lookup expected"))
        k = _kpis(_info(financialCurrency="USD"))
        # 400 / 10_000 and Yahoo's own EV 9_999 / 400
        assert k["fcfYield"] == pytest.approx(0.04)
        assert k["evToFcf"] == pytest.approx(9_999.0 / 400.0)
        assert k["unavailable"] == {}


class TestRatiosCrossCurrency:
    def test_ps_recomputed(self, fx_half):
        # revenue 2_000 TWD * 0.5 = 1_000 USD; 10_000 / 1_000 = 10 (Yahoo passthrough said 5)
        r = metrics.compute_ratios(_bundle())
        assert r["valuation"]["psRatio"] == pytest.approx(10.0)

    def test_ev_ebitda_recomputed(self, fx_half):
        # EV 9_000 USD (see above); EBITDA 600 * 0.5 = 300 -> 30 (Yahoo said 15)
        r = metrics.compute_ratios(_bundle())
        assert r["valuation"]["evEbitda"] == pytest.approx(30.0)

    def test_ev_revenue_recomputed(self, fx_half):
        # EV 9_000 / revenue 1_000 = 9
        r = metrics.compute_ratios(_bundle())
        assert r["valuation"]["evRevenue"] == pytest.approx(9.0)

    def test_pb_recomputed(self, fx_half):
        # equity 4_000 TWD * 0.5 = 2_000 USD; 10_000 / 2_000 = 5 (Yahoo said 2.5)
        r = metrics.compute_ratios(_bundle())
        assert r["valuation"]["pbRatio"] == pytest.approx(5.0)

    def test_altman_z_converts_liabilities(self, fx_half):
        # x1 = (5000-2000)/10000 = .3 -> 0.36 ; x2 = 3000/10000 = .3 -> 0.42 ; x3 = 1000/10000 = .1 -> 0.33
        # x4 = mcap 10_000 USD / (TL 4_000 TWD * 0.5 = 2_000) = 5 -> 3.0 ; x5 = 8000/10000 = .8
        # Z = 0.36 + 0.42 + 0.33 + 3.0 + 0.8 = 4.91 (unconverted TL gives 3.41)
        r = metrics.compute_ratios(_bundle())
        assert r["zScore"] == pytest.approx(4.91)

    def test_altman_z_standalone_looks_up_fx(self, fx_half):
        # screener_service calls altman_z directly with the raw bundle
        b = _bundle()
        assert metrics.altman_z(b["info"], b["balance_sheet"], b["financials"]) == pytest.approx(4.91)

    def test_margins_unchanged_by_conversion(self, fx_half):
        # scale-invariant: both statement lines scale by the same rate, 600 / 8000 = 0.075 either way
        b = _bundle()
        b["financials"]["EBITDA"] = 600.0
        r = metrics.compute_ratios(b)
        assert r["profitability"]["ebitdaMargin"] == pytest.approx(0.075)

    def test_no_rate_nulls_with_reasons(self, fx_missing):
        r = metrics.compute_ratios(_bundle())
        for k in ("psRatio", "evEbitda", "evRevenue", "pbRatio"):
            assert r["valuation"][k] is None
            assert "TWD/USD" in r["unavailable"][f"valuation.{k}"]
        assert r["zScore"] is None
        assert "TWD/USD" in r["unavailable"]["zScore"]
        assert metrics.altman_z(_bundle()["info"], _bundle()["balance_sheet"], _bundle()["financials"]) is None

    def test_missing_input_reason(self, fx_half):
        info = _info()
        del info["totalCash"]
        r = metrics.compute_ratios(_bundle(info))
        assert r["valuation"]["evEbitda"] is None
        assert "totalCash" in r["unavailable"]["valuation.evEbitda"]
        assert r["valuation"]["psRatio"] == pytest.approx(10.0)  # does not need cash

    def test_same_currency_passes_yahoo_through(self, monkeypatch):
        monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: pytest.fail("no FX lookup expected"))
        r = metrics.compute_ratios(_bundle(_info(financialCurrency="USD")))
        assert r["valuation"]["psRatio"] == 5.0
        assert r["valuation"]["evEbitda"] == 15.0
        assert r["valuation"]["evRevenue"] == 5.0
        assert r["valuation"]["pbRatio"] == 2.5
        # x4 = 10_000 / 4_000 = 2.5 -> 1.5 ; Z = 0.36 + 0.42 + 0.33 + 1.5 + 0.8 = 3.41
        assert r["zScore"] == pytest.approx(3.41)
        assert r["unavailable"] == {}


class TestNegativeFcfEvMultiple:
    """EV / negative FCF is not a multiple (JPM showed EV/FCF −4.85); FCF yield stays a real number."""

    def test_same_currency_negative_fcf(self):
        info = {"currency": "USD", "financialCurrency": "USD", "marketCap": 1_000.0,
                "enterpriseValue": 1_200.0, "freeCashflow": -100.0}
        m = metrics.market_multiples({"info": info})
        assert m["values"]["evToFcf"] is None
        assert m["unavailable"]["evToFcf"] == "not meaningful: free cash flow ≤ 0"
        assert m["values"]["fcfYield"] == pytest.approx(-0.1)   # −100 / 1_000

    def test_cross_currency_negative_fcf(self, fx_half):
        m = metrics.market_multiples(_bundle(_info(freeCashflow=-400.0)))
        assert m["values"]["evToFcf"] is None
        assert m["unavailable"]["evToFcf"] == "not meaningful: free cash flow ≤ 0"
        assert m["values"]["fcfYield"] == pytest.approx(-0.02)  # −400 × 0.5 / 10_000
