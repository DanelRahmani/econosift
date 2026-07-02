"""Tests for liquidity_service (net liquidity = WALCL − RRP − TGA) — Phase 38b."""
from backend.services.liquidity_service import _compute_net_liquidity, _weekly_series


def _pts(pairs):
    return [{"date": d, "value": v} for d, v in pairs]


# Four consecutive H.4.1 Wednesdays
_WEDS = ["2024-01-03", "2024-01-10", "2024-01-17", "2024-01-24"]


def _sample_data():
    return {
        # WALCL in millions → 7.5tn, 7.4tn, 7.3tn, 7.2tn
        "WALCL": _pts(zip(_WEDS, [7_500_000, 7_400_000, 7_300_000, 7_200_000])),
        # RRPONTSYD in billions → 0.5tn constant
        "RRPONTSYD": _pts(zip(_WEDS, [500, 500, 500, 500])),
        # WTREGEN in millions → 0.7tn constant
        "WTREGEN": _pts(zip(_WEDS, [700_000, 700_000, 700_000, 700_000])),
        # WRESBAL in millions → 3.2tn constant
        "WRESBAL": _pts(zip(_WEDS, [3_200_000, 3_200_000, 3_200_000, 3_200_000])),
    }


def test_net_liquidity_units_and_arithmetic():
    out = _compute_net_liquidity(_sample_data(), spx_pts=[])
    # 7.2 − 0.5 − 0.7 = 6.0tn on the latest Wednesday
    assert out["kpis"]["netLiquidity"] == 6.0
    assert out["kpis"]["rrp"] == 0.5
    assert out["kpis"]["tga"] == 0.7
    assert out["kpis"]["reserves"] == 3.2
    assert len(out["history"]["netLiquidity"]) == 4
    assert out["history"]["netLiquidity"][0] == {"date": "2024-01-03", "value": 6.3}


def test_missing_rrp_treated_as_zero():
    data = _sample_data()
    data["RRPONTSYD"] = []
    out = _compute_net_liquidity(data, spx_pts=[])
    # 7.2 − 0 − 0.7 = 6.5tn
    assert out["kpis"]["netLiquidity"] == 6.5
    assert out["kpis"]["rrp"] is None


def test_empty_walcl_returns_empty():
    assert _compute_net_liquidity({}, spx_pts=[]) == {}


def test_none_values_skipped():
    data = _sample_data()
    data["WALCL"][1]["value"] = None  # gap is forward-filled on the weekly grid
    out = _compute_net_liquidity(data, spx_pts=[])
    hist = out["history"]["netLiquidity"]
    assert len(hist) == 4
    assert hist[1]["value"] == 6.3  # ffilled from 7.5tn week


def test_weekly_series_resamples_daily_to_wednesday():
    daily = _pts([("2024-01-08", 1000), ("2024-01-09", 1100), ("2024-01-10", 1200),
                  ("2024-01-11", 1300)])
    s = _weekly_series(daily, 1e-3)
    # Week ending Wed 2024-01-10 takes the Wednesday observation (1.2tn);
    # Thursday's print lands in the following week.
    assert str(s.index[0].date()) == "2024-01-10"
    assert s.iloc[0] == 1.2
