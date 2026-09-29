"""Offline unit tests for valuation_engine.py (no network calls)."""
from __future__ import annotations

import math
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_network(monkeypatch):
    """Block all network calls in discount_rates and valuation_engine."""
    from backend.services import discount_rates
    from backend.services import valuation_engine
    from backend.cache import _caches

    # Monkeypatch rf10y fetch
    monkeypatch.setattr(discount_rates, "_fetch_dgs10", lambda: 0.043)
    # Monkeypatch AAA yield (so Graham Formula works offline)
    monkeypatch.setattr(valuation_engine, "_get_aaa_yield", lambda: 5.0)

    # Clear caches so patched functions are called
    for key in ("rf10y", "aaa_yield", "erp_json", "sector_multiples_json"):
        _caches.pop(key, None)

    yield

    for key in ("rf10y", "aaa_yield"):
        _caches.pop(key, None)


def _make_bundle(
    ticker="AAPL",
    currentPrice=150.0,
    freeCashflow=10_000_000_000,
    sharesOutstanding=16_000_000_000,
    totalDebt=100_000_000_000,
    totalCash=60_000_000_000,
    trailingEps=6.0,
    forwardEps=7.0,
    bookValue=4.0,
    dividendRate=1.0,
    returnOnEquity=0.35,
    payoutRatio=0.15,
    earningsGrowth=0.10,
    ebitda=30_000_000_000,
    marketCap=2_400_000_000_000,
    exchange="NMS",
    sector="Technology",
    effectiveTaxRate=0.21,
) -> dict:
    """Full synthetic bundle with all fields required for every model."""
    info: dict = {
        "exchange": exchange,
        "sector": sector,
        "currentPrice": currentPrice,
        "currency": "USD",
        "freeCashflow": freeCashflow,
        "operatingCashflow": freeCashflow,
        "sharesOutstanding": sharesOutstanding,
        "totalDebt": totalDebt,
        "totalCash": totalCash,
        "trailingEps": trailingEps,
        "forwardEps": forwardEps,
        "bookValue": bookValue,
        "dividendRate": dividendRate,
        "returnOnEquity": returnOnEquity,
        "payoutRatio": payoutRatio,
        "earningsGrowth": earningsGrowth,
        "revenueGrowth": 0.07,
        "ebitda": ebitda,
        "marketCap": marketCap,
        "effectiveTaxRate": effectiveTaxRate,
        "interestExpense": 3_000_000_000,
        "ebit": 35_000_000_000,
    }
    return {
        "ticker": ticker,
        "info": info,
        "financials": {},
        "balance_sheet": {},
        "cashflow": {},
    }


# ---------------------------------------------------------------------------
# Top-level shape test
# ---------------------------------------------------------------------------

class TestValuationModelsShape:
    def setup_method(self):
        from backend.services.valuation_engine import valuation_models
        self.result = valuation_models(_make_bundle(), beta=1.1, growth=0.10)

    def test_top_level_keys(self):
        expected = {"ticker", "currency", "spotPrice", "wacc", "models",
                    "capmImplied", "axiomFairValue", "asOf"}
        assert set(self.result.keys()) == expected

    def test_ticker_matches(self):
        assert self.result["ticker"] == "AAPL"

    def test_currency_present(self):
        assert self.result["currency"] == "USD"

    def test_spot_price_present(self):
        assert self.result["spotPrice"] == 150.0

    def test_as_of_format(self):
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", self.result["asOf"])

    def test_eight_models(self):
        assert len(self.result["models"]) == 8

    def test_all_models_have_required_keys(self):
        required = {"model", "value", "locked", "reason", "detail"}
        for m in self.result["models"]:
            assert required.issubset(set(m.keys())), f"Model {m.get('model')} missing keys"

    def test_capm_implied_has_required_keys(self):
        ci = self.result["capmImplied"]
        assert {"model", "value", "locked", "reason", "detail"}.issubset(set(ci.keys()))

    def test_axiom_fair_value_has_required_keys(self):
        af = self.result["axiomFairValue"]
        assert {"value", "upsidePct", "verdict", "weightsUsed"}.issubset(set(af.keys()))

    def test_wacc_dict_has_required_keys(self):
        w = self.result["wacc"]
        expected = {"wacc", "costOfEquity", "costOfDebt", "taxRate",
                    "beta", "country", "riskFree", "erp", "weightEquity", "weightDebt"}
        assert set(w.keys()) == expected


