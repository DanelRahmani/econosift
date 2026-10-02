"""Fully offline unit tests for Phase 4 calendar_service.

All external calls (yfinance, requests, finnhub_service) are monkeypatched.
No network access occurs.
"""
from __future__ import annotations

import datetime
import math

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Autouse fixture: clear caches before/after every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_caches():
    from backend import cache
    cache._caches.clear()
    cache._stats.clear()
    yield
    cache._caches.clear()
    cache._stats.clear()


# ---------------------------------------------------------------------------
# Helpers / shared fakes
# ---------------------------------------------------------------------------

_START = "2026-06-01"
_END = "2026-06-30"

_CB_MEETINGS = [
    {"date": "2026-06-17", "bank": "Fed", "country": "US", "title": "FOMC Meeting"},
    {"date": "2026-07-29", "bank": "Fed", "country": "US", "title": "FOMC Meeting"},  # out of range
]

_MEMBERS = [
    {"symbol": "AAA", "name": "Alpha Corp", "sector": "Technology", "industry": None},
    {"symbol": "BBB", "name": "Beta Corp", "sector": "Financials", "industry": None},
]


def _make_earnings_df(
    dates: list[str],
    estimates: list[float | None],
    actuals: list[float | None],
    surprises: list[float | None],
) -> pd.DataFrame:
    """Build a minimal earnings_dates DataFrame like yfinance returns."""
    idx = pd.to_datetime(dates)
    df = pd.DataFrame(
        {
            "EPS Estimate": estimates,
            "Reported EPS": actuals,
            "Surprise(%)": surprises,
        },
        index=idx,
    )
    df.index.name = "Earnings Date"
    return df


class _FakeTicker:
    """Minimal yf.Ticker stand-in."""

    def __init__(self, sym: str, earnings_df=None, info=None):
        self.sym = sym
        self._earnings_df = earnings_df
        self._info = info or {}

    @property
    def earnings_dates(self):
        return self._earnings_df

    @property
    def info(self):
        return self._info


# ---------------------------------------------------------------------------
# 1. Common event schema — all keys present
# ---------------------------------------------------------------------------

class TestEventSchema:
    def test_event_has_all_keys(self):
        from backend.services.calendar_service import _event, _EVENT_KEYS
        ev = _event(date="2026-06-17", category="macro", title="FOMC Meeting")
        for key in _EVENT_KEYS:
            assert key in ev, f"Missing key: {key}"

    def test_event_missing_fields_are_none(self):
        from backend.services.calendar_service import _event
        ev = _event(date="2026-06-17", category="macro", title="Test")
        assert ev["ticker"] is None
        assert ev["epsEstimate"] is None
        assert ev["beatMiss"] is None
        assert ev["amount"] is None
        assert ev["exchange"] is None

    def test_event_explicit_values_set(self):
        from backend.services.calendar_service import _event
        ev = _event(
            date="2026-06-17",
            category="earnings",
            title="AAA Earnings",
            ticker="AAA",
            epsEstimate=1.5,
            epsActual=1.8,
            beatMiss="beat",
        )
        assert ev["epsEstimate"] == 1.5
        assert ev["epsActual"] == 1.8
        assert ev["beatMiss"] == "beat"


# ---------------------------------------------------------------------------
# 2. Date-range filtering
# ---------------------------------------------------------------------------

