"""Offline tests for risk_parity_service (Phase 14).

get_close_frame is monkeypatched with a deterministic synthetic price frame so
tests are fully offline and reproducible.
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
    return pd.date_range(end="2026-06-25", periods=n, freq="B")


def _synthetic_prices(n: int = 756, seed: int = 42) -> pd.DataFrame:
    """Four-asset geometric random-walk price frame with ~3 years of history."""
    rng = np.random.default_rng(seed)
    idx = _bdays(n)
    tickers = ["ASSET_A", "ASSET_B", "ASSET_C", "ASSET_D"]
    prices: dict[str, list[float]] = {}
    for i, t in enumerate(tickers):
        daily_vol = 0.01 + i * 0.005          # different vols: 1%, 1.5%, 2%, 2.5%
        log_ret = rng.normal(0.0003, daily_vol, size=n)
        prices[t] = list(100.0 * np.exp(np.cumsum(log_ret)))
    return pd.DataFrame(prices, index=idx)


def _spy_agg_prices(n: int = 756, seed: int = 99) -> pd.DataFrame:
    """SPY + AGG prices to feed the benchmark column."""
    rng = np.random.default_rng(seed)
    idx = _bdays(n)
    log_ret_spy = rng.normal(0.0004, 0.012, size=n)
    log_ret_agg = rng.normal(0.0001, 0.003, size=n)
    return pd.DataFrame(
        {"SPY": 400.0 * np.exp(np.cumsum(log_ret_spy)),
         "AGG": 100.0 * np.exp(np.cumsum(log_ret_agg))},
        index=idx,
    )


# Combined frame used by backtest (assets + SPY + AGG)
def _full_frame(n: int = 756) -> pd.DataFrame:
    a = _synthetic_prices(n)
    b = _spy_agg_prices(n)
    return pd.concat([a, b], axis=1)


_TICKERS = ("ASSET_A", "ASSET_B", "ASSET_C", "ASSET_D")


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
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def patch_yfs(monkeypatch):
    """Patch yfinance_service.get_close_frame inside risk_parity_service."""
    from backend.services import risk_parity_service as rps

    frame = _synthetic_prices()
    monkeypatch.setattr(rps.yfs, "get_close_frame", lambda syms, period: frame)
    return frame


@pytest.fixture()
def patch_yfs_full(monkeypatch):
    """Patch with full frame (assets + SPY + AGG) for backtest tests."""
    from backend.services import risk_parity_service as rps

    frame = _full_frame()
    monkeypatch.setattr(rps.yfs, "get_close_frame", lambda syms, period: frame)
    return frame


# ---------------------------------------------------------------------------
# inverse_vol_weights
# ---------------------------------------------------------------------------

class TestInverseVolWeights:
    def test_weights_sum_to_one(self, patch_yfs):
        from backend.services.risk_parity_service import inverse_vol_weights
        result = inverse_vol_weights(_TICKERS)
        assert "weights" in result
        total = sum(w["weight"] for w in result["weights"])
        assert abs(total - 1.0) < 1e-6

    def test_weights_non_negative(self, patch_yfs):
        from backend.services.risk_parity_service import inverse_vol_weights
        result = inverse_vol_weights(_TICKERS)
        for w in result["weights"]:
            assert w["weight"] >= 0.0

    def test_all_tickers_present(self, patch_yfs):
        from backend.services.risk_parity_service import inverse_vol_weights
        result = inverse_vol_weights(_TICKERS)
        returned = {w["ticker"] for w in result["weights"]}
        assert returned == set(_TICKERS)

    def test_lower_vol_gets_higher_weight(self, patch_yfs):
        """ASSET_A has vol=1% (lowest) so should have the highest weight."""
        from backend.services.risk_parity_service import inverse_vol_weights
        result = inverse_vol_weights(_TICKERS)
        w_map = {w["ticker"]: w["weight"] for w in result["weights"]}
        assert w_map["ASSET_A"] > w_map["ASSET_D"]  # 1% vol vs 2.5% vol

    def test_risk_contrib_present(self, patch_yfs):
        from backend.services.risk_parity_service import inverse_vol_weights
        result = inverse_vol_weights(_TICKERS)
        assert "riskContrib" in result
        assert len(result["riskContrib"]) == len(_TICKERS)

    def test_pct_contrib_sum_to_one(self, patch_yfs):
        from backend.services.risk_parity_service import inverse_vol_weights
        result = inverse_vol_weights(_TICKERS)
        total_pc = sum(r["pctContrib"] for r in result["riskContrib"])
        assert abs(total_pc - 1.0) < 1e-5

    def test_missing_key_present(self, patch_yfs):
        from backend.services.risk_parity_service import inverse_vol_weights
        result = inverse_vol_weights(_TICKERS)
        assert "missing" in result

    def test_insufficient_data_returns_error(self, monkeypatch):
        """With only 1 asset having enough data, return graceful error."""
        from backend.services import risk_parity_service as rps
        # Return frame with only 1 column
        tiny = pd.DataFrame(
            {"ASSET_A": [100.0 + i for i in range(756)]},
            index=_bdays(756),
        )
        monkeypatch.setattr(rps.yfs, "get_close_frame", lambda s, p: tiny)
        result = rps.inverse_vol_weights(_TICKERS)
        assert "error" in result
        assert result["error"] == "insufficient data"

    def test_empty_frame_returns_error(self, monkeypatch):
        from backend.services import risk_parity_service as rps
        monkeypatch.setattr(rps.yfs, "get_close_frame", lambda s, p: pd.DataFrame())
        result = rps.inverse_vol_weights(_TICKERS)
        assert "error" in result


# ---------------------------------------------------------------------------
# erc_weights
# ---------------------------------------------------------------------------

class TestERCWeights:
    def test_weights_sum_to_one(self, patch_yfs):
        from backend.services.risk_parity_service import erc_weights
        result = erc_weights(_TICKERS)
        total = sum(w["weight"] for w in result["weights"])
        assert abs(total - 1.0) < 1e-5

    def test_weights_non_negative(self, patch_yfs):
        from backend.services.risk_parity_service import erc_weights
        result = erc_weights(_TICKERS)
        for w in result["weights"]:
            assert w["weight"] >= 0.0

    def test_all_tickers_present(self, patch_yfs):
        from backend.services.risk_parity_service import erc_weights
        result = erc_weights(_TICKERS)
        returned = {w["ticker"] for w in result["weights"]}
        assert returned == set(_TICKERS)

    def test_pct_contrib_roughly_equal(self, patch_yfs):
        """ERC should equalise risk contributions — max-min < 0.10."""
        from backend.services.risk_parity_service import erc_weights
        result = erc_weights(_TICKERS)
        contribs = [r["pctContrib"] for r in result["riskContrib"]]
        assert max(contribs) - min(contribs) < 0.10

    def test_pct_contrib_sum_to_one(self, patch_yfs):
        from backend.services.risk_parity_service import erc_weights
        result = erc_weights(_TICKERS)
        total_pc = sum(r["pctContrib"] for r in result["riskContrib"])
        assert abs(total_pc - 1.0) < 1e-4

    def test_risk_contrib_fields(self, patch_yfs):
        from backend.services.risk_parity_service import erc_weights
        result = erc_weights(_TICKERS)
        for row in result["riskContrib"]:
            assert "ticker" in row
            assert "weight" in row
            assert "pctContrib" in row

    def test_missing_key_present(self, patch_yfs):
        from backend.services.risk_parity_service import erc_weights
        result = erc_weights(_TICKERS)
        assert "missing" in result

    def test_insufficient_data_graceful(self, monkeypatch):
        from backend.services import risk_parity_service as rps
        monkeypatch.setattr(rps.yfs, "get_close_frame", lambda s, p: pd.DataFrame())
        result = rps.erc_weights(_TICKERS)
        assert "error" in result
        assert result["error"] == "insufficient data"


# ---------------------------------------------------------------------------
# risk_parity_backtest
# ---------------------------------------------------------------------------

class TestRiskParityBacktest:
    def test_series_non_empty(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        assert "series" in result
        assert len(result["series"]) > 0

    def test_series_has_strategy_and_benchmark(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        for pt in result["series"]:
            assert "date" in pt
            assert "strategy" in pt
            assert "benchmark" in pt

    def test_series_dates_format(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        for pt in result["series"]:
            parts = pt["date"].split("-")
            assert len(parts) == 3

    def test_series_strategy_values_finite(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        for pt in result["series"]:
            assert math.isfinite(pt["strategy"])
            assert math.isfinite(pt["benchmark"])

    def test_final_weights_present(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        assert "finalWeights" in result
        assert len(result["finalWeights"]) > 0

    def test_final_weights_sum_to_one(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        total = sum(w["weight"] for w in result["finalWeights"])
        assert abs(total - 1.0) < 1e-5

    def test_metrics_keys_present(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        assert "metrics" in result
        m = result["metrics"]
        assert "strategy" in m
        assert "benchmark" in m
        for key in ("cagr", "vol", "sharpe", "maxDrawdown"):
            assert key in m["strategy"]
            assert key in m["benchmark"]

    def test_missing_key_present(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="erc")
        assert "missing" in result

    def test_inv_vol_mode(self, patch_yfs_full):
        from backend.services.risk_parity_service import risk_parity_backtest
        result = risk_parity_backtest(_TICKERS, period="3y", mode="inv_vol")
        assert len(result["series"]) > 0

    def test_insufficient_data_graceful(self, monkeypatch):
        from backend.services import risk_parity_service as rps
        monkeypatch.setattr(rps.yfs, "get_close_frame", lambda s, p: pd.DataFrame())
        result = rps.risk_parity_backtest(_TICKERS)
        assert "error" in result
        assert result["error"] == "insufficient data"

    def test_single_asset_graceful(self, monkeypatch):
        from backend.services import risk_parity_service as rps
        # Only 1 asset column → insufficient data
        tiny = pd.DataFrame(
            {"ASSET_A": [100.0 + i * 0.1 for i in range(756)]},
            index=_bdays(756),
        )
        monkeypatch.setattr(rps.yfs, "get_close_frame", lambda s, p: tiny)
        result = rps.risk_parity_backtest(_TICKERS)
        assert "error" in result


def test_portfolio_metrics_cagr_is_compounded():
    """Audit C-04: +21% over two years is a 10% CAGR, not 10.5%."""
    import numpy as np
    import pandas as pd
    from backend.services.risk_parity_service import _portfolio_metrics, TRADING_DAYS

    n = 2 * TRADING_DAYS
    daily = (1.21) ** (1 / n) - 1
    m = _portfolio_metrics(pd.Series(np.full(n, daily)))
    assert m["cagr"] == pytest.approx(0.10, abs=1e-9)
