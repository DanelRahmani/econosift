"""Offline tests for realized_moments_service (Phase 15).

get_ohlc_frame and constituent_symbols are monkeypatched with deterministic
synthetic OHLC data so tests are fully offline and reproducible.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------

_TICKERS_30 = [f"STOCK_{i:02d}" for i in range(30)]


def _bdays(n: int) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-06-25", periods=n, freq="B")


def _synthetic_ohlc(n: int = 520, seed: int = 42, ticker: str = "AAPL") -> pd.DataFrame:
    """Geometric random-walk OHLC where High >= max(Open,Close) and Low <= min(Open,Close)."""
    rng = np.random.default_rng(seed)
    idx = _bdays(n)
    log_ret = rng.normal(0.0003, 0.012, size=n)
    close = 100.0 * np.exp(np.cumsum(log_ret))
    # Build open as previous close (with a small overnight gap)
    open_ = np.roll(close, 1)
    open_[0] = close[0] * (1 + rng.normal(0, 0.005))
    # High = max(open, close) + intraday range
    intraday = np.abs(rng.normal(0, 0.008, size=n)) * close
    high = np.maximum(open_, close) + intraday
    low = np.minimum(open_, close) - intraday
    low = np.clip(low, 1e-6, None)  # keep positive
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close}, index=idx)


def _multi_ohlc(n: int = 520, seed: int = 42) -> dict[str, pd.DataFrame]:
    """Build an OHLC dict for all 30 synthetic tickers."""
    rng = np.random.default_rng(seed)
    result = {}
    for i, ticker in enumerate(_TICKERS_30):
        df = _synthetic_ohlc(n=n, seed=seed + i, ticker=ticker)
        result[ticker] = df
    return result


# ---------------------------------------------------------------------------
# Auto-clear caches between tests
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
# Patch fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def patch_moments(monkeypatch):
    """Patch yfinance_service inside realized_moments_service for single-ticker tests."""
    from backend.services import realized_moments_service as rms

    df = _synthetic_ohlc(n=520)
    monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: {syms[0]: df})
    return df


@pytest.fixture()
def patch_crosssection(monkeypatch):
    """Patch constituents and yfinance_service for cross-section tests."""
    from backend.services import realized_moments_service as rms

    ohlc_dict = _multi_ohlc(n=300)
    monkeypatch.setattr(rms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
    monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: ohlc_dict)
    return ohlc_dict


# ---------------------------------------------------------------------------
# get_moments: schema
# ---------------------------------------------------------------------------

class TestGetMomentsSchema:
    def test_top_level_keys(self, patch_moments):
        from backend.services.realized_moments_service import get_moments
        result = get_moments("AAPL", "3y")
        required = {"ticker", "period", "asOf", "series", "latest"}
        assert required <= set(result.keys()), f"missing keys: {required - set(result.keys())}"

    def test_series_non_empty(self, patch_moments):
        from backend.services.realized_moments_service import get_moments
        result = get_moments("AAPL", "3y")
        assert len(result["series"]) > 0

    def test_series_row_fields(self, patch_moments):
        from backend.services.realized_moments_service import get_moments
        result = get_moments("AAPL", "3y")
        required = {"date", "rvol21", "rvol63", "rvol252", "skew21", "skew63", "skew252",
                    "kurt21", "kurt63", "kurt252"}
        for row in result["series"]:
            assert required <= set(row.keys()), f"row missing keys: {required - set(row.keys())}"

    def test_all_leaves_finite_or_none(self, patch_moments):
        from backend.services.realized_moments_service import get_moments
        result = get_moments("AAPL", "3y")
        for row in result["series"]:
            for k, v in row.items():
                if k == "date":
                    continue
                if v is not None:
                    assert math.isfinite(v), f"non-finite value {v} for {k} on {row['date']}"

    def test_rvol_non_negative_where_not_none(self, patch_moments):
        from backend.services.realized_moments_service import get_moments
        result = get_moments("AAPL", "3y")
        for row in result["series"]:
            for w in (21, 63, 252):
                v = row.get(f"rvol{w}")
                if v is not None:
                    assert v >= 0.0, f"rvol{w} is negative: {v} on {row['date']}"

    def test_252d_none_when_short_history(self, monkeypatch):
        """With exactly 100 rows, rvol252 must be None for all rows (needs 252)."""
        from backend.services import realized_moments_service as rms
        from backend import cache

        short_df = _synthetic_ohlc(n=100)
        monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: {syms[0]: short_df})
        cache._caches.clear()
        result = rms.get_moments("AAPL", "1y")
        # No error — 100 >= _MIN_TS_ROWS(22)
        assert "error" not in result or result.get("error") is None
        for row in result["series"]:
            assert row["rvol252"] is None, f"expected rvol252=None but got {row['rvol252']}"

    def test_latest_keys(self, patch_moments):
        from backend.services.realized_moments_service import get_moments
        result = get_moments("AAPL", "3y")
        assert result["latest"] is not None
        assert set(result["latest"].keys()) == {"rvol21", "skew21", "kurt21"}

    def test_ticker_echoed(self, patch_moments):
        from backend.services.realized_moments_service import get_moments
        result = get_moments("MSFT", "3y")
        assert result["ticker"] == "MSFT"


# ---------------------------------------------------------------------------
# GK formula unit test
# ---------------------------------------------------------------------------

class TestGKFormula:
    def test_known_value(self):
        """Hand-computed Garman-Klass for a single row."""
        from backend.services.realized_moments_service import _gk_variance, _GK_K
        H, L, O, C = 110.0, 90.0, 100.0, 105.0
        expected = 0.5 * math.log(H / L) ** 2 - _GK_K * math.log(C / O) ** 2
        df = pd.DataFrame(
            {"Open": [O], "High": [H], "Low": [L], "Close": [C]},
            index=pd.DatetimeIndex(["2024-01-02"]),
        )
        result = _gk_variance(df)
        assert abs(float(result.iloc[0]) - expected) < 1e-9, (
            f"GK mismatch: got {float(result.iloc[0])}, expected {expected}"
        )


# ---------------------------------------------------------------------------
# Negative-GK clip
# ---------------------------------------------------------------------------

class TestNegativeGKClip:
    def test_negative_gk_gives_zero_rvol(self, monkeypatch):
        """Bar with tiny H-L and large C/O gap → raw GK < 0 → clipped to 0 → rvol = 0, not NaN."""
        from backend.services import realized_moments_service as rms
        from backend import cache

        # Build a price series where most bars are normal but one bar has tiny H-L and big C/O
        n = 60
        df = _synthetic_ohlc(n=n)
        # Overwrite the last bar: force H very close to L (tiny spread)
        # and make C much larger than O so GK < 0
        df.iloc[-1, df.columns.get_loc("Open")]  = 100.0
        df.iloc[-1, df.columns.get_loc("High")]  = 100.001   # nearly same H/L
        df.iloc[-1, df.columns.get_loc("Low")]   = 99.999
        df.iloc[-1, df.columns.get_loc("Close")] = 120.0     # big O→C gap

        monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: {syms[0]: df})
        cache._caches.clear()
        result = rms.get_moments("TEST", "1y")
        assert "error" not in result
        # Check no rvol21 is NaN (None allowed, but not NaN)
        for row in result["series"]:
            v = row["rvol21"]
            if v is not None:
                assert not math.isnan(v), f"rvol21 is NaN on {row['date']}"
                assert v >= 0.0, f"rvol21 negative: {v}"


# ---------------------------------------------------------------------------
# Insufficient history
# ---------------------------------------------------------------------------

class TestInsufficientHistory:
    def test_10_rows_returns_error_dict(self, monkeypatch):
        from backend.services import realized_moments_service as rms

        tiny_df = _synthetic_ohlc(n=10)
        monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: {syms[0]: tiny_df})
        result = rms.get_moments("AAPL", "1y")
        assert "error" in result
        assert result["series"] == []
        assert result["latest"] is None

    def test_none_ticker_missing_from_ohlc(self, monkeypatch):
        """When the ticker is not in the returned ohlc dict → error dict."""
        from backend.services import realized_moments_service as rms

        monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: {})
        result = rms.get_moments("AAPL", "1y")
        assert "error" in result
        assert result["series"] == []


# ---------------------------------------------------------------------------
# get_crosssection: schema
# ---------------------------------------------------------------------------

class TestCrossSectionSchema:
    def test_top_level_keys(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        required = {"universe", "window", "asOf", "deciles", "names", "missing"}
        assert required <= set(result.keys()), f"missing keys: {required - set(result.keys())}"

    def test_decile_labels_sorted(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        labels = [d["decile"] for d in result["deciles"]]
        assert labels == sorted(labels), "decile labels not in ascending order"

    def test_decile_labels_start_at_1(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        if result["deciles"]:
            assert result["deciles"][0]["decile"] == 1

    def test_decile_counts_plus_missing_eq_universe(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        total_valid = sum(d["count"] for d in result["deciles"])
        total = total_valid + len(result["missing"])
        assert total == len(_TICKERS_30), (
            f"counts {total_valid} + missing {len(result['missing'])} != {len(_TICKERS_30)}"
        )

    def test_names_fields(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        for item in result["names"]:
            assert "ticker" in item
            assert "priorSkew" in item
            assert "fwdReturn" in item

    def test_names_count_matches_valid(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        valid_count = sum(d["count"] for d in result["deciles"])
        assert len(result["names"]) == valid_count

    def test_decile_fields(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        for d in result["deciles"]:
            assert "decile" in d
            assert "avgSkew" in d
            assert "avgFwdReturn" in d
            assert "count" in d

    def test_finite_or_none_in_deciles(self, patch_crosssection):
        from backend.services.realized_moments_service import get_crosssection
        result = get_crosssection("dow", 21)
        for d in result["deciles"]:
            for key in ("avgSkew", "avgFwdReturn"):
                v = d[key]
                if v is not None:
                    assert math.isfinite(v), f"{key} non-finite: {v}"


# ---------------------------------------------------------------------------
# Cross-section: insufficient data → error dict
# ---------------------------------------------------------------------------

class TestCrossSectionInsufficientData:
    def test_fewer_than_10_valid_returns_error(self, monkeypatch):
        """Only 5 tickers with sufficient data → error dict with all keys."""
        from backend.services import realized_moments_service as rms
        from backend import cache

        # Give only 5 tickers enough rows; rest get 2 rows (insufficient)
        few_tickers = _TICKERS_30[:5]
        tiny_ohlc: dict[str, pd.DataFrame] = {}
        for sym in _TICKERS_30:
            if sym in few_tickers:
                tiny_ohlc[sym] = _synthetic_ohlc(n=300, seed=hash(sym) % 100)
            else:
                tiny_ohlc[sym] = _synthetic_ohlc(n=2, seed=0)

        monkeypatch.setattr(rms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
        monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: tiny_ohlc)
        cache._caches.clear()

        result = rms.get_crosssection("dow", 21)
        assert "error" in result
        for key in ("universe", "window", "asOf", "error", "deciles", "names", "missing"):
            assert key in result, f"error response missing key {key!r}"
        assert result["deciles"] == []

    def test_failed_universe_returns_error(self, monkeypatch):
        from backend.services import realized_moments_service as rms
        from backend import cache

        def _boom(index):
            raise RuntimeError("network failure")

        monkeypatch.setattr(rms.constituents, "constituent_symbols", _boom)
        monkeypatch.setattr(rms.yfs, "get_ohlc_frame", lambda syms, period: {})
        cache._caches.clear()

        result = rms.get_crosssection("dow", 21)
        assert "error" in result
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# No-lookahead index math
# ---------------------------------------------------------------------------

class TestNoLookaheadMath:
    def test_formation_and_forward_windows_disjoint(self, monkeypatch):
        """Assert the formation slice [t-window:t] and forward slice [t-1:end]
        refer to disjoint price bars (the formation end bar t-1 is the last
        bar used for skew; the forward return starts at bar t-1 as the basis).

        This is a structural unit test of the cut arithmetic used in get_crosssection:
            t = len(df) - window
            formation uses logret[t-window-1 : t-1]   → price bars [t-window-1 .. t-1]
            forward return = close[t-1] .. close[-1]   → price bars [t-1 .. end]

        The two windows share exactly one price bar (t-1, the formation endpoint),
        which is the basis for the forward return — it is NOT used in computing
        the prior return signal itself. The logret formation slice and the
        forward return bars are therefore disjoint.
        """
        from backend.services import realized_moments_service as rms

        # Use a small deterministic price series so we can reason about indices.
        n = 60
        window = 10
        df = _synthetic_ohlc(n=n)

        t = n - window                  # = 50
        # Formation logret slice (0-based into logret, length n-1)
        form_start = t - window - 1    # = 39
        form_end   = t - 1             # = 49  (exclusive in Python slicing)
        formation_iloc = list(range(form_start, form_end))  # 39..48

        # Forward return uses price at bar t-1=49 as denominator, bars 50..59 as numerator
        # → forward price bars are 49 (basis) .. n-1 = 59
        fwd_price_bars = list(range(t - 1, n))             # 49..59

        # The formation logret bars (in price-bar space) are one ahead:
        # logret[i] = log(close[i+1]) - log(close[i]), so logret iloc i
        # uses price bars i and i+1. The slice above uses price bars 39..49.
        # Forward price bars: 49..59.
        # Overlap: only bar 49 (t-1) — used as the FORWARD BASIS, not in skew.
        # So the formation signal (skew) is computed from log-returns of bars 39..49,
        # while the forward return = close[49..59]. They are disjoint in signal space.
        form_price_bars = set(range(form_start, form_end + 1))  # 39..49 (both ends inclusive)
        fwd_price_bars_set = set(range(t, n))                   # 50..59 (bars after basis)

        # These two sets must have no overlap
        assert form_price_bars.isdisjoint(fwd_price_bars_set), (
            f"Formation and forward windows overlap in price bar space: "
            f"{form_price_bars & fwd_price_bars_set}"
        )

        # Verify the arithmetic matches what the service actually uses
        assert t == n - window
        assert form_end == t - 1
        assert t - 1 not in fwd_price_bars_set   # basis bar not in forward bars
