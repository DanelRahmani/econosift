"""Corporate health (Altman / Piotroski / Beneish) — audit C-12, C-13, C-14."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.services import corporate_health_service as ch


def _annual(values: dict[str, float], date="2025-12-31") -> pd.DataFrame:
    """One annual column only (as for a recent IPO)."""
    return pd.DataFrame({pd.Timestamp(date): values})


def _quarterly(rows: dict[str, list[float]], end="2025-12-31", n=8) -> pd.DataFrame:
    cols = pd.date_range(end=end, periods=n, freq="QE")[::-1]  # latest first
    return pd.DataFrame({c: {k: v[i] for k, v in rows.items()} for i, c in enumerate(cols)})


def test_prior_stock_item_is_the_quarter_one_year_back():
    annual = _annual({"Total Assets": 200.0})
    q = _quarterly({"Total Assets": [200, 190, 180, 170, 160, 150, 140, 130]})
    # Latest annual 2025-12-31 → prior year-end 2024-12-31 = 5th column (160),
    # not iloc[3] (170, three quarters back).
    assert ch._prior_value(annual, q, "Total Assets", flow=False) == 160.0


def test_prior_flow_item_sums_four_quarters_not_one():
    annual = _annual({"Total Revenue": 400.0})
    q = _quarterly({"Total Revenue": [110, 100, 100, 90, 80, 80, 70, 70]})
    # FY2024 = Q1–Q4 2024 = columns 4..7 = 80+80+70+70 = 300 (not one quarter).
    assert ch._prior_value(annual, q, "Total Revenue", flow=True) == 300.0


def test_prior_flow_item_none_without_four_quarters():
    annual = _annual({"Total Revenue": 400.0})
    q = _quarterly({"Total Revenue": [110, 100, 100, 90, 80]}, n=5)
    assert ch._prior_value(annual, q, "Total Revenue", flow=True) is None


def test_piotroski_missing_prior_is_not_a_pass():
    fin = _annual({"Net Income": 10.0, "Total Revenue": 100.0, "Gross Profit": 40.0})
    bs = _annual({"Total Assets": 100.0, "Current Assets": 50.0, "Current Liabilities": 25.0,
                  "Long Term Debt": 20.0, "Ordinary Shares Number": 10.0})
    cf = _annual({"Operating Cash Flow": 15.0})
    r = ch._piotroski(fin, bs, cf)
    # Only the three single-period criteria (NI > 0, CFO > 0, CFO > NI) can
    # be evaluated — all pass; the six year-over-year ones are not scored.
    assert r["score"] == 3 and r["maxScore"] == 3
    assert r["criteria"]["roaIncreasing"] is None
    assert r["criteria"]["noShareDilution"] is None


def test_beneish_imputes_neutral_one_for_missing_indexes():
    """With every ratio index at its neutral 1.0 and TATA = 0, M is the sum
    of the coefficients plus the intercept: −4.84 + 0.920 + 0.528 + 0.404 +
    0.892 + 0.115 − 0.172 − 0.327 = −2.48 (previously missing indexes added
    0, giving about −4.84)."""
    fin = _annual({"Total Revenue": 100.0, "Cost Of Revenue": 60.0, "Net Income": 10.0,
                   "Selling General And Administration": 20.0})
    bs = _annual({"Total Assets": 200.0, "Current Assets": 80.0, "Net PPE": 60.0,
                  "Accounts Receivable": 30.0, "Total Liabilities Net Minority Interest": 90.0})
    cf = _annual({"Operating Cash Flow": 10.0})
    r = ch._beneish(fin, bs, cf)
    # No prior year at all → 7 ratio indexes missing → too many imputed.
    assert r["mScore"] is None

    fin2 = pd.concat([fin, pd.DataFrame({pd.Timestamp("2024-12-31"): {
        "Total Revenue": 100.0, "Cost Of Revenue": 60.0, "Net Income": 10.0,
        "Selling General And Administration": 20.0}})], axis=1)
    bs2 = pd.concat([bs, pd.DataFrame({pd.Timestamp("2024-12-31"): {
        "Total Assets": 200.0, "Current Assets": 80.0, "Net PPE": 60.0,
        "Accounts Receivable": 30.0, "Total Liabilities Net Minority Interest": 90.0}})], axis=1)
    cf2 = pd.concat([cf, pd.DataFrame({pd.Timestamp("2024-12-31"): {"Operating Cash Flow": 10.0}})], axis=1)
    r = ch._beneish(fin2, bs2, cf2)
    # Unchanged firm, DEPI missing (no D&A line) → imputed 1.0; TATA = 0.
    assert r["imputedNeutral"] == ["depi"]
    assert r["mScore"] == pytest.approx(-4.84 + 0.920 + 0.528 + 0.404 + 0.892 + 0.115 - 0.172 - 0.327, abs=1e-4)
