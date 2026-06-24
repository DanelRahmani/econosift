"""Offline tests for the Phase 2 dashboard services.

Price/volume downloads and the constituent universe are monkeypatched with
deterministic synthetic data so breadth / movers / indices math is checked
exactly, with no network.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_caches():
    """Isolate tests: the services are @cached by args, so clear between tests."""
    from backend import cache
    cache._caches.clear()
    cache._stats.clear()
    yield
    cache._caches.clear()
    cache._stats.clear()


def _bdays(n: int) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-06-23", periods=n, freq="B")


def _frame(series: dict[str, list[float]], n: int = 60) -> pd.DataFrame:
    idx = _bdays(n)
    return pd.DataFrame({k: v for k, v in series.items()}, index=idx)


# Four deterministic constituents over 60 sessions:
#   AAA strictly up      -> advancing, at 52w high, above SMA50
#   BBB strictly down    -> declining, at 52w low,  below SMA50
#   CCC up then flat last -> unchanged on the day,   above SMA50
#   DDD strictly up      -> advancing, at 52w high, above SMA50
def _synthetic_universe(n: int = 60) -> pd.DataFrame:
    up = list(np.linspace(100, 160, n))
    down = list(np.linspace(160, 100, n))
    flat_last = list(np.linspace(100, 150, n))
    flat_last[-1] = flat_last[-2]  # unchanged on the final day
    up2 = list(np.linspace(50, 90, n))
    return _frame({"AAA": up, "BBB": down, "CCC": flat_last, "DDD": up2}, n)


@pytest.fixture()
def patch_universe(monkeypatch):
    frame = _synthetic_universe()
    from backend.services import breadth_service, movers_service, constituents

    syms = tuple(frame.columns)
    monkeypatch.setattr(constituents, "constituent_symbols", lambda index="sp500": list(syms))
    monkeypatch.setattr(
        constituents, "get_constituents",
        lambda index="sp500": [{"symbol": s, "name": f"{s} Corp", "sector": "Tech"} for s in syms],
    )
    monkeypatch.setattr(breadth_service.yfs, "get_close_frame", lambda s, p: frame)
    monkeypatch.setattr(movers_service.yfs, "get_close_frame", lambda s, p: frame)
    return frame


class TestBreadth:
    def test_counts_partition_total(self, patch_universe):
        from backend.services.breadth_service import breadth
        b = breadth("sp500")
        assert b["advancing"] + b["declining"] + b["unchanged"] == b["total"]

    def test_advancing_declining_unchanged(self, patch_universe):
        from backend.services.breadth_service import breadth
        b = breadth("sp500")
        assert b["advancing"] == 2  # AAA, DDD
        assert b["declining"] == 1  # BBB
        assert b["unchanged"] == 1  # CCC

    def test_new_highs_lows(self, patch_universe):
        from backend.services.breadth_service import breadth
        b = breadth("sp500")
        assert b["newHighs"] == 3  # AAA, CCC, DDD all peak on last bar
        assert b["newLows"] == 1   # BBB

    def test_pct_above_sma50(self, patch_universe):
        from backend.services.breadth_service import breadth
        b = breadth("sp500")
        assert b["pctAboveSma50"] == 75.0  # 3 of 4 above their SMA50

    def test_mcclellan_present(self, patch_universe):
        from backend.services.breadth_service import breadth
        b = breadth("sp500")
        assert b["mcclellanOscillator"] is not None
        assert b["mcclellanSummation"] is not None

    def test_cumulative_ad_line_capped(self, patch_universe):
        from backend.services.breadth_service import breadth
        b = breadth("sp500")
        assert len(b["cumulativeAdLine"]) <= 90
        assert all({"date", "value"} <= set(p) for p in b["cumulativeAdLine"])

    def test_empty_frame_safe(self, monkeypatch):
        from backend.services import breadth_service
        monkeypatch.setattr(breadth_service.yfs, "get_close_frame", lambda s, p: pd.DataFrame())
        monkeypatch.setattr(breadth_service.constituents, "constituent_symbols", lambda i="sp500": ["AAA"])
        b = breadth_service.breadth("sp500")
        assert b["total"] == 0 and b["advancing"] == 0


class TestMovers:
    def test_gainers_sorted_desc(self, patch_universe):
        from backend.services.movers_service import top_movers
        monkeypatch_vol(patch_universe)
        m = top_movers("sp500")
        chg = [r["changePercent"] for r in m["gainers"]]
        assert chg == sorted(chg, reverse=True)

    def test_losers_include_decliner(self, patch_universe):
        from backend.services.movers_service import top_movers
        monkeypatch_vol(patch_universe)
        m = top_movers("sp500")
        assert any(r["ticker"] == "BBB" for r in m["losers"])

    def test_new_highs_contains_risers(self, patch_universe):
        from backend.services.movers_service import top_movers
        monkeypatch_vol(patch_universe)
        m = top_movers("sp500")
        hi = {r["ticker"] for r in m["newHighs"]}
        assert {"AAA", "DDD"} <= hi


def monkeypatch_vol(frame):
    """Attach a synthetic volume frame: AAA spikes 3x, others normal."""
    import pytest as _p
    from backend.services import movers_service
    n = len(frame)
    vol = pd.DataFrame(
        {c: [1_000_000.0] * n for c in frame.columns}, index=frame.index)
    vol.iloc[-1, vol.columns.get_loc("AAA")] = 3_000_000.0
    movers_service.yfs.get_volume_frame = lambda s, p: vol  # type: ignore


class TestIndices:
    def test_shape_and_pct(self, monkeypatch):
        from backend.services import indices_service
        syms = [i[0] for i in indices_service.INDICES]
        n = 260
        idx = _bdays(n)
        data = {s: list(np.linspace(100, 110, n)) for s in syms}
        frame = pd.DataFrame(data, index=idx)
        monkeypatch.setattr(indices_service.yfs, "get_close_frame", lambda s, p: frame)
        d = indices_service.global_indices()
        assert len(d["indices"]) == len(syms)
        row = d["indices"][0]
        assert row["price"] == pytest.approx(110.0, abs=0.01)
        assert row["change1d"] is not None
        assert len(row["spark"]) == 5

    def test_empty_safe(self, monkeypatch):
        from backend.services import indices_service
        monkeypatch.setattr(indices_service.yfs, "get_close_frame", lambda s, p: pd.DataFrame())
        d = indices_service.global_indices()
        assert all(r["price"] is None for r in d["indices"])


class TestFearGreedHelpers:
    def test_clip(self):
        from backend.services.feargreed_service import _clip
        assert _clip(150) == 100.0
        assert _clip(-5) == 0.0
        assert _clip(42) == 42.0

    def test_label_bands(self):
        from backend.services.feargreed_service import _label
        assert _label(10) == "Extreme Fear"
        assert _label(35) == "Fear"
        assert _label(50) == "Neutral"
        assert _label(65) == "Greed"
        assert _label(90) == "Extreme Greed"

    def test_percentile_score_high(self):
        from backend.services.feargreed_service import _percentile_score
        s = pd.Series(list(range(100)))  # last value is the max
        assert _percentile_score(s) == pytest.approx(100.0)

    def test_percentile_score_inverted(self):
        from backend.services.feargreed_service import _percentile_score
        s = pd.Series(list(range(100)))
        assert _percentile_score(s, invert=True) == pytest.approx(0.0)

    def test_percentile_score_too_short(self):
        from backend.services.feargreed_service import _percentile_score
        assert _percentile_score(pd.Series([1, 2, 3])) is None
