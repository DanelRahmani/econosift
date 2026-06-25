"""Offline tests for momentum_service (Phase 14).

get_close_frame and constituent_symbols are monkeypatched with deterministic
synthetic data so tests are fully offline and reproducible.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------

_TICKERS_30 = [f"STOCK_{i:02d}" for i in range(30)]  # 30-ticker Dow-like universe


def _bdays(n: int) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-06-25", periods=n, freq="B")


def _synthetic_prices(n: int = 520, seed: int = 42) -> pd.DataFrame:
    """Geometric random-walk price frame with varied drift so signals differ.

    Uses n=520 (~2 years of trading days) so all signals (12m1m needs 253) work.
    Tickers get drift proportional to their index so decile ordering is stable.
    """
    rng = np.random.default_rng(seed)
    idx = _bdays(n)
    prices: dict[str, list[float]] = {}
    for i, ticker in enumerate(_TICKERS_30):
        # drift increases with i: STOCK_00 has low momentum, STOCK_29 high
        daily_drift = -0.0003 + i * 0.00004   # range −0.0003 to +0.00084
        daily_vol   = 0.012
        log_ret = rng.normal(daily_drift, daily_vol, size=n)
        prices[ticker] = list(100.0 * np.exp(np.cumsum(log_ret)))
    return pd.DataFrame(prices, index=idx)


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
# Patch fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def patch_momentum(monkeypatch):
    """Patch constituents and yfinance_service inside momentum_service."""
    from backend.services import momentum_service as ms

    frame = _synthetic_prices()

    monkeypatch.setattr(ms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
    monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: frame)
    return frame


# ---------------------------------------------------------------------------
# Shape / schema tests
# ---------------------------------------------------------------------------

class TestMomentumShape:
    def test_top_level_keys_present(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        required = {"universe", "signal", "asOf", "deciles", "top", "bottom", "missing"}
        assert required <= set(result.keys()), f"missing keys: {required - set(result.keys())}"

    def test_universe_and_signal_echoed(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "1m")
        assert result["universe"] == "dow"
        assert result["signal"]   == "1m"

    def test_asof_format(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        parts = result["asOf"].split("-")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_deciles_non_empty(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        assert len(result["deciles"]) > 0

    def test_decile_fields(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        for d in result["deciles"]:
            assert "decile" in d
            assert "avgReturn" in d
            assert "count" in d

    def test_top_non_empty(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        assert len(result["top"]) > 0

    def test_bottom_non_empty(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        assert len(result["bottom"]) > 0

    def test_top_max_20(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        assert len(result["top"]) <= 20

    def test_bottom_max_20(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        assert len(result["bottom"]) <= 20

    def test_top_bottom_fields(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        for item in result["top"] + result["bottom"]:
            assert "ticker"   in item
            assert "momentum" in item

    def test_missing_is_list(self, patch_momentum):
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        assert isinstance(result["missing"], list)


# ---------------------------------------------------------------------------
# Ordering / decile sanity
# ---------------------------------------------------------------------------

class TestMomentumOrdering:
    def test_top_decile_avg_gt_bottom_decile_avg(self, patch_momentum):
        """Highest decile avgReturn > lowest decile avgReturn."""
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        deciles = result["deciles"]
        avgs = {d["decile"]: d["avgReturn"] for d in deciles if d["avgReturn"] is not None}
        assert avgs, "no decile avgReturns"
        top_avg = avgs[max(avgs)]
        bot_avg = avgs[min(avgs)]
        assert top_avg > bot_avg, f"top decile avg ({top_avg}) not > bottom ({bot_avg})"

    def test_top_sorted_desc(self, patch_momentum):
        """top list must be in descending momentum order."""
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        momenta = [item["momentum"] for item in result["top"] if item["momentum"] is not None]
        assert momenta == sorted(momenta, reverse=True), "top not sorted descending"

    def test_bottom_sorted_asc(self, patch_momentum):
        """bottom list must be in ascending momentum order (worst first)."""
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        momenta = [item["momentum"] for item in result["bottom"] if item["momentum"] is not None]
        assert momenta == sorted(momenta), "bottom not sorted ascending"

    def test_decile_labels_ascending(self, patch_momentum):
        """Decile list should be ordered 1..k."""
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        labels = [d["decile"] for d in result["deciles"]]
        assert labels == sorted(labels), "decile labels not in order"

    def test_decile_counts_sum_to_total(self, patch_momentum):
        """Sum of decile counts + missing = total tickers."""
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        total = sum(d["count"] for d in result["deciles"]) + len(result["missing"])
        assert total == len(_TICKERS_30)

    def test_no_nan_inf_in_returns(self, patch_momentum):
        """All momentum floats must be finite."""
        from backend.services.momentum_service import get_momentum
        result = get_momentum("dow", "12m1m")
        for item in result["top"] + result["bottom"]:
            m = item["momentum"]
            if m is not None:
                assert math.isfinite(m), f"non-finite momentum for {item['ticker']}: {m}"
        for d in result["deciles"]:
            avg = d["avgReturn"]
            if avg is not None:
                assert math.isfinite(avg), f"non-finite avgReturn in decile {d['decile']}: {avg}"


# ---------------------------------------------------------------------------
# Signal switching
# ---------------------------------------------------------------------------

class TestSignalSwitching:
    def test_switching_signal_changes_top_ticker(self, monkeypatch):
        """Switching from 12m1m to 1m should change the top ticker (different signals)."""
        from backend.services import momentum_service as ms
        from backend import cache

        frame = _synthetic_prices(seed=7)  # different seed → more dispersion

        monkeypatch.setattr(ms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
        monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: frame)

        cache._caches.clear()
        result_12m1m = ms.get_momentum("dow", "12m1m")

        cache._caches.clear()
        result_1m    = ms.get_momentum("dow", "1m")

        top_12m1m = [item["ticker"] for item in result_12m1m["top"]]
        top_1m    = [item["ticker"] for item in result_1m["top"]]
        # They shouldn't be identical lists (different time windows → different ranking)
        assert top_12m1m != top_1m, "Switching signal should change ordering"

    def test_all_signals_return_deciles(self, monkeypatch):
        """All four signals should produce non-empty deciles."""
        from backend.services import momentum_service as ms
        from backend import cache

        frame = _synthetic_prices()
        monkeypatch.setattr(ms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
        monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: frame)

        for sig in ("1m", "3m", "6m", "12m1m"):
            cache._caches.clear()
            result = ms.get_momentum("dow", sig)
            assert len(result["deciles"]) > 0, f"signal {sig!r} produced no deciles"


# ---------------------------------------------------------------------------
# Insufficient-data / error paths
# ---------------------------------------------------------------------------

class TestInsufficientData:
    def test_empty_frame_returns_error(self, monkeypatch):
        from backend.services import momentum_service as ms

        monkeypatch.setattr(ms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
        monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: pd.DataFrame())

        result = ms.get_momentum("dow", "12m1m")
        assert "error" in result
        assert result["deciles"] == []
        assert result["top"]     == []
        assert result["bottom"]  == []

    def test_too_few_tickers_returns_error(self, monkeypatch):
        """If only 5 tickers have enough history, service should return error."""
        from backend.services import momentum_service as ms
        from backend import cache

        # Only 5 columns — fewer than the 10-ticker minimum
        tiny_tickers = _TICKERS_30[:5]
        frame = _synthetic_prices()[[t for t in tiny_tickers]]

        monkeypatch.setattr(ms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
        monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: frame)

        cache._caches.clear()
        result = ms.get_momentum("dow", "12m1m")
        assert "error" in result
        assert result["error"] == "insufficient data"

    def test_short_history_returns_error(self, monkeypatch):
        """Frame with only 10 rows of history → most signals fail → insufficient data."""
        from backend.services import momentum_service as ms
        from backend import cache

        short_frame = _synthetic_prices(n=10)
        monkeypatch.setattr(ms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
        monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: short_frame)

        cache._caches.clear()
        result = ms.get_momentum("dow", "12m1m")
        assert "error" in result

    def test_failed_universe_returns_error(self, monkeypatch):
        """When constituent_symbols raises, return error dict without raising."""
        from backend.services import momentum_service as ms
        from backend import cache

        def _boom(index):
            raise RuntimeError("network error")

        monkeypatch.setattr(ms.constituents, "constituent_symbols", _boom)
        monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: _synthetic_prices())

        cache._caches.clear()
        result = ms.get_momentum("dow", "12m1m")
        assert isinstance(result, dict)
        assert "error" in result

    def test_error_shape_has_all_keys(self, monkeypatch):
        """Error response must still include universe/signal/asOf/missing."""
        from backend.services import momentum_service as ms
        from backend import cache

        monkeypatch.setattr(ms.constituents, "constituent_symbols", lambda index: _TICKERS_30)
        monkeypatch.setattr(ms.yfs, "get_close_frame", lambda syms, period: pd.DataFrame())

        cache._caches.clear()
        result = ms.get_momentum("dow", "12m1m")
        for key in ("universe", "signal", "asOf", "error", "deciles", "top", "bottom", "missing"):
            assert key in result, f"error response missing key {key!r}"
