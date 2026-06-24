"""Offline unit tests for the extended fundamentals service.

All tests use synthetic bundles — no network calls are made.
"""
from __future__ import annotations

import math
import pytest

from backend.services.fundamentals import (
    roic,
    dupont,
    piotroski_f,
    beneish_m,
    ohlson_o,
    cash_conversion_cycle,
    extended_fundamentals,
)


# ---------------------------------------------------------------------------
# Synthetic bundle helpers
# ---------------------------------------------------------------------------

def _make_bundle(
    # info
    effectiveTaxRate: float | None = 0.21,
    totalDebt: float | None = 10_000,
    totalCash: float | None = 2_000,
    totalStockholderEquity: float | None = None,
    # financials
    total_revenue: float | None = 100_000,
    gross_profit: float | None = 40_000,
    operating_income: float | None = 20_000,
    pretax_income: float | None = 18_000,
    net_income: float | None = 14_000,
    cost_of_revenue: float | None = 60_000,
    # balance_sheet
    total_assets: float | None = 80_000,
    total_liabilities: float | None = 50_000,
    current_assets: float | None = 30_000,
    current_liabilities: float | None = 15_000,
    stockholders_equity: float | None = 30_000,
    inventory: float | None = 10_000,
    accounts_receivable: float | None = 8_000,
    accounts_payable: float | None = 5_000,
    # cashflow
    operating_cf: float | None = 16_000,
) -> dict:
    """Construct a synthetic yfinance-style bundle."""
    info: dict = {}
    if effectiveTaxRate is not None:
        info["effectiveTaxRate"] = effectiveTaxRate
    if totalDebt is not None:
        info["totalDebt"] = totalDebt
    if totalCash is not None:
        info["totalCash"] = totalCash
    if totalStockholderEquity is not None:
        info["totalStockholderEquity"] = totalStockholderEquity

    fin: dict = {}
    if total_revenue is not None:
        fin["Total Revenue"] = total_revenue
    if gross_profit is not None:
        fin["Gross Profit"] = gross_profit
    if operating_income is not None:
        fin["Operating Income"] = operating_income
    if pretax_income is not None:
        fin["Pretax Income"] = pretax_income
    if net_income is not None:
        fin["Net Income"] = net_income
    if cost_of_revenue is not None:
        fin["Cost Of Revenue"] = cost_of_revenue

    bs: dict = {}
    if total_assets is not None:
        bs["Total Assets"] = total_assets
    if total_liabilities is not None:
        bs["Total Liabilities Net Minority Interest"] = total_liabilities
    if current_assets is not None:
        bs["Current Assets"] = current_assets
    if current_liabilities is not None:
        bs["Current Liabilities"] = current_liabilities
    if stockholders_equity is not None:
        bs["Stockholders Equity"] = stockholders_equity
    if totalDebt is not None:
        bs["Total Debt"] = totalDebt
    if inventory is not None:
        bs["Inventory"] = inventory
    if accounts_receivable is not None:
        bs["Accounts Receivable"] = accounts_receivable
    if accounts_payable is not None:
        bs["Accounts Payable"] = accounts_payable
    # Cash for ROIC
    if totalCash is not None:
        bs["Cash And Cash Equivalents"] = totalCash

    cf: dict = {}
    if operating_cf is not None:
        cf["Operating Cash Flow"] = operating_cf

    return {
        "ticker": "TEST",
        "info": info,
        "financials": fin,
        "balance_sheet": bs,
        "cashflow": cf,
    }


_FULL = _make_bundle()
_EMPTY = {}
_SPARSE = {"info": {}, "financials": {}, "balance_sheet": {}, "cashflow": {}}


# ===========================================================================
# ROIC
# ===========================================================================

