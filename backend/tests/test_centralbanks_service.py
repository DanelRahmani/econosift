"""Tests for centralbanks_service — Phase 16."""
from datetime import date, timedelta
from backend.services.centralbanks_service import _next_meeting, _pick_series, CB_SERIES


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
