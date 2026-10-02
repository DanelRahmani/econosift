"""Offline known-value tests for Phase 54 audit findings M-07 and M-08.

M-07: YTD return base must be the last close of the *prior* calendar year, not the first January close
      (sector returns and the treemap).
M-08: the sector table (fundamentals) and the sector chart (returns) must use one definition of the
      N-session base: "close N trading sessions earlier" = ``series.iloc[-1 - N]``.

No network: ``yfs.get_close_frame`` and ``yf.Ticker`` are monkeypatched.
"""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_caches():
    from backend import cache
    cache._caches.clear()
    cache._stats.clear()
    yield
    cache._caches.clear()
    cache._stats.clear()


def _row(rows: list[dict], ticker: str) -> dict:
    return next(r for r in rows if r["ticker"] == ticker)


# ---------------------------------------------------------------------------
# M-07 — YTD base
# ---------------------------------------------------------------------------

# Dec-30 and Dec-31 are the prior year; Jan-02 is the first January close.
_YTD_INDEX = pd.to_datetime(["2025-12-30", "2025-12-31", "2026-01-02", "2026-01-05", "2026-01-06"])


class TestSectorYtd:
    def test_ytd_base_is_prior_year_end_close(self, monkeypatch):
        from backend.services import sector_service, yfinance_service

        # XLK: prior year-end close (31 Dec) = 110, first Jan close = 120, last = 132.
        #   correct YTD = 132 / 110 - 1 = +20.00 %   (old code: 132 / 120 - 1 = +10.00 %)
        # SPY: 31 Dec = 400, 2 Jan = 410, last = 440.
        #   correct YTD = 440 / 400 - 1 = +10.00 %   -> XLK vs SPY = +10.00 pp
        frame = pd.DataFrame({
            "XLK": [100.0, 110.0, 120.0, 121.0, 132.0],
            "SPY": [390.0, 400.0, 410.0, 415.0, 440.0],
        }, index=_YTD_INDEX)
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda syms, period: frame)

        out = sector_service.get_sector_returns()
        xlk = _row(out["periods"]["ytd"], "XLK")
        assert xlk["changePercent"] == pytest.approx(20.0, abs=0.005)
        assert xlk["vsSpy"] == pytest.approx(10.0, abs=0.005)

    def test_ytd_is_none_when_history_misses_prior_year_end(self, monkeypatch):
        from backend.services import sector_service, yfinance_service

        # No row before 1 Jan -> there is no honest YTD base; never fall back to the first January close.
        frame = pd.DataFrame({
            "XLK": [120.0, 121.0, 132.0],
            "SPY": [410.0, 415.0, 440.0],
        }, index=pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]))
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda syms, period: frame)

        out = sector_service.get_sector_returns()
        xlk = _row(out["periods"]["ytd"], "XLK")
        assert xlk["changePercent"] is None
        assert xlk["vsSpy"] is None


class TestTreemapYtd:
    @pytest.fixture()
    def patch_all(self, monkeypatch):
        from backend.services import constituents, yfinance_service

        members = [
            {"symbol": "AAA", "name": "Alpha", "sector": "Technology", "industry": "Software"},
            {"symbol": "BBB", "name": "Beta", "sector": "Financials", "industry": "Banks"},
        ]
        # AAA: 31 Dec = 110, 2 Jan = 120, last = 132 -> YTD = 132/110 - 1 = +20.00 % (old: +10.00 %)
        # BBB: 31 Dec = 200, 2 Jan = 190, last = 180 -> YTD = 180/200 - 1 = -10.00 % (old: -5.26 %)
        frame = pd.DataFrame({
            "AAA": [100.0, 110.0, 120.0, 121.0, 132.0],
            "BBB": [205.0, 200.0, 190.0, 185.0, 180.0],
        }, index=_YTD_INDEX)
        monkeypatch.setattr(constituents, "get_constituents", lambda idx: members)
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda syms, period: frame)
        monkeypatch.setattr(yfinance_service, "get_market_caps",
                            lambda syms: {"AAA": 1e9, "BBB": 5e8})
        return frame

    def test_treemap_ytd_uses_prior_year_end(self, patch_all):
        from backend.services.treemap_service import treemap

        by = {s["symbol"]: s for s in treemap("sp500", "ytd")["stocks"]}
        assert by["AAA"]["changePercent"] == pytest.approx(20.0, abs=0.005)
        assert by["BBB"]["changePercent"] == pytest.approx(-10.0, abs=0.005)

    def test_treemap_ytd_drops_symbol_without_prior_year_close(self, monkeypatch):
        from backend.services import constituents, yfinance_service
        from backend.services.treemap_service import treemap

        members = [
            {"symbol": "AAA", "name": "Alpha", "sector": "Technology", "industry": "Software"},
            {"symbol": "NEW", "name": "Recent IPO", "sector": "Technology", "industry": "Software"},
        ]
        # NEW listed on 2 Jan: no December close, so no honest YTD base -> dropped.
        frame = pd.DataFrame({
            "AAA": [100.0, 110.0, 120.0, 121.0, 132.0],
            "NEW": [float("nan"), float("nan"), 20.0, 21.0, 22.0],
        }, index=_YTD_INDEX)
        monkeypatch.setattr(constituents, "get_constituents", lambda idx: members)
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda syms, period: frame)
        monkeypatch.setattr(yfinance_service, "get_market_caps", lambda syms: {"AAA": 1e9, "NEW": 1e8})

        syms = {s["symbol"] for s in treemap("sp500", "ytd")["stocks"]}
        assert syms == {"AAA"}


