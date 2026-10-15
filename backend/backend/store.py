"""Market-data tables in econosift.db and the helpers that read and write them.

Phase 66: the fetcher thread is the only writer of these tables; API requests
only read them. Writes are batched (`executemany` in one transaction) instead
of one ORM `merge()` per row, which ran a SELECT before every insert.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterable, Iterator, Sequence

import pandas as pd

from .database import engine

# Tables keyed on (symbol, date)-like tuples are WITHOUT ROWID: the rows are
# stored in primary-key order, so a range scan for one symbol is one B-tree walk.
SCHEMA = """
CREATE TABLE IF NOT EXISTS security (
    symbol              TEXT PRIMARY KEY,
    name                TEXT,
    cik                 TEXT,
    exchange            TEXT,
    sector              TEXT,
    industry            TEXT,
    shares_outstanding  REAL,
    listed_date         TEXT,
    delisted_date       TEXT,
    history_at          TEXT    -- UTC time the full daily history was last stored
);
CREATE TABLE IF NOT EXISTS index_membership (
    index_name  TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    start       TEXT NOT NULL,  -- '' = joined before the change log's coverage
    end         TEXT,           -- NULL = still a member
    PRIMARY KEY (index_name, symbol, start)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS price_daily (
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    adj_close   REAL,
    volume      REAL,
    PRIMARY KEY (symbol, date)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_price_daily_date ON price_daily (date);
CREATE TABLE IF NOT EXISTS corporate_action (
    symbol  TEXT NOT NULL,
    date    TEXT NOT NULL,
    type    TEXT NOT NULL,      -- 'dividend' | 'split'
    value   REAL,
    PRIMARY KEY (symbol, date, type)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS quote_latest (
    symbol      TEXT PRIMARY KEY,
    ts          INTEGER,        -- Yahoo regularMarketTime, epoch seconds
    price       REAL,
    change      REAL,
    change_pct  REAL,
    open        REAL,
    high        REAL,
    low         REAL,
    prev_close  REAL,
    volume      REAL,
    market_cap  REAL,
    shares      REAL,
    pe          REAL,
    forward_pe  REAL,
    eps_ttm     REAL,
    pb          REAL,
    div_yield   REAL,
    high52      REAL,
    low52       REAL,
    avg_vol_3m  REAL,
    avg_vol_10d REAL,
    market_state TEXT,
    source      TEXT,
    fetched_at  TEXT
);
CREATE TABLE IF NOT EXISTS quote_intraday (
    symbol  TEXT NOT NULL,
    ts      INTEGER NOT NULL,
    price   REAL,
    volume  REAL,
    PRIMARY KEY (symbol, ts)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS fundamental (
    symbol      TEXT NOT NULL,
    concept     TEXT NOT NULL,
    period_end  TEXT NOT NULL,
    filed       TEXT NOT NULL,  -- filing date: what was knowable when (point-in-time)
    value       REAL,
    unit        TEXT,
    form        TEXT,
    source      TEXT,
    PRIMARY KEY (symbol, concept, period_end, filed)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS macro_series (
    series      TEXT NOT NULL,
    country     TEXT NOT NULL,
    date        TEXT NOT NULL,
    value       REAL,
    source      TEXT,
    PRIMARY KEY (series, country, date)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS fx_daily (
    base    TEXT NOT NULL,
    quote   TEXT NOT NULL,
    date    TEXT NOT NULL,
    rate    REAL,
    PRIMARY KEY (base, quote, date)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS source_health (
    source          TEXT PRIMARY KEY,
    last_success    TEXT,
    last_error      TEXT,
    last_error_at   TEXT,
    failures        INTEGER DEFAULT 0,
    open_until      TEXT,           -- circuit breaker open until (UTC), NULL = closed
    day             TEXT,           -- UTC date that requests_today counts
    requests_today  INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fetch_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    key         TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 5,  -- lower runs first
    created_at  TEXT NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    UNIQUE (kind, key)
);
"""

# Columns prices() may read, so the field name can be interpolated safely.
PRICE_FIELDS = ("open", "high", "low", "close", "adj_close", "volume")


@contextlib.contextmanager
def connect() -> Iterator:
    """A DB-API connection from the app engine, committed on success."""
    conn = engine.raw_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    """Create the market-data tables. Idempotent (CREATE ... IF NOT EXISTS)."""
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert(table: str, rows: Sequence[dict], key: Sequence[str]) -> int:
    """Insert or update ``rows`` in one transaction. Returns the row count.

    ``table`` and the column names are this module's own constants, never user
    input. Every row must have the same keys as the first one.
    """
    if not rows:
        return 0
    cols = list(rows[0])
    updates = [c for c in cols if c not in key]
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
        f"ON CONFLICT ({', '.join(key)}) DO "
        + (f"UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in updates)}" if updates else "NOTHING")
    )
    with connect() as conn:
        conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)


def prices(symbols: Iterable[str], start: str | None = None, end: str | None = None,
           field: str = "adj_close") -> pd.DataFrame:
    """One ``price_daily`` column as a wide frame: DatetimeIndex x symbol.

    ``start``/``end`` are inclusive ISO dates. Symbols with no stored rows are
    left out, so callers can tell missing data from a flat price. Returns an
    empty frame when nothing is stored.
    """
    if field not in PRICE_FIELDS:
        raise ValueError(f"unknown price field {field!r}")
    syms = list(dict.fromkeys(symbols))
    if not syms:
        return pd.DataFrame()
    sql = (f"SELECT symbol, date, {field} FROM price_daily "
           f"WHERE symbol IN ({', '.join('?' * len(syms))})")
    params: list = list(syms)
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["symbol", "date", field])
    wide = df.pivot(index="date", columns="symbol", values=field)
    wide.index = pd.to_datetime(wide.index)
    wide.columns.name = None
    return wide[[s for s in syms if s in wide.columns]].sort_index()


def counts() -> dict[str, int]:
    """Row count per market-data table, for the Admin health panel."""
    tables = ("security", "price_daily", "quote_latest", "quote_intraday", "fundamental",
              "macro_series", "fx_daily", "fetch_queue")
    with connect() as conn:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
