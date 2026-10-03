"""P2-33: count cached responses that predate source annotations.

Entries cached before an upgrade that added provenance keep serving without a
map until they expire. A cache whose other dict entries carry a map shows the
function now attaches one, so its map-less dict entries are pre-upgrade leftovers.
Caches that never attach a map (internal lists, plain dicts) are not counted, nor
are error payloads, which skip provenance by design.
"""
from __future__ import annotations

import json

import pytest

from backend import cache
from backend.database import SessionLocal, init_db
from backend.db_models import CacheEntry


@pytest.fixture(autouse=True)
def _tables():
    init_db()  # the pinned test DB starts empty
    cache.clear_all()


def _put(name: str, key: str, value) -> None:
    with SessionLocal() as db:
        db.merge(CacheEntry(cache_name=name, key=key, value_json=json.dumps(value)))
        db.commit()


def test_counts_only_map_less_entries_of_caches_that_now_attach_maps():
    prov = {"*": {"provider": "yahoo"}}
    _put("quote", "AAPL", {"price": 1, "provenance": prov})
    _put("quote", "MSFT", {"price": 2, "provenance": prov})
    _put("quote", "NVDA", {"price": 3})                       # pre-upgrade: counted
    _put("quote", "ZZZZ", {"error": "no data"})               # error payload: not counted
    _put("series", "x", [1, 2, 3])                            # internal list cache: not counted
    _put("plain", "y", {"a": 1})                              # never attaches a map: not counted

    assert cache.provenance_gaps() == {"total": 1, "byName": {"quote": 1}}


def test_no_gaps_on_an_empty_cache():
    assert cache.provenance_gaps() == {"total": 0, "byName": {}}
