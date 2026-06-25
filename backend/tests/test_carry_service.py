"""Tests for carry_service — fully offline (FRED and yfinance monkeypatched)."""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------

def _make_fred_data() -> dict[str, pd.Series]:
    """Return synthetic FRED series for G10 policy rates.

    AUD/NZD get high rates (above USD) → positive carry.
    JPY/CHF get near-zero rates → negative carry vs USD.
    USD (FEDFUNDS) = 3.00% (below AUD/NZD so they have positive carry).
    """
    end = date.today()
    idx = pd.date_range(end=end, periods=24, freq="MS")  # 24 months back

    def _series(rate: float) -> pd.Series:
        return pd.Series([rate] * len(idx), index=idx)

    return {
        "FEDFUNDS":          _series(3.00),   # USD
        "ECBMRRFR":          _series(2.50),   # EUR  carry = -0.50
        "BOERUKM":           _series(3.50),   # GBP  carry = +0.50
        "INTDSRAUAM193N":    _series(4.35),   # AUD  carry = +1.35
        "INTDSRNZM193N":     _series(5.50),   # NZD  carry = +2.50  ← highest
        "INTDSRCAM193N":     _series(3.25),   # CAD  carry = +0.25
        "INTDSRCHM193N":     _series(1.50),   # CHF  carry = -1.50
        "INTDSRJPM193N":     _series(0.10),   # JPY  carry = -2.90  ← lowest
    }


def _make_fx_close(symbols: tuple[str, ...], period: str) -> pd.DataFrame:
    """Return synthetic FX price series for the requested symbols.

    Flat prices (1.0 base) with tiny drift so vol is non-zero.
    """
    rows = 756  # ~3 years of trading days
    idx = pd.date_range(end=date.today(), periods=rows, freq="B")
    data: dict[str, list[float]] = {}
    for i, sym in enumerate(symbols):
        base = 0.8 + i * 0.05
        prices = [base + j * 0.0001 for j in range(rows)]
        data[sym] = prices
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------

def _patch_services(monkeypatch, *, fred_data: dict | None = None):
    """Monkeypatch rates_service._fetch_many_fred_sync and yfs.get_close_frame."""
    import backend.services.carry_service as cs
    import backend.services.rates_service as rs
    import backend.services.yfinance_service as yfs_mod
    from backend.cache import _caches

    # Clear carry caches
    for key in list(_caches.keys()):
        if "carry" in key:
            _caches[key].clear()
    # Also clear yf_close so monkeypatched version is used
    for key in list(_caches.keys()):
        if "yf_close" in key:
            _caches[key].clear()

    _data = fred_data if fred_data is not None else _make_fred_data()

    def _fake_fred(series_ids: list[str], start: str) -> dict[str, pd.Series]:
        return {sid: s for sid, s in _data.items() if sid in series_ids}

    def _fake_fx(symbols: tuple, period: str) -> pd.DataFrame:
        return _make_fx_close(symbols, period)

    monkeypatch.setattr(rs, "_fetch_many_fred_sync", _fake_fred)
    # carry_service holds its own module reference
    monkeypatch.setattr(cs.rates_service, "_fetch_many_fred_sync", _fake_fred)
    monkeypatch.setattr(yfs_mod, "get_close_frame", _fake_fx)
    monkeypatch.setattr(cs.yfs, "get_close_frame", _fake_fx)


# ---------------------------------------------------------------------------
# get_carry_table tests
# ---------------------------------------------------------------------------

