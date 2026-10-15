"""An empty DataFrame/Series is a failed fetch and must never be cached.

A failed yf.download returns an empty DataFrame; caching it blanked the
treemap/breadth/sector/risk views for the full TTL.
"""
import pandas as pd

from backend import cache
from backend.cache import _is_empty_result


def test_empty_frame_and_series_count_as_empty():
    assert _is_empty_result(pd.DataFrame())
    assert _is_empty_result(pd.DataFrame(columns=["Close"]))
    assert _is_empty_result(pd.Series(dtype=float))


def test_non_empty_frame_and_series_are_kept():
    assert not _is_empty_result(pd.DataFrame({"Close": [1.0]}))
    assert not _is_empty_result(pd.Series([1.0]))


def test_cached_does_not_store_empty_frame():
    calls = []

    @cache.cached(name="test_empty_frame_p65")
    def fetch():
        calls.append(1)
        return pd.DataFrame()

    fetch()
    fetch()
    assert len(calls) == 2
