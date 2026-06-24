"""Offline unit tests for Phase 3 treemap service and constituents industry field.

All external calls are monkeypatched — no network required.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_caches():
    """Isolate each test: clear the TTL caches before and after."""
    from backend import cache
    cache._caches.clear()
    cache._stats.clear()
    yield
    cache._caches.clear()
    cache._stats.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bdays(n: int) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-06-23", periods=n, freq="B")


def _make_frame(data: dict[str, list[float]], n: int = 10) -> pd.DataFrame:
    return pd.DataFrame(data, index=_bdays(n))


# Three stocks: AAA and BBB have market caps; CCC is missing its cap.
_SYMS = ("AAA", "BBB", "CCC")

_MEMBERS = [
    {"symbol": "AAA", "name": "Alpha Corp",  "sector": "Technology",  "industry": "Semiconductors"},
    {"symbol": "BBB", "name": "Beta Corp",   "sector": "Financials",  "industry": "Banks"},
    {"symbol": "CCC", "name": "Gamma Corp",  "sector": "Health Care", "industry": "Biotech"},
]

_MCAPS = {"AAA": 1_000_000_000.0, "BBB": 500_000_000.0}  # CCC intentionally absent

# 10 business-day price history: AAA up, BBB down, CCC flat
_PRICES_AAA = list(np.linspace(100.0, 120.0, 10))   # +20% over window
_PRICES_BBB = list(np.linspace(200.0, 180.0, 10))   # -10% over window
_PRICES_CCC = [50.0] * 10                            # unchanged


def _make_close_frame(n: int = 10) -> pd.DataFrame:
    return _make_frame(
        {"AAA": _PRICES_AAA[:n], "BBB": _PRICES_BBB[:n], "CCC": _PRICES_CCC[:n]},
        n=n,
    )


# ---------------------------------------------------------------------------
# treemap_service tests
# ---------------------------------------------------------------------------

class TestTreemapService:
    @pytest.fixture()
    def patch_all(self, monkeypatch):
        from backend.services import treemap_service, constituents, yfinance_service

        monkeypatch.setattr(constituents, "get_constituents", lambda idx: _MEMBERS)
        frame = _make_close_frame()
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda syms, period: frame)
        monkeypatch.setattr(yfinance_service, "get_market_caps", lambda syms: dict(_MCAPS))
        return frame

    def test_payload_top_level_keys(self, patch_all):
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1d")
        assert set(result.keys()) == {"index", "period", "asOf", "stocks"}

    def test_index_and_period_echoed(self, patch_all):
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1w")
        assert result["index"] == "sp500"
        assert result["period"] == "1w"

    def test_mcap_less_stock_dropped(self, patch_all):
        """CCC has no market cap and must not appear in stocks."""
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1d")
        syms = {s["symbol"] for s in result["stocks"]}
        assert "CCC" not in syms
        assert {"AAA", "BBB"} == syms

    def test_stock_schema(self, patch_all):
        """Every stock dict must carry all required keys."""
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1d")
        required = {"symbol", "name", "sector", "industry", "price",
                    "changePercent", "marketCap", "high52", "low52"}
        for stock in result["stocks"]:
            assert required <= set(stock.keys()), f"Missing keys in {stock}"

    def test_change_percent_1d(self, patch_all):
        """1d return: last close vs previous close."""
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1d")
        by = {s["symbol"]: s for s in result["stocks"]}

        # AAA: linspace 100→120 over 10 steps, step = 20/9
        step = (120.0 - 100.0) / 9
        expected_aaa = round((step / (_PRICES_AAA[-2])) * 100.0, 2)
        assert by["AAA"]["changePercent"] == pytest.approx(expected_aaa, abs=0.01)

        # BBB: decreasing, so changePercent should be negative
        assert by["BBB"]["changePercent"] < 0

    def test_price_is_last_close(self, patch_all):
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1d")
        by = {s["symbol"]: s for s in result["stocks"]}
        assert by["AAA"]["price"] == pytest.approx(120.0, abs=0.01)
        assert by["BBB"]["price"] == pytest.approx(180.0, abs=0.01)

    def test_period_window_mapping(self, monkeypatch):
        """The *first* call to get_close_frame must use the window from _PERIOD_MAP."""
        from backend.services import treemap_service, constituents, yfinance_service

        first_calls: list[str] = []

        def _fake_close(syms, period):
            first_calls.append(period)
            return _make_close_frame()

        monkeypatch.setattr(constituents, "get_constituents", lambda idx: _MEMBERS)
        monkeypatch.setattr(yfinance_service, "get_close_frame", _fake_close)
        monkeypatch.setattr(yfinance_service, "get_market_caps", lambda syms: dict(_MCAPS))

        for ui_period, expected_window in treemap_service._PERIOD_MAP.items():
            # clear cache so each call actually hits the function
            from backend import cache
            cache._caches.clear()
            first_calls.clear()
            treemap_service.treemap("sp500", ui_period)
            # The first download must use the mapped window; a second download
            # (for 52w range) is allowed and uses "1y".
            assert len(first_calls) >= 1, f"get_close_frame not called for period '{ui_period}'"
            assert first_calls[0] == expected_window, (
                f"UI period '{ui_period}' should map to window '{expected_window}' "
                f"as first call, got '{first_calls[0]}'"
            )

    def test_as_of_date(self, patch_all):
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1d")
        assert result["asOf"] == "2026-06-23"

    def test_empty_universe_returns_empty_stocks(self, monkeypatch):
        from backend.services import treemap_service, constituents, yfinance_service
        monkeypatch.setattr(constituents, "get_constituents", lambda idx: [])
        result = treemap_service.treemap("sp500", "1d")
        assert result["stocks"] == []

    def test_empty_frame_returns_empty_stocks(self, monkeypatch):
        from backend.services import treemap_service, constituents, yfinance_service
        monkeypatch.setattr(constituents, "get_constituents", lambda idx: _MEMBERS)
        monkeypatch.setattr(yfinance_service, "get_close_frame", lambda s, p: pd.DataFrame())
        monkeypatch.setattr(yfinance_service, "get_market_caps", lambda syms: dict(_MCAPS))
        result = treemap_service.treemap("sp500", "1d")
        assert result["stocks"] == []

    def test_sector_and_industry_populated(self, patch_all):
        from backend.services.treemap_service import treemap
        result = treemap("sp500", "1d")
        by = {s["symbol"]: s for s in result["stocks"]}
        assert by["AAA"]["sector"] == "Technology"
        assert by["AAA"]["industry"] == "Semiconductors"
        assert by["BBB"]["sector"] == "Financials"


# ---------------------------------------------------------------------------
# constituents industry field tests
# ---------------------------------------------------------------------------

# S&P 500-style table with both GICS Sector and GICS Sub-Industry columns.
_SP_WITH_SUBIND = """
{| class="wikitable sortable"
|-
! Symbol !! Security !! GICS Sector !! GICS Sub-Industry
|-
| AAPL || Apple Inc. || Information Technology || Technology Hardware, Storage & Peripherals
|-
| JPM || JPMorgan Chase || Financials || Diversified Banks
|-
| BRK.B || Berkshire Hathaway || Financials || Multi-Sector Holdings
|}
"""

# Dow-style table with only a bare "Sector" column (no sub-industry).
_DOW_NO_SUBIND = """
{| class="wikitable"
|-
! Company !! Exchange !! Symbol !! Sector
|-
| 3M || NYSE || MMM || Industrials
|-
| Amgen || Nasdaq || AMGN || Health care
|}
"""


class TestConstituentsIndustry:
    def test_industry_parsed_from_sp500_table(self):
        from backend.services.constituents import _parse_constituents
        rows = _parse_constituents(_SP_WITH_SUBIND, "sp500")
        by = {r["symbol"]: r for r in rows}
        assert by["AAPL"]["industry"] == "Technology Hardware, Storage & Peripherals"
        assert by["JPM"]["industry"] == "Diversified Banks"
        assert by["BRK-B"]["industry"] == "Multi-Sector Holdings"

    def test_sector_is_gics_sector_not_subindustry(self):
        """The 'sector' field must be the GICS Sector column, not Sub-Industry."""
        from backend.services.constituents import _parse_constituents
        rows = _parse_constituents(_SP_WITH_SUBIND, "sp500")
        by = {r["symbol"]: r for r in rows}
        # sector should be the broad sector, NOT the sub-industry value
        assert by["AAPL"]["sector"] == "Information Technology"
        assert by["AAPL"]["sector"] != by["AAPL"]["industry"]
        assert by["JPM"]["sector"] == "Financials"

    def test_industry_none_when_no_subindustry_column(self):
        """Tables without a GICS Sub-Industry column must yield industry=None."""
        from backend.services.constituents import _parse_constituents
        rows = _parse_constituents(_DOW_NO_SUBIND, "dow")
        by = {r["symbol"]: r for r in rows}
        assert by["MMM"]["industry"] is None
        assert by["AMGN"]["industry"] is None

    def test_industry_none_does_not_break_sector(self):
        """Sector must still resolve correctly when sub-industry column is absent."""
        from backend.services.constituents import _parse_constituents
        rows = _parse_constituents(_DOW_NO_SUBIND, "dow")
        by = {r["symbol"]: r for r in rows}
        assert by["MMM"]["sector"] == "Industrials"

    def test_industry_key_present_in_all_rows(self):
        """The 'industry' key must exist in every returned dict (may be None)."""
        from backend.services.constituents import _parse_constituents
        for wikitext, idx in [(_SP_WITH_SUBIND, "sp500"), (_DOW_NO_SUBIND, "dow")]:
            rows = _parse_constituents(wikitext, idx)
            for row in rows:
                assert "industry" in row, f"'industry' key missing in {row}"

    def test_backward_compat_existing_keys_present(self):
        """Existing callers rely on symbol/name/sector — all must still be present."""
        from backend.services.constituents import _parse_constituents
        rows = _parse_constituents(_SP_WITH_SUBIND, "sp500")
        for row in rows:
            for key in ("symbol", "name", "sector"):
                assert key in row, f"Key '{key}' missing in {row}"
