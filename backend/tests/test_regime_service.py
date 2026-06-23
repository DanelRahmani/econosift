"""Unit tests for regime_service — no network calls.

Tests the pure classify_quadrant helper and the structure of regime_series output
using a monkeypatched data-fetch layer so no real FRED/Eurostat calls are made.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.services.regime_service import classify_quadrant


# ---------------------------------------------------------------------------
# classify_quadrant — all four quadrants + None edge cases
# ---------------------------------------------------------------------------

class TestClassifyQuadrant:
    """Pure function; no I/O."""

    def test_goldilocks(self):
        # GDP above threshold, inflation below threshold
        assert classify_quadrant(3.0, 1.5) == "Goldilocks"

    def test_goldilocks_exact_gdp_threshold(self):
        # GDP == threshold counts as "above" (>=)
        assert classify_quadrant(2.0, 1.0) == "Goldilocks"

    def test_overheating(self):
        # Both GDP and inflation above thresholds
        assert classify_quadrant(4.0, 4.0) == "Overheating"

    def test_overheating_exact_cpi_threshold(self):
        # CPI == threshold counts as "above" (>=)
        assert classify_quadrant(3.0, 2.5) == "Overheating"

    def test_slowdown(self):
        # GDP below threshold, inflation below threshold
        assert classify_quadrant(0.5, 1.0) == "Slowdown"

    def test_stagflation(self):
        # GDP below threshold, inflation above threshold
        assert classify_quadrant(-1.0, 5.0) == "Stagflation"

    def test_stagflation_zero_growth(self):
        assert classify_quadrant(0.0, 3.0) == "Stagflation"

    def test_none_gdp_returns_none(self):
        assert classify_quadrant(None, 2.0) is None

    def test_none_cpi_returns_none(self):
        assert classify_quadrant(3.0, None) is None

    def test_both_none_returns_none(self):
        assert classify_quadrant(None, None) is None

    def test_custom_thresholds(self):
        # With stricter thresholds (gdp_thr=3, cpi_thr=3)
        # gdp=2.5 < 3 → below; cpi=2.0 < 3 → below → Slowdown
        assert classify_quadrant(2.5, 2.0, gdp_thr=3.0, cpi_thr=3.0) == "Slowdown"
        # gdp=3.5 >= 3, cpi=3.5 >= 3 → Overheating
        assert classify_quadrant(3.5, 3.5, gdp_thr=3.0, cpi_thr=3.0) == "Overheating"


# ---------------------------------------------------------------------------
# regime_series — structural checks with mocked I/O
# ---------------------------------------------------------------------------

def _make_quarterly_series(start: str, periods: int, values=None) -> pd.Series:
    """Build a quarterly pd.Series with fake values."""
    idx = pd.date_range(start=start, periods=periods, freq="QE")
    if values is None:
        values = [2.5 + i * 0.1 for i in range(periods)]
    return pd.Series(values, index=idx)


class TestRegimeSeriesStructure:
    """Patches out all network fetchers; verifies output shape."""

    def test_output_keys_present(self, monkeypatch):
        from backend.services import regime_service

        gdp_fake = _make_quarterly_series("2020-03-31", 12, [2.5] * 12)
        cpi_fake = _make_quarterly_series("2020-03-31", 12, [2.0] * 12)

        monkeypatch.setattr(regime_service, "_gdp_yoy_quarterly", lambda sy: gdp_fake)
        monkeypatch.setattr(regime_service, "_cpi_yoy_quarterly", lambda sy: cpi_fake)

        result = regime_service.regime_series("US", 2020)

        assert "country" in result
        assert "thresholds" in result
        assert "series" in result
        assert "current" in result
        assert "source" in result
        assert "asOf" in result
        assert "note" in result

    def test_thresholds_values(self, monkeypatch):
        from backend.services import regime_service

        monkeypatch.setattr(regime_service, "_gdp_yoy_quarterly",
                            lambda sy: _make_quarterly_series("2020-03-31", 4))
        monkeypatch.setattr(regime_service, "_cpi_yoy_quarterly",
                            lambda sy: _make_quarterly_series("2020-03-31", 4))

        result = regime_service.regime_series("US", 2020)
        assert result["thresholds"]["gdp"] == 2.0
        assert result["thresholds"]["cpi"] == 2.5

    def test_series_items_have_required_fields(self, monkeypatch):
        from backend.services import regime_service

        gdp_fake = _make_quarterly_series("2020-03-31", 6, [3.0] * 6)
        cpi_fake = _make_quarterly_series("2020-03-31", 6, [1.5] * 6)

        monkeypatch.setattr(regime_service, "_gdp_yoy_quarterly", lambda sy: gdp_fake)
        monkeypatch.setattr(regime_service, "_cpi_yoy_quarterly", lambda sy: cpi_fake)

        result = regime_service.regime_series("US", 2020)
        assert len(result["series"]) > 0

        item = result["series"][0]
        assert "date" in item
        assert "gdpGrowth" in item
        assert "cpiInflation" in item
        assert "quadrant" in item

    def test_goldilocks_quadrant_in_series(self, monkeypatch):
        from backend.services import regime_service

        # GDP=3.0 > 2.0, CPI=1.5 < 2.5 → Goldilocks
        gdp_fake = _make_quarterly_series("2020-03-31", 4, [3.0] * 4)
        cpi_fake = _make_quarterly_series("2020-03-31", 4, [1.5] * 4)

        monkeypatch.setattr(regime_service, "_gdp_yoy_quarterly", lambda sy: gdp_fake)
        monkeypatch.setattr(regime_service, "_cpi_yoy_quarterly", lambda sy: cpi_fake)

        result = regime_service.regime_series("US", 2020)
        quadrants = {item["quadrant"] for item in result["series"]}
        assert "Goldilocks" in quadrants

    def test_current_matches_last_series_item(self, monkeypatch):
        from backend.services import regime_service

        gdp_fake = _make_quarterly_series("2020-03-31", 8, [2.5] * 8)
        cpi_fake = _make_quarterly_series("2020-03-31", 8, [2.0] * 8)

        monkeypatch.setattr(regime_service, "_gdp_yoy_quarterly", lambda sy: gdp_fake)
        monkeypatch.setattr(regime_service, "_cpi_yoy_quarterly", lambda sy: cpi_fake)

        result = regime_service.regime_series("US", 2020)
        assert result["current"] == result["series"][-1]

    def test_empty_series_on_unsupported_country(self, monkeypatch):
        from backend.services import regime_service

        result = regime_service.regime_series("ZZ", 2020)
        assert result["series"] == []
        assert result["current"] is None
        assert result["note"] is not None
        assert "ZZ" in result["note"]

    def test_empty_gdp_and_cpi_gives_empty_series(self, monkeypatch):
        from backend.services import regime_service

        monkeypatch.setattr(regime_service, "_gdp_yoy_quarterly",
                            lambda sy: pd.Series(dtype=float))
        monkeypatch.setattr(regime_service, "_cpi_yoy_quarterly",
                            lambda sy: pd.Series(dtype=float))

        result = regime_service.regime_series("US", 2020)
        assert result["series"] == []
        assert result["current"] is None

    def test_country_us_source_label(self, monkeypatch):
        from backend.services import regime_service

        monkeypatch.setattr(regime_service, "_gdp_yoy_quarterly",
                            lambda sy: _make_quarterly_series("2020-03-31", 4))
        monkeypatch.setattr(regime_service, "_cpi_yoy_quarterly",
                            lambda sy: _make_quarterly_series("2020-03-31", 4))

        result = regime_service.regime_series("US", 2020)
        assert "FRED" in result["source"]
