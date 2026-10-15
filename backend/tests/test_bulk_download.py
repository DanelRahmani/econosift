"""Large yf.download batches run as low-priority chunks (Phase 65 gate fix).

A cold start fired ~4,600 chart requests from 500-ticker downloads; a
two-ticker page request waited 117 s behind them in the shared bucket.
"""
import pandas as pd

from backend import rate_limit
from backend.services import yfinance_service as yfs


def _fake_download(calls):
    def download(symbols, **kw):
        calls.append((list(symbols), kw.get("threads"), rate_limit.is_bulk()))
        idx = pd.date_range("2026-01-01", periods=3, freq="D")
        cols = pd.MultiIndex.from_product([["Close", "Volume"], list(symbols)])
        return pd.DataFrame(1.0, index=idx, columns=cols)
    return download


def test_small_batch_is_one_normal_priority_download(monkeypatch):
    calls = []
    monkeypatch.setattr(yfs.yf, "download", _fake_download(calls))
    frame = yfs.get_close_frame(("AAPL", "MSFT"), "1y")
    assert calls == [(["AAPL", "MSFT"], True, False)]
    assert list(frame.columns) == ["AAPL", "MSFT"]


def test_large_batch_is_chunked_low_priority_and_reassembled(monkeypatch):
    calls = []
    monkeypatch.setattr(yfs.yf, "download", _fake_download(calls))
    syms = tuple(f"T{i:03d}" for i in range(100))
    frame = yfs.get_close_frame(syms, "1y")
    assert len(calls) == yfs._BULK_WORKERS
    assert all(threads is False and bulk for _, threads, bulk in calls)
    assert sorted(s for chunk, _, _ in calls for s in chunk) == sorted(syms)
    assert sorted(frame.columns) == sorted(syms)
    assert len(frame) == 3
