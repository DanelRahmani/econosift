"""SQLAlchemy engine, session factory, and init_db for EconoSift."""
from __future__ import annotations

import os
import pathlib

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Resolve the data dir from config (single source of truth): ECONOSIFT_DATA_DIR
# (or legacy AXIOM_DATA_DIR) if set, otherwise the OS app-data dir. Do NOT
# default to a CWD-relative "./data" — in the packaged desktop app the backend's
# working directory is unpredictable, which would scatter the SQLite DB.
from .config import DATA_DIR

_DEFAULT_DB_URL = f"sqlite:///{DATA_DIR.as_posix()}/axiomfinance.db"
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)

# Ensure the data directory exists for SQLite paths
if DATABASE_URL.startswith("sqlite") and DATABASE_URL != "sqlite:///:memory:":
    db_path = DATABASE_URL.replace("sqlite:///", "")
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

# Enable WAL mode for SQLite — better concurrent read performance
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist. Idempotent (CREATE TABLE IF NOT EXISTS)."""
    from . import db_models  # noqa: F401 — side-effect: registers ORM models
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


# Columns added to existing tables after release; create_all only creates missing tables.
_ADDED_COLUMNS = {"ai_summary": {"grounding": "TEXT"}}


def _add_missing_columns() -> None:
    """Idempotently ALTER TABLE ... ADD COLUMN for columns newer than the user's database."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
