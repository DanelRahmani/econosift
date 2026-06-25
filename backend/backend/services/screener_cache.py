"""SQLite persistence layer for the Phase 5 screener universe cache.

Stores one row per ticker per index-refresh cycle.  All reads/writes are
thread-safe via a module-level lock (WAL mode allows concurrent readers, but
we serialise writers to keep things simple).

The DB path defaults to ``backend/data/screener_cache.db`` (computed relative
to this file), but can be overridden via the ``SCREENER_DB_PATH`` environment
variable — used by tests to inject a tmp_path DB without touching the real one.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# DB path (overrideable for tests)
# ---------------------------------------------------------------------------

def _default_db_path() -> pathlib.Path:
    """backend/data/screener_cache.db, relative to this file."""
    return pathlib.Path(__file__).resolve().parents[2] / "data" / "screener_cache.db"


def _db_path() -> pathlib.Path:
    override = os.environ.get("SCREENER_DB_PATH")
    if override:
        return pathlib.Path(override)
    return _default_db_path()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol              TEXT PRIMARY KEY,
    name                TEXT,
    sector              TEXT,
    industry            TEXT,
    price               REAL,
    change_percent      REAL,
    market_cap          REAL,
    volume              REAL,
    avg_volume20d       REAL,
    volume_ratio        REAL,
    pe                  REAL,
    forward_pe          REAL,
    eps                 REAL,
    dividend_yield      REAL,
    beta                REAL,
    pb                  REAL,
    ev_ebitda           REAL,
    ev_fcf              REAL,
    fcf_yield           REAL,
    roic                REAL,
    ps_ratio            REAL,
    short_float         REAL,
    short_ratio         REAL,
    gross_margin        REAL,
    operating_margin    REAL,
    net_margin          REAL,
    roe                 REAL,
    roa                 REAL,
    debt_to_equity      REAL,
    current_ratio       REAL,
    revenue_growth      REAL,
    eps_growth          REAL,
    sma50               REAL,
    sma200              REAL,
    above_sma200        INTEGER,   -- 0/1/NULL (boolean)
    golden_cross        INTEGER,   -- 0/1/NULL (boolean)
    rsi14               REAL,
    high52              REAL,
    low52               REAL,
    pct_from_high       REAL,
    piotroski           REAL,
    altman_z            REAL,
    esg                 REAL,
    earnings_rev30d     REAL,
    spark_json          TEXT,      -- JSON array of floats
    macd                REAL,
    macd_signal         REAL,
    bb_pct_b            REAL,
    bb_squeeze          INTEGER,   -- 0/1/NULL (boolean)
    obv                 REAL,
    cmf20               REAL,
    ichimoku_bullish    INTEGER,   -- 0/1/NULL (boolean)
    obv_divergence      INTEGER,   -- 0/1/NULL (boolean)
    updated_at          TEXT       -- ISO-8601 UTC
);

CREATE TABLE IF NOT EXISTS shares (
    symbol              TEXT PRIMARY KEY,
    shares_outstanding  REAL,
    updated_at          TEXT
);
"""

# ---------------------------------------------------------------------------
# Module-level connection + lock
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_PHASE12_COLS = [
    ("macd",             "REAL"),
    ("macd_signal",      "REAL"),
    ("bb_pct_b",         "REAL"),
    ("bb_squeeze",       "INTEGER"),
    ("obv",              "REAL"),
    ("cmf20",            "REAL"),
    ("ichimoku_bullish", "INTEGER"),
    ("obv_divergence",   "INTEGER"),
]


def _migrate_phase12(conn: sqlite3.Connection) -> None:
    """Add Phase 12 columns if they do not already exist (idempotent)."""
    cur = conn.execute("PRAGMA table_info(fundamentals)")
    existing = {row[1] for row in cur.fetchall()}
    for col_name, col_type in _PHASE12_COLS:
        if col_name not in existing:
            try:
                conn.execute(f"ALTER TABLE fundamentals ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass


def _get_conn() -> sqlite3.Connection:
    """Return (and lazily initialise) the module-level connection."""
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        path = _db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_DDL)
        # Phase 12 migration: add new technical columns if they don't exist yet
        _migrate_phase12(conn)
        conn.commit()
        _conn = conn
    return _conn


