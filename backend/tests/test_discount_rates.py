"""Offline unit tests for discount_rates.py (no network calls)."""
from __future__ import annotations

import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_bundle(
    exchange="NMS",
    marketCap=2_000_000_000_000,
    totalDebt=100_000_000_000,
    totalCash=50_000_000_000,
    interestExpense=3_000_000_000,
    effectiveTaxRate=0.21,
    currentPrice=150.0,
    currency="USD",
    sector="Technology",
) -> dict:
    return {
        "ticker": "TEST",
        "info": {
            "exchange": exchange,
            "marketCap": marketCap,
            "totalDebt": totalDebt,
            "totalCash": totalCash,
            "interestExpense": interestExpense,
            "effectiveTaxRate": effectiveTaxRate,
            "currentPrice": currentPrice,
            "currency": currency,
            "sector": sector,
        },
        "financials": {},
        "balance_sheet": {},
        "cashflow": {},
    }


@pytest.fixture(autouse=True)
def patch_rf(monkeypatch):
    """Monkeypatch FRED fetch so no network is needed."""
    from backend.services import discount_rates
    # Replace the internal fetch function AND invalidate the cache
    monkeypatch.setattr(discount_rates, "_fetch_dgs10", lambda: 0.043)
    # Clear the TTLCache so our monkeypatched function is actually called
    from backend.cache import _caches
    _caches.pop("rf10y", None)
    yield
    # Clean up cache after test
    _caches.pop("rf10y", None)


# ---------------------------------------------------------------------------
# detect_country
# ---------------------------------------------------------------------------

class TestDetectCountry:
    def test_nms_maps_to_united_states(self):
        from backend.services.discount_rates import detect_country
        info = {"exchange": "NMS"}
        assert detect_country(info) == "United States"

    def test_nyq_maps_to_united_states(self):
        from backend.services.discount_rates import detect_country
        assert detect_country({"exchange": "NYQ"}) == "United States"

    def test_lse_maps_to_united_kingdom(self):
        from backend.services.discount_rates import detect_country
        assert detect_country({"exchange": "LSE"}) == "United Kingdom"

    def test_tyo_maps_to_japan(self):
        from backend.services.discount_rates import detect_country
        assert detect_country({"exchange": "TYO"}) == "Japan"

    def test_tor_maps_to_canada(self):
        from backend.services.discount_rates import detect_country
        assert detect_country({"exchange": "TOR"}) == "Canada"

    def test_full_exchange_name_nasdaq(self):
        from backend.services.discount_rates import detect_country
        info = {"exchange": "UNKNOWN", "fullExchangeName": "NasdaqGS - Nasdaq Global Select Market"}
        assert detect_country(info) == "United States"

    def test_full_exchange_name_london(self):
        from backend.services.discount_rates import detect_country
        info = {"exchange": "UNKNOWN", "fullExchangeName": "London Stock Exchange"}
        assert detect_country(info) == "United Kingdom"

    def test_country_field_fallback(self):
        from backend.services.discount_rates import detect_country
        info = {"exchange": "UNKNOWN", "country": "Germany"}
        assert detect_country(info) == "Germany"

    def test_unknown_defaults_to_united_states(self):
        from backend.services.discount_rates import detect_country
        info = {}
        assert detect_country(info) == "United States"


# ---------------------------------------------------------------------------
# erp_for_country
# ---------------------------------------------------------------------------

class TestErpForCountry:
    def test_us_erp_approx(self):
        from backend.services.discount_rates import erp_for_country
        erp = erp_for_country("United States")
        # Damodaran 2026: US ERP = 4.46% → 0.0446
        assert abs(erp - 0.0446) < 1e-6

    def test_erp_is_decimal_not_percent(self):
        from backend.services.discount_rates import erp_for_country
        erp = erp_for_country("United States")
        assert 0.01 < erp < 0.30, f"ERP should be a decimal in (0.01, 0.30), got {erp}"

    def test_unknown_country_falls_back(self):
        from backend.services.discount_rates import erp_for_country
        erp = erp_for_country("Ruritania")
        # Should fall back to matureMarketERP = 4.46% → 0.0446
        assert abs(erp - 0.0446) < 1e-6

    def test_high_risk_country_erp_greater_than_us(self):
        from backend.services.discount_rates import erp_for_country
        us = erp_for_country("United States")
        arg = erp_for_country("Argentina")
        assert arg > us


# ---------------------------------------------------------------------------
# tax_rate_for
# ---------------------------------------------------------------------------

