"""Tests for centralbanks_service — Phase 16."""
from datetime import date, timedelta

import pytest

from backend.services.centralbanks_service import _START, _next_meeting, _pick_series, CB_SERIES


def test_next_meeting_future():
    future_date = (date.today() + timedelta(days=10)).isoformat()
    meetings = [{"bank": "Fed", "date": future_date}]
    nxt, days = _next_meeting("Fed", meetings)
    assert nxt == future_date
    assert days == 10


def test_next_meeting_skips_past():
    past_date = (date.today() - timedelta(days=5)).isoformat()
    meetings = [{"bank": "Fed", "date": past_date}]
    nxt, days = _next_meeting("Fed", meetings)
    assert nxt is None
    assert days is None


def test_next_meeting_picks_closest():
    d1 = (date.today() + timedelta(days=5)).isoformat()
    d2 = (date.today() + timedelta(days=20)).isoformat()
    meetings = [{"bank": "Fed", "date": d2}, {"bank": "Fed", "date": d1}]
    nxt, days = _next_meeting("Fed", meetings)
    assert nxt == d1
    assert days == 5


def test_pick_series_recent():
    today_str = date.today().isoformat()
    all_data = {"FEDFUNDS": [{"date": today_str, "value": 4.5}]}
    assert _pick_series("Fed", all_data) == "FEDFUNDS"


def test_pick_series_fallback():
    all_data = {}
    sid = _pick_series("Fed", all_data)
    assert sid == CB_SERIES["Fed"][0]


# ---------------------------------------------------------------------------
# P2-44: official BIS rates first, FRED/OECD proxies only as a labelled fallback
# ---------------------------------------------------------------------------
from unittest.mock import AsyncMock, patch


def _recent(values: list[float], step_days: int = 30) -> list[dict]:
    """Points ending today, ``step_days`` apart (so they are never stale)."""
    end = date.today()
    n = len(values)
    return [{"date": str(end - timedelta(days=step_days * (n - 1 - i))), "value": v}
            for i, v in enumerate(values)]


def _bis() -> dict:
    return {
        "US": {"points": _recent([3.875, 3.875]), "compilation": "Fed target midpoint"},
        "XM": {"points": _recent([2.75, 2.50]),
               "compilation": "From 18 Sep 2024 onwards: official central bank steering rate is the deposit facility rate"},
        "JP": {"points": _recent([1.0, 1.25]), "compilation": "BoJ target"},
    }


_PROXIES = {
    "ECBMRRFR": _recent([3.5, 3.5]),
    "ECBDFR": _recent([2.5, 2.25]),
    "IRSTCI01GBM156N": _recent([4.0, 3.8]),
}


async def _run(bis: dict, fred: dict):
    bulk = AsyncMock(return_value=bis)
    fetch = AsyncMock(return_value=fred)
    with patch("backend.sources.source_bis.get_policy_rates_bulk", bulk), \
         patch("backend.services.macro_expansion_service.fetch_fred_series", fetch), \
         patch("backend.services.centralbanks_service._load_meetings", return_value=[]):
        from backend.services import centralbanks_service as cbs
        fn = getattr(cbs.get_centralbanks, "__wrapped__", cbs.get_centralbanks)
        return await fn(), bulk, fetch


async def test_bis_rate_preferred_and_labelled():
    result, bulk, _ = await _run(_bis(), _PROXIES)

    ecb = result["current"]["ECB"]
    assert ecb["rate"] == pytest.approx(2.50)
    assert ecb["rateSource"] == "bis"
    assert "deposit facility" in ecb["rateType"]
    assert result["current"]["Fed"]["rate"] == pytest.approx(3.875)
    assert result["current"]["BoJ"]["rateSource"] == "bis"

    prov = result["provenance"]
    assert prov["current.ECB"]["provider"] == "bis"
    assert prov["current.ECB"]["series"] == "WS_CBPOL"
    assert prov["history.ECB"]["provider"] == "bis"
    # the chart history for a BIS bank is the BIS series, requested back to _START
    assert bulk.await_args.kwargs["since"] == _START
    assert [r["ECB"] for r in result["history"][-2:]] == [2.75, 2.50]


async def test_bank_missing_in_bis_falls_back_to_labelled_proxy():
    result, _, _ = await _run(_bis(), _PROXIES)

    boe = result["current"]["BoE"]
    assert boe["rate"] == pytest.approx(3.8)
    assert boe["rateSource"] == "proxy"
    assert "proxy" in boe["rateType"]
    prov = result["provenance"]["current.BoE"]
    assert prov["provider"] == "fred"
    assert "fallback" in prov["note"]


async def test_ecb_without_bis_falls_back_to_deposit_facility_not_mro():
    bis = _bis()
    del bis["XM"]
    result, _, fetch = await _run(bis, _PROXIES)

    ecb = result["current"]["ECB"]
    assert ecb["rate"] == pytest.approx(2.25)
    assert ecb["series"] == "ECBDFR"
    assert ecb["rateSource"] == "proxy"
    assert "deposit facility" in ecb["rateType"]
    assert "ECBMRRFR" not in CB_SERIES["ECB"]
    assert "ECBMRRFR" not in fetch.await_args.args[0]
