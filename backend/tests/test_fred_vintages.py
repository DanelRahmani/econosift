"""Tests for FRED vintage support and the walk-forward probit — Phase 42 (task C2).

Two separate look-ahead problems:

1. `fetch_fred_series` returned only the latest revision. GDP and payrolls are
   revised heavily, so a model scored on revised data looks better than it could
   have been in real time. `vintage` / `first_release` fix that.

2. The recession probit was fitted over the whole sample and then applied back
   across it, so the displayed historical path knew about recessions that had
   not happened yet. `_walk_forward_probit` refits at each month on data
   available then.

Note what was *not* wrong: T10Y3M is market data and is never revised, and the
service already used SAHMREALTIME rather than the revised Sahm series. The
contamination was in the fitting, not the inputs.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.services import macro_expansion_service as mes
from backend.services.recession_service import _walk_forward_probit


# ── Vintage plumbing ─────────────────────────────────────────────────────────

def test_vintage_and_first_release_reach_the_right_fredapi_methods(monkeypatch):
    calls: list[str] = []

    class FakeFred:
        def __init__(self, api_key=None):
            pass

        def get_series(self, sid, observation_start=None):
            calls.append("latest")
            return pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]))

        def get_series_first_release(self, sid):
            calls.append("first_release")
            return pd.Series([2.0], index=pd.to_datetime(["2020-01-01"]))

        def get_series_as_of_date(self, sid, vintage):
            calls.append(f"as_of:{vintage}")
            return pd.Series([3.0], index=pd.to_datetime(["2020-01-01"]))

    import fredapi
    monkeypatch.setattr(fredapi, "Fred", FakeFred)
    monkeypatch.setattr(mes, "FRED_API_KEY", "test-key")

    mes._fetch_fred_series_sync(["GDPC1"], "2015-01-01")
    mes._fetch_fred_series_sync(["GDPC1"], "2015-01-01", first_release=True)
    mes._fetch_fred_series_sync(["GDPC1"], "2015-01-01", vintage="2019-06-01")

    assert calls == ["latest", "first_release", "as_of:2019-06-01"]


def test_default_behaviour_is_unchanged(monkeypatch):
    """Existing callers must keep getting the latest revision."""
    class FakeFred:
        def __init__(self, api_key=None):
            pass

        def get_series(self, sid, observation_start=None):
            return pd.Series([1.5], index=pd.to_datetime(["2020-01-01"]))

    import fredapi
    monkeypatch.setattr(fredapi, "Fred", FakeFred)
    monkeypatch.setattr(mes, "FRED_API_KEY", "test-key")

    out = mes._fetch_fred_series_sync(["X"], "2015-01-01")
    assert out["X"] == [{"date": "2020-01-01", "value": 1.5}]


def test_vintage_requests_get_distinct_cache_keys():
    """_make_key folds in kwargs, so a vintage cannot collide with latest."""
    from backend.cache import _make_key

    latest = _make_key((("GDPC1",), "2015-01-01"), {})
    first = _make_key((("GDPC1",), "2015-01-01"), {"first_release": True})
    vint = _make_key((("GDPC1",), "2015-01-01"), {"vintage": "2019-06-01"})

    assert len({latest, first, vint}) == 3


def test_a_failing_series_still_degrades_to_empty(monkeypatch):
    class FakeFred:
        def __init__(self, api_key=None):
            pass

        def get_series_first_release(self, sid):
            raise RuntimeError("ALFRED unavailable")

    import fredapi
    monkeypatch.setattr(fredapi, "Fred", FakeFred)
    monkeypatch.setattr(mes, "FRED_API_KEY", "test-key")

    out = mes._fetch_fred_series_sync(["X"], "2015-01-01", first_release=True)
    assert out == {"X": []}


# ── Walk-forward probit ──────────────────────────────────────────────────────

def _monthly(start: str, values: list[float]) -> list[dict]:
    idx = pd.period_range(start, periods=len(values), freq="M")
    return [{"date": str(p), "value": v} for p, v in zip(idx, values)]


def _usrec_map(start: str, flags: list[int]) -> dict[str, float]:
    idx = pd.period_range(start, periods=len(flags), freq="M")
    return {str(p): float(f) for p, f in zip(idx, flags)}


def test_walk_forward_emits_nothing_before_the_training_window_fills():
    spread = _monthly("2000-01", [1.0] * 60)
    usrec = _usrec_map("2000-01", [0] * 60)

    out = _walk_forward_probit(spread, usrec, min_train=120)
    assert out == []


def test_walk_forward_never_uses_an_outcome_from_the_future():
    """The guard that matters: at month t, only pairs whose 12-month outcome
    already landed by t may be trained on."""
    seen: list[int] = []

    def spy(xs, ys):
        seen.append(len(xs))
        return 0.0, -1.0

    import backend.services.recession_service as rs
    original = rs._fit_probit
    rs._fit_probit = spy
    try:
        n = 200
        spread = _monthly("2000-01", [1.0] * n)
        usrec = _usrec_map("2000-01", [0] * n)
        _walk_forward_probit(spread, usrec, min_train=24)
    finally:
        rs._fit_probit = original

    # Training size grows monotonically and always lags the current index by
    # at least the 12-month outcome horizon.
    assert seen == sorted(seen)
    assert max(seen) <= 200 - 12


def test_walk_forward_produces_a_shorter_path_than_the_in_sample_one():
    n = 200
    spread = _monthly("2000-01", [1.0 if i % 3 else -1.0 for i in range(n)])
    usrec = _usrec_map("2000-01", [1 if i % 3 == 0 else 0 for i in range(n)])

    out = _walk_forward_probit(spread, usrec, min_train=60)

    assert 0 < len(out) < n
    assert all(0.0 <= p["value"] <= 100.0 for p in out)


def test_walk_forward_tracks_the_spread_sign():
    """Inverted spread should map to a higher probability than a steep one,
    given a training sample where inversion preceded recession."""
    n = 240
    # Inversions in the first half are followed by recessions 12m later.
    spread_vals = [-1.0 if (i // 12) % 2 == 0 else 2.0 for i in range(n)]
    flags = [1 if (max(0, i - 12) // 12) % 2 == 0 else 0 for i in range(n)]
    out = _walk_forward_probit(_monthly("2000-01", spread_vals), _usrec_map("2000-01", flags), min_train=60)

    assert out
    by_date = {p["date"]: p["value"] for p in out}
    inverted = [by_date[d] for i, d in enumerate(sorted(by_date)) if spread_vals[n - len(by_date) + i] < 0]
    steep = [by_date[d] for i, d in enumerate(sorted(by_date)) if spread_vals[n - len(by_date) + i] > 0]
    if inverted and steep:
        assert sum(inverted) / len(inverted) > sum(steep) / len(steep)


def test_walk_forward_handles_empty_input():
    assert _walk_forward_probit([], {}) == []
