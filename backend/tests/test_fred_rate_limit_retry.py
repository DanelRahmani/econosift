"""A FRED rate-limit error must be retried, not cached as an empty series (P1-14).

`fetch_fred_series` only skips caching when *every* series came back empty, so
one rate-limited series inside a 43-series request used to be cached as [] for
an hour — a silent hole in the curve.
"""
from __future__ import annotations

import pandas as pd

from backend.services import macro_expansion_service as mes


def _fake_fred(fail_times: dict[str, int], calls: list[str]):
    class FakeFred:
        def __init__(self, api_key=None):
            pass

        def get_series(self, sid, observation_start=None):
            calls.append(sid)
            if fail_times.get(sid, 0) > 0:
                fail_times[sid] -= 1
                raise ValueError("Too Many Requests.  Exceeded Rate Limit")
            return pd.Series([1.5], index=pd.to_datetime(["2026-01-01"]))

    return FakeFred


def test_rate_limited_series_is_retried(monkeypatch):
    import fredapi
    calls: list[str] = []
    monkeypatch.setattr(fredapi, "Fred", _fake_fred({"DGS10": 1}, calls))
    monkeypatch.setattr(mes, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(mes, "_RATE_LIMIT_RETRY_S", 0)

    out = mes._fetch_fred_series_sync(["DGS2", "DGS10"], "2020-01-01")

    assert out["DGS10"] == [{"date": "2026-01-01", "value": 1.5}]
    assert calls == ["DGS2", "DGS10", "DGS10"]


def test_persistent_rate_limit_gives_up_after_one_retry(monkeypatch):
    import fredapi
    calls: list[str] = []
    monkeypatch.setattr(fredapi, "Fred", _fake_fred({"DGS10": 5}, calls))
    monkeypatch.setattr(mes, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(mes, "_RATE_LIMIT_RETRY_S", 0)

    out = mes._fetch_fred_series_sync(["DGS10"], "2020-01-01")

    assert out["DGS10"] == []
    assert calls == ["DGS10", "DGS10"]