# ---------------------------------------------------------------------------
# M-08 — table and chart share the N-session base
# ---------------------------------------------------------------------------

class _FakeTicker:
    def __init__(self, sym):
        self.info = {}


class TestSectorTableMatchesChart:
    @pytest.fixture()
    def patch_all(self, monkeypatch):
        from backend.services import sector_service, yfinance_service

        # 130 business days, XLK close = 100 + i  (i = 0..129), so last = 229.
        idx = pd.bdate_range(end="2026-06-30", periods=130)
        frame = pd.DataFrame({
            "XLK": [100.0 + i for i in range(130)],
            "SPY": [100.0 + i for i in range(130)],
        }, index=idx)
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda syms, period: frame)
        monkeypatch.setattr(sector_service.yf, "Ticker", _FakeTicker)

    def test_three_month_is_63_sessions_back_in_both(self, patch_all):
        from backend.services import sector_service

        # 63 sessions before the last close (i = 129) is i = 66 -> 166.
        #   229 / 166 - 1 = +37.95 %   (old table used i = 67 -> 167 -> +37.13 %)
        chart = _row(sector_service.get_sector_returns()["periods"]["3m"], "XLK")["changePercent"]
        table = _row(sector_service.get_sector_fundamentals(), "XLK")["return3m"]
        assert chart == pytest.approx(37.95, abs=0.005)
        assert table == pytest.approx(37.95, abs=0.005)

    def test_six_month_is_126_sessions_back(self, patch_all):
        from backend.services import sector_service

        # 126 sessions before i = 129 is i = 3 -> 103.  229 / 103 - 1 = +122.33 %
        # (old table used i = 4 -> 104 -> +120.19 %)
        table = _row(sector_service.get_sector_fundamentals(), "XLK")["return6m"]
        assert table == pytest.approx(122.33, abs=0.005)

    def test_one_month_unchanged_and_consistent(self, patch_all):
        from backend.services import sector_service

        # 21 sessions back: i = 108 -> 208.  229 / 208 - 1 = +10.10 %
        chart = _row(sector_service.get_sector_returns()["periods"]["1m"], "XLK")["changePercent"]
        table = _row(sector_service.get_sector_fundamentals(), "XLK")["return1m"]
        assert chart == pytest.approx(10.10, abs=0.005)
        assert table == pytest.approx(10.10, abs=0.005)

    def test_short_history_gives_none_not_a_clamped_number(self, monkeypatch):
        from backend.services import sector_service, yfinance_service

        # 40 rows cannot support a 63-session base: report None instead of silently using the first row.
        idx = pd.bdate_range(end="2026-06-30", periods=40)
        frame = pd.DataFrame({"XLK": [100.0 + i for i in range(40)],
                              "SPY": [100.0 + i for i in range(40)]}, index=idx)
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda syms, period: frame)
        monkeypatch.setattr(sector_service.yf, "Ticker", _FakeTicker)

        assert _row(sector_service.get_sector_returns()["periods"]["3m"], "XLK")["changePercent"] is None
        assert _row(sector_service.get_sector_fundamentals(), "XLK")["return3m"] is None