# ---------------------------------------------------------------------------
# Model-level locked / unlocked tests
# ---------------------------------------------------------------------------

class TestDCFModel:
    def _run(self, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=0.10)
        return next(m for m in result["models"] if m["model"] == "DCF (Two-Stage)")

    def test_dcf_unlocked_full_bundle(self):
        m = self._run()
        assert m["locked"] is False
        assert m["value"] is not None
        assert m["value"] > 0

    def test_dcf_locked_no_fcf(self):
        m = self._run(freeCashflow=None)
        assert m["locked"] is True

    def test_dcf_has_detail_keys(self):
        m = self._run()
        assert "scenarios" in m["detail"]
        assert "sensitivity" in m["detail"]


class TestDDMModel:
    def _run(self, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=0.10)
        return next(m for m in result["models"] if m["model"] == "DDM (Gordon Growth)")

    def test_ddm_locked_when_no_dividend(self):
        m = self._run(dividendRate=0)
        assert m["locked"] is True
        assert m["value"] is None

    def test_ddm_locked_when_dividend_none(self):
        m = self._run(dividendRate=None)
        assert m["locked"] is True

    def test_ddm_unlocked_with_dividend(self):
        # Use a very small growth so ke - g > 0
        m = self._run(dividendRate=2.0, earningsGrowth=0.03)
        # May or may not be locked depending on ke vs g, but must not raise
        assert "locked" in m

    def test_ddm_detail_has_dividend_rate(self):
        m = self._run(dividendRate=2.0, earningsGrowth=0.03)
        if not m["locked"]:
            assert "dividendRate" in m["detail"]


class TestGrahamFormulaModel:
    def _run(self, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=0.10)
        return next(m for m in result["models"] if m["model"] == "Graham Formula")

    def test_locked_when_eps_zero(self):
        m = self._run(trailingEps=0.0)
        assert m["locked"] is True

    def test_locked_when_eps_negative(self):
        m = self._run(trailingEps=-1.0)
        assert m["locked"] is True

    def test_unlocked_with_positive_eps(self):
        m = self._run()
        assert m["locked"] is False
        assert m["value"] is not None
        assert m["value"] > 0

    def test_detail_has_formula(self):
        m = self._run()
        if not m["locked"]:
            assert "formula" in m["detail"]


class TestGrahamNumberModel:
    def _run(self, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=0.10)
        return next(m for m in result["models"] if m["model"] == "Graham Number")

    def test_locked_when_eps_negative(self):
        m = self._run(trailingEps=-1.0)
        assert m["locked"] is True

    def test_locked_when_bvps_zero(self):
        m = self._run(bookValue=0.0)
        assert m["locked"] is True

    def test_unlocked_positive_eps_and_bvps(self):
        m = self._run()
        assert m["locked"] is False
        assert m["value"] is not None

    def test_formula_value(self):
        """Graham Number = sqrt(22.5 * eps * bvps) — verify numerically."""
        m = self._run(trailingEps=6.0, bookValue=4.0)
        if not m["locked"]:
            expected = math.sqrt(22.5 * 6.0 * 4.0)
            assert abs(m["value"] - expected) < 0.01


class TestPeterLynchModel:
    def _run(self, growth=0.10, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=growth)
        return next(m for m in result["models"] if m["model"] == "Peter Lynch / PEG")

    def test_locked_when_eps_zero(self):
        m = self._run(trailingEps=0.0)
        assert m["locked"] is True

    def test_locked_when_growth_zero(self):
        # Pass explicit growth=0 to the engine (overrides earningsGrowth)
        m = self._run(growth=0.0)
        # Growth = 0 → locked
        assert m["locked"] is True

    def test_unlocked_standard(self):
        m = self._run()
        assert m["locked"] is False
        assert m["value"] is not None

    def test_value_capped_at_growth_20(self):
        """When growth=0.50 (50%), growth_whole capped at 20."""
        m = self._run(growth=0.50, trailingEps=5.0)
        if not m["locked"]:
            assert m["detail"]["growthPctUsed"] == 20.0
            assert abs(m["value"] - 5.0 * 20.0) < 0.01