def reset_connection() -> None:
    """Close and forget the module-level connection (used by tests)."""
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


# ---------------------------------------------------------------------------
# Column mapping helpers
# ---------------------------------------------------------------------------

# Map camelCase row key → DB column name (snake_case).
_COL: dict[str, str] = {
    "symbol":           "symbol",
    "name":             "name",
    "sector":           "sector",
    "industry":         "industry",
    "price":            "price",
    "changePercent":    "change_percent",
    "marketCap":        "market_cap",
    "volume":           "volume",
    "avgVolume20d":     "avg_volume20d",
    "volumeRatio":      "volume_ratio",
    "pe":               "pe",
    "forwardPE":        "forward_pe",
    "eps":              "eps",
    "dividendYield":    "dividend_yield",
    "beta":             "beta",
    "pb":               "pb",
    "evEbitda":         "ev_ebitda",
    "evFcf":            "ev_fcf",
    "fcfYield":         "fcf_yield",
    "roic":             "roic",
    "psRatio":          "ps_ratio",
    "shortFloat":       "short_float",
    "shortRatio":       "short_ratio",
    "grossMargin":      "gross_margin",
    "operatingMargin":  "operating_margin",
    "netMargin":        "net_margin",
    "roe":              "roe",
    "roa":              "roa",
    "debtToEquity":     "debt_to_equity",
    "currentRatio":     "current_ratio",
    "revenueGrowth":    "revenue_growth",
    "epsGrowth":        "eps_growth",
    "sma50":            "sma50",
    "sma200":           "sma200",
    "aboveSma200":      "above_sma200",
    "goldenCross":      "golden_cross",
    "rsi14":            "rsi14",
    "high52":           "high52",
    "low52":            "low52",
    "pctFromHigh":      "pct_from_high",
    "piotroski":        "piotroski",
    "altmanZ":          "altman_z",
    "esg":              "esg",
    "earningsRev30d":   "earnings_rev30d",
    "spark":            "spark_json",  # stored as JSON text
    "macd":             "macd",
    "macdSignal":       "macd_signal",
    "bbPctB":           "bb_pct_b",
    "bbSqueeze":        "bb_squeeze",
    "obv":              "obv",
    "cmf20":            "cmf20",
    "ichimokuBullish":  "ichimoku_bullish",
    "obvDivergence":    "obv_divergence",
    "updated_at":       "updated_at",
}

# Reverse map for reads: db_col → camelCase key
_CAMEL: dict[str, str] = {v: k for k, v in _COL.items() if k != "spark"}
# spark_json → spark handled specially

_BOOL_COLS = {"above_sma200", "golden_cross", "bb_squeeze", "ichimoku_bullish", "obv_divergence"}


