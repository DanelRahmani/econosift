"""Offline unit tests for the two-stage DCF engine."""
from __future__ import annotations

import pytest
from backend.services.dcf_engine import two_stage_dcf


def _make_bundle(
    freeCashflow=5_000_000_000,
    sharesOutstanding=1_000_000_000,
    totalDebt=10_000_000_000,
    totalCash=20_000_000_000,
    currentPrice=150.0,
    currency="USD",
) -> dict:
    """Synthetic bundle that mimics yfinance_service.get_info() output."""
    return {
        "ticker": "TEST",
        "info": {
            "freeCashflow": freeCashflow,
            "sharesOutstanding": sharesOutstanding,
            "totalDebt": totalDebt,
            "totalCash": totalCash,
            "currentPrice": currentPrice,
            "currency": currency,
        },
        "financials": {},
        "balance_sheet": {},
        "cashflow": {},
    }


class TestKnownGoodCase:
    """Base case with valid inputs — should return a positive intrinsic value."""

    def setup_method(self):
        self.bundle = _make_bundle()
        self.result = two_stage_dcf(
            self.bundle,
            fcf_growth=0.08,
            terminal_growth=0.025,
            wacc=0.09,
            stage1_years=10,
        )

    def test_not_locked(self):
        assert self.result["locked"] is False

    def test_intrinsic_value_positive(self):
        iv = self.result["intrinsicValue"]
        assert iv is not None
        assert iv > 0

    def test_ticker_in_result(self):
        assert self.result["ticker"] == "TEST"

    def test_currency_in_result(self):
        assert self.result["currency"] == "USD"

    def test_spot_price_present(self):
        assert self.result["spotPrice"] == 150.0

    def test_upside_pct_present(self):
        assert self.result["upsidePct"] is not None

    def test_as_of_format(self):
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", self.result["asOf"])

    def test_inputs_keys(self):
        inp = self.result["inputs"]
        expected_keys = {"ttmFcf", "shares", "netDebt", "fcfGrowth", "terminalGrowth", "wacc", "stage1Years",
                         "fcfBasis", "fcfPeriod", "statementCurrency", "fxRate"}
        assert set(inp.keys()) == expected_keys

    def test_inputs_values(self):
        inp = self.result["inputs"]
        assert inp["ttmFcf"] == 5_000_000_000
        assert inp["shares"] == 1_000_000_000
        assert inp["netDebt"] == -10_000_000_000  # 10B debt - 20B cash
        assert inp["fcfGrowth"] == 0.08
        assert inp["terminalGrowth"] == 0.025
        assert inp["wacc"] == 0.09
        assert inp["stage1Years"] == 10

    def test_scenarios_has_three_entries(self):
        scenarios = self.result["scenarios"]
        assert len(scenarios) == 3

    def test_scenarios_labels(self):
        labels = [s["scenario"] for s in self.result["scenarios"]]
        assert labels == ["Bear", "Base", "Bull"]

    def test_scenarios_have_required_keys(self):
        required = {"scenario", "fcfGrowth", "wacc", "intrinsicValue", "upsidePct"}
        for s in self.result["scenarios"]:
            assert required.issubset(set(s.keys()))

    def test_bear_has_higher_wacc_lower_growth(self):
        base = self.result["scenarios"][1]
        bear = self.result["scenarios"][0]
        assert bear["wacc"] > base["wacc"]
        assert bear["fcfGrowth"] < base["fcfGrowth"]

    def test_bull_has_lower_wacc_higher_growth(self):
        base = self.result["scenarios"][1]
        bull = self.result["scenarios"][2]
        assert bull["wacc"] < base["wacc"]
        assert bull["fcfGrowth"] > base["fcfGrowth"]

    def test_scenario_ordering_bear_lt_base_lt_bull(self):
        """Bear intrinsic < Base < Bull (directionally)."""
        bear_iv = self.result["scenarios"][0]["intrinsicValue"]
        base_iv = self.result["scenarios"][1]["intrinsicValue"]
        bull_iv = self.result["scenarios"][2]["intrinsicValue"]
        assert bear_iv is not None and base_iv is not None and bull_iv is not None
        assert bear_iv < base_iv < bull_iv

    def test_sensitivity_grid_is_7x7(self):
        sens = self.result["sensitivity"]
        assert len(sens["fcfGrowthAxis"]) == 7
        assert len(sens["waccAxis"]) == 7
        assert len(sens["grid"]) == 7
        for row in sens["grid"]:
            assert len(row) == 7

    def test_sensitivity_axes_centered_on_inputs(self):
        sens = self.result["sensitivity"]
        # Middle element (index 3) should equal base inputs
        assert sens["fcfGrowthAxis"][3] == pytest.approx(0.08, abs=1e-6)
        assert sens["waccAxis"][3] == pytest.approx(0.09, abs=1e-6)

    def test_sensitivity_axis_steps(self):
        sens = self.result["sensitivity"]
        fg = sens["fcfGrowthAxis"]
        wc = sens["waccAxis"]
        for i in range(1, 7):
            assert fg[i] - fg[i - 1] == pytest.approx(0.01, abs=1e-9)
            assert wc[i] - wc[i - 1] == pytest.approx(0.005, abs=1e-9)

    def test_sensitivity_grid_values_are_positive_near_center(self):
        grid = self.result["sensitivity"]["grid"]
        center = grid[3][3]
        assert center is not None
        assert center > 0