class TestROIC:
    def test_known_case(self):
        """ROIC = NOPAT / Invested Capital with known numbers."""
        bundle = _make_bundle(
            effectiveTaxRate=0.25,
            operating_income=20_000,
            totalDebt=10_000,
            stockholders_equity=30_000,
            totalCash=2_000,
        )
        result = roic(bundle)
        nopat_expected = 20_000 * (1 - 0.25)          # 15 000
        ic_expected = 10_000 + 30_000 - 2_000          # 38 000
        roic_expected = nopat_expected / ic_expected    # ≈ 0.3947...

        assert result["nopat"] == pytest.approx(nopat_expected, rel=1e-6)
        assert result["investedCapital"] == pytest.approx(ic_expected, rel=1e-6)
        assert result["roic"] == pytest.approx(roic_expected, rel=1e-6)

    def test_fallback_tax_rate(self):
        """Missing effectiveTaxRate should fall back to 21 %."""
        bundle = _make_bundle(effectiveTaxRate=None, operating_income=10_000)
        result = roic(bundle)
        assert result["nopat"] == pytest.approx(10_000 * 0.79, rel=1e-6)

    def test_missing_ebit_returns_none_roic(self):
        bundle = _make_bundle(operating_income=None)
        result = roic(bundle)
        assert result["nopat"] is None
        assert result["roic"] is None

    def test_missing_equity_returns_none_ic(self):
        bundle = _make_bundle(stockholders_equity=None)
        # equity not in balance_sheet and not in info
        bundle["balance_sheet"].pop("Stockholders Equity", None)
        bundle["info"].pop("totalStockholderEquity", None)
        result = roic(bundle)
        assert result["investedCapital"] is None
        assert result["roic"] is None

    def test_no_raise_on_empty(self):
        result = roic(_EMPTY)
        assert result["roic"] is None
        assert result["nopat"] is None
        assert result["investedCapital"] is None

    def test_zero_invested_capital_returns_none(self):
        """Zero IC should not produce division-by-zero — returns None."""
        bundle = _make_bundle(totalDebt=0, stockholders_equity=0, totalCash=0)
        result = roic(bundle)
        # IC = 0 + 0 - 0 = 0, so ROIC cannot be computed
        assert result["roic"] is None


# ===========================================================================
# DuPont
# ===========================================================================

class TestDuPont:
    def test_three_factor_product_equals_roe(self):
        """Net Margin × Asset Turnover × Equity Multiplier should equal ROE."""
        result = dupont(_FULL)
        tf = result["threeFactor"]
        nm = tf["netMargin"]
        at = tf["assetTurnover"]
        em = tf["equityMultiplier"]
        roe = tf["roe"]

        assert None not in (nm, at, em, roe)
        assert nm * at * em == pytest.approx(roe, rel=1e-6)

    def test_five_factor_product_equals_roe(self):
        """5-factor ROE should be the product of its five components."""
        result = dupont(_FULL)
        ff = result["fiveFactor"]
        components = [
            ff["taxBurden"],
            ff["interestBurden"],
            ff["operatingMargin"],
            ff["assetTurnover"],
            ff["equityMultiplier"],
        ]
        roe = ff["roe"]
        assert None not in components
        assert roe is not None
        product = 1.0
        for c in components:
            product *= c
        assert product == pytest.approx(roe, rel=1e-6)

    def test_three_and_five_factor_roe_consistent(self):
        """Both decompositions should produce the same ROE (same underlying data)."""
        result = dupont(_FULL)
        roe3 = result["threeFactor"]["roe"]
        roe5 = result["fiveFactor"]["roe"]
        if roe3 is not None and roe5 is not None:
            assert roe3 == pytest.approx(roe5, rel=1e-4)

    def test_no_raise_on_sparse_bundle(self):
        result = dupont(_SPARSE)
        assert "threeFactor" in result
        assert "fiveFactor" in result

    def test_none_revenue_gives_none_margins(self):
        bundle = _make_bundle(total_revenue=None)
        result = dupont(bundle)
        assert result["threeFactor"]["netMargin"] is None
        assert result["fiveFactor"]["operatingMargin"] is None

    def test_dict_shape(self):
        result = dupont(_FULL)
        assert set(result.keys()) == {"threeFactor", "fiveFactor"}
        for k in ("netMargin", "assetTurnover", "equityMultiplier", "roe"):
            assert k in result["threeFactor"]
        for k in ("taxBurden", "interestBurden", "operatingMargin",
                   "assetTurnover", "equityMultiplier", "roe"):
            assert k in result["fiveFactor"]


# ===========================================================================
# Piotroski F-Score
# ===========================================================================

