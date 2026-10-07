"""Tests for the policy intelligence service (Phase 18A Task 3, P2-29)."""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock


def _pts(values: list[float]) -> list[dict]:
    base = date(2023, 1, 1)
    return [{"date": str(base + timedelta(days=30 * i)), "value": v} for i, v in enumerate(values)]


def _recent(values: list[float], step_days: int = 30) -> list[dict]:
    """Points ending today, ``step_days`` apart (so they are never stale)."""
    end = date.today()
    n = len(values)
    return [{"date": str(end - timedelta(days=step_days * (n - 1 - i))), "value": v}
            for i, v in enumerate(values)]


MOCK_CB = {
    "FEDFUNDS": _pts([4.75, 5.00, 5.25, 5.25, 5.00, 4.75, 4.50, 4.50, 4.25, 4.25, 4.00, 4.00, 3.75]),
    "ECBDFR": _pts([3.00, 3.50, 4.00, 4.00, 3.75, 3.50, 3.25, 3.25, 3.00, 3.00, 2.75, 2.75, 2.50]),
}


@pytest.mark.asyncio
async def test_policy_tracker_structure():
    with patch(
        "backend.services.policy_service._fetch_cb_series",
        new_callable=AsyncMock,
        return_value=MOCK_CB,
    ), patch(
        "backend.sources.source_bis.get_policy_rates_bulk",
        new_callable=AsyncMock,
        return_value={},
    ):
        from backend.services.policy_service import get_policy_tracker
        result = await get_policy_tracker()

    assert "divergence" in result
    assert "carry_differentials" in result
    assert len(result["divergence"]) >= 2

    fed = next(d for d in result["divergence"] if d["cb"] == "Fed")
    assert "stance" in fed
    assert "change_12m" in fed
    assert fed["stance"] == "easing"  # rate dropped from 4.75 → 3.75 over 12M


def _bis_payload() -> dict:
    # 13 monthly-spaced points; the last is today, the first is ~360 days earlier.
    return {
        "US": {"points": _recent([3.875] * 12 + [3.625]), "compilation": "From 19 Dec 1985 onwards: mid-point of the Federal Reserve target rate"},
        "XM": {"points": _recent([2.50] * 12 + [2.25]),
               "compilation": "From 18 Sep 2024 onwards: official central bank steering rate is the deposit facility rate"},
        "JP": {"points": _recent([0.5] * 12 + [1.25]), "compilation": "BoJ target"},
    }


_OECD_FALLBACK = {
    "IRSTCI01GBM156N": _recent([4.0, 3.9, 3.8]),
    "IRSTCI01CAM156N": _recent([3.0, 2.9, 2.8]),
    "IRSTCI01AUM156N": _recent([4.5, 4.4, 4.3]),
    "IRSTCI01CHM156N": _recent([0.5, 0.4, 0.3]),
}


async def _run(bis: dict, fred: dict):
    with patch("backend.services.policy_service._fetch_cb_series",
               new_callable=AsyncMock, return_value=fred), \
         patch("backend.sources.source_bis.get_policy_rates_bulk",
               new_callable=AsyncMock, return_value=bis):
        from backend.services import policy_service
        # bypass the cache wrapper so each test computes fresh
        fn = getattr(policy_service.get_policy_tracker, "__wrapped__", policy_service.get_policy_tracker)
        return await fn()


