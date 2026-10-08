"""Offline tests for P2-41: prune screener-cache rows for non-members.

Uses a temp SQLite DB; constituents and cache.clear_all are monkeypatched —
no network required.
"""
from __future__ import annotations

import sqlite3

import pytest

from backend.services import screener_cache, screener_service


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "s.db"
    monkeypatch.setenv("SCREENER_DB_PATH", str(path))
    screener_cache.reset_connection()
    screener_cache.upsert_rows(
        [{"symbol": s, "name": s} for s in ("AAPL", "MSFT", "ZS", "INSM")]
    )
    yield path
    screener_cache.reset_connection()


def _symbols() -> set[str]:
    conn = screener_cache._get_conn()
    return {r[0] for r in conn.execute("SELECT symbol FROM fundamentals").fetchall()}


def _patch_members(monkeypatch, members: dict[str, list[str]]) -> None:
    monkeypatch.setattr(
        screener_service._constituents,
        "get_constituents",
        lambda index: [{"symbol": s} for s in members.get(index, [])],
    )


def _record_clear_all(monkeypatch) -> list[str | None]:
    calls: list[str | None] = []
    monkeypatch.setattr(
        screener_service._cache, "clear_all", lambda name=None: calls.append(name) or {}
    )
    return calls


def test_prune_non_members_deletes_only_non_members(db, monkeypatch):
    _patch_members(monkeypatch, {"dow": ["AAPL"], "ndx": ["MSFT"], "sp500": ["AAPL", "MSFT"]})
    _record_clear_all(monkeypatch)
    assert screener_service.prune_non_members() == 2
    assert _symbols() == {"AAPL", "MSFT"}


def test_prune_skipped_when_any_index_fetch_empty(db, monkeypatch):
    _patch_members(monkeypatch, {"dow": ["AAPL"], "ndx": ["MSFT"], "sp500": []})
    calls = _record_clear_all(monkeypatch)
    assert screener_service.prune_non_members() == 0
    assert _symbols() == {"AAPL", "MSFT", "ZS", "INSM"}
    assert calls == []


def test_prune_except_empty_keep_deletes_nothing(db):
    assert screener_cache.prune_except([]) == 0
    assert screener_cache.prune_except(set()) == 0
    assert _symbols() == {"AAPL", "MSFT", "ZS", "INSM"}


def test_prune_except_also_prunes_shares(db):
    screener_cache.upsert_shares({"AAPL": 1.0, "ZS": 2.0})
    assert screener_cache.prune_except({"AAPL", "MSFT"}) == 2
    assert set(screener_cache.get_shares(["AAPL", "ZS"])) == {"AAPL"}


def test_old_member_row_is_kept(db, monkeypatch):
    conn = screener_cache._get_conn()
    conn.execute(
        "UPDATE fundamentals SET updated_at = '2026-06-01T00:00:00+00:00' WHERE symbol = 'AAPL'"
    )
    conn.commit()
    _patch_members(monkeypatch, {"dow": ["AAPL"], "ndx": ["MSFT"], "sp500": ["AAPL", "MSFT"]})
    _record_clear_all(monkeypatch)
    screener_service.prune_non_members()
    assert "AAPL" in _symbols()


def test_clear_all_called_for_three_caches_only_when_rows_deleted(db, monkeypatch):
    calls = _record_clear_all(monkeypatch)

    # Nothing to prune -> no cache flush
    _patch_members(
        monkeypatch,
        {"dow": ["AAPL"], "ndx": ["MSFT", "ZS", "INSM"], "sp500": ["AAPL"]},
    )
    assert screener_service.prune_non_members() == 0
    assert calls == []

    # Rows deleted -> exactly the three named caches flushed
    _patch_members(monkeypatch, {"dow": ["AAPL"], "ndx": ["MSFT"], "sp500": ["AAPL"]})
    assert screener_service.prune_non_members() == 2
    assert sorted(calls) == ["sector_fundamentals", "snowflake_batch", "snowflake_full"]


def test_refresh_universe_prunes_after_writing(db, monkeypatch):
    """A rebuild through refresh_universe (the path a long-running container uses)
    prunes too, not only the startup warm (spec review of P2-41)."""
    import pandas as pd

    _patch_members(monkeypatch, {"dow": ["AAPL"], "ndx": ["MSFT"], "sp500": ["AAPL", "MSFT"]})
    _record_clear_all(monkeypatch)
    yfs = screener_service.yfs
    monkeypatch.setattr(yfs, "get_close_frame", lambda syms, period: pd.DataFrame())
    monkeypatch.setattr(yfs, "get_volume_frame", lambda syms, period: pd.DataFrame())
    monkeypatch.setattr(yfs, "get_info", lambda sym: {"info": {}, "financials": {}, "balance_sheet": {}, "cashflow": {}})

    screener_service.refresh_universe("dow")
    # ZS and INSM are in no tracked index, so the rebuild removed them.
    assert _symbols() == {"AAPL", "MSFT"}
