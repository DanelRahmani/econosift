"""Phase 59: net debt incl. short-term investments, D/E percent fallback, labelled bases."""
import pytest

from backend.services import metrics


def _bundle(bs, info=None, cf=None):
    return {
        "ticker": "T",
        "info": {"currency": "USD", "financialCurrency": "USD", "industry": "Software - Application",
                 **(info or {})},
        "financials": {"Total Revenue": 1_000.0, "Net Income": 100.0, "EBITDA": 200.0},
        "balance_sheet": {"Total Assets": 5_000.0, "Stockholders Equity": 1_000.0, **bs},
        "cashflow": cf or {},
    }


def test_net_debt_prefers_cash_plus_sti_line():
    # debt 600, "Cash Cash Equivalents And Short Term Investments" 400 (already includes the 100 cash
    # and 300 STI -> never add them again): (600 - 400) / 200 = 1.0
    out = metrics.compute_ratios(_bundle({
        "Total Debt": 600.0, "Cash And Cash Equivalents": 100.0, "Other Short Term Investments": 300.0,
        "Cash Cash Equivalents And Short Term Investments": 400.0}))
    assert out["leverage"]["netDebtEbitda"] == pytest.approx(1.0)


def test_net_debt_adds_other_short_term_investments_when_no_combined_line():
    # (600 - (100 + 300)) / 200 = 1.0
    out = metrics.compute_ratios(_bundle({
        "Total Debt": 600.0, "Cash And Cash Equivalents": 100.0, "Other Short Term Investments": 300.0}))
    assert out["leverage"]["netDebtEbitda"] == pytest.approx(1.0)


def test_net_debt_cash_only_unchanged():
    # (600 - 100) / 200 = 2.5
    out = metrics.compute_ratios(_bundle({"Total Debt": 600.0, "Cash And Cash Equivalents": 100.0}))
    assert out["leverage"]["netDebtEbitda"] == pytest.approx(2.5)


def test_debt_to_equity_info_fallback_is_percent():
    # no balance-sheet total debt: Yahoo reports 150.0 (percent) -> 1.5
    out = metrics.compute_ratios(_bundle({}, info={"debtToEquity": 150.0}))
    assert out["leverage"]["debtToEquity"] == pytest.approx(1.5)


def test_debt_to_equity_statement_path_unchanged():
    # 600 / 1000 = 0.6
    out = metrics.compute_ratios(_bundle({"Total Debt": 600.0}))
    assert out["leverage"]["debtToEquity"] == pytest.approx(0.6)


def test_roe_is_labelled_fiscal_year():
    out = metrics.compute_ratios(_bundle({}))
    assert out["profitability"]["roe"] == pytest.approx(0.1)   # 100 / 1000
    assert out["basis"]["roe"].startswith("FY")


def test_fcf_margin_basis_statement_vs_ttm_fallback():
    stmt = metrics.compute_ratios(_bundle({}, cf={"Free Cash Flow": 50.0}))
    assert stmt["basis"]["fcfMargin"].startswith("FY")
    ttm = metrics.compute_ratios(_bundle({}, info={"freeCashflow": 80.0, "totalRevenue": 1_000.0}))
    assert ttm["profitability"]["fcfMargin"] == pytest.approx(0.08)
    assert ttm["basis"]["fcfMargin"].startswith("TTM")
