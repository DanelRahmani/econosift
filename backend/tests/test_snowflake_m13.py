"""Audit M-13: Snowflake health uses the full 9-point Piotroski, real sector peers, honest FCF-coverage units."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.services import fundamentals, snowflake_service as sf


def _df(rows: dict) -> pd.DataFrame:
    cols = [pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")]
    return pd.DataFrame({c: [v[i] for v in rows.values()] for i, c in enumerate(cols)}, index=list(rows))


def _bundle():
    fin = _df({"Net Income": (120.0, 100.0), "Total Revenue": (1000.0, 900.0), "Gross Profit": (500.0, 400.0)})
    bs = _df({"Total Assets": (1000.0, 1000.0), "Current Assets": (500.0, 400.0),
              "Current Liabilities": (200.0, 200.0), "Long Term Debt": (100.0, 150.0),
              "Ordinary Shares Number": (10.0, 10.0)})
    cf = _df({"Operating Cash Flow": (150.0, 130.0)})

    def cur(df):
        return {k: float(df.loc[k].iloc[0]) for k in df.index}
    return {"info": {"currency": "USD", "financialCurrency": "USD"}, "financials": cur(fin),
            "balance_sheet": cur(bs), "cashflow": cur(cf),
            "financials_df": fin, "balance_sheet_df": bs, "cashflow_df": cf}


def test_health_axis_scores_all_nine_piotroski_tests(monkeypatch):
    # ROA .12 > .10; NI>0; OCF 150>0; OCF 150 > NI 120; LTD/TA .10 < .15; CR 2.5 > 2.0;
    # shares 10 <= 10; GM .5 > .444; turnover 1.0 > .9 -> 9 of 9 -> score 10.
    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 660.0)
    monkeypatch.setattr(sf, "compute_wacc", lambda b, beta: {"wacc": 0.08})
    b = _bundle()
    _, comps = sf._axis_health({}, [], b["info"], b)
    pio = next(c for c in comps if c["label"] == "Piotroski F-Score")
    assert pio["detail"] == "9/9" and pio["value"] == 9 and pio["score"] == 10.0


# ── peers ──

def _rows(sector, n):
    return [{"sector": sector, "industry": f"{sector} sub"} for _ in range(n)]


def test_non_index_yahoo_sector_maps_to_gics_peers():
    # TSM: Yahoo "Technology", not in the cache. 12 GICS "Information Technology" rows + 3 Yahoo-named
    # stragglers = 15 peers; the 20 Health Care rows are not peers (it used to get all 35).
    universe = _rows("Information Technology", 12) + _rows("Technology", 3) + _rows("Health Care", 20)
    peers, scope = sf._sector_peers("Technology", "Semiconductors", universe)
    assert len(peers) == 15 and scope == "sector"


def test_no_honest_peer_set_returns_none_not_the_universe():
    universe = _rows("Information Technology", 12) + _rows("Health Care", 20)
    assert sf._sector_peers(None, None, universe) == ([], None)
    assert sf._sector_peers("Telecommunications", "Wireless", universe) == ([], None)   # 0 < 10 peers


def test_industry_fallback_when_sector_is_thin():
    universe = _rows("Energy", 3) + [{"sector": "Energy", "industry": "Oil"}] * 0
    universe += [{"sector": "Utilities", "industry": "Water"} for _ in range(10)]
    peers, scope = sf._sector_peers("Energy", "Water", universe)
    assert len(peers) == 10 and scope == "industry"


# ── FCF coverage display unit ──

def test_fcf_coverage_value_is_a_multiple_not_a_percent_ratio(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("no network")
    monkeypatch.setattr(sf.yf, "Ticker", Boom)
    # dividend yield 2.0 (percent units), FCF yield 0.05 (fraction): coverage = 0.05 / 0.02 = 2.5x
    _, comps = sf._axis_dividend({"dividend_yield": 2.0, "fcf_yield": 0.05}, [], {"symbol": "X"})
    cov = next(c for c in comps if c["label"] == "FCF Coverage")
    assert cov["value"] == pytest.approx(2.5) and cov["score"] == 8.0


def test_no_evaluable_piotroski_test_is_unscored_not_zero(monkeypatch):
    # maxScore 0 ("Insufficient data") must drop the component, not score it 0 of 10 at weight 0.20.
    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 660.0)
    monkeypatch.setattr(sf, "compute_wacc", lambda b, beta: {"wacc": 0.08})
    monkeypatch.setattr(sf, "piotroski_f", lambda b: {"score": 0, "maxScore": 0})
    b = _bundle()
    _, comps = sf._axis_health({}, [], b["info"], b)
    pio = next(c for c in comps if c["label"] == "Piotroski F-Score")
    assert pio["score"] is None