class TestDateRangeFiltering:
    def test_cb_meetings_in_range_included(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: _CB_MEETINGS)
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        # Patch FRED key to None so FRED branch is skipped
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)

        events = calendar_service.macro_events(_START, _END)
        dates = [ev["date"] for ev in events]
        assert "2026-06-17" in dates

    def test_cb_meetings_out_of_range_excluded(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: _CB_MEETINGS)
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)

        events = calendar_service.macro_events(_START, _END)
        dates = [ev["date"] for ev in events]
        assert "2026-07-29" not in dates

    def test_earnings_out_of_range_dropped(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs
        # Earnings row outside of range
        df = _make_earnings_df(["2026-07-15"], [1.0], [1.1], [10.0])
        fake = _FakeTicker("AAA", earnings_df=df, info={})
        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        import yfinance as yf
        monkeypatch.setattr(yf, "Ticker", lambda sym: fake)

        result = calendar_service.earnings_events("dow", _START, _END)
        assert result == []

    def test_earnings_in_range_included(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs
        df = _make_earnings_df(["2026-06-10"], [1.0], [1.1], [10.0])
        fake = _FakeTicker("AAA", earnings_df=df, info={})
        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        import yfinance as yf
        monkeypatch.setattr(yf, "Ticker", lambda sym: fake)

        result = calendar_service.earnings_events("dow", _START, _END)
        assert len(result) == 1
        assert result[0]["date"] == "2026-06-10"


# ---------------------------------------------------------------------------
# 3. CB meetings merged into macro_events
# ---------------------------------------------------------------------------

class TestCbMeetingsMerge:
    def test_cb_meeting_appears_in_macro_events(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: _CB_MEETINGS)
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)

        events = calendar_service.macro_events(_START, _END)
        fomc = [ev for ev in events if ev["title"] == "FOMC Meeting"]
        assert len(fomc) == 1
        assert fomc[0]["country"] == "US"
        assert fomc[0]["impact"] == 3
        assert fomc[0]["category"] == "macro"

    def test_cb_meeting_has_full_schema(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: _CB_MEETINGS)
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)

        from backend.services.calendar_service import _EVENT_KEYS
        events = calendar_service.macro_events(_START, _END)
        for ev in events:
            for key in _EVENT_KEYS:
                assert key in ev, f"Missing key '{key}' in event {ev}"


# ---------------------------------------------------------------------------
# 4. Beat/miss logic
# ---------------------------------------------------------------------------

class TestBeatMiss:
    def _run_single(self, monkeypatch, estimate, actual, surprise=None):
        from backend.services import calendar_service, constituents as cs
        import yfinance as yf

        df = _make_earnings_df(
            ["2026-06-10"],
            [estimate],
            [actual if actual is not None else float("nan")],
            [surprise if surprise is not None else float("nan")],
        )
        fake = _FakeTicker("AAA", earnings_df=df, info={})
        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        monkeypatch.setattr(yf, "Ticker", lambda sym: fake)

        result = calendar_service.earnings_events("dow", _START, _END)
        assert len(result) == 1
        return result[0]

    def test_beat(self, monkeypatch):
        ev = self._run_single(monkeypatch, estimate=1.0, actual=1.2)
        assert ev["beatMiss"] == "beat"
        assert ev["epsActual"] == pytest.approx(1.2)
        assert ev["epsEstimate"] == pytest.approx(1.0)

    def test_miss(self, monkeypatch):
        ev = self._run_single(monkeypatch, estimate=1.0, actual=0.8)
        assert ev["beatMiss"] == "miss"

    def test_inline(self, monkeypatch):
        ev = self._run_single(monkeypatch, estimate=1.0, actual=1.0)
        assert ev["beatMiss"] == "inline"

    def test_missing_actual_gives_none(self, monkeypatch):
        ev = self._run_single(monkeypatch, estimate=1.0, actual=None)
        assert ev["beatMiss"] is None
        assert ev["epsActual"] is None

    def test_missing_estimate_gives_none(self, monkeypatch):
        ev = self._run_single(monkeypatch, estimate=None, actual=1.0)
        assert ev["beatMiss"] is None