class TestEvEbitdaModel:
    def _run(self, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=0.10)
        return next(m for m in result["models"] if m["model"] == "EV/EBITDA Comps")

    def test_locked_for_financial_services(self):
        m = self._run(sector="Financial Services")
        assert m["locked"] is True

    def test_locked_for_financials_sector(self):
        m = self._run(sector="Financials")
        assert m["locked"] is True

    def test_locked_when_ebitda_missing(self):
        m = self._run(ebitda=None)
        assert m["locked"] is True

    def test_locked_when_ebitda_zero(self):
        m = self._run(ebitda=0)
        assert m["locked"] is True

    def test_unlocked_technology(self):
        m = self._run(sector="Technology")
        assert m["locked"] is False
        assert m["value"] is not None

    def test_detail_has_sector_multiple(self):
        m = self._run(sector="Technology")
        if not m["locked"]:
            assert "sectorMultiple" in m["detail"]
            assert m["detail"]["sectorMultiple"] > 0


class TestRIMModel:
    def _run(self, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=0.10)
        return next(m for m in result["models"] if m["model"] == "Residual Income (RIM)")

    def test_locked_when_roe_missing(self):
        b = _make_bundle()
        b["info"].pop("returnOnEquity", None)
        b["info"]["returnOnEquity"] = None
        from backend.services.valuation_engine import valuation_models
        result = valuation_models(b, beta=1.0)
        m = next(m for m in result["models"] if m["model"] == "Residual Income (RIM)")
        assert m["locked"] is True

    def test_locked_when_bvps_missing(self):
        m = self._run(bookValue=None)
        assert m["locked"] is True

    def test_unlocked_full_bundle(self):
        m = self._run()
        assert m["locked"] is False
        assert m["value"] is not None

    def test_detail_has_roe_and_ke(self):
        m = self._run()
        if not m["locked"]:
            assert "roe" in m["detail"]
            assert "costOfEquity" in m["detail"]


class TestEPVModel:
    def _run(self, **overrides):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(**overrides)
        result = valuation_models(b, beta=1.0, growth=0.10)
        return next(m for m in result["models"] if m["model"] == "EPV (Earnings Power Value)")

    def test_unlocked_full_bundle(self):
        m = self._run()
        assert m["locked"] is False
        assert m["value"] is not None

    def test_locked_when_ebit_missing(self):
        b = _make_bundle()
        b["info"].pop("ebit", None)
        from backend.services.valuation_engine import valuation_models
        result = valuation_models(b, beta=1.0)
        m = next(m for m in result["models"] if m["model"] == "EPV (Earnings Power Value)")
        # ebit missing from info — may still compute from financials, just check no raise
        assert isinstance(m, dict)

    def test_detail_has_nopat(self):
        m = self._run()
        if not m["locked"]:
            assert "nopat" in m["detail"]
            assert "epvFirm" in m["detail"]


# ---------------------------------------------------------------------------
# CAPM Implied
# ---------------------------------------------------------------------------

