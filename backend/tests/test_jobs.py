"""Tests for backend.services.jobs - job logging and scheduler control."""
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


@pytest.fixture
def in_memory_session():
    """Create an in-memory SQLite session factory for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.db_models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return Session


def _make_jobs_mod(Session):
    """Import (or reload) jobs module with SessionLocal pre-set to the test Session."""
    import importlib
    import backend.services.jobs as jobs_mod
    importlib.reload(jobs_mod)
    # Override the lazy sentinel so _get_session() returns our in-memory factory.
    jobs_mod.SessionLocal = Session
    return jobs_mod


def test_log_job_start(in_memory_session):
    """log_job_start creates a JobExecution row with status=running."""
    from backend.db_models import JobExecution
    Session = in_memory_session
    jobs_mod = _make_jobs_mod(Session)

    job_id = jobs_mod.log_job_start("test_job")

    assert job_id is not None
    with Session() as session:
        job = session.get(JobExecution, job_id)
        assert job is not None
        assert job.status == "running"
        assert job.job_name == "test_job"
        assert job.started_at is not None


def test_log_job_success(in_memory_session):
    """log_job_success updates status to success and records rows_affected."""
    from backend.db_models import JobExecution
    Session = in_memory_session
    jobs_mod = _make_jobs_mod(Session)

    job_id = str(uuid.uuid4())
    with Session() as session:
        session.add(JobExecution(
            job_id=job_id, job_name="test", status="running",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        session.commit()

    jobs_mod.log_job_success(job_id, rows=42)

    with Session() as session:
        job = session.get(JobExecution, job_id)
        assert job.status == "success"
        assert job.rows_affected == 42
        assert job.completed_at is not None


def test_log_job_failure(in_memory_session):
    """log_job_failure updates status to failed and stores the error message."""
    from backend.db_models import JobExecution
    Session = in_memory_session
    jobs_mod = _make_jobs_mod(Session)

    job_id = str(uuid.uuid4())
    with Session() as session:
        session.add(JobExecution(
            job_id=job_id, job_name="test", status="running",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        session.commit()

    jobs_mod.log_job_failure(job_id, "Something broke")

    with Session() as session:
        job = session.get(JobExecution, job_id)
        assert job.status == "failed"
        assert "Something broke" in job.error_message


def test_start_scheduler_disabled():
    """Scheduler returns None when SCHEDULER_ENABLED=false."""
    import os
    import importlib
    import backend.services.jobs as jobs_mod
    importlib.reload(jobs_mod)

    with patch.dict(os.environ, {"SCHEDULER_ENABLED": "false"}):
        result = jobs_mod.start_scheduler()
    assert result is None


def test_refresh_fx_rates_logs_job(in_memory_session):
    """refresh_fx_rates creates a JobExecution entry with terminal status."""
    from backend.db_models import JobExecution
    import pandas as pd
    Session = in_memory_session
    jobs_mod = _make_jobs_mod(Session)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()  # empty - skips all pairs

    with patch("yfinance.Ticker", return_value=mock_ticker):
        jobs_mod.refresh_fx_rates()

    with Session() as session:
        jobs = session.query(JobExecution).filter_by(job_name="refresh_fx_rates").all()
        assert len(jobs) == 1
        assert jobs[0].status in ("success", "failed")


# ---------------------------------------------------------------------------
# P1-16: jobs must not hold SQLite's write lock across network fetches, or
# every cache write and Admin "Clear cache" fails with "database is locked"
# for the whole run (refresh_daily_quotes held it ~14 min).
# ---------------------------------------------------------------------------

def _file_session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.db_models import Base

    url = f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 0.1})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False), url


def _can_write(url) -> bool:
    import sqlite3
    conn = sqlite3.connect(url.replace("sqlite:///", ""), timeout=0.1)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS probe (x INTEGER)")
        conn.execute("INSERT INTO probe VALUES (1)")
        conn.commit()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def test_daily_quotes_does_not_hold_write_lock_while_fetching(tmp_path):
    Session, url = _file_session(tmp_path)
    jobs_mod = _make_jobs_mod(Session)
    writable = []

    def fake_quote(sym):
        writable.append(_can_write(url))  # another writer during the fetch
        return {"price": 10.0}

    with patch.object(jobs_mod, "_get_all_tracked_tickers", return_value=["AAA", "BBB", "CCC"]), \
         patch("backend.services.yfinance_service.get_quote", side_effect=fake_quote), \
         patch("backend.services.yfinance_service.get_info", return_value={"marketCap": 1e9}):
        jobs_mod.refresh_daily_quotes()

    assert writable == [True, True, True]
    from backend.db_models import DailyQuote
    with Session() as s:
        assert {q.symbol for q in s.query(DailyQuote)} == {"AAA", "BBB", "CCC"}