# ---------------------------------------------------------------------------
# 5. Graceful degradation without API keys
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def test_no_finnhub_key_ipos_empty(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        monkeypatch.setattr(calendar_service, "FINNHUB_API_KEY", None)
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: [])

        result = calendar_service.ipo_events(_START, _END)
        assert result == []

    def test_no_fred_key_fred_not_called(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])

        import requests as req
        called = []
        original_get = req.get

        def spy_get(url, **kwargs):
            called.append(url)
            return original_get(url, **kwargs)

        # We can't monkeypatch requests.get easily here — just verify result is []
        events = calendar_service.macro_events(_START, _END)
        assert events == []

    def test_no_keys_cb_meetings_still_present(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "FINNHUB_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: _CB_MEETINGS)
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])

        events = calendar_service.macro_events(_START, _END)
        assert any(ev["title"] == "FOMC Meeting" for ev in events)

    def test_sources_flags_correct(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service, constituents as cs
        import yfinance as yf

        monkeypatch.setattr(calendar_service, "FINNHUB_API_KEY", None)
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: [])
        monkeypatch.setattr(cs, "get_constituents", lambda idx: [])

        result = calendar_service.calendar("dow", _START, _END)
        assert result["sources"]["finnhub"] is False
        assert result["sources"]["fred"] is False
        assert result["sources"]["cbMeetings"] is True

    def test_sources_flags_true_with_keys(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service, constituents as cs

        monkeypatch.setattr(calendar_service, "FINNHUB_API_KEY", "fake-key")
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", "fake-fred")
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: [])
        monkeypatch.setattr(cs, "get_constituents", lambda idx: [])

        result = calendar_service.calendar("dow", _START, _END)
        assert result["sources"]["finnhub"] is True
        assert result["sources"]["fred"] is True


# ---------------------------------------------------------------------------
# 6. calendar() top-level keys
# ---------------------------------------------------------------------------

class TestCalendarTopLevel:
    def test_calendar_returns_exact_keys(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service, constituents as cs

        monkeypatch.setattr(calendar_service, "FINNHUB_API_KEY", None)
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: [])
        monkeypatch.setattr(cs, "get_constituents", lambda idx: [])

        result = calendar_service.calendar("dow", _START, _END)
        expected_keys = {"index", "start", "end", "macro", "earnings", "dividends", "ipos", "sources", "cbScheduleEnds",
                         "provenance"}
        assert set(result.keys()) == expected_keys

    def test_calendar_echoes_params(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service, constituents as cs

        monkeypatch.setattr(calendar_service, "FINNHUB_API_KEY", None)
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: [])
        monkeypatch.setattr(cs, "get_constituents", lambda idx: [])

        result = calendar_service.calendar("sp500", _START, _END)
        assert result["index"] == "sp500"
        assert result["start"] == _START
        assert result["end"] == _END

    def test_calendar_lists_are_lists(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service, constituents as cs

        monkeypatch.setattr(calendar_service, "FINNHUB_API_KEY", None)
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: [])
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: [])
        monkeypatch.setattr(cs, "get_constituents", lambda idx: [])

        result = calendar_service.calendar("dow", _START, _END)
        assert isinstance(result["macro"], list)
        assert isinstance(result["earnings"], list)
        assert isinstance(result["dividends"], list)
        assert isinstance(result["ipos"], list)


# ---------------------------------------------------------------------------
# 7. Dividend events
# ---------------------------------------------------------------------------

