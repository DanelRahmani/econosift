"""Tests for the Earnings Quality & Accruals Monitor (Sloan 1996) — pure compute."""
from backend.services.corporate_health_service import compute_earnings_quality


def _row(ticker, sector=None, netIncome=None, operatingCashFlow=None,
         totalAssets=None, prevTotalAssets=None, cash=None, prevCash=None,
         totalLiabilities=None, prevTotalLiabilities=None,
         totalDebt=None, prevTotalDebt=None):
    return {
        "ticker": ticker, "sector": sector,
        "netIncome": netIncome, "operatingCashFlow": operatingCashFlow,
        "totalAssets": totalAssets, "prevTotalAssets": prevTotalAssets,
        "cash": cash, "prevCash": prevCash,
        "totalLiabilities": totalLiabilities, "prevTotalLiabilities": prevTotalLiabilities,
        "totalDebt": totalDebt, "prevTotalDebt": prevTotalDebt,
    }


def _synthetic_rows():
    rows = [
        # AAA: full data, mild negative accrual, good cash conversion, modest NOA growth
        _row("AAA", sector="Tech", netIncome=100, operatingCashFlow=110,
             totalAssets=1000, prevTotalAssets=900, cash=200, prevCash=180,
             totalLiabilities=400, prevTotalLiabilities=380, totalDebt=100, prevTotalDebt=100),
        # BBB: worst (highest) accrual in the universe -> should be flagged
        _row("BBB", sector="Industrials", netIncome=500, operatingCashFlow=50,
             totalAssets=2000, prevTotalAssets=1800, cash=100, prevCash=90,
             totalLiabilities=800, prevTotalLiabilities=750, totalDebt=300, prevTotalDebt=300),
        # C..J: filler tickers, no prior-year assets/liabilities (tests avg-assets
        # fallback + None-safe NOA), spread of accrual ratios for decile/median checks
        _row("C", netIncome=100, operatingCashFlow=150, totalAssets=1000),   # accrual -0.05
        _row("D", netIncome=100, operatingCashFlow=130, totalAssets=1000),   # accrual -0.03
        _row("E", netIncome=100, operatingCashFlow=120, totalAssets=1000),   # accrual -0.02
        _row("F", netIncome=100, operatingCashFlow=110, totalAssets=1000),   # accrual -0.01
        _row("G", netIncome=100, operatingCashFlow=90, totalAssets=1000),    # accrual +0.01
        _row("H", netIncome=100, operatingCashFlow=80, totalAssets=1000),    # accrual +0.02
        _row("I", netIncome=100, operatingCashFlow=70, totalAssets=1000),    # accrual +0.03
        _row("J", netIncome=100, operatingCashFlow=50, totalAssets=1000),    # accrual +0.05
        # NEG: net loss -> cashConversion must be None even though OCF is positive
        _row("NEG", netIncome=-40, operatingCashFlow=10, totalAssets=2000),  # accrual -0.025
        # NODATA: nothing but the ticker -> every derived metric must be None, no crash
        _row("NODATA", sector="Unknown"),
    ]
    return rows


def test_accrual_arithmetic_hand_computed():
    rows = _synthetic_rows()
    out = compute_earnings_quality(rows)
    by_ticker = {r["ticker"]: r for r in out["rows"]}
    aaa = by_ticker["AAA"]

    avg_assets = (1000 + 900) / 2.0
    expected_accrual = round((100 - 110) / avg_assets, 6)
    assert aaa["accrualRatio"] == expected_accrual
    assert expected_accrual == -0.010526

    expected_cc = round(110 / 100, 6)
    assert aaa["cashConversion"] == expected_cc

    noa = (1000 - 200) - (400 - 100)
    prev_noa = (900 - 180) - (380 - 100)
    expected_noa_growth = round((noa - prev_noa) / abs(prev_noa), 6)
    assert aaa["noaGrowth"] == expected_noa_growth

    # Verify qualityScore against the documented formula.
    score = 50.0
    score += 25.0 * (1.0 - min(abs(expected_accrual) / 0.15, 1.0))
    score += min(max(expected_cc - 1.0, 0.0) / 0.5, 1.0) * 15.0
    if expected_noa_growth < 0.20:
        score += 10.0
    score = max(0.0, min(100.0, score))
    assert aaa["qualityScore"] == round(score, 2)


def test_cash_conversion_none_when_net_income_non_positive():
    out = compute_earnings_quality(_synthetic_rows())
    by_ticker = {r["ticker"]: r for r in out["rows"]}
    neg = by_ticker["NEG"]
    assert neg["accrualRatio"] == round((-40 - 10) / 2000, 6)
    assert neg["cashConversion"] is None
    assert neg["flag"] is False  # accrual -0.025 is not the worst decile


def test_decile_flagging_picks_worst_accrual_names():
    out = compute_earnings_quality(_synthetic_rows())
    # 90th percentile (linear interpolation) over the 11 non-null accrual
    # ratios lands exactly on J's 0.05, so both J (0.05) and BBB (~0.2368,
    # the single worst accrual in the universe) clear the threshold.
    flagged = {r["ticker"] for r in out["rows"] if r["flag"]}
    assert flagged == {"J", "BBB"}
    by_ticker = {r["ticker"]: r for r in out["rows"]}
    for t in ("AAA", "C", "D", "E", "F", "G", "H", "I", "NEG"):
        assert by_ticker[t]["flag"] is False


def test_kpis_medians_and_pct_flagged():
    out = compute_earnings_quality(_synthetic_rows())
    kpis = out["kpis"]
    assert kpis["n"] == 12
    # 11 tickers have a non-null accrualRatio; sorted median is ticker F's -0.01
    assert kpis["medianAccrual"] == -0.01
    # 10 tickers have a non-null cashConversion; median of
    # [0.1, 0.5, 0.7, 0.8, 0.9, 1.1, 1.1, 1.2, 1.3, 1.5] is 1.0
    assert kpis["medianCashConversion"] == 1.0
    # Exactly 2 of 12 tickers flagged (J and BBB)
    assert kpis["pctFlagged"] == round(100.0 * 2 / 12, 2)


def test_rows_sorted_by_quality_score_descending_nulls_last():
    out = compute_earnings_quality(_synthetic_rows())
    scores = [r["qualityScore"] for r in out["rows"]]
    non_null = [s for s in scores if s is not None]
    assert non_null == sorted(non_null, reverse=True)
    # NODATA (the only null-score row) must be last
    assert scores[-1] is None
    assert out["rows"][-1]["ticker"] == "NODATA"


def test_missing_field_ticker_yields_none_metrics_without_crashing():
    out = compute_earnings_quality(_synthetic_rows())
    by_ticker = {r["ticker"]: r for r in out["rows"]}
    nodata = by_ticker["NODATA"]
    assert nodata["accrualRatio"] is None
    assert nodata["cashConversion"] is None
    assert nodata["noaGrowth"] is None
    assert nodata["qualityScore"] is None
    assert nodata["flag"] is False
    assert nodata["sector"] == "Unknown"


def test_empty_input_returns_empty_dict():
    assert compute_earnings_quality([]) == {}