class TestPiotroskiF:
    def test_score_within_max_score(self):
        result = piotroski_f(_FULL)
        assert 0 <= result["score"] <= result["maxScore"]

    def test_max_score_at_most_4_from_snapshot(self):
        """Snapshot data can only evaluate 4 criteria (the non-YoY ones)."""
        result = piotroski_f(_FULL)
        assert result["maxScore"] <= 4

    def test_profitable_firm_scores_high(self):
        """A clearly profitable firm (positive NI, ROA, OCF > NI) should score 4."""
        bundle = _make_bundle(
            net_income=10_000,
            total_assets=80_000,
            operating_cf=15_000,   # OCF > NI
        )
        result = piotroski_f(bundle)
        assert result["score"] == result["maxScore"]
        assert result["criteria"]["positiveNetIncome"] is True
        assert result["criteria"]["positiveROA"] is True
        assert result["criteria"]["positiveOperatingCF"] is True
        assert result["criteria"]["accrualQuality"] is True

    def test_loss_making_firm_scores_zero(self):
        # NI=-5000, OCF=-8000 → OCF < NI (accrualQuality=False), so all 4 = False
        bundle = _make_bundle(
            net_income=-5_000,
            operating_cf=-8_000,
        )
        result = piotroski_f(bundle)
        assert result["criteria"]["positiveNetIncome"] is False
        assert result["criteria"]["positiveROA"] is False
        assert result["criteria"]["positiveOperatingCF"] is False
        assert result["criteria"]["accrualQuality"] is False
        assert result["score"] == 0

    def test_yor_criteria_are_none(self):
        """Prior-year dependent criteria must be None (not fabricated)."""
        result = piotroski_f(_FULL)
        for key in ("lowerLTDebtRatio", "higherCurrentRatio", "noNewShares",
                    "higherGrossMargin", "higherAssetTurnover"):
            assert result["criteria"][key] is None

    def test_no_raise_on_sparse(self):
        result = piotroski_f(_SPARSE)
        assert "score" in result
        assert "maxScore" in result
        assert "criteria" in result

    def test_no_raise_on_empty(self):
        result = piotroski_f(_EMPTY)
        assert result["score"] == 0
        assert result["maxScore"] == 0

    def test_criteria_has_nine_keys(self):
        result = piotroski_f(_FULL)
        assert len(result["criteria"]) == 9


# ===========================================================================
# Beneish M-Score
# ===========================================================================

class TestBeneishM:
    def test_returns_none_on_full_bundle(self):
        """Even with full data, M-Score requires prior-period → must be None."""
        result = beneish_m(_FULL)
        assert result["mScore"] is None

    def test_returns_none_on_empty(self):
        result = beneish_m(_EMPTY)
        assert result["mScore"] is None

    def test_note_key_present(self):
        result = beneish_m(_FULL)
        assert "note" in result
        assert len(result["note"]) > 10

    def test_no_raise(self):
        for bundle in (_FULL, _SPARSE, _EMPTY):
            result = beneish_m(bundle)
            assert isinstance(result, dict)


# ===========================================================================
# Ohlson O-Score
# ===========================================================================

class TestOhlsonO:
    def test_healthy_firm_low_prob_default(self):
        """A firm with low debt ratio and positive earnings should have
        lower probability of default than a distressed firm."""
        healthy = _make_bundle(
            total_assets=100_000,
            total_liabilities=20_000,   # TLTA = 0.20
            net_income=15_000,
            operating_cf=18_000,
            current_assets=40_000,
            current_liabilities=10_000,
        )
        distressed = _make_bundle(
            total_assets=100_000,
            total_liabilities=95_000,   # TLTA = 0.95 (near insolvent)
            net_income=-8_000,
            operating_cf=-5_000,
            current_assets=10_000,
            current_liabilities=30_000,
        )
        r_healthy = ohlson_o(healthy)
        r_distressed = ohlson_o(distressed)

        assert r_healthy["probDefault"] is not None
        assert r_distressed["probDefault"] is not None
        assert r_healthy["probDefault"] < r_distressed["probDefault"]

    def test_prob_default_in_unit_interval(self):
        result = ohlson_o(_FULL)
        pd_val = result["probDefault"]
        if pd_val is not None:
            assert 0.0 <= pd_val <= 1.0

    def test_none_on_missing_total_assets(self):
        bundle = _make_bundle()
        bundle["balance_sheet"].pop("Total Assets", None)
        result = ohlson_o(bundle)
        assert result["oScore"] is None
        assert result["probDefault"] is None

    def test_no_raise_on_empty(self):
        result = ohlson_o(_EMPTY)
        assert result["oScore"] is None
        assert result["probDefault"] is None

    def test_no_raise_on_sparse(self):
        result = ohlson_o(_SPARSE)
        assert isinstance(result, dict)

    def test_dict_shape(self):
        result = ohlson_o(_FULL)
        assert set(result.keys()) == {"oScore", "probDefault"}

    def test_oscore_is_float_or_none(self):
        result = ohlson_o(_FULL)
        assert result["oScore"] is None or isinstance(result["oScore"], float)


# ===========================================================================
# Cash Conversion Cycle
# ===========================================================================

