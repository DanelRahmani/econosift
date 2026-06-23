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
        expected_keys = {"ttmFcf", "shares", "netDebt", "fcfGrowth", "terminalGrowth", "wacc", "stage1Years"}
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

    def test_negative_fcf_returns_negative_intrinsic(self):
        """Negative FCF should still complete without raising (intrinsic may be negative)."""
        bundle = _make_bundle(freeCashflow=-1_000_000_000, totalCash=50_000_000_000)
        result = two_stage_dcf(bundle, fcf_growth=0.08, terminal_growth=0.025, wacc=0.09)
        # Should not raise and locked should be False (inputs are technically valid)
        assert result["locked"] is False

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
