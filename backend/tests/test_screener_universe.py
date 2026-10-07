"""Offline unit tests for Phase 5 screener service.

All external calls are monkeypatched — no network required.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bdays(n: int) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-06-24", periods=n, freq="B")


def _make_close(data: dict[str, list[float]], n: int) -> pd.DataFrame:
    return pd.DataFrame(data, index=_bdays(n))


def _make_vol(data: dict[str, list[float]], n: int) -> pd.DataFrame:
    return pd.DataFrame(data, index=_bdays(n))


# ---------------------------------------------------------------------------
# _passes_preset
# ---------------------------------------------------------------------------

class TestPassesPreset:
    def _row(self, **kw) -> dict:
        defaults = {
            "symbol": "TEST", "name": "Test Co",
            "price": 100.0, "changePercent": 1.5,
            "high52": 110.0, "low52": 80.0,
            "pe": 14.0, "pb": 1.2,
            "beta": 1.0, "dividendYield": 0.05,
            "roic": 0.20, "roe": 0.18,
            "revenueGrowth": 0.12, "netMargin": 0.15,
            "shortFloat": 0.25, "rsi14": 50.0,
            "aboveSma200": True, "goldenCross": True,
            "volumeRatio": 1.0,
        }
        defaults.update(kw)
        return defaults

    def test_top_gainers_positive_change(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(changePercent=2.0), "top_gainers") is True

    def test_top_gainers_negative_change(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(changePercent=-1.0), "top_gainers") is False

    def test_top_losers_negative_change(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(changePercent=-3.0), "top_losers") is True

    def test_top_losers_positive_change(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(changePercent=1.0), "top_losers") is False

    def test_high_52w_near_high(self):
        from backend.services.screener_service import _passes_preset
        # price = 105, high52 = 110 → 105 >= 110*0.95=104.5 → passes
        assert _passes_preset(self._row(price=105.0, high52=110.0), "high_52w") is True

    def test_high_52w_far_from_high(self):
        from backend.services.screener_service import _passes_preset
        # price = 90, high52 = 110 → 90 < 110*0.95=104.5 → fails
        assert _passes_preset(self._row(price=90.0, high52=110.0), "high_52w") is False

    def test_low_52w_near_low(self):
        from backend.services.screener_service import _passes_preset
        # price = 82, low52 = 80 → 82 <= 80*1.05=84 → passes
        assert _passes_preset(self._row(price=82.0, low52=80.0), "low_52w") is True

    def test_low_52w_far_from_low(self):
        from backend.services.screener_service import _passes_preset
        # price = 95, low52 = 80 → 95 > 80*1.05=84 → fails
        assert _passes_preset(self._row(price=95.0, low52=80.0), "low_52w") is False

    def test_above_sma200_true(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(aboveSma200=True), "above_sma200") is True

    def test_above_sma200_false(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(aboveSma200=False), "above_sma200") is False

    def test_below_sma200_false_means_pass(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(aboveSma200=False), "below_sma200") is True

    def test_unusual_volume(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(volumeRatio=2.5), "unusual_volume") is True
        assert _passes_preset(self._row(volumeRatio=1.5), "unusual_volume") is False

    def test_overbought(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(rsi14=75.0), "overbought") is True
        assert _passes_preset(self._row(rsi14=65.0), "overbought") is False

    def test_oversold(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(rsi14=25.0), "oversold") is True
        assert _passes_preset(self._row(rsi14=35.0), "oversold") is False

    def test_high_beta(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(beta=1.8), "high_beta") is True
        assert _passes_preset(self._row(beta=1.2), "high_beta") is False

    def test_undervalued(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(pe=12.0, pb=1.2), "undervalued") is True
        assert _passes_preset(self._row(pe=20.0, pb=1.2), "undervalued") is False

    def test_high_dividend(self):
        from backend.services.screener_service import _passes_preset
        # dividendYield stored in percent units (BUG-A2); 4.0 = 4% → passes
        assert _passes_preset(self._row(dividendYield=4.0), "high_dividend") is True
        assert _passes_preset(self._row(dividendYield=2.0), "high_dividend") is False

    def test_high_roic(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(roic=0.20), "high_roic") is True
        assert _passes_preset(self._row(roic=0.10), "high_roic") is False

    def test_quality_growth(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(
            self._row(roe=0.20, revenueGrowth=0.15, netMargin=0.12), "quality_growth"
        ) is True
        assert _passes_preset(
            self._row(roe=0.10, revenueGrowth=0.15, netMargin=0.12), "quality_growth"
        ) is False

    def test_deep_value(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(pb=0.8, pe=8.0), "deep_value") is True
        assert _passes_preset(self._row(pb=1.5, pe=8.0), "deep_value") is False

    def test_high_short_interest(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(shortFloat=0.25), "high_short_interest") is True
        assert _passes_preset(self._row(shortFloat=0.15), "high_short_interest") is False

    def test_none_field_returns_false(self):
        from backend.services.screener_service import _passes_preset
        assert _passes_preset(self._row(pe=None, pb=None), "undervalued") is False
        assert _passes_preset(self._row(beta=None), "high_beta") is False


# ---------------------------------------------------------------------------
# apply_presets (AND logic)
# ---------------------------------------------------------------------------

class TestApplyPresets:
    def test_no_presets_returns_all(self):
        from backend.services.screener_service import apply_presets
        rows = [{"symbol": "A", "changePercent": 1.0}, {"symbol": "B", "changePercent": -1.0}]
        assert apply_presets(rows, []) == rows

    def test_single_preset(self):
        from backend.services.screener_service import apply_presets
        rows = [
            {"symbol": "A", "changePercent": 1.5},
            {"symbol": "B", "changePercent": -2.0},
        ]
        result = apply_presets(rows, ["top_gainers"])
        assert [r["symbol"] for r in result] == ["A"]

    def test_and_logic_narrows_results(self):
        from backend.services.screener_service import apply_presets
        rows = [
            {"symbol": "A", "changePercent": 1.5, "volumeRatio": 3.0},
            {"symbol": "B", "changePercent": 1.5, "volumeRatio": 1.0},
            {"symbol": "C", "changePercent": -1.0, "volumeRatio": 3.0},
        ]
        result = apply_presets(rows, ["top_gainers", "unusual_volume"])
        assert [r["symbol"] for r in result] == ["A"]


# ---------------------------------------------------------------------------
# apply_filters
# ---------------------------------------------------------------------------

class TestApplyFilters:
    def _rows(self):
        return [
            {"symbol": "A", "pe": 10.0, "pb": 1.0},
            {"symbol": "B", "pe": 20.0, "pb": 2.0},
            {"symbol": "C", "pe": None,  "pb": 1.5},
        ]

    def test_no_filters_returns_all(self):
        from backend.services.screener_service import apply_filters
        rows = self._rows()
        assert apply_filters(rows, []) == rows

    def test_lt_filter(self):
        from backend.services.screener_service import apply_filters
        result = apply_filters(self._rows(), [{"field": "pe", "op": "lt", "value": 15}])
        assert [r["symbol"] for r in result] == ["A"]

    def test_gt_filter(self):
        from backend.services.screener_service import apply_filters
        result = apply_filters(self._rows(), [{"field": "pe", "op": "gt", "value": 15}])
        assert [r["symbol"] for r in result] == ["B"]

    def test_eq_filter(self):
        from backend.services.screener_service import apply_filters
        result = apply_filters(self._rows(), [{"field": "pe", "op": "eq", "value": 20.0}])
        assert [r["symbol"] for r in result] == ["B"]

    def test_null_field_excluded(self):
        from backend.services.screener_service import apply_filters
        result = apply_filters(self._rows(), [{"field": "pe", "op": "lt", "value": 100}])
        symbols = [r["symbol"] for r in result]
        assert "C" not in symbols

    def test_multiple_filters_and(self):
        from backend.services.screener_service import apply_filters
        result = apply_filters(
            self._rows(),
            [{"field": "pe", "op": "lt", "value": 25}, {"field": "pb", "op": "lt", "value": 1.5}]
        )
        assert [r["symbol"] for r in result] == ["A"]


# ---------------------------------------------------------------------------
# sort_rows
# ---------------------------------------------------------------------------

class TestSortRows:
    def _rows(self):
        return [
            {"symbol": "A", "pe": 5.0},
            {"symbol": "B", "pe": None},
            {"symbol": "C", "pe": 10.0},
        ]

    def test_desc_sort(self):
        from backend.services.screener_service import sort_rows
        result = sort_rows(self._rows(), "pe", "desc")
        assert result[0]["symbol"] == "C"
        assert result[1]["symbol"] == "A"
        assert result[-1]["symbol"] == "B"  # null last

    def test_asc_sort(self):
        from backend.services.screener_service import sort_rows
        result = sort_rows(self._rows(), "pe", "asc")
        assert result[0]["symbol"] == "A"
        assert result[1]["symbol"] == "C"
        assert result[-1]["symbol"] == "B"  # null last regardless of direction

    def test_nulls_always_last_in_asc(self):
        from backend.services.screener_service import sort_rows
        rows = [{"symbol": "X", "v": None}, {"symbol": "Y", "v": 1.0}]
        result = sort_rows(rows, "v", "asc")
        assert result[-1]["symbol"] == "X"

    def test_nulls_always_last_in_desc(self):
        from backend.services.screener_service import sort_rows
        rows = [{"symbol": "X", "v": None}, {"symbol": "Y", "v": 1.0}]
        result = sort_rows(rows, "v", "desc")
        assert result[-1]["symbol"] == "X"


# ---------------------------------------------------------------------------
# _rsi
# ---------------------------------------------------------------------------

class TestRsi:
    def test_flat_series_returns_none_if_short(self):
        from backend.services.screener_service import _rsi
        s = pd.Series([100.0] * 5)
        assert _rsi(s) is None

    def test_all_gains_returns_100(self):
        from backend.services.screener_service import _rsi
        # Strictly increasing series — RSI should be 100 (no losses)
        s = pd.Series(np.linspace(100, 200, 30))
        result = _rsi(s)
        assert result == pytest.approx(100.0, abs=0.01)

    def test_all_losses_returns_near_zero(self):
        from backend.services.screener_service import _rsi
        s = pd.Series(np.linspace(200, 100, 30))
        result = _rsi(s)
        assert result is not None
        assert result < 5.0

    def test_rsi_in_range(self):
        from backend.services.screener_service import _rsi
        rng = np.random.default_rng(42)
        s = pd.Series(100 + np.cumsum(rng.normal(0, 1, 50)))
        result = _rsi(s)
        assert result is not None
        assert 0.0 <= result <= 100.0


# ---------------------------------------------------------------------------
# _compute_technicals
# ---------------------------------------------------------------------------

class TestComputeTechnicals:
    def _close(self, sym: str, prices: list[float]) -> pd.DataFrame:
        return pd.DataFrame({sym: prices}, index=_bdays(len(prices)))

    def _vol(self, sym: str, volumes: list[float]) -> pd.DataFrame:
        return pd.DataFrame({sym: volumes}, index=_bdays(len(volumes)))

    def test_price_is_last_close(self):
        from backend.services.screener_service import _compute_technicals
        prices = list(np.linspace(100, 120, 250))
        result = _compute_technicals("AAAA", self._close("AAAA", prices), None)
        assert result["price"] == pytest.approx(120.0, abs=0.01)

    def test_change_percent_correct(self):
        from backend.services.screener_service import _compute_technicals
        prices = [100.0] * 248 + [100.0, 105.0]  # last day +5%
        result = _compute_technicals("AAAA", self._close("AAAA", prices), None)
        assert result["changePercent"] == pytest.approx(5.0, abs=0.01)

    def test_above_sma200_true(self):
        from backend.services.screener_service import _compute_technicals
        # 200 days at 100, then last 50 climb to 150; last price > SMA200
        prices = [100.0] * 200 + list(np.linspace(100, 150, 50))
        result = _compute_technicals("AAAA", self._close("AAAA", prices), None)
        assert result["aboveSma200"] is True

    def test_spark_length(self):
        from backend.services.screener_service import _compute_technicals
        prices = list(range(1, 301))  # 300 days
        result = _compute_technicals("AAAA", self._close("AAAA", prices), None)
        # spark = last 63 closes
        assert len(result["spark"]) == 63

    def test_volume_ratio(self):
        from backend.services.screener_service import _compute_technicals
        prices = [100.0] * 50
        # avg20 includes the spike day itself, so ratio = 3M / ((19*1M+3M)/20) ≈ 2.73
        vols = [1_000_000.0] * 49 + [3_000_000.0]
        result = _compute_technicals(
            "AAAA",
            self._close("AAAA", prices),
            self._vol("AAAA", vols),
        )
        assert result["volumeRatio"] is not None
        assert result["volumeRatio"] > 2.0  # clearly above baseline

    def test_missing_symbol_returns_nones(self):
        from backend.services.screener_service import _compute_technicals
        prices = list(range(1, 50))
        frame = self._close("OTHER", prices)
        result = _compute_technicals("AAAA", frame, None)
        assert result["price"] is None
        assert result["changePercent"] is None

    def test_empty_frame_returns_nones(self):
        from backend.services.screener_service import _compute_technicals
        result = _compute_technicals("AAAA", pd.DataFrame(), None)
        assert result["price"] is None


# ---------------------------------------------------------------------------
# HTTP endpoints (using TestClient)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_screener(monkeypatch):
    """Prevent warm_all() from running during tests and provide stub data."""
    from backend.services import screener_service, screener_cache, constituents

    _MEMBERS = [
        {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics"},
        {"symbol": "MSFT", "name": "Microsoft", "sector": "Technology", "industry": "Software"},
    ]

    monkeypatch.setattr(constituents, "get_constituents", lambda idx: _MEMBERS)
    monkeypatch.setattr(screener_cache, "row_count", lambda syms: len(syms))
    monkeypatch.setattr(screener_cache, "last_refresh", lambda syms: "2026-06-24T00:00:00+00:00")
    monkeypatch.setattr(screener_cache, "is_stale", lambda syms: False)
    monkeypatch.setattr(
        screener_cache, "get_rows",
        lambda syms: [
            {"symbol": "AAPL", "name": "Apple Inc.", "marketCap": 3e12, "changePercent": 1.5},
            {"symbol": "MSFT", "name": "Microsoft", "marketCap": 2.8e12, "changePercent": -0.5},
        ]
    )
    monkeypatch.setattr(screener_service, "warm_all", lambda: None)


def test_presets_endpoint(client):
    resp = client.get("/api/screener/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert "presets" in data
    assert len(data["presets"]) > 0
    first = data["presets"][0]
    assert "id" in first and "label" in first and "category" in first


def test_status_endpoint_dow(client):
    resp = client.get("/api/screener/status?index=dow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["index"] == "dow"
    assert data["rowCount"] == 2  # from stub _MEMBERS
    assert data["stale"] is False


def test_status_endpoint_invalid_index(client):
    resp = client.get("/api/screener/status?index=invalid")
    assert resp.status_code == 422


def test_universe_endpoint_returns_results(client):
    resp = client.get("/api/screener/universe?index=dow&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["index"] == "dow"
    assert len(data["results"]) == 2


def test_universe_endpoint_invalid_index(client):
    resp = client.get("/api/screener/universe?index=bogus")
    assert resp.status_code == 422


def test_refresh_endpoint(client, monkeypatch):
    from backend.services import screener_service
    called = []
    monkeypatch.setattr(screener_service, "refresh_universe", lambda idx: called.append(idx))
    resp = client.post("/api/screener/refresh?index=dow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["started"] is True


def test_universe_provenance_is_dated_by_the_snapshot(client, monkeypatch):
    # P1-20: the Navbar's "Data as of" reads provenance fetchedAt. The universe
    # is a stored snapshot, so its fetchedAt is the snapshot time (asOf), not
    # the time of the request.
    from backend.services import screener_service
    monkeypatch.setattr(screener_service, "query", lambda **kw: {
        "index": "dow", "results": [{"ticker": "AAPL"}], "count": 1,
        "asOf": "2026-10-02T09:47:14.485149+00:00", "stale": False})
    resp = client.get("/api/screener/universe?index=dow")
    assert resp.json()["provenance"]["*"]["fetchedAt"] == "2026-10-02T09:47:14Z"


def test_screener_roic_uses_the_wacc_tax_rate(monkeypatch):
    # A tax benefit (provision -50 on pretax 100) made the old effective rate
    # -50%, so NOPAT = 100 × 1.5 = 150 and ROIC = 150 / (400 + 100) = 0.30.
    # Like Markets (P3-21) the rate now comes from discount_rates.tax_rate_for:
    # no usable effectiveTaxRate, no country entry -> 21%, NOPAT = 79,
    # ROIC = 79 / 500 = 0.158.
    from backend.services import discount_rates, screener_service
    monkeypatch.setattr(discount_rates, "load_erp", lambda: {"countries": {}})
    monkeypatch.setattr(screener_service.yfs, "get_info", lambda sym: {
        "info": {"country": "United States"},
        "financials": {"EBIT": 100.0, "Tax Provision": -50.0, "Pretax Income": 100.0},
        "balance_sheet": {"Stockholders Equity": 400.0, "Total Debt": 100.0},
        "cashflow": {},
    })
    row = screener_service._fetch_ticker_fundamentals("TEST")
    assert row["roic"] == pytest.approx(0.158)
