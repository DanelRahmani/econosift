"""Tests for the Phase 17.A SQLAlchemy persistence layer.

All tests use an in-memory SQLite engine — no file I/O, no network, fully
deterministic.  The module-level `engine` in database.py is NOT used here;
we build a fresh engine per test session to keep the suite isolated.
"""
from __future__ import annotations

import importlib
import sys
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mem_engine():
    """In-memory SQLite engine with all ORM tables created."""
    # Patch DATABASE_URL so database.py doesn't touch the filesystem when
    # db_models is first imported (the module-level mkdir guard skips :memory:).
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

    from backend.database import Base
    import backend.db_models  # noqa: F401 — registers ORM classes

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(mem_engine):
    """Transactional session that rolls back after each test."""
    Session = sessionmaker(bind=mem_engine)
    db = Session()
    yield db
    db.rollback()
    db.close()


# ---------------------------------------------------------------------------
# Helper: import ORM classes lazily (after fixture bootstraps the package)
# ---------------------------------------------------------------------------

def _models():
    import backend.db_models as db_models
    return db_models


# ---------------------------------------------------------------------------
# 1. All 6 tables exist
# ---------------------------------------------------------------------------

def test_all_tables_exist(mem_engine):
    inspector = inspect(mem_engine)
    tables = set(inspector.get_table_names())
    expected = {
        "daily_price",
        "daily_quote",
        "daily_macro",
        "daily_fx",
        "job_execution",
        "cache_entry",
    }
    assert expected <= tables, f"Missing tables: {expected - tables}"


# ---------------------------------------------------------------------------
# 2. DailyPrice — insert and select by (symbol, date)
# ---------------------------------------------------------------------------

def test_daily_price_insert_and_select(session):
    m = _models()
    row = m.DailyPrice(
        symbol="AAPL",
        date=date(2024, 1, 2),
        open=185.0,
        high=188.5,
        low=184.0,
        close=187.0,
        adj_close=187.0,
        volume=55_000_000,
    )
    session.add(row)
    session.flush()

    result = (
        session.query(m.DailyPrice)
        .filter_by(symbol="AAPL", date=date(2024, 1, 2))
        .one()
    )
    assert result.close == pytest.approx(187.0)
    assert result.volume == 55_000_000


def test_daily_price_composite_pk_prevents_duplicate(session):
    m = _models()
    row1 = m.DailyPrice(symbol="MSFT", date=date(2024, 1, 3), close=400.0)
    row2 = m.DailyPrice(symbol="MSFT", date=date(2024, 1, 3), close=401.0)
    session.add(row1)
    session.flush()

    session.add(row2)
    with pytest.raises(Exception):  # IntegrityError from SQLite
        session.flush()


# ---------------------------------------------------------------------------
# 3. CacheEntry — insert and upsert (same key → one row)
# ---------------------------------------------------------------------------

def test_cache_entry_insert(session):
    m = _models()
    entry = m.CacheEntry(
        cache_name="macro",
        key="gdp_us_2023",
        value_json='{"value": 26.9}',
    )
    session.add(entry)
    session.flush()

    result = session.query(m.CacheEntry).filter_by(
        cache_name="macro", key="gdp_us_2023"
    ).one()
    assert result.value_json == '{"value": 26.9}'


def test_cache_entry_upsert_same_key_one_row(session):
    """Inserting the same PK twice (with merge) leaves exactly one row."""
    m = _models()
    entry1 = m.CacheEntry(
        cache_name="fx",
        key="EURUSD",
        value_json='"1.08"',
        created_at=datetime(2024, 1, 1),
    )
    session.merge(entry1)
    session.flush()

    entry2 = m.CacheEntry(
        cache_name="fx",
        key="EURUSD",
        value_json='"1.09"',
        created_at=datetime(2024, 1, 2),
    )
    session.merge(entry2)
    session.flush()

    rows = session.query(m.CacheEntry).filter_by(cache_name="fx", key="EURUSD").all()
    assert len(rows) == 1
    assert rows[0].value_json == '"1.09"'


# ---------------------------------------------------------------------------
# 4. JobExecution — insert and query by job_name
# ---------------------------------------------------------------------------

def test_job_execution_insert_and_query(session):
    m = _models()
    job = m.JobExecution(
        job_id="job-001",
        job_name="daily_price_refresh",
        status="completed",
        started_at=datetime(2024, 6, 25, 0, 0, 0),
        completed_at=datetime(2024, 6, 25, 0, 5, 30),
        rows_affected=503,
    )
    session.add(job)
    session.flush()

    result = (
        session.query(m.JobExecution)
        .filter_by(job_name="daily_price_refresh")
        .one()
    )
    assert result.status == "completed"
    assert result.rows_affected == 503
    assert result.error_message is None


# ---------------------------------------------------------------------------
# 5. DailyMacro — composite PK and index
# ---------------------------------------------------------------------------

def test_daily_macro_insert(session):
    m = _models()
    row = m.DailyMacro(
        indicator_id="NY.GDP.MKTP.CD",
        country="US",
        date=date(2023, 1, 1),
        value=26_950_000_000_000.0,
    )
    session.add(row)
    session.flush()

    result = session.query(m.DailyMacro).filter_by(
        indicator_id="NY.GDP.MKTP.CD", country="US", date=date(2023, 1, 1)
    ).one()
    assert result.value == pytest.approx(26_950_000_000_000.0)


# ---------------------------------------------------------------------------
# 6. DailyFX — composite PK
# ---------------------------------------------------------------------------

def test_daily_fx_insert(session):
    m = _models()
    row = m.DailyFX(base_ccy="EUR", quote_ccy="USD", date=date(2024, 3, 1), rate=1.085)
    session.add(row)
    session.flush()

    result = session.query(m.DailyFX).filter_by(
        base_ccy="EUR", quote_ccy="USD", date=date(2024, 3, 1)
    ).one()
    assert result.rate == pytest.approx(1.085)


# ---------------------------------------------------------------------------
# 7. DailyQuote — single-column PK
# ---------------------------------------------------------------------------

def test_daily_quote_insert(session):
    m = _models()
    row = m.DailyQuote(
        symbol="NVDA",
        date=date(2024, 6, 25),
        price=135.0,
        market_cap=3_300_000_000_000.0,
        pe=65.0,
        beta=1.7,
    )
    session.add(row)
    session.flush()

    result = session.query(m.DailyQuote).filter_by(symbol="NVDA").one()
    assert result.price == pytest.approx(135.0)
    assert result.beta == pytest.approx(1.7)
