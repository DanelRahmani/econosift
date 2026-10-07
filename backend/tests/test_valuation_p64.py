"""P2-34 (A2): the DDM grows the forward dividend once; an unknown quote currency is None + a reason, never USD."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def patch_network(monkeypatch):
    """Block the FRED / AAA lookups so the models run offline."""
    from backend.cache import _caches
    from backend.services import discount_rates, valuation_engine

    monkeypatch.setattr(discount_rates, "_fetch_dgs10", lambda: 0.043)
    monkeypatch.setattr(valuation_engine, "_get_aaa_yield", lambda: 5.0)
    for key in ("rf10y", "aaa_yield", "erp_json", "sector_multiples_json"):
        _caches.pop(key, None)
    yield
    for key in ("rf10y", "aaa_yield"):
        _caches.pop(key, None)


def _bundle(currency: str | None = "USD", **overrides) -> dict:
    info: dict = {
        "exchange": "NMS", "sector": "Technology", "currentPrice": 150.0,
        "freeCashflow": 10_000_000_000, "operatingCashflow": 10_000_000_000,
        "sharesOutstanding": 16_000_000_000, "totalDebt": 100_000_000_000, "totalCash": 60_000_000_000,
        "trailingEps": 6.0, "forwardEps": 7.0, "bookValue": 4.0,
        "dividendRate": 2.0, "returnOnEquity": 0.06, "payoutRatio": 0.5,
        "revenueGrowth": 0.07, "ebitda": 30_000_000_000, "marketCap": 2_400_000_000_000,
        "effectiveTaxRate": 0.21, "interestExpense": 3_000_000_000, "ebit": 35_000_000_000,
    }
    if currency is not None:
        info["currency"] = currency
    info.update(overrides)
    return {"ticker": "AAPL", "info": info, "financials": {}, "balance_sheet": {}, "cashflow": {}}


# ---------------------------------------------------------------------------
# DDM: dividendRate is already the forward annual dividend
# ---------------------------------------------------------------------------

def test_ddm_does_not_grow_the_forward_dividend_a_second_time():
    from backend.services import valuation_engine as ve

    ctx = ve._Ctx(_bundle(), 1.0, None)
    ctx.ke = 0.08                      # g = (1 - 0.5) * 0.06 = 0.03, below the risk-free cap
    ddm = ve._model_ddm(ctx)
    assert ddm["detail"]["growthRate"] == pytest.approx(0.03)
    assert ddm["value"] == pytest.approx(2.0 / (0.08 - 0.03))      # 40.0, not 2.0 * 1.03 / 0.05 = 41.2
    assert ddm["detail"]["D1"] == pytest.approx(2.0)


def test_ddm_formula_text_says_the_rate_is_already_forward():
    from backend.services import valuation_engine as ve

    src = open(ve.__file__, encoding="utf-8").read()
    assert "D1 = dividendRate (Yahoo's forward annual rate)" in src
    assert "dividendRate × (1 + g)" not in src


# ---------------------------------------------------------------------------
# Unknown quote currency: None + reason, never USD
# ---------------------------------------------------------------------------

def test_major_currency_of_none_is_none():
    from backend.services.discount_rates import _major_currency

    assert _major_currency(None) is None
    assert _major_currency("GBp") == "GBP"
    assert _major_currency("USD") == "USD"


def test_local_risk_free_rate_without_a_currency_is_null_with_a_reason():
    from backend.services.discount_rates import local_risk_free_rate

    out = local_risk_free_rate("United States", None)
    assert out["value"] is None
    assert "no quote currency" in out["reason"]


def test_wacc_without_a_currency_does_not_use_the_us_rate():
    from backend.services.discount_rates import wacc

    w = wacc(_bundle(currency=None), 1.0)
    assert w["riskFree"] is None and w["costOfEquity"] is None and w["wacc"] is None
    assert "no quote currency" in w["unavailable"]["riskFree"]
    assert w["unavailable"]["currency"] == "Yahoo reported no quote currency"


def test_wacc_with_usd_still_uses_the_us_rate():
    from backend.services.discount_rates import wacc

    w = wacc(_bundle(currency="USD"), 1.0)
    assert w["riskFree"] == pytest.approx(0.043)
    assert "currency" not in w["unavailable"]


def test_valuation_models_without_a_currency_expose_none_and_lock_the_rate_models():
    from backend.services.valuation_engine import valuation_models

    out = valuation_models(_bundle(currency=None), beta=1.0)
    assert out["currency"] is None
    by_name = {m["model"]: m for m in out["models"]}
    for name in ("DCF (Two-Stage)", "DDM (Gordon Growth)"):
        assert by_name[name]["locked"] is True and by_name[name]["value"] is None
        assert "quote currency" in by_name[name]["reason"]
    assert out["wacc"]["unavailable"]["currency"] == "Yahoo reported no quote currency"


def test_two_stage_dcf_without_a_currency_does_not_raise_and_reports_none():
    from backend.services import dcf_engine

    out = dcf_engine.two_stage_dcf(_bundle(currency=None), fcf_growth=0.05, terminal_growth=0.025, wacc=0.09)
    assert out["currency"] is None
    assert out["unavailable"]["currency"] == "Yahoo reported no quote currency"
    assert "unavailable" not in dcf_engine.two_stage_dcf(
        _bundle(currency="USD"), fcf_growth=0.05, terminal_growth=0.025, wacc=0.09)


def test_analyst_data_without_a_currency_exposes_none(monkeypatch):
    from backend.services import analyst_service

    class _T:
        def get_info(self):
            return {"currentPrice": 10.0}

        def __getattr__(self, name):
            raise AttributeError(name)

    monkeypatch.setattr(analyst_service.yf, "Ticker", lambda t: _T())
    out = analyst_service.analyst_data.__wrapped__("XYZ")
    assert out["currency"] is None
    assert out["unavailable"]["currency"] == "Yahoo reported no quote currency"


def test_statements_to_usd_without_any_currency_is_not_usd():
    from backend.services.fundamentals import _statements_to_usd

    assert _statements_to_usd({"info": {}}) == (None, None)
    assert _statements_to_usd({"info": {"currency": "USD"}}) == (1.0, "USD")


def test_ohlson_without_a_currency_is_null_with_a_reason(monkeypatch):
    from backend.services import fundamentals

    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 100.0)
    bundle = {"info": {}, "balance_sheet": {"Total Assets": 1000.0, "Total Liabilities Net Minority Interest": 500.0},
              "financials": {}, "cashflow": {}}
    out = fundamentals.ohlson_o(bundle)
    assert out["oScore"] is None
    assert "no quote currency" in out["reason"].lower() or "no currency" in out["reason"].lower()


def test_get_quote_without_a_currency_is_none(monkeypatch):
    from backend.services import yfinance_service as yfs

    class _T:
        fast_info = {"last_price": 10.0, "previous_close": 9.0}

        def history(self, **kw):
            return pd.DataFrame()

        def get_info(self):
            return {}

    monkeypatch.setattr(yfs.yf, "Ticker", lambda t: _T())
    assert yfs.get_quote.__wrapped__("XYZ")["currency"] is None


def test_kpis_without_a_currency_are_none_with_a_reason():
    from backend.routers import valuation as router

    kpis = router._kpis({"currentPrice": 10.0}, None)
    assert kpis["currency"] is None
    assert kpis["unavailable"]["currency"] == "Yahoo reported no quote currency"
    assert "currency" not in router._kpis({"currentPrice": 10.0, "currency": "EUR"}, None)["unavailable"]


# ---------------------------------------------------------------------------
# Technicals carry the quote currency
# ---------------------------------------------------------------------------

def _ohlcv() -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-09-30", periods=600)
    close = pd.Series(100.0 + np.arange(600) * 0.1, index=idx)
    return pd.DataFrame(
        {"Open": close, "High": close + 1.0, "Low": close - 1.0, "Close": close, "Volume": 1_000.0}, index=idx)


def test_technicals_report_the_quote_currency(monkeypatch):
    from backend.services import technicals_service as ts
    from backend.services import yfinance_service as yfs

    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: _ohlcv())
    monkeypatch.setattr(yfs, "get_quote", lambda t: {"currency": "EUR"})
    assert ts.get_technicals.__wrapped__("SAP.DE", "1y")["currency"] == "EUR"


def test_technicals_currency_is_none_when_unknown(monkeypatch):
    from backend.services import technicals_service as ts
    from backend.services import yfinance_service as yfs

    monkeypatch.setattr(ts.yf, "download", lambda *a, **k: _ohlcv())
    monkeypatch.setattr(yfs, "get_quote", lambda t: {"currency": None})
    assert ts.get_technicals.__wrapped__("XYZ", "1y")["currency"] is None

    def boom(t):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(yfs, "get_quote", boom)
    assert ts.get_technicals.__wrapped__("XYZ", "1y")["currency"] is None
    assert ts._empty_response("XYZ", "1y")["currency"] is None