def test_carry_table_shape(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    assert "asOf" in result
    assert "usdRate" in result
    assert "rows" in result
    assert isinstance(result["rows"], list)
    assert len(result["rows"]) > 0


def test_carry_table_usd_rate(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    assert result["usdRate"] == pytest.approx(3.00, rel=1e-3)


def test_carry_table_sorted_by_carry_desc(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    carries = [r["carry"] for r in result["rows"] if r["carry"] is not None]
    assert carries == sorted(carries, reverse=True), "rows must be sorted by carry descending"


def test_carry_table_nzd_aud_above_jpy_chf(monkeypatch):
    """NZD (5.50%) and AUD (4.35%) should have positive carry; JPY (0.10%) and CHF (1.50%) negative."""
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    rows_by_ccy = {r["ccy"]: r for r in result["rows"]}

    assert "NZD" in rows_by_ccy, "NZD must appear in table"
    assert "AUD" in rows_by_ccy, "AUD must appear in table"
    assert "JPY" in rows_by_ccy, "JPY must appear in table"
    assert "CHF" in rows_by_ccy, "CHF must appear in table"

    assert rows_by_ccy["NZD"]["carry"] > 0, "NZD carry should be positive"
    assert rows_by_ccy["AUD"]["carry"] > 0, "AUD carry should be positive"
    assert rows_by_ccy["JPY"]["carry"] < 0, "JPY carry should be negative"
    assert rows_by_ccy["CHF"]["carry"] < 0, "CHF carry should be negative"

    # NZD must rank above JPY
    ccys = [r["ccy"] for r in result["rows"]]
    assert ccys.index("NZD") < ccys.index("JPY"), "NZD must rank higher than JPY"


def test_carry_table_row_fields(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    required = {"ccy", "pair", "spot", "foreignRate", "carry", "fxVol", "volAdjCarry", "rateSource"}
    for row in result["rows"]:
        missing = required - set(row.keys())
        assert not missing, f"Row {row.get('ccy')} missing fields: {missing}"


def test_carry_table_no_nan_inf(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    float_fields = ("spot", "foreignRate", "carry", "fxVol", "volAdjCarry")
    for row in result["rows"]:
        for field in float_fields:
            val = row.get(field)
            if val is not None:
                assert math.isfinite(val), f"{row['ccy']}.{field} is not finite: {val}"


def test_carry_table_pair_format(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    for row in result["rows"]:
        assert row["pair"] == f"{row['ccy']}/USD", f"pair format wrong: {row['pair']}"


def test_carry_table_carry_equals_foreign_minus_usd(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    usd_rate = result["usdRate"]
    for row in result["rows"]:
        if row["carry"] is not None and row["foreignRate"] is not None:
            expected = round(row["foreignRate"] - usd_rate, 4)
            assert row["carry"] == pytest.approx(expected, abs=1e-3), (
                f"{row['ccy']}: carry={row['carry']} != foreignRate-usdRate={expected}"
            )


def test_carry_table_vol_adj_carry_sign(monkeypatch):
    """volAdjCarry should have same sign as carry."""
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    for row in result["rows"]:
        if row["carry"] is not None and row["volAdjCarry"] is not None:
            same_sign = (row["carry"] >= 0) == (row["volAdjCarry"] >= 0)
            assert same_sign, f"{row['ccy']}: carry and volAdjCarry have different signs"


# ---------------------------------------------------------------------------
# get_carry_backtest tests
# ---------------------------------------------------------------------------

def test_backtest_series_non_empty(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    assert "series" in result
    assert len(result["series"]) > 0


def test_backtest_legs_count(monkeypatch):
    """Exactly 3 long and 3 short legs."""
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    assert len(result["legs"]["long"]) == 3
    assert len(result["legs"]["short"]) == 3


def test_backtest_legs_no_overlap(monkeypatch):
    """Long and short legs must not share any currency."""
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    overlap = set(result["legs"]["long"]) & set(result["legs"]["short"])
    assert not overlap, f"Long/short legs overlap: {overlap}"


def test_backtest_legs_nzd_aud_in_long(monkeypatch):
    """NZD and AUD (highest carry) should be in the long leg."""
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    long_set = set(result["legs"]["long"])
    assert "NZD" in long_set, "NZD should be in long leg"
    assert "AUD" in long_set, "AUD should be in long leg"


def test_backtest_legs_jpy_in_short(monkeypatch):
    """JPY (lowest carry) should be in the short leg."""
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    short_set = set(result["legs"]["short"])
    assert "JPY" in short_set, "JPY should be in short leg"


def test_backtest_series_fields(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    required = {"date", "strategy", "benchmark"}
    for rec in result["series"][:5]:
        missing = required - set(rec.keys())
        assert not missing, f"Series record missing fields: {missing}"


def test_backtest_series_dates_ascending(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    dates = [r["date"] for r in result["series"]]
    assert dates == sorted(dates), "Series dates must be in ascending order"


def test_backtest_metrics_present(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    assert "metrics" in result
    for key in ("cagr", "vol", "sharpe", "maxDrawdown"):
        assert key in result["metrics"], f"metrics missing key: {key}"


def test_backtest_metrics_finite(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    for key, val in result["metrics"].items():
        if val is not None:
            assert math.isfinite(val), f"metrics.{key} is not finite: {val}"


def test_backtest_strategy_no_nan(monkeypatch):
    _patch_services(monkeypatch)
    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    for rec in result["series"]:
        strat = rec["strategy"]
        if strat is not None:
            assert math.isfinite(strat), f"strategy value not finite: {strat}"


# ---------------------------------------------------------------------------
# Graceful degradation: no FRED key
# ---------------------------------------------------------------------------

def test_no_fred_key_graceful(monkeypatch):
    """When FRED returns empty (no API key), get_carry_table returns error shape without raising."""
    import backend.services.carry_service as cs
    import backend.services.rates_service as rs
    import backend.services.yfinance_service as yfs_mod
    from backend.cache import _caches

    for key in list(_caches.keys()):
        if "carry" in key:
            _caches[key].clear()
    for key in list(_caches.keys()):
        if "yf_close" in key:
            _caches[key].clear()

    # FRED returns empty (simulates missing API key)
    monkeypatch.setattr(rs, "_fetch_many_fred_sync", lambda ids, start: {})
    monkeypatch.setattr(cs.rates_service, "_fetch_many_fred_sync", lambda ids, start: {})
    monkeypatch.setattr(yfs_mod, "get_close_frame", _make_fx_close)
    monkeypatch.setattr(cs.yfs, "get_close_frame", _make_fx_close)

    from backend.services.carry_service import get_carry_table

    result = get_carry_table("3y")
    # Must not raise, must return a dict with "rows" key
    assert isinstance(result, dict)
    assert "rows" in result or "error" in result


def test_no_fx_data_graceful(monkeypatch):
    """When FX data is empty, get_carry_backtest returns error shape without raising."""
    import backend.services.carry_service as cs
    import backend.services.rates_service as rs
    import backend.services.yfinance_service as yfs_mod
    from backend.cache import _caches

    for key in list(_caches.keys()):
        if "carry" in key:
            _caches[key].clear()
    for key in list(_caches.keys()):
        if "yf_close" in key:
            _caches[key].clear()

    monkeypatch.setattr(rs, "_fetch_many_fred_sync", lambda ids, start: _make_fred_data())
    monkeypatch.setattr(cs.rates_service, "_fetch_many_fred_sync", lambda ids, start: _make_fred_data())

    def _empty_fx(symbols, period):
        return pd.DataFrame()

    monkeypatch.setattr(yfs_mod, "get_close_frame", _empty_fx)
    monkeypatch.setattr(cs.yfs, "get_close_frame", _empty_fx)

    from backend.services.carry_service import get_carry_backtest

    result = get_carry_backtest("3y")
    assert isinstance(result, dict)
    assert "series" in result
    # With no FX data, series should be empty or there's an error key
    assert len(result["series"]) == 0 or "error" in result
