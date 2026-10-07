"""P2-36: the suite must never run against the live database.

`conftest.py` clears both cache tiers before every test. If pytest used
whatever DATABASE_URL the shell (or the backend container) provides, a test
run would wipe the live cache. conftest therefore pins its own throwaway
SQLite file, overriding any inherited DATABASE_URL.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from backend import database


def test_database_url_is_pinned_to_a_throwaway_file():
    assert database.DATABASE_URL.startswith("sqlite:///")
    db_path = Path(database.DATABASE_URL.replace("sqlite:///", "", 1)).resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    # The DB lives directly in the OS temp dir under a pytest-specific name ...
    assert db_path.parent == tmp
    assert db_path.name == "econosift_pytest.db"
    # ... and is never the app's default (live) database.
    assert database.DATABASE_URL != database._DEFAULT_DB_URL


def test_engine_uses_the_pinned_url():
    assert str(database.engine.url) == database.DATABASE_URL