class TestCCC:
    def test_known_case(self):
        """Verify CCC = DSO + DIO - DPO with controlled numbers."""
        bundle = _make_bundle(
            total_revenue=100_000,
            cost_of_revenue=60_000,
            accounts_receivable=8_000,
            inventory=10_000,
            accounts_payable=5_000,
        )
        result = cash_conversion_cycle(bundle)
        dso_exp = 8_000 / 100_000 * 365      # 29.2
        dio_exp = 10_000 / 60_000 * 365      # 60.833...
        dpo_exp = 5_000 / 60_000 * 365       # 30.416...
        ccc_exp = dso_exp + dio_exp - dpo_exp

        assert result["dso"] == pytest.approx(dso_exp, rel=1e-5)
        assert result["dio"] == pytest.approx(dio_exp, rel=1e-5)
        assert result["dpo"] == pytest.approx(dpo_exp, rel=1e-5)
        assert result["ccc"] == pytest.approx(ccc_exp, rel=1e-5)

    def test_no_inventory_returns_none_dio(self):
        bundle = _make_bundle(inventory=None)
        result = cash_conversion_cycle(bundle)
        assert result["dio"] is None

    def test_ccc_without_inventory_uses_dso_minus_dpo(self):
        """Service-firm proxy: CCC = DSO - DPO when inventory is None."""
        bundle = _make_bundle(inventory=None)
        result = cash_conversion_cycle(bundle)
        if result["dso"] is not None and result["dpo"] is not None:
            assert result["ccc"] == pytest.approx(
                result["dso"] - result["dpo"], rel=1e-6
            )

    def test_missing_revenue_gives_none_dso(self):
        bundle = _make_bundle(total_revenue=None)
        result = cash_conversion_cycle(bundle)
        assert result["dso"] is None

    def test_no_raise_on_empty(self):
        result = cash_conversion_cycle(_EMPTY)
        assert result["ccc"] is None
        assert result["dso"] is None

    def test_dict_shape(self):
        result = cash_conversion_cycle(_FULL)
        assert set(result.keys()) == {"ccc", "dso", "dio", "dpo"}


# ===========================================================================
# extended_fundamentals — aggregator
# ===========================================================================

class TestExtendedFundamentals:
    _TOP_KEYS = {"roic", "dupont", "piotroski", "beneish", "ohlson",
                 "cashConversionCycle"}

    def test_empty_bundle_does_not_raise(self):
        result = extended_fundamentals({})
        assert isinstance(result, dict)

    def test_top_level_keys_always_present(self):
        for bundle in ({}, _SPARSE, _FULL):
            result = extended_fundamentals(bundle)
            assert set(result.keys()) == self._TOP_KEYS

    def test_empty_bundle_all_sub_dicts_present(self):
        """Even with an empty bundle, each key should be a dict (not None)."""
        result = extended_fundamentals({})
        for key in self._TOP_KEYS:
            assert result[key] is not None, f"Key '{key}' is None on empty bundle"
            assert isinstance(result[key], dict)

    def test_roic_sub_shape(self):
        result = extended_fundamentals(_FULL)
        assert set(result["roic"].keys()) == {"roic", "nopat", "investedCapital"}

    def test_dupont_sub_shape(self):
        result = extended_fundamentals(_FULL)
        assert set(result["dupont"].keys()) == {"threeFactor", "fiveFactor"}

    def test_piotroski_sub_shape(self):
        result = extended_fundamentals(_FULL)
        pf = result["piotroski"]
        assert "score" in pf and "maxScore" in pf and "criteria" in pf

    def test_beneish_always_none(self):
        result = extended_fundamentals(_FULL)
        assert result["beneish"]["mScore"] is None

    def test_ohlson_sub_shape(self):
        result = extended_fundamentals(_FULL)
        assert set(result["ohlson"].keys()) == {"oScore", "probDefault"}

    def test_ccc_sub_shape(self):
        result = extended_fundamentals(_FULL)
        assert set(result["cashConversionCycle"].keys()) == {"ccc", "dso", "dio", "dpo"}

    def test_full_bundle_computes_values(self):
        """With a rich bundle, the non-history-limited metrics should be non-None."""
        result = extended_fundamentals(_FULL)
        assert result["roic"]["roic"] is not None
        assert result["dupont"]["threeFactor"]["roe"] is not None
        assert result["piotroski"]["score"] is not None
        assert result["ohlson"]["oScore"] is not None
        assert result["cashConversionCycle"]["ccc"] is not None
