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
    monkeypatch.setattr(breadth_service.yfs, "get_ohlc_frame", lambda s, p, **kw: _as_ohlc(frame))
    monkeypatch.setattr(movers_service.yfs, "get_close_frame", lambda s, p: frame)
    return frame


def _as_ohlc(close: pd.DataFrame, high: pd.DataFrame | None = None,
             low: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """{symbol: OHLC frame} as returned by yfinance_service.get_ohlc_frame."""
    high = close if high is None else high
    low = close if low is None else low
    return {
        c: pd.DataFrame({"Open": close[c], "High": high[c], "Low": low[c], "Close": close[c]}).dropna()
        for c in close.columns
    }


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

    def test_empty_frame_is_unavailable_not_zero(self, monkeypatch):
        """Audit D-02: a failed download must read as unknown, never as 0."""
        from backend.services import breadth_service
        monkeypatch.setattr(breadth_service.yfs, "get_ohlc_frame", lambda s, p, **kw: {})
        monkeypatch.setattr(breadth_service.constituents, "constituent_symbols", lambda i="sp500": ["AAA"])
        b = breadth_service.breadth("sp500")
        assert b["status"] == "unavailable"
        assert b["total"] is None and b["advancing"] is None and b["newHighs"] is None

    def test_in_progress_session_is_dropped(self, monkeypatch, patch_universe):
        """While NYSE is open, today's partial bar must not define asOf."""
        from datetime import datetime
        from backend.services import breadth_service
        last = patch_universe.index[-1]
        monkeypatch.setattr(breadth_service, "_now_ny",
                            lambda: datetime(last.year, last.month, last.day, 11, 0,
                                             tzinfo=breadth_service._NY))
        b = breadth_service.breadth("sp500")
        assert b["asOf"] == patch_universe.index[-2].strftime("%Y-%m-%d")

    def test_stale_member_excluded_from_session_counts(self, monkeypatch, patch_universe):
        """A member with no bar on the as-of session contributes nothing."""
        from backend.services import breadth_service
        frame = patch_universe.copy()
        frame.loc[frame.index[-1], "BBB"] = np.nan  # BBB did not print last session
        # 3 of 4 printed = 75% < 90% coverage, so pad the universe.
        for k in range(8):
            frame[f"PAD{k}"] = np.linspace(10, 20, len(frame))
        monkeypatch.setattr(breadth_service.yfs, "get_ohlc_frame", lambda s, p, **kw: _as_ohlc(frame))
        monkeypatch.setattr(breadth_service.constituents, "constituent_symbols",
                            lambda i="sp500": list(frame.columns))
        b = breadth_service.breadth("sp500")
        assert b["asOf"] == frame.index[-1].strftime("%Y-%m-%d")
        assert b["newLows"] == 0      # BBB's stale bar is not a "new low today"
        assert b["declining"] == 0    # and it is not counted as declining

    def test_new_highs_use_intraday_high(self, monkeypatch, patch_universe):
        """A close below the prior high still counts if the intraday high reached it."""
        from backend.services import breadth_service
        close = patch_universe.copy()
        close["EEE"] = [100.0] * (len(close) - 1) + [99.0]
        high = close.copy()
        high.loc[high.index[-1], "EEE"] = 101.0  # traded through the prior high
        monkeypatch.setattr(breadth_service.yfs, "get_ohlc_frame", lambda s, p, **kw: _as_ohlc(close, high=high))
        monkeypatch.setattr(breadth_service.constituents, "constituent_symbols",
                            lambda i="sp500": list(close.columns))
        b = breadth_service.breadth("sp500")
        assert b["newHighs"] == 4  # AAA, CCC, DDD + EEE via intraday high


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


class TestFearGreedAlignment:
    """Audit P2-24 / C-21: headline and history must agree and be dated."""

    def _patch(self, monkeypatch, hy_lag_days: int = 0):
        from backend.services import feargreed_service as fg
        idx = _bdays(120)
        as_of = idx[-1]
        rng = np.random.default_rng(7)

        def mk(offset=0):
            return pd.Series(rng.uniform(10, 90, len(idx)), index=idx).iloc[: len(idx) - offset]

        monkeypatch.setattr(fg.breadth_service, "breadth_internals", lambda i="sp500": {
            "summation": pd.Series(np.cumsum(rng.normal(size=len(idx))), index=idx),
            "highsLows": pd.DataFrame({"highs": rng.integers(0, 40, len(idx)),
                                       "lows": rng.integers(1, 40, len(idx))}, index=idx),
            "asOf": as_of,
        })
        monkeypatch.setattr(fg, "_sp_momentum", lambda a: mk())
        monkeypatch.setattr(fg, "_vix", lambda a: mk())
        monkeypatch.setattr(fg, "_stocks_vs_bonds", lambda a: mk())
        monkeypatch.setattr(fg, "_hy_spread", lambda a: mk(hy_lag_days))
        monkeypatch.setattr(fg, "_put_call", lambda: {"score": None, "ratio": None, "historyDays": None, "asOf": None})
        return fg, as_of

    def test_headline_equals_last_history_point(self, monkeypatch):
        fg, as_of = self._patch(monkeypatch)
        out = fg.fear_greed()
        assert out["asOf"] == as_of.strftime("%Y-%m-%d")
        assert out["history"][-1]["date"] == out["asOf"]
        assert out["history"][-1]["value"] == pytest.approx(out["index"], abs=0.11)
        assert all(s["asOf"] == out["asOf"] for s in out["signals"] if s["score"] is not None)

    def test_lagging_signal_is_dated_and_flagged_stale(self, monkeypatch):
        fg, _ = self._patch(monkeypatch, hy_lag_days=6)
        out = fg.fear_greed()
        hy = next(s for s in out["signals"] if s["key"] == "hySpread")
        assert hy["stale"] is True
        assert hy["asOf"] < out["asOf"]


class TestPutCallHistory:
    """Audit L-01: put/call is ranked against its own history, not a fixed band."""

    def _run(self, monkeypatch, ratio, hist):
        from backend.services import feargreed_service as fg, snapshots
        monkeypatch.setattr(fg, "_put_call_ratio", lambda: ratio)
        monkeypatch.setattr(snapshots, "record", lambda *a, **k: None)
        monkeypatch.setattr(snapshots, "history", lambda *a, **k: [(None, v) for v in hist])
        return fg._put_call()

    def test_structurally_high_ratio_is_not_pinned_to_zero(self, monkeypatch):
        # SPY OI P/C lives around 2-2.5; a median day must score near 50.
        hist = list(np.linspace(1.9, 2.7, 100))
        out = self._run(monkeypatch, 2.3, hist)
        assert 40 <= out["score"] <= 60

    def test_insufficient_history_is_none_not_zero(self, monkeypatch):
        out = self._run(monkeypatch, 2.4, [2.4] * 10)
        assert out["score"] is None and out["historyDays"] == 10 and out["ratio"] == 2.4

    def test_zero_open_interest_is_missing_not_a_ratio(self, monkeypatch):
        # Pre-market, Yahoo reports 0 open interest on every contract: that
        # must read as "no data", never as a put/call ratio of 0.0.
        import sys
        import types
        from backend.services import feargreed_service as fg

        def ticker(put_oi):
            chain = types.SimpleNamespace(calls=pd.DataFrame({"openInterest": [100.0]}),
                                          puts=pd.DataFrame({"openInterest": [put_oi]}))
            return types.SimpleNamespace(options=["2026-10-16"], option_chain=lambda e: chain)

        monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=lambda s: ticker(0.0)))
        assert fg._put_call_ratio() is None
        monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=lambda s: ticker(230.0)))
        assert fg._put_call_ratio() == pytest.approx(2.3)
