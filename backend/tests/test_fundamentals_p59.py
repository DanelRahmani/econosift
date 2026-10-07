"""P3-33: Piotroski drops current ratio, gross margin and asset turnover for banks."""
from __future__ import annotations

from backend.services.fundamentals import piotroski_f

_BANK_ONLY = ("higherCurrentRatio", "higherGrossMargin", "higherAssetTurnover")


def _bundle(industry: str) -> tuple[dict, dict]:
    def mk(ni, ta, rev, gp, ca, cl, ltd, sh, ocf):
        return {
            "info": {"industry": industry},
            "financials": {"Net Income": ni, "Total Revenue": rev, "Gross Profit": gp},
            "balance_sheet": {"Total Assets": ta, "Current Assets": ca, "Current Liabilities": cl,
                              "Long Term Debt": ltd, "Ordinary Shares Number": sh},
            "cashflow": {"Operating Cash Flow": ocf},
        }
    # t: ROA 10/100 = .10 vs t-1 8/100 = .08 -> F2 pass; LTD 20/100 < 30/100 -> F5 pass;
    # shares flat -> F7 pass; NI>0 F1, OCF>0 F3, OCF 15 > NI 10 F4 all pass.
    # F6 CR 2.0 > 1.5, F8 GM .5 > .4, F9 turnover .5 > .4 would all pass for a non-bank.
    cur = mk(10, 100, 50, 25, 200, 100, 20, 1000, 15)
    pri = mk(8, 100, 40, 16, 150, 100, 30, 1000, 12)
    return cur, pri


def test_bank_drops_three_criteria_and_max_score_is_six():
    cur, pri = _bundle("Banks - Diversified")
    r = piotroski_f(cur, prior_year=pri)
    for k in _BANK_ONLY:
        assert r["criteria"][k] is None
        assert r["reasons"][k]
    assert r["maxScore"] == 6
    assert r["score"] == 6


def test_non_bank_unchanged_at_nine():
    cur, pri = _bundle("Consumer Electronics")
    r = piotroski_f(cur, prior_year=pri)
    assert r["maxScore"] == 9
    assert r["score"] == 9
    assert r["reasons"] == {}


def test_roic_tax_rate_matches_the_wacc_tax_rate(monkeypatch):
    """P3-21: ROIC's NOPAT uses the WACC's tax rate (discount_rates.tax_rate_for).
    No effectiveTaxRate, country Germany at a 25 % statutory rate:
    NOPAT = EBIT 100 x (1 - 0.25) = 75 (the old 21 % fallback gave 79)."""
    from backend.services import discount_rates
    from backend.services.fundamentals import roic
    monkeypatch.setattr(discount_rates, "load_erp",
                        lambda: {"countries": {"Germany": {"taxRate": 25.0}}})
    r = roic({"info": {"country": "Germany"}, "financials": {"EBIT": 100.0},
              "balance_sheet": {"Total Debt": 200.0, "Stockholders Equity": 300.0}})
    assert r["nopat"] == 75.0
