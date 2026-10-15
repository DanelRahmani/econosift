"""Market-data tables in econosift.db and the helpers that read and write them.

Phase 66: the fetcher thread is the only writer of these tables; API requests
only read them. Writes are batched (`executemany` in one transaction) instead
of one ORM `merge()` per row, which ran a SELECT before every insert.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime, timezone

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
    fetched_at  TEXT,
    currency    TEXT,
    name        TEXT
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
    concept     TEXT NOT NULL,  -- statement label; '|Q' suffix = one fiscal quarter (sec_fundamentals)
    period_end  TEXT NOT NULL,
    filed       TEXT NOT NULL,  -- filing date: what was knowable when (point-in-time)
    value       REAL,
    unit        TEXT,
    form        TEXT,
    source      TEXT,
    PRIMARY KEY (symbol, concept, period_end, filed)
) WITHOUT ROWID;
-- Filings behind the stored SEC facts, so the nightly frames check can spot a new one.
CREATE TABLE IF NOT EXISTS sec_filing (
    cik     TEXT NOT NULL,
    accn    TEXT NOT NULL,
    filed   TEXT,
    form    TEXT,
    PRIMARY KEY (cik, accn)
) WITHOUT ROWID;
-- Per company, the last two annual columns of each statement as JSON (fundamentals_store):
-- the 500-company pages (DuPont, earnings quality) read these instead of every fact.
CREATE TABLE IF NOT EXISTS fundamental_summary (
    symbol      TEXT PRIMARY KEY,
    summary     TEXT NOT NULL,
    built_at    TEXT NOT NULL
);
-- Yahoo-only data SEC lacks, as JSON per symbol (yahoo_info.py): 'info' = Ticker.info
-- (estimates, targets, profile; weekly rotation), 'analyst' = the analyst panel (on demand).
CREATE TABLE IF NOT EXISTS yahoo_doc (
    kind        TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    doc         TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (kind, symbol)
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
-- SEC quarterly data sets (Form 3/4/5 insider trades, Form 13F), reduced on download.
CREATE TABLE IF NOT EXISTS sec_dataset (
    name        TEXT NOT NULL,      -- 'form345' | 'form13f'
    period_key  TEXT NOT NULL,      -- quarter ('2026q2') or filing window ('01mar2026-31may2026')
    period      TEXT,               -- 13F: the quarter-end the holdings are reported for
    format      INTEGER,            -- reduce_dataset version that built it
    url         TEXT,
    built_at    TEXT,
    PRIMARY KEY (name, period_key)
);
CREATE TABLE IF NOT EXISTS insider_trade (
    quarter       TEXT NOT NULL,
    accession     TEXT NOT NULL,
    sk            TEXT NOT NULL,
    symbols       TEXT,
    insider_name  TEXT,
    title         TEXT,
    code          TEXT,
    shares        REAL,
    price         REAL,
    date          TEXT,
    PRIMARY KEY (quarter, accession, sk)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS thirteenf_holder (
    filing_window TEXT NOT NULL,
    cusip         TEXT NOT NULL,
    rank          INTEGER NOT NULL,
    cik           TEXT,
    manager       TEXT,
    shares        REAL,
    value         REAL,
    PRIMARY KEY (filing_window, cusip, rank)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS thirteenf_total (
    filing_window TEXT NOT NULL,
    cusip         TEXT NOT NULL,
    filers        INTEGER,
    shares        REAL,
    value         REAL,
    PRIMARY KEY (filing_window, cusip)
) WITHOUT ROWID;
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


# Columns added after a table was first created; CREATE TABLE IF NOT EXISTS
# does not add them to a database built by an earlier version.
_ADDED_COLUMNS = {"quote_latest": {"currency": "TEXT", "name": "TEXT"},
                  "security": {"facts_at": "TEXT"}}  # UTC time SEC companyfacts were last stored


def init_schema() -> None:
    """Create the market-data tables. Idempotent (CREATE ... IF NOT EXISTS)."""
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, cols in _ADDED_COLUMNS.items():
            have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col, ddl in cols.items():
                if col not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


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


def replace_fundamentals(symbols: Sequence[str], rows: Sequence[dict], source_prefix: str) -> int:
    """Replace one source's ``fundamental`` rows for ``symbols`` with ``rows``.

    A companyfacts document is a company's full history, so stored rows it no
    longer has go too. Delete and insert share one transaction. An empty
    ``rows`` changes nothing (never replace stored data with an empty result).
    """
    if not rows or not symbols:
        return 0
    cols = ("symbol", "concept", "period_end", "filed", "value", "unit", "form", "source")
    with connect() as conn:
        conn.executemany("DELETE FROM fundamental WHERE symbol = ? AND source LIKE ?",
                         [(s, source_prefix + "%") for s in symbols])
        conn.executemany(
            f"INSERT OR REPLACE INTO fundamental ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [tuple(r[c] for c in cols) for r in rows])
    return len(rows)


def frames(symbols: Iterable[str], fields: Sequence[str], start: str | None = None,
           end: str | None = None) -> dict[str, pd.DataFrame]:
    """Several ``price_daily`` columns from one query, each a wide frame:
    DatetimeIndex x symbol. ``start``/``end`` are inclusive ISO dates.

    Symbols with no stored rows are left out, so callers can tell missing data
    from a flat price. Every frame is empty when nothing is stored.
    """
    bad = [f for f in fields if f not in PRICE_FIELDS]
    if bad:
        raise ValueError(f"unknown price field {bad[0]!r}")
    syms = list(dict.fromkeys(symbols))
    if not syms:
        return {f: pd.DataFrame() for f in fields}
    sql = (f"SELECT symbol, date, {', '.join(fields)} FROM price_daily "
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
        return {f: pd.DataFrame() for f in fields}
    df = pd.DataFrame(rows, columns=["symbol", "date", *fields])
    df["date"] = pd.to_datetime(df["date"])
    wide = df.set_index(["date", "symbol"]).unstack("symbol").sort_index()  # one reshape for all fields
    wide.index.name = None
    cols = [s for s in syms if s in wide.columns.get_level_values("symbol")]
    out = {}
    for f in fields:
        frame = wide[f][cols]
        frame.columns.name = None
        out[f] = frame
    return out


def prices(symbols: Iterable[str], start: str | None = None, end: str | None = None,
           field: str = "adj_close") -> pd.DataFrame:
    """One ``price_daily`` column as a wide frame (see :func:`frames`)."""
    return frames(symbols, (field,), start, end)[field]


def quotes(symbols: Iterable[str]) -> dict[str, dict]:
    """``quote_latest`` rows by symbol, for the symbols that have one."""
    syms = list(dict.fromkeys(symbols))
    if not syms:
        return {}
    with connect() as conn:
        cur = conn.execute(f"SELECT * FROM quote_latest WHERE symbol IN ({', '.join('?' * len(syms))})", syms)
        cols = [d[0] for d in cur.description]
        return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}


def records(df: pd.DataFrame, cols: Sequence[str]) -> list[tuple]:
    """``df[cols]`` as tuples of plain Python values (NaN -> None) for executemany."""
    part = df[list(cols)].astype(object)
    return [tuple(r) for r in part.where(part.notna(), None).values.tolist()]


def counts() -> dict[str, int]:
    """Row count per market-data table, for the Admin health panel."""
    tables = ("security", "price_daily", "quote_latest", "quote_intraday", "fundamental",
              "sec_filing", "fundamental_summary", "macro_series", "fx_daily", "fetch_queue")
    with connect() as conn:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}

# Series periods are stored as each source publishes them: 'YYYY' (annual),
# 'YYYY-MM' (monthly), 'YYYY-Qn' (quarterly) or an ISO date (daily).

def replace_series(series: str, rows: Sequence[tuple[str, str, float]], source: str) -> int:
    """Replace one full ``macro_series`` dataset with ``(country, date, value)`` rows.

    A bulk download is the whole dataset, so points the source has since
    dropped go too. The delete, the insert and the stored-at stamp share one
    transaction: a reader never sees the series half-written.
    """
    if not rows:
        return 0  # never replace stored data with an empty download
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connect() as conn:
        conn.execute("DELETE FROM macro_series WHERE series = ?", (series,))
        conn.executemany(
            "INSERT OR REPLACE INTO macro_series (series, country, date, value, source) VALUES (?, ?, ?, ?, ?)",
            [(series, c, d, v, source) for c, d, v in rows])
        conn.execute(
            "INSERT INTO source_health (source, last_success) VALUES (?, ?) "
            "ON CONFLICT (source) DO UPDATE SET last_success = excluded.last_success",
            (f"series:{series}", now))
    return len(rows)


def series_stored_at(series: str) -> str | None:
    """UTC time ``series`` was last stored, or None if it never was."""
    with connect() as conn:
        row = conn.execute("SELECT last_success FROM source_health WHERE source = ?",
                           (f"series:{series}",)).fetchone()
    return row[0] if row else None


def read_series(series: str, countries: Iterable[str] | None = None) -> pd.DataFrame:
    """``macro_series`` rows as a frame with columns country, date, value."""
    sql = "SELECT country, date, value FROM macro_series WHERE series = ?"
    params: list = [series]
    if countries is not None:
        cs = list(countries)
        if not cs:
            return pd.DataFrame(columns=["country", "date", "value"])
        sql += f" AND country IN ({', '.join('?' * len(cs))})"
        params += cs
    with connect() as conn:
        rows = conn.execute(sql + " ORDER BY country, date", params).fetchall()
    return pd.DataFrame(rows, columns=["country", "date", "value"])