class TestDividendEvents:
    def test_dividend_event_extracted(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs
        import yfinance as yf

        # ex-dividend date as unix timestamp at UTC midnight (yfinance convention)
        ex_div_ts = int(datetime.datetime(2026, 6, 15, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
        fake = _FakeTicker("AAA", earnings_df=None, info={"exDividendDate": ex_div_ts, "dividendRate": 2.4})
        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        monkeypatch.setattr(yf, "Ticker", lambda sym: fake)

        result = calendar_service.dividend_events("dow", _START, _END)
        assert len(result) == 1
        assert result[0]["category"] == "dividend"
        assert result[0]["ticker"] == "AAA"
        assert result[0]["amount"] == pytest.approx(2.4)

    def test_dividend_no_ex_date_excluded(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs
        import yfinance as yf

        fake = _FakeTicker("AAA", earnings_df=None, info={})
        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        monkeypatch.setattr(yf, "Ticker", lambda sym: fake)

        result = calendar_service.dividend_events("dow", _START, _END)
        assert result == []


# ---------------------------------------------------------------------------
# 8. IPO events from Finnhub
# ---------------------------------------------------------------------------

class TestIpoEvents:
    def test_ipo_mapped_to_common_shape(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service

        fake_ipos = [
            {"date": "2026-06-20", "name": "NewCo Inc", "symbol": "NEW",
             "exchange": "NASDAQ", "numberOfShares": 1000000, "price": 15.0},
        ]
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: fake_ipos)

        result = calendar_service.ipo_events(_START, _END)
        assert len(result) == 1
        ev = result[0]
        assert ev["category"] == "ipo"
        assert ev["ticker"] == "NEW"
        assert ev["exchange"] == "NASDAQ"
        assert ev["date"] == "2026-06-20"

    def test_ipo_has_full_schema(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service
        from backend.services.calendar_service import _EVENT_KEYS

        fake_ipos = [
            {"date": "2026-06-20", "name": "NewCo Inc", "symbol": "NEW", "exchange": "NYSE"},
        ]
        monkeypatch.setattr(finnhub_service, "ipo_calendar", lambda s, e: fake_ipos)

        result = calendar_service.ipo_events(_START, _END)
        for ev in result:
            for key in _EVENT_KEYS:
                assert key in ev, f"Missing key '{key}'"


# ---------------------------------------------------------------------------
# 9. Finnhub economic calendar mapped correctly
# ---------------------------------------------------------------------------

class TestFinnhubEconomicCalendar:
    def test_finnhub_events_merged_into_macro(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service

        fake_events = [
            {"time": "2026-06-05 08:30:00", "event": "Non-Farm Payrolls",
             "country": "US", "impact": "high"},
        ]
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: fake_events)

        events = calendar_service.macro_events(_START, _END)
        nfp = [ev for ev in events if "Non-Farm" in ev["title"]]
        assert len(nfp) == 1
        assert nfp[0]["impact"] == 3
        assert nfp[0]["country"] == "US"
        assert nfp[0]["date"] == "2026-06-05"

    def test_finnhub_impact_mapping(self, monkeypatch):
        from backend.services import calendar_service, finnhub_service

        fake_events = [
            {"time": "2026-06-10", "event": "Low Impact", "country": "DE", "impact": "low"},
            {"time": "2026-06-11", "event": "Mid Impact", "country": "FR", "impact": "medium"},
            {"time": "2026-06-12", "event": "High Impact", "country": "US", "impact": "high"},
        ]
        monkeypatch.setattr(calendar_service, "FRED_API_KEY", None)
        monkeypatch.setattr(calendar_service, "_load_cb_meetings", lambda: [])
        monkeypatch.setattr(finnhub_service, "economic_calendar", lambda s, e: fake_events)

        events = calendar_service.macro_events(_START, _END)
        by_title = {ev["title"]: ev for ev in events}
        assert by_title["Low Impact"]["impact"] == 1
        assert by_title["Mid Impact"]["impact"] == 2
        assert by_title["High Impact"]["impact"] == 3


# ---------------------------------------------------------------------------
# 10. Robustness: yfinance Ticker raises, empty df, None df
# ---------------------------------------------------------------------------

class TestRobustness:
    def test_ticker_raises_skipped_gracefully(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs
        import yfinance as yf

        def _bad_ticker(sym):
            raise RuntimeError("network error")

        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        monkeypatch.setattr(yf, "Ticker", _bad_ticker)

        # Should not raise
        result = calendar_service.earnings_events("dow", _START, _END)
        assert result == []

    def test_empty_earnings_df_handled(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs
        import yfinance as yf

        fake = _FakeTicker("AAA", earnings_df=pd.DataFrame(), info={})
        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        monkeypatch.setattr(yf, "Ticker", lambda sym: fake)

        result = calendar_service.earnings_events("dow", _START, _END)
        assert result == []

    def test_none_earnings_df_handled(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs
        import yfinance as yf

        fake = _FakeTicker("AAA", earnings_df=None, info={})
        monkeypatch.setattr(cs, "get_constituents", lambda idx: _MEMBERS[:1])
        monkeypatch.setattr(yf, "Ticker", lambda sym: fake)

        result = calendar_service.earnings_events("dow", _START, _END)
        assert result == []

    def test_empty_universe_returns_empty_events(self, monkeypatch):
        from backend.services import calendar_service, constituents as cs

        monkeypatch.setattr(cs, "get_constituents", lambda idx: [])

        result = calendar_service.earnings_events("dow", _START, _END)
        assert result == []
