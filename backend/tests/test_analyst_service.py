"""Unit tests for analyst_service — fully offline via monkeypatching.

All tests patch `yf.Ticker` in the *analyst_service* module's namespace so
no real network calls are made.  Tests verify:
  - price-target upside is computed correctly
  - missing yfinance attributes yield None / [] without raising
  - a completely-empty fake Ticker returns the full expected shape
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Fake Ticker helpers
# ---------------------------------------------------------------------------

class _FakeTicker:
    """Minimal stand-in for yf.Ticker with configurable internals."""

    def __init__(
        self,
        info: dict | None = None,
        recommendations: pd.DataFrame | None = None,
        earnings_dates: pd.DataFrame | None = None,
        earnings_estimate: pd.DataFrame | None = None,
        revenue_estimate: pd.DataFrame | None = None,
        growth_estimates: pd.DataFrame | None = None,
    ):
        self._info = info or {}
        self.recommendations = recommendations
        self.earnings_dates = earnings_dates
        self.earnings_estimate = earnings_estimate
        self.revenue_estimate = revenue_estimate
        self.growth_estimates = growth_estimates

    def get_info(self) -> dict:
        return self._info

    # Some yfinance versions expose .info as a property
    @property
    def info(self) -> dict:
        return self._info


def _make_ticker(info: dict | None = None, **kwargs) -> _FakeTicker:
    return _FakeTicker(info=info, **kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _FakeYF:
    """Mimics the yfinance module namespace — just needs .Ticker."""

    def __init__(self, fake: "_FakeTicker"):
        self._fake = fake

    def Ticker(self, sym: str) -> "_FakeTicker":  # noqa: N802
        return self._fake


@pytest.fixture()
def patch_ticker(monkeypatch):
    """Return a factory that installs a fake Ticker and returns the analyst_service module."""
    import backend.services.analyst_service as svc

    def _install(fake: _FakeTicker):
        monkeypatch.setattr(svc, "yf", _FakeYF(fake))
        # Bust the cache so each test exercises fresh code paths
        from backend.cache import _caches
        _caches.pop("analyst", None)
        return svc

    return _install


# ---------------------------------------------------------------------------
# 1. Price-target upside computation
# ---------------------------------------------------------------------------

class TestPriceTargetUpside:
    def test_upside_computed_correctly(self, patch_ticker):
        fake = _make_ticker(info={
            "currentPrice": 100.0,
            "targetMeanPrice": 120.0,
            "targetHighPrice": 140.0,
            "targetLowPrice": 90.0,
            "targetMedianPrice": 118.0,
            "numberOfAnalystOpinions": 15,
            "currency": "USD",
        })
        svc = patch_ticker(fake)
        result = svc.analyst_data("AAPL")

        pt = result["priceTarget"]
        assert pt["meanPrice"] == 120.0
        assert pt["highPrice"] == 140.0
        assert pt["lowPrice"] == 90.0
        assert pt["medianPrice"] == 118.0
        assert pt["numberOfAnalysts"] == 15
        # upside = (120 - 100) / 100 = 0.20
        assert abs(pt["upsidePct"] - 0.20) < 1e-9

    def test_upside_none_when_price_missing(self, patch_ticker):
        fake = _make_ticker(info={"targetMeanPrice": 120.0, "currency": "USD"})
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        assert result["priceTarget"]["upsidePct"] is None

    def test_upside_none_when_mean_price_missing(self, patch_ticker):
        fake = _make_ticker(info={"currentPrice": 100.0, "currency": "USD"})
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        assert result["priceTarget"]["upsidePct"] is None

    def test_negative_upside(self, patch_ticker):
        # mean below current price → negative upside
        fake = _make_ticker(info={
            "currentPrice": 200.0,
            "targetMeanPrice": 150.0,
            "currency": "USD",
        })
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        pt = result["priceTarget"]
        assert pt["upsidePct"] is not None
        assert pt["upsidePct"] < 0


# ---------------------------------------------------------------------------
# 2. Missing attributes yield None / [] without raising
# ---------------------------------------------------------------------------

class TestMissingAttributes:
    def test_no_recommendations_gives_empty_history(self, patch_ticker):
        fake = _make_ticker(info={"currency": "USD"})
        # .recommendations is None by default
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        assert result["consensus"]["history"] == []

    def test_no_earnings_dates_gives_empty_list(self, patch_ticker):
        fake = _make_ticker(info={"currency": "USD"})
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        assert result["earningsSurprises"] == []

    def test_no_estimates_dfs_falls_back_to_info_fields(self, patch_ticker):
        fake = _make_ticker(info={
            "currency": "USD",
            "forwardEps": 5.5,
            "forwardPE": 22.0,
            "revenueGrowth": 0.08,
        })
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        est = result["estimates"]
        assert est["forwardEps"] == 5.5
        assert est["forwardPE"] == 22.0
        assert abs(est["revenueGrowth"] - 0.08) < 1e-9

    def test_no_growth_estimates_gives_none(self, patch_ticker):
        fake = _make_ticker(info={"currency": "USD"})
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        assert result["growthEstimates"] is None

    def test_bad_numeric_in_info_does_not_raise(self, patch_ticker):
        fake = _make_ticker(info={
            "currency": "USD",
            "targetMeanPrice": "not-a-number",
            "currentPrice": "also-bad",
            "recommendationMean": float("nan"),
        })
        svc = patch_ticker(fake)
        # Must not raise
        result = svc.analyst_data("X")
        assert result["priceTarget"]["meanPrice"] is None
        assert result["price"] is None
        assert result["consensus"]["recommendationMean"] is None

    def test_recommendations_with_bad_dataframe_gives_empty_history(self, patch_ticker):
        # DataFrame with unexpected columns should degrade gracefully
        bad_df = pd.DataFrame({"weirdCol": [1, 2]})
        fake = _make_ticker(info={"currency": "USD"}, recommendations=bad_df)
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        # history should still be a list (possibly with partial entries)
        assert isinstance(result["consensus"]["history"], list)


# ---------------------------------------------------------------------------
# 3. Recommendations DataFrame → history list
# ---------------------------------------------------------------------------

class TestConsensusHistory:
    def test_recommendations_parsed(self, patch_ticker):
        recs_df = pd.DataFrame(
            {
                "strongBuy": [10, 12],
                "buy": [5, 6],
                "hold": [3, 2],
                "sell": [1, 0],
                "strongSell": [0, 0],
            },
            index=["0q", "-1q"],
        )
        fake = _make_ticker(
            info={"currency": "USD", "recommendationMean": 1.8, "recommendationKey": "buy"},
            recommendations=recs_df,
        )
        svc = patch_ticker(fake)
        result = svc.analyst_data("MSFT")

        assert result["consensus"]["recommendationMean"] == 1.8
        assert result["consensus"]["recommendationKey"] == "buy"
        history = result["consensus"]["history"]
        assert len(history) == 2
        assert history[0]["period"] == "0q"
        assert history[0]["strongBuy"] == 10
        assert history[1]["buy"] == 6


# ---------------------------------------------------------------------------
# 4. Earnings surprises DataFrame → list
# ---------------------------------------------------------------------------

class TestEarningsSurprises:
    def test_earnings_dates_parsed(self, patch_ticker):
        idx = pd.to_datetime(["2024-01-30", "2023-10-27", "2023-07-28"])
        ed_df = pd.DataFrame(
            {
                "EPS Estimate": [2.10, 1.95, 1.80],
                "Reported EPS": [2.18, 2.02, 1.73],
                "Surprise(%)": [3.81, 3.59, -3.89],
            },
            index=idx,
        )
        fake = _make_ticker(info={"currency": "USD"}, earnings_dates=ed_df)
        svc = patch_ticker(fake)
        result = svc.analyst_data("AAPL")

        surprises = result["earningsSurprises"]
        assert len(surprises) == 3
        first = surprises[0]
        assert first["date"] == "2024-01-30"
        assert abs(first["epsEstimate"] - 2.10) < 1e-9
        assert abs(first["epsActual"] - 2.18) < 1e-9
        assert abs(first["surprisePct"] - 3.81) < 1e-9

    def test_earnings_dates_capped_at_8(self, patch_ticker):
        idx = pd.to_datetime([f"2024-{m:02d}-01" for m in range(1, 13)])
        ed_df = pd.DataFrame(
            {
                "EPS Estimate": [1.0] * 12,
                "Reported EPS": [1.1] * 12,
                "Surprise(%)": [10.0] * 12,
            },
            index=idx,
        )
        fake = _make_ticker(info={"currency": "USD"}, earnings_dates=ed_df)
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        assert len(result["earningsSurprises"]) <= 8

    def test_rows_without_actual_excluded(self, patch_ticker):
        idx = pd.to_datetime(["2024-01-30", "2024-04-30"])
        ed_df = pd.DataFrame(
            {
                "EPS Estimate": [2.10, 2.30],
                "Reported EPS": [2.18, None],  # second row has no actual yet
                "Surprise(%)": [3.81, None],
            },
            index=idx,
        )
        fake = _make_ticker(info={"currency": "USD"}, earnings_dates=ed_df)
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")
        # Only the first row (with actual) should be included
        assert len(result["earningsSurprises"]) == 1
        assert result["earningsSurprises"][0]["epsActual"] == 2.18


# ---------------------------------------------------------------------------
# 5. Completely-empty fake → full shape with safe defaults
# ---------------------------------------------------------------------------

class TestEmptyFaker:
    def test_full_shape_returned_with_safe_defaults(self, patch_ticker):
        fake = _make_ticker()  # no info, no attributes
        svc = patch_ticker(fake)
        result = svc.analyst_data("EMPTY")

        # Top-level keys
        assert result["ticker"] == "EMPTY"
        assert "currency" in result       # defaults to "USD"
        assert result["price"] is None
        assert result["asOf"] == date.today().isoformat()

        # priceTarget sub-dict
        pt = result["priceTarget"]
        for key in ("meanPrice", "highPrice", "lowPrice", "medianPrice",
                    "numberOfAnalysts", "upsidePct"):
            assert key in pt
            assert pt[key] is None

        # consensus sub-dict
        c = result["consensus"]
        assert c["recommendationMean"] is None
        assert c["recommendationKey"] is None
        assert c["history"] == []

        # lists
        assert result["earningsSurprises"] == []

        # estimates (empty dict is acceptable)
        assert isinstance(result["estimates"], dict)

        # growth estimates (None when unavailable)
        assert result["growthEstimates"] is None

    def test_exception_in_get_info_via_monkeypatch(self, monkeypatch):
        """If get_info() raises, service returns safe defaults."""
        import backend.services.analyst_service as svc
        from backend.cache import _caches

        class _BrokenTicker:
            def get_info(self):
                raise RuntimeError("network down")

            @property
            def info(self):
                raise RuntimeError("network down")

            recommendations = None
            earnings_dates = None
            earnings_estimate = None
            revenue_estimate = None
            growth_estimates = None

        class _BrokenYF:
            def Ticker(self, sym: str) -> _BrokenTicker:  # noqa: N802
                return _BrokenTicker()

        monkeypatch.setattr(svc, "yf", _BrokenYF())
        _caches.pop("analyst", None)

        result = svc.analyst_data("BROKEN")
        assert result["ticker"] == "BROKEN"
        assert result["price"] is None
        assert result["earningsSurprises"] == []
        assert isinstance(result["estimates"], dict)


# ---------------------------------------------------------------------------
# 6. Growth estimates DataFrame → dict
# ---------------------------------------------------------------------------

class TestGrowthEstimates:
    def test_growth_estimates_parsed(self, patch_ticker):
        ge_df = pd.DataFrame(
            {"stock": [0.12, 0.15, 0.10], "index": [0.08, 0.09, 0.07]},
            index=["0q", "+1q", "+5y"],
        )
        fake = _make_ticker(info={"currency": "USD"}, growth_estimates=ge_df)
        svc = patch_ticker(fake)
        result = svc.analyst_data("X")

        ge = result["growthEstimates"]
        assert ge is not None
        assert "0q" in ge
        assert abs(ge["0q"]["stock"] - 0.12) < 1e-9
        assert abs(ge["+1q"]["index"] - 0.09) < 1e-9