class TestLockedCases:
    """All locked cases must return intrinsicValue=None and locked=True without raising."""

    def test_missing_fcf(self):
        bundle = _make_bundle(freeCashflow=None)
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None
        assert "reason" in result

    def test_missing_shares(self):
        bundle = _make_bundle(sharesOutstanding=None)
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None

    def test_zero_shares(self):
        bundle = _make_bundle(sharesOutstanding=0)
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None

    def test_wacc_equal_to_terminal_growth(self):
        bundle = _make_bundle()
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.05, wacc=0.05)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None

    def test_wacc_less_than_terminal_growth(self):
        bundle = _make_bundle()
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.06, wacc=0.04)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None

    def test_no_raise_on_empty_info(self):
        """Even with a completely empty bundle, should never raise."""
        bundle = {"ticker": "EMPTY", "info": {}, "financials": {}, "balance_sheet": {}, "cashflow": {}}
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None

    def test_no_raise_on_missing_info_key(self):
        """Bundle without 'info' key should not raise."""
        bundle = {"ticker": "NOINFO"}
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None


class TestEdgeCases:
    """Numeric edge cases that should still produce valid results."""

    def test_negative_fcf_is_locked_not_a_negative_value(self):
        """Audit M-02: FCF <= 0 cannot be capitalised; lock instead of printing a negative price."""
        bundle = _make_bundle(freeCashflow=-1_000_000_000, totalCash=50_000_000_000)
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None
        assert result["reason"] == "not meaningful: free cash flow ≤ 0"
        assert result["scenarios"] == []

    def test_zero_fcf_is_locked(self):
        result = two_stage_dcf(_make_bundle(freeCashflow=0), fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["reason"] == "not meaningful: free cash flow ≤ 0"

    def test_no_spot_price_still_works(self):
        """Missing spot price: upside is None but intrinsic should still compute."""
        bundle = _make_bundle(currentPrice=None)
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is False
        assert result["intrinsicValue"] is not None
        assert result["upsidePct"] is None
        assert result["spotPrice"] is None

    def test_stage1_years_param(self):
        """stage1_years should be reflected in inputs."""
        bundle = _make_bundle()
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09, stage1_years=5)
        assert result["inputs"]["stage1Years"] == 5
        assert result["locked"] is False


class TestBankLock:
    """Audit M-02: a bank's debt and cash are operating balances, so a free-cash-flow DCF is meaningless."""

    @staticmethod
    def _bank(fcf):
        b = _make_bundle(freeCashflow=fcf)
        b["info"]["sector"] = "Financial Services"
        b["info"]["industry"] = "Banks - Diversified"
        return b

    def test_bank_with_negative_fcf_locked_with_exact_reason(self):
        # JPM-like: FCF -147.8bn.
        result = two_stage_dcf(self._bank(-147_782_000_000), fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["reason"] == "not meaningful for banks"
        assert result["intrinsicValue"] is None
        assert result["upsidePct"] is None
        assert result["scenarios"] == []

    def test_bank_with_positive_fcf_also_locked(self):
        result = two_stage_dcf(self._bank(5_000_000_000), fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        assert result["locked"] is True
        assert result["reason"] == "not meaningful for banks"

    def test_non_bank_financial_company_is_not_locked(self):
        # Visa-like: Financial Services but "Credit Services" - FCF is real.
        b = _make_bundle()
        b["info"]["sector"] = "Financial Services"
        b["info"]["industry"] = "Credit Services"
        assert two_stage_dcf(b, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)["locked"] is False


class TestNonPositiveEquity:
    def test_single_dcf_returns_none_when_net_debt_exceeds_ev(self):
        from backend.services.dcf_engine import _single_dcf
        # 1 year, g=0, terminal g=0, wacc 10%: PV(year 1) = 1e9/1.1 = 0.909e9;
        # TV = 1e9*1/0.10 = 1e10, PV(TV) = 9.091e9; EV = 1e10.
        # Equity = 1e10 - 2e10 = -1e10; per share (1e9 shares) = -10 -> not meaningful.
        assert _single_dcf(1e9, 0.0, 0.0, 0.10, 1, 2e10, 1e9) is None

    def test_two_stage_locks_when_equity_value_not_positive(self):
        bundle = _make_bundle(freeCashflow=1_000_000_000, totalDebt=2_000_000_000_000, totalCash=0)
        result = two_stage_dcf(bundle, fcf_growth=0.0, terminal_growth=0.0, wacc=0.10, stage1_years=1)
        assert result["locked"] is True
        assert result["intrinsicValue"] is None
        assert result["reason"] == "not meaningful: equity value ≤ 0 after net debt"


def test_fcf_period_is_labelled_from_its_source():
    """P3-26: when Yahoo has no trailing freeCashflow, get_info fills it from the
    annual statement and marks it _fcfPeriod = "FY2025"; the DCF must say FY2025,
    not TTM. A real trailing figure (no marker) stays TTM."""
    annual = _make_bundle()
    annual["info"]["_fcfPeriod"] = "FY2025"
    inp = two_stage_dcf(annual, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)["inputs"]
    assert inp["fcfPeriod"] == "FY2025"
    assert "TTM" not in inp["fcfBasis"] and "FY2025" in inp["fcfBasis"]
    assert two_stage_dcf(_make_bundle(), fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)["inputs"]["fcfPeriod"] == "TTM"