@pytest.mark.asyncio
async def test_bis_rates_preferred_with_proxy_fallback_labelled():
    result = await _run(_bis_payload(), {**MOCK_CB, **_OECD_FALLBACK})
    rows = {d["cb"]: d for d in result["divergence"]}

    assert rows["ECB"]["current_rate"] == pytest.approx(2.25)
    assert rows["ECB"]["rateSource"] == "bis"
    assert "deposit facility" in rows["ECB"]["rateType"]
    assert rows["ECB"]["change_12m"] == pytest.approx(2.25 - 2.50)

    assert rows["Fed"]["current_rate"] == pytest.approx(3.625)
    assert rows["Fed"]["rateSource"] == "bis"
    assert "midpoint" in rows["Fed"]["rateType"]

    assert rows["BoJ"]["current_rate"] == pytest.approx(1.25)
    assert rows["BoJ"]["rateSource"] == "bis"

    assert rows["BoE"]["rateSource"] == "proxy"
    assert "proxy" in rows["BoE"]["rateType"]
    assert rows["BoE"]["current_rate"] == pytest.approx(3.8)

    assert result["carry_differentials"]["EURUSD"] == pytest.approx(2.25 - 3.625)  # -1.375

    prov = result["provenance"]
    assert prov["divergence.ECB"]["provider"] == "bis"
    assert prov["divergence.ECB"]["series"] == "WS_CBPOL"
    assert prov["divergence.BoE"]["provider"] == "fred"
    assert "fallback" in prov["divergence.BoE"]["note"]


@pytest.mark.asyncio
async def test_ecb_falls_back_to_deposit_facility_rate_when_bis_missing():
    bis = _bis_payload()
    del bis["XM"]
    result = await _run(bis, {**MOCK_CB, "ECBDFR": _recent([2.5, 2.5, 2.25]), **_OECD_FALLBACK})
    ecb = next(d for d in result["divergence"] if d["cb"] == "ECB")
    assert ecb["rateSource"] == "proxy"
    assert ecb["current_rate"] == pytest.approx(2.25)
    assert "deposit facility" in ecb["rateType"]
    assert result["provenance"]["divergence.ECB"]["series"] == "ECBDFR"


@pytest.mark.asyncio
async def test_stale_bis_series_falls_back_to_fred():
    bis = _bis_payload()
    old = date.today() - timedelta(days=400)
    bis["XM"]["points"] = [{"date": str(old - timedelta(days=30)), "value": 2.0},
                           {"date": str(old), "value": 2.1}]
    result = await _run(bis, {**MOCK_CB, "ECBDFR": _recent([2.5, 2.5, 2.25]), **_OECD_FALLBACK})
    ecb = next(d for d in result["divergence"] if d["cb"] == "ECB")
    assert ecb["rateSource"] == "proxy"
    assert ecb["current_rate"] == pytest.approx(2.25)


def test_rate_n_months_ago_on_daily_points():
    from backend.services.policy_service import _rate_n_months_ago

    end = date(2026, 9, 29)
    pts = [{"date": str(end - timedelta(days=i)), "value": float(i)} for i in range(400, -1, -1)]
    # target = end - 90 days; last observation on/before it has value 90.0
    assert _rate_n_months_ago(pts, 3) == pytest.approx(90.0)
    # gap in the series: nothing on the target date, take the earlier observation
    gappy = [p for p in pts if p["value"] != 90.0]
    assert _rate_n_months_ago(gappy, 3) == pytest.approx(91.0)


def test_parse_policy_rates_daily_preferred_over_monthly():
    import pandas as pd
    from backend.sources.source_bis import _parse_policy_rates

    df = pd.DataFrame({
        "FREQ:Frequency": ["D: Daily", "D: Daily", "M: Monthly", "M: Monthly", "M: Monthly"],
        "REF_AREA:Reference area": ["JP: Japan", "JP: Japan", "JP: Japan", "US: United States", "US: United States"],
        "TIME_PERIOD:Time period or range": ["2026-09-28", "2026-09-29", "2026-08", "2026-07", "2026-08"],
        "OBS_VALUE:Observation Value": [1.0, 1.25, 1.0, 3.5, 3.625],
        "COMPILATION:Compilation": ["BoJ target", "BoJ target", "BoJ target", "Fed mid", "Fed mid"],
    })
    out = _parse_policy_rates(df, ["JP", "US", "GB"])
    assert out["JP"]["points"][-1] == {"date": "2026-09-29", "value": 1.25}
    assert out["JP"]["compilation"] == "BoJ target"
    assert out["US"]["points"] == [{"date": "2026-07-01", "value": 3.5},
                                   {"date": "2026-08-01", "value": 3.625}]
    assert "GB" not in out