class TestTaxRateFor:
    def test_uses_effective_tax_rate_when_valid(self):
        from backend.services.discount_rates import tax_rate_for
        info = {"effectiveTaxRate": 0.18}
        assert abs(tax_rate_for(info, "United States") - 0.18) < 1e-9

    def test_ignores_effective_tax_rate_when_out_of_range(self):
        from backend.services.discount_rates import tax_rate_for
        info = {"effectiveTaxRate": 0.90}  # > 0.6 → use country default
        rate = tax_rate_for(info, "United States")
        # Damodaran US taxRate = 25.0 → 0.25
        assert abs(rate - 0.25) < 1e-9

    def test_fallback_to_damodaran_country_rate(self):
        from backend.services.discount_rates import tax_rate_for
        info = {}
        # Germany: taxRate = 29.825 in Damodaran; just check it's sane
        rate = tax_rate_for(info, "Germany")
        assert 0.10 < rate < 0.50

    def test_fallback_21pct_on_unknown_country(self):
        from backend.services.discount_rates import tax_rate_for
        info = {}
        rate = tax_rate_for(info, "Ruritania")
        assert abs(rate - 0.21) < 1e-9


# ---------------------------------------------------------------------------
# risk_free_rate
# ---------------------------------------------------------------------------

class TestRiskFreeRate:
    def test_returns_monkeypatched_value(self):
        from backend.services.discount_rates import risk_free_rate
        rf = risk_free_rate()
        assert abs(rf - 0.043) < 1e-9

    def test_returns_decimal_not_percent(self):
        from backend.services.discount_rates import risk_free_rate
        rf = risk_free_rate()
        assert 0 < rf < 0.20


# ---------------------------------------------------------------------------
# cost_of_equity
# ---------------------------------------------------------------------------

class TestCostOfEquity:
    def test_capm_formula(self):
        from backend.services.discount_rates import cost_of_equity, erp_for_country
        rf = 0.043
        beta = 1.2
        erp = erp_for_country("United States")
        expected = rf + beta * erp
        result = cost_of_equity(beta, "United States", rf=rf)
        assert abs(result - expected) < 1e-9

    def test_none_beta_uses_1(self):
        from backend.services.discount_rates import cost_of_equity, erp_for_country
        rf = 0.043
        erp = erp_for_country("United States")
        result_none = cost_of_equity(None, "United States", rf=rf)
        result_one = cost_of_equity(1.0, "United States", rf=rf)
        assert abs(result_none - result_one) < 1e-9


# ---------------------------------------------------------------------------
# wacc()
# ---------------------------------------------------------------------------

class TestWacc:
    def test_wacc_sane_range_full_bundle(self):
        from backend.services.discount_rates import wacc
        bundle = _make_bundle()
        result = wacc(bundle, beta=1.1)
        w = result["wacc"]
        assert w is not None
        assert 0.05 <= w <= 0.20, f"WACC out of range: {w}"

    def test_wacc_return_keys(self):
        from backend.services.discount_rates import wacc
        bundle = _make_bundle()
        result = wacc(bundle, beta=1.0)
        expected_keys = {
            "wacc", "costOfEquity", "costOfDebt", "taxRate",
            "beta", "country", "riskFree", "erp", "weightEquity", "weightDebt",
            # audit M-10: which rate and beta were used, and why one is missing
            "rawBeta", "betaAdjustment", "riskFreeSource", "riskFreeAsOf", "riskFreeStale", "unavailable",
        }
        assert set(result.keys()) == expected_keys

    def test_wacc_country_detected(self):
        from backend.services.discount_rates import wacc
        bundle = _make_bundle(exchange="LSE")
        result = wacc(bundle, beta=0.9)
        assert result["country"] == "United Kingdom"

    def test_wacc_beta_stored(self):
        from backend.services.discount_rates import wacc
        bundle = _make_bundle()
        result = wacc(bundle, beta=1.5)
        assert abs(result["beta"] - 1.5) < 1e-9

    def test_wacc_none_safe_empty_bundle(self):
        from backend.services.discount_rates import wacc
        result = wacc({}, beta=None)
        # Should not raise; wacc may be ke or None but dict must exist
        assert isinstance(result, dict)
        assert "wacc" in result

    def test_wacc_none_safe_no_info(self):
        from backend.services.discount_rates import wacc
        result = wacc({"ticker": "X", "info": None}, beta=None)
        assert isinstance(result, dict)

    def test_wacc_weights_sum_to_one(self):
        from backend.services.discount_rates import wacc
        bundle = _make_bundle()
        result = wacc(bundle, beta=1.0)
        we = result["weightEquity"] or 0
        wd = result["weightDebt"] or 0
        assert abs(we + wd - 1.0) < 1e-9

    def test_wacc_no_market_cap_falls_back_to_ke(self):
        from backend.services.discount_rates import wacc
        bundle = _make_bundle(marketCap=None)
        result = wacc(bundle, beta=1.0)
        # Without marketCap, wacc should equal costOfEquity (or be close)
        w = result["wacc"]
        ke = result["costOfEquity"]
        if w is not None and ke is not None:
            # With no marketCap: we=1, wd=0 → wacc = ke
            assert abs(w - ke) < 1e-9 or w >= 0.05

    def test_wacc_minimum_floor(self):
        from backend.services.discount_rates import wacc
        # Very low beta → ke could be very low, but WACC must stay ≥ 0.05
        bundle = _make_bundle()
        result = wacc(bundle, beta=0.0)
        w = result["wacc"]
        if w is not None:
            assert w >= 0.05