def test_sector_chart_endpoint_ytd_uses_prior_year_end(monkeypatch):
    # /api/market/sectors?period=ytd (the Sectors heatmap) measured YTD from the first January close.
    # Closes: 2025-12-31 100, 2026-01-02 110, latest 120 -> YTD = 120/100 - 1 = 20 % (not 120/110 - 1 = 9.09 %).
    import asyncio
    from backend.routers import market as market_router
    idx = pd.to_datetime(["2025-12-30", "2025-12-31", "2026-01-02", "2026-03-02"])
    asked = []

    def frame(syms, period):
        asked.append(period)
        return pd.DataFrame({s: [99.0, 100.0, 110.0, 120.0] for s in syms}, index=idx)
    monkeypatch.setattr(market_router.yfs, "get_close_frame", frame)
    out = asyncio.run(market_router.sectors("ytd"))
    assert asked == ["1y"]
    assert all(r["changePercent"] == 20.0 for r in out["sectors"])


# ---------------------------------------------------------------------------
# P2-31 — Treemap, sector chart and Sectors heatmap share the N-session base
# ---------------------------------------------------------------------------

# 300 business days, close = 100 + i (i = 0..299), last = 399.
#   1w  =   5 sessions back: i = 294 -> 394.  399/394 - 1 =   +1.27 %
#   1m  =  21 sessions back: i = 278 -> 378.  399/378 - 1 =   +5.56 %
#   3m  =  63 sessions back: i = 236 -> 336.  399/336 - 1 =  +18.75 %
#   6m  = 126 sessions back: i = 173 -> 273.  399/273 - 1 =  +46.15 %
#   1y  = 252 sessions back: i =  47 -> 147.  399/147 - 1 = +171.43 %
# Old treemap/heatmap base = first close of the download window (i = 0 -> 100: 1y +299 %).
_P231_IDX = pd.bdate_range(end="2026-06-30", periods=300)
_P231_EXPECTED = {"1w": 1.27, "1m": 5.56, "3m": 18.75, "1y": 171.43}


class TestSessionBaseEverywhere:
    @pytest.fixture()
    def patch_all(self, monkeypatch):
        from backend.services import constituents, sector_service, yfinance_service
        members = [{"symbol": "XLK", "name": "Tech SPDR", "sector": "Technology", "industry": "ETF"}]

        def frame(syms, period):
            return pd.DataFrame({s: [100.0 + i for i in range(300)] for s in syms}, index=_P231_IDX)
        monkeypatch.setattr(constituents, "get_constituents", lambda idx: members)
        monkeypatch.setattr(yfinance_service, "get_close_frame", frame)
        monkeypatch.setattr(yfinance_service, "get_market_caps", lambda syms: {"XLK": 1e9})
        monkeypatch.setattr(sector_service.yf, "Ticker", _FakeTicker)

    @pytest.mark.parametrize("period", ["1w", "1m", "3m", "1y"])
    def test_treemap_equals_sector_chart(self, patch_all, period):
        from backend import cache
        from backend.services import sector_service
        from backend.services.treemap_service import treemap

        tile = treemap("sp500", period)["stocks"][0]["changePercent"]
        cache._caches.clear()
        chart = _row(sector_service.get_sector_returns()["periods"][period], "XLK")["changePercent"]
        assert tile == pytest.approx(_P231_EXPECTED[period], abs=0.005)
        assert chart == pytest.approx(_P231_EXPECTED[period], abs=0.005)

    @pytest.mark.parametrize("period,expected", [("1mo", 5.56), ("3mo", 18.75), ("6mo", 46.15), ("1y", 171.43)])
    def test_sectors_heatmap_uses_the_same_base(self, patch_all, period, expected):
        import asyncio
        from backend.routers import market as market_router

        out = asyncio.run(market_router.sectors(period))
        assert _row(out["sectors"], "XLK")["changePercent"] == pytest.approx(expected, abs=0.005)


def test_treemap_short_history_drops_the_tile_instead_of_using_the_first_close(monkeypatch):
    # 40 rows cannot reach a 63-session base: no tile rather than a mislabelled return.
    from backend.services import constituents, yfinance_service
    from backend.services.treemap_service import treemap
    idx = pd.bdate_range(end="2026-06-30", periods=40)
    monkeypatch.setattr(constituents, "get_constituents",
                        lambda idx_: [{"symbol": "AAA", "name": "A", "sector": "T", "industry": "S"}])
    monkeypatch.setattr(yfinance_service, "get_close_frame",
                        lambda syms, period: pd.DataFrame({"AAA": [100.0 + i for i in range(40)]}, index=idx))
    monkeypatch.setattr(yfinance_service, "get_market_caps", lambda syms: {"AAA": 1e9})
    assert treemap("sp500", "3m")["stocks"] == []