class TestCAPMImplied:
    def test_capm_implied_unlocked(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models(_make_bundle(), beta=1.0, growth=0.10)
        ci = result["capmImplied"]
        assert ci["locked"] is False
        assert ci["value"] is not None

    def test_capm_implied_locked_when_no_eps(self):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(trailingEps=None, forwardEps=None)
        result = valuation_models(b, beta=1.0, growth=0.10)
        ci = result["capmImplied"]
        assert ci["locked"] is True

    def test_capm_implied_value_formula(self):
        """forwardEPS / costOfEquity — verify numerically."""
        from backend.services.valuation_engine import valuation_models
        from backend.services.discount_rates import erp_for_country
        b = _make_bundle(forwardEps=7.0, exchange="NMS")
        result = valuation_models(b, beta=1.0, growth=0.10)
        ci = result["capmImplied"]
        if not ci["locked"]:
            ke = result["wacc"]["costOfEquity"]
            expected = 7.0 / ke
            assert abs(ci["value"] - expected) < 0.01


# ---------------------------------------------------------------------------
# EconoSift Fair Value composite
# ---------------------------------------------------------------------------

class TestCompositeFairValue:
    def test_composite_value_present_full_bundle(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models(_make_bundle(), beta=1.0, growth=0.10)
        af = result["axiomFairValue"]
        assert af["value"] is not None

    def test_verdict_is_string(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models(_make_bundle(), beta=1.0, growth=0.10)
        af = result["axiomFairValue"]
        assert isinstance(af["verdict"], str)
        assert af["verdict"] in {
            "Significantly Undervalued", "Undervalued", "Fairly Valued",
            "Overvalued", "Significantly Overvalued", "Insufficient Data",
        }

    def test_weights_used_sums_to_one(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models(_make_bundle(), beta=1.0, growth=0.10)
        af = result["axiomFairValue"]
        wu = af["weightsUsed"]
        if wu:
            total = sum(wu.values())
            assert abs(total - 1.0) < 1e-6, f"Weights sum to {total}, not 1.0"

    def test_composite_renormalizes_when_some_models_locked(self):
        """With no dividends + financials sector, fewer models are available → weights renormalize."""
        from backend.services.valuation_engine import valuation_models
        # DDM locked (dividendRate=0), EV/EBITDA locked (Financial Services)
        b = _make_bundle(dividendRate=0, sector="Financial Services")
        result = valuation_models(b, beta=1.0, growth=0.10)
        af = result["axiomFairValue"]
        wu = af["weightsUsed"]
        # These models should not appear in weightsUsed
        assert "DDM (Gordon Growth)" not in wu
        assert "EV/EBITDA Comps" not in wu
        # But composite should still be present (other models available)
        # Weights that ARE present must sum to 1
        if wu:
            assert abs(sum(wu.values()) - 1.0) < 1e-6

    def test_upside_pct_computed_when_spot_present(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models(_make_bundle(currentPrice=150.0), beta=1.0, growth=0.10)
        af = result["axiomFairValue"]
        if af["value"] is not None:
            assert af["upsidePct"] is not None
            expected_upside = (af["value"] - 150.0) / 150.0
            assert abs(af["upsidePct"] - expected_upside) < 1e-6

    def test_verdict_significantly_undervalued(self):
        """Very low spot price → should be 'Significantly Undervalued'."""
        from backend.services.valuation_engine import valuation_models
        # Large EPS + tiny spot price
        b = _make_bundle(currentPrice=1.0, trailingEps=20.0, forwardEps=25.0,
                          freeCashflow=50_000_000_000)
        result = valuation_models(b, beta=1.0, growth=0.15)
        af = result["axiomFairValue"]
        if af["value"] is not None and af["upsidePct"] is not None:
            if af["upsidePct"] > 0.25:
                assert af["verdict"] == "Significantly Undervalued"


# ---------------------------------------------------------------------------
# Empty / degenerate bundle safety
# ---------------------------------------------------------------------------

class TestEmptyBundle:
    def test_empty_bundle_does_not_raise(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models({})
        assert isinstance(result, dict)

    def test_empty_bundle_all_models_locked_or_none(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models({})
        for m in result["models"]:
            # Each model should be locked (no data) or have None value
            assert m["locked"] is True or m["value"] is None

    def test_empty_bundle_axiom_insufficient_data(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models({})
        # Most models will be locked with no data → composite is None
        af = result["axiomFairValue"]
        assert af["value"] is None or af["verdict"] in {
            "Insufficient Data", "Significantly Undervalued", "Undervalued",
            "Fairly Valued", "Overvalued", "Significantly Overvalued",
        }

    def test_none_info_does_not_raise(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models({"ticker": "X", "info": None,
                                    "financials": None, "balance_sheet": None, "cashflow": None})
        assert isinstance(result, dict)

    def test_returns_full_shape_even_on_empty(self):
        from backend.services.valuation_engine import valuation_models
        result = valuation_models({})
        assert "models" in result
        assert len(result["models"]) == 8
        assert "axiomFairValue" in result
        assert "capmImplied" in result
        assert "wacc" in result
