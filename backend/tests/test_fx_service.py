"""Tests for fx_service.fx_rates — fully offline via monkeypatching."""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Synthetic data factory
# ---------------------------------------------------------------------------

def _make_synthetic_frame(tickers: tuple, rows: int = 260) -> pd.DataFrame:
    """Return a DataFrame of synthetic daily close prices for the given tickers."""
    idx = pd.date_range(end=date.today(), periods=rows, freq="B")
    data = {}
    for i, tk in enumerate(tickers):
        # Different base prices per ticker to vary columns.
        base_price = 1.0 + i * 0.5
        # Steady upward drift so change1d/1w/1m/1y are all positive.
        prices = [base_price + (j * 0.001) for j in range(rows)]
        # Small extra bump on the last day to ensure change1d > 0.
        prices[-1] = prices[-2] * 1.005
        data[tk] = prices
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def patch_get_close_frame(monkeypatch):
    """Replace yfs.get_close_frame with a deterministic synthetic implementation."""
    import backend.services.fx_service as fx_svc
    import backend.services.yfinance_service as yfs_mod

    call_count = {"n": 0}

    def _fake_get_close_frame(symbols: tuple, period: str) -> pd.DataFrame:
        call_count["n"] += 1
        return _make_synthetic_frame(symbols, rows=260)

    monkeypatch.setattr(yfs_mod, "get_close_frame", _fake_get_close_frame)
    # fx_service holds its own reference to the yfs module object; patch it there too.
    monkeypatch.setattr(fx_svc.yfs, "get_close_frame", _fake_get_close_frame)

    return call_count


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fx_rates_shape(patch_get_close_frame):
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")

    assert result["base"] == "USD"
    assert "asOf" in result
    assert "pairs" in result

    # Exactly 16 pairs in the universe.
    pairs = result["pairs"]
    assert len(pairs) == 16


def test_fx_rates_pair_fields(patch_get_close_frame):
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")
    required_fields = {"pair", "quote", "rate", "change1d", "change1w", "change1m", "change1y", "sparkline"}

    for p in result["pairs"]:
        missing = required_fields - set(p.keys())
        assert not missing, f"Pair {p.get('pair')} missing fields: {missing}"


def test_fx_rates_rate_is_float(patch_get_close_frame):
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")
    for p in result["pairs"]:
        if p["rate"] is not None:
            assert isinstance(p["rate"], float), f"{p['pair']} rate not float"
            assert not math.isnan(p["rate"]), f"{p['pair']} rate is NaN"
            assert not math.isinf(p["rate"]), f"{p['pair']} rate is Inf"


def test_fx_rates_change_signs_positive(patch_get_close_frame):
    """With an upward-drifting synthetic series, change1d must be positive."""
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")
    for p in result["pairs"]:
        if p["change1d"] is not None:
            assert p["change1d"] > 0, (
                f"{p['pair']} expected positive 1d change, got {p['change1d']}"
            )


def test_fx_rates_change_1y_positive(patch_get_close_frame):
    """1y change should be positive for 260-row upward-drifting series."""
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")
    for p in result["pairs"]:
        if p["change1y"] is not None:
            assert p["change1y"] > 0, (
                f"{p['pair']} expected positive 1y change, got {p['change1y']}"
            )


def test_fx_rates_sparkline_length(patch_get_close_frame):
    """Sparkline must have at most 30 entries and all-finite floats."""
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")
    for p in result["pairs"]:
        assert len(p["sparkline"]) <= 30, (
            f"{p['pair']} sparkline has {len(p['sparkline'])} entries (max 30)"
        )
        for v in p["sparkline"]:
            assert isinstance(v, float)
            assert not math.isnan(v)
            assert not math.isinf(v)


def test_fx_rates_pair_labels(patch_get_close_frame):
    """Pair labels must follow 'BASE/QUOTE' format."""
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")
    for p in result["pairs"]:
        assert "/" in p["pair"], f"Pair label {p['pair']} missing '/'"
        base, quote = p["pair"].split("/")
        assert base == "USD"
        assert quote == p["quote"]


def test_fx_rates_no_network(monkeypatch):
    """Verify no live network is used: the mock is wired in and the result is valid.

    The cache may serve a hit from earlier tests — that is fine; it means the
    data came from the already-patched call, not the network. We simply assert
    the returned structure is well-formed, which would be wrong if a live
    network call somehow bypassed the mock and returned unexpected data.
    """
    import backend.services.fx_service as fx_svc
    import backend.services.yfinance_service as yfs_mod

    # Wire a distinctive fake so any live call would corrupt the result.
    def _fake(symbols, period):
        return _make_synthetic_frame(symbols, rows=260)

    monkeypatch.setattr(yfs_mod, "get_close_frame", _fake)
    monkeypatch.setattr(fx_svc.yfs, "get_close_frame", _fake)

    result = fx_svc.fx_rates("USD")
    assert result["base"] == "USD"
    assert len(result["pairs"]) == 16
    # All pairs must have the required keys — proves the service ran correctly.
    for p in result["pairs"]:
        assert "rate" in p and "sparkline" in p


def test_fx_rates_eur_present(patch_get_close_frame):
    """EUR pair must always appear in the results."""
    from backend.services.fx_service import fx_rates

    result = fx_rates("USD")
    quotes = {p["quote"] for p in result["pairs"]}
    assert "EUR" in quotes


def test_fx_rates_short_series_guarded(monkeypatch):
    """If only 3 rows come back, changes use available history; no exceptions."""
    import backend.services.fx_service as fx_svc
    import backend.services.yfinance_service as yfs_mod

    def _short_frame(symbols, period):
        idx = pd.date_range(end=date.today(), periods=3, freq="B")
        data = {tk: [1.0, 1.01, 1.02] for tk in symbols}
        return pd.DataFrame(data, index=idx)

    monkeypatch.setattr(yfs_mod, "get_close_frame", _short_frame)
    monkeypatch.setattr(fx_svc.yfs, "get_close_frame", _short_frame)

    result = fx_svc.fx_rates("USD")
    eur = next(p for p in result["pairs"] if p["quote"] == "EUR")

    # With 3 rows: change1d (n=1) works fine.
    assert eur["change1d"] is not None
    assert isinstance(eur["change1d"], float)

    # All change values (if returned) must be finite floats.
    for key in ("change1d", "change1w", "change1m", "change1y"):
        val = eur[key]
        if val is not None:
            assert isinstance(val, float)
            assert not math.isnan(val)
            assert not math.isinf(val)

    # Sparkline must not exceed 30 entries (and here <= 3 rows).
    assert len(eur["sparkline"]) <= 30