def _clean_float(v: Any) -> float | None:
    """Convert to float, return None for NaN/Inf/None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public write functions
# ---------------------------------------------------------------------------

def upsert_rows(rows: list[dict]) -> None:
    """Insert or replace rows into the fundamentals table.

    Each dict uses camelCase keys matching the canonical row contract.
    Missing keys default to NULL.
    """
    if not rows:
        return
    conn = _get_conn()

    db_rows = []
    for row in rows:
        db_row: dict[str, Any] = {"updated_at": _now_iso()}
        for camel, col in _COL.items():
            if camel == "spark":
                spark = row.get("spark")
                db_row["spark_json"] = json.dumps(spark) if spark is not None else None
            elif camel == "updated_at":
                pass
            elif col in _BOOL_COLS:
                v = row.get(camel)
                db_row[col] = None if v is None else (1 if v else 0)
            else:
                db_row[col] = _clean_float(row.get(camel)) if camel not in ("symbol", "name", "sector", "industry") else row.get(camel)
        db_rows.append(db_row)

    cols = list(db_rows[0].keys())
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO fundamentals ({col_str}) VALUES ({placeholders})"

    with _lock:
        conn.executemany(sql, [[r[c] for c in cols] for r in db_rows])
        conn.commit()


def upsert_shares(shares: dict[str, float]) -> None:
    """Update the shares table with {symbol: shares_outstanding} data."""
    if not shares:
        return
    conn = _get_conn()
    now = _now_iso()
    rows = [(sym, float(so), now) for sym, so in shares.items() if so is not None]
    with _lock:
        conn.executemany(
            "INSERT OR REPLACE INTO shares (symbol, shares_outstanding, updated_at) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Public read functions
# ---------------------------------------------------------------------------

def get_rows(symbols: list[str]) -> list[dict]:
    """Return camelCase row dicts for the given symbols (those present in DB)."""
    if not symbols:
        return []
    conn = _get_conn()
    placeholders = ", ".join("?" * len(symbols))
    cur = conn.execute(
        f"SELECT * FROM fundamentals WHERE symbol IN ({placeholders})",
        symbols,
    )
    col_names = [d[0] for d in cur.description]
    rows = []
    for db_row in cur.fetchall():
        row_dict = dict(zip(col_names, db_row))
        out: dict[str, Any] = {}
        for col, val in row_dict.items():
            if col == "spark_json":
                try:
                    out["spark"] = json.loads(val) if val is not None else []
                except Exception:
                    out["spark"] = []
            elif col in _BOOL_COLS:
                out[_CAMEL.get(col, col)] = None if val is None else bool(val)
            elif col == "updated_at":
                out["updated_at"] = val
            elif col in ("symbol", "name", "sector", "industry"):
                out[_CAMEL.get(col, col)] = val
            else:
                out[_CAMEL.get(col, col)] = _clean_float(val)
        rows.append(out)
    return rows


def get_shares(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: shares_outstanding} for symbols present in the shares table."""
    if not symbols:
        return {}
    conn = _get_conn()
    placeholders = ", ".join("?" * len(symbols))
    cur = conn.execute(
        f"SELECT symbol, shares_outstanding FROM shares WHERE symbol IN ({placeholders})",
        symbols,
    )
    return {row[0]: float(row[1]) for row in cur.fetchall() if row[1] is not None}


def last_refresh(symbols: list[str]) -> str | None:
    """Return the ISO timestamp of the most-recently updated row among symbols.

    Returns None if no rows are present.
    """
    if not symbols:
        return None
    conn = _get_conn()
    placeholders = ", ".join("?" * len(symbols))
    cur = conn.execute(
        f"SELECT MAX(updated_at) FROM fundamentals WHERE symbol IN ({placeholders})",
        symbols,
    )
    row = cur.fetchone()
    return row[0] if row else None


def is_stale(symbols: list[str], max_age_h: float = 24.0) -> bool:
    """Return True if any symbol is missing from the DB or the oldest row is stale.

    Stale means: oldest ``updated_at`` among present rows is older than
    ``max_age_h`` hours, OR at least one symbol is not present at all.
    """
    if not symbols:
        return False
    conn = _get_conn()
    placeholders = ", ".join("?" * len(symbols))
    cur = conn.execute(
        f"SELECT symbol, updated_at FROM fundamentals WHERE symbol IN ({placeholders})",
        symbols,
    )
    rows = cur.fetchall()

    # Any missing symbol → stale
    found_syms = {r[0] for r in rows}
    if len(found_syms) < len(symbols):
        return True

    # Oldest row older than max_age_h → stale
    now = datetime.now(timezone.utc)
    for _, ts in rows:
        try:
            row_dt = datetime.fromisoformat(ts)
            if row_dt.tzinfo is None:
                row_dt = row_dt.replace(tzinfo=timezone.utc)
            age_h = (now - row_dt).total_seconds() / 3600.0
            if age_h > max_age_h:
                return True
        except Exception:
            return True  # unparseable timestamp → treat as stale

    return False


def row_count(symbols: list[str]) -> int:
    """Return how many of the requested symbols are present in fundamentals."""
    if not symbols:
        return 0
    conn = _get_conn()
    placeholders = ", ".join("?" * len(symbols))
    cur = conn.execute(
        f"SELECT COUNT(*) FROM fundamentals WHERE symbol IN ({placeholders})",
        symbols,
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0
