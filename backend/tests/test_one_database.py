"""Phase 66: one SQLite file, econosift.db, for everything."""
from backend import database
from backend.services import screener_cache


def test_default_database_file_is_econosift_db():
    assert database._DEFAULT_DB_URL.endswith("/econosift.db")


def test_screener_cache_lives_in_the_app_database(monkeypatch):
    monkeypatch.delenv("SCREENER_DB_PATH", raising=False)
    assert screener_cache._db_path() == database.DB_PATH
