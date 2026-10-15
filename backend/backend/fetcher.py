"""The fetcher: one background thread that fills econosift.db (Phase 66).

Work is a persisted queue (`fetch_queue`), so a restart resumes where it
stopped instead of starting over: the first-ever start backfills the full
daily history of every tracked symbol once, later starts find it stored.
Every Yahoo call still passes the per-endpoint token buckets and circuit
breakers in `rate_limit`, and runs in the bulk lane so a page's own request
is served first.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from yfinance.exceptions import YFRateLimitError

from . import rate_limit, store

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3        # a task that failed this often stays in the queue as failed
IDLE_WAIT = 5.0         # seconds to sleep when the queue is empty
HEALTH_EVERY = 60.0     # seconds between request-log updates while idle (pages call Yahoo too)
UNIVERSE_MAX_AGE = timedelta(days=7)
INDEXES = ("sp500", "ndx", "dow")

# Priorities: lower runs first.
PRIORITY_SNAPSHOT = 0
PRIORITY_UNIVERSE = 1
PRIORITY_REFETCH = 2    # history whose stored closes no longer match (a split)
PRIORITY_ON_DEMAND = 3  # a symbol a page asked for that is not stored yet
PRIORITY_FACTS = 4      # SEC companyfacts (backfill and changed filers)
PRIORITY_HISTORY = 5

# Index levels the dashboard shows intraday; yf.screen covers equities only,
# so these are filled by chart calls in every snapshot (4 calls a run).
INTRADAY_EXTRAS = {"^GSPC": "S&P 500", "^NDX": "Nasdaq 100", "^DJI": "Dow Jones Industrial Average",
                   "^VIX": "CBOE Volatility Index"}

# Page caches built from the store's intraday data: a snapshot clears them so
# pages show the new quotes instead of an hour-old computation.
SNAPSHOT_CACHES = ("treemap", "movers", "indices", "feargreed", "breadth", "sector_returns", "yf_info")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

def enqueue(kind: str, key: str, priority: int = PRIORITY_HISTORY, retry_failed: bool = True) -> None:
    """Queue a task once; a task already queued keeps its place. A failed one is
    retried only with ``retry_failed``, so pages asking for a symbol Yahoo
    doesn't have never re-trigger its fetch."""
    reset = "attempts = 0, last_error = NULL, " if retry_failed else ""
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO fetch_queue (kind, key, priority, created_at) VALUES (?, ?, ?, ?) "
            f"ON CONFLICT (kind, key) DO UPDATE SET {reset}priority = MIN(priority, excluded.priority)",
            (kind, key, priority, _now()),
        )
    _wake.set()


def request_history(symbols) -> list[str]:
    """Queue history for requested symbols that aren't stored; returns the ones
    still pending. A symbol whose fetch already failed (Yahoo has no data, e.g.
    a delisted former member) is known-missing, not pending.

    Called on the read path: it only writes the queue, never calls a source.
    """
    syms = list(dict.fromkeys(symbols))
    if not syms:
        return []
    marks = ", ".join("?" * len(syms))
    with store.connect() as conn:
        have = {r[0] for r in conn.execute(
            f"SELECT symbol FROM security WHERE history_at IS NOT NULL AND symbol IN ({marks})", syms)}
        failed = {r[0] for r in conn.execute(
            f"SELECT key FROM fetch_queue WHERE kind = 'history' AND attempts >= ? AND key IN ({marks})",
            (MAX_ATTEMPTS, *syms))}
    missing = [s for s in syms if s not in have and s not in failed]
    for sym in missing:
        enqueue("history", sym, PRIORITY_ON_DEMAND, retry_failed=False)
    return missing


def request_yahoo_info(symbols) -> list[str]:
    """Queue Yahoo's company fields for requested symbols that have none stored;
    returns the ones still pending (a symbol whose fetch failed is not pending).
    Read path: writes the queue only."""
    from . import yahoo_info

    syms = list(dict.fromkeys(symbols))
    if not syms:
        return []
    have = yahoo_info.stored(syms)
    marks = ", ".join("?" * len(syms))
    with store.connect() as conn:
        failed = {r[0] for r in conn.execute(
            f"SELECT key FROM fetch_queue WHERE kind = 'yahoo_info' AND attempts >= ? AND key IN ({marks})",
            (MAX_ATTEMPTS, *syms))}
    missing = [s for s in syms if s not in have and s not in failed]
    for sym in missing:
        enqueue("yahoo_info", sym, PRIORITY_ON_DEMAND, retry_failed=False)
    return missing


def _next_task() -> tuple[int, str, str] | None:
    with store.connect() as conn:
        return conn.execute(
            "SELECT id, kind, key FROM fetch_queue WHERE attempts < ? ORDER BY priority, id LIMIT 1",
            (MAX_ATTEMPTS,),
        ).fetchone()


def _finish(task_id: int) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM fetch_queue WHERE id = ?", (task_id,))


def _fail(task_id: int, error: str) -> None:
    with store.connect() as conn:
        conn.execute(
            "UPDATE fetch_queue SET attempts = attempts + 1, last_error = ? WHERE id = ?",
            (error[:500], task_id),
        )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def membership_intervals(current: list[str], changes: list[dict]) -> list[tuple[str, str, str | None]]:
    """(symbol, start, end) intervals from today's roster and a newest-first change log.

    Walking back from today: a current member is in until NULL; a change that
    removed a symbol means it was in until that date; a change that added it
    is where that interval starts. An interval with no add in the log starts
    at '' (before the log's coverage).
    """
    open_end: dict[str, str | None] = {s: None for s in current}
    out: list[tuple[str, str, str | None]] = []
    for ch in changes:  # newest first
        day = ch["date"].isoformat()
        added, removed = ch.get("added"), ch.get("removed")
        if added and added in open_end:
            out.append((added, day, open_end.pop(added)))
        if removed:
            open_end[removed] = day
    out.extend((s, "", end) for s, end in open_end.items())
    return out


def run_universe(_key: str) -> int:
    """Store index rosters and membership, then queue history for symbols without it."""
    from .services import constituents

    securities: dict[str, dict] = {}
    membership: list[dict] = []
    for index in INDEXES:
        members = constituents.get_constituents(index, live=True)
        if not members:
            raise RuntimeError(f"no constituents for {index}")
        for m in members:
            securities.setdefault(m["symbol"], dict(
                symbol=m["symbol"], name=m.get("name"), sector=m.get("sector"),
                industry=m.get("industry")))
        changes = constituents.get_membership_changes(index, live=True)
        for sym, start, end in membership_intervals([m["symbol"] for m in members], changes):
            membership.append(dict(index_name=index, symbol=sym, start=start, end=end))

    for sym, name in INTRADAY_EXTRAS.items():
        securities.setdefault(sym, dict(symbol=sym, name=name, sector=None, industry=None))
    store.upsert("security", list(securities.values()), ("symbol",))
    with store.connect() as conn:
        conn.execute("DELETE FROM index_membership")
    store.upsert("index_membership", membership, ("index_name", "symbol", "start"))
    _mark_success("constituents")
    queue_ciks()  # new members need their CIK for SEC fundamentals

    with store.connect() as conn:
        missing = [r[0] for r in conn.execute(
            "SELECT symbol FROM security WHERE history_at IS NULL ORDER BY symbol")]
    for sym in missing:
        enqueue("history", sym, PRIORITY_HISTORY)
    return len(securities)


def run_history(symbol: str) -> int:
    """Store a symbol's full daily history (raw + adjusted close) and its splits/dividends."""
    import yfinance as yf

    df = yf.Ticker(symbol).history(period="max", auto_adjust=False, actions=True)
    if df is None or df.empty:
        raise RuntimeError(f"no history for {symbol}")  # never store an empty result

    def num(row, col):
        v = row.get(col)
        return None if v is None or v != v else float(v)

    bars, actions = [], []
    for ts, row in df.iterrows():
        day = ts.date().isoformat()
        bars.append(dict(symbol=symbol, date=day, open=num(row, "Open"), high=num(row, "High"),
                         low=num(row, "Low"), close=num(row, "Close"),
                         adj_close=num(row, "Adj Close"), volume=num(row, "Volume")))
        for col, kind in (("Dividends", "dividend"), ("Stock Splits", "split")):
            v = num(row, col)
            if v:
                actions.append(dict(symbol=symbol, date=day, type=kind, value=v))
    store.upsert("price_daily", bars, ("symbol", "date"))
    store.upsert("corporate_action", actions, ("symbol", "date", "type"))
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO security (symbol, history_at) VALUES (?, ?) "
            "ON CONFLICT (symbol) DO UPDATE SET history_at = excluded.history_at",
            (symbol, _now()))
    return len(bars)


def run_ciks(_key: str) -> int:
    """Map every stored security to its SEC CIK (``company_tickers.json``, one request)."""
    from .sources import source_sec

    ciks = source_sec.ticker_ciks()
    if not ciks:
        raise RuntimeError("SEC company_tickers.json returned no tickers")  # never store an empty result
    with store.connect() as conn:
        syms = [r[0] for r in conn.execute("SELECT symbol FROM security")]
        rows = [(ciks[s], s) for s in syms if s in ciks]
        conn.executemany("UPDATE security SET cik = ? WHERE symbol = ?", rows)
    _mark_success("sec_ciks")
    queue_facts_backfill()
    return len(rows)


def run_facts(cik: str) -> int:
    """Store one company's SEC companyfacts (every symbol sharing the CIK) into `fundamental`."""
    from . import cache, sec_fundamentals
    from .sources import source_sec

    with store.connect() as conn:
        syms = [r[0] for r in conn.execute("SELECT symbol FROM security WHERE cik = ? ORDER BY symbol", (cik,))]
    if not syms:
        return 0  # no tracked symbol has this CIK any more
    doc = source_sec.companyfacts(cik)
    rows = [r for s in syms for r in sec_fundamentals.rows(doc or {}, s)]
    if not rows:
        raise RuntimeError(f"no usable SEC facts for CIK {cik}")  # e.g. an IFRS filer; Yahoo fills in
    store.replace_fundamentals(syms, rows, "sec:")
    store.upsert("sec_filing", [dict(cik=cik, accn=a, filed=f, form=fm)
                                for a, (f, fm) in sec_fundamentals.filings(doc).items()], ("cik", "accn"))
    with store.connect() as conn:
        conn.executemany("UPDATE security SET facts_at = ? WHERE symbol = ?", [(_now(), s) for s in syms])
    _mark_success("sec_facts")
    cache.clear_all("yf_info")  # bundles built before these facts were stored
    return len(rows)


def run_frames(day: str) -> int:
    """Nightly: ~10 SEC frames calls; queue companyfacts for every tracked CIK
    that has filed something not stored yet. Returns the number queued."""
    from datetime import date
    from . import sec_fundamentals
    from .sources import source_sec

    with store.connect() as conn:
        tracked = {r[0] for r in conn.execute("SELECT DISTINCT cik FROM security WHERE cik IS NOT NULL")}
        known = set(conn.execute("SELECT cik, accn FROM sec_filing"))
    changed: set[str] = set()
    answered = 0
    for call in sec_fundamentals.frame_calls(date.fromisoformat(day)):
        doc = source_sec.frame(*call)
        if doc is None:
            continue  # a frame with no filings yet
        answered += 1
        for row in doc.get("data") or []:
            if row.get("cik") is None or not row.get("accn"):
                continue
            cik = source_sec.cik10(row["cik"])
            if cik in tracked and (cik, row["accn"]) not in known:
                changed.add(cik)
    if not answered:
        raise RuntimeError("no SEC frame answered")
    for cik in sorted(changed):
        enqueue("facts", cik, PRIORITY_FACTS)
    _mark_success("sec_frames")
    return len(changed)


def run_yahoo_info(symbol: str) -> int:
    from . import cache, yahoo_info
    rows = yahoo_info.fetch(symbol)
    cache.clear_all("yf_info")
    return rows


def run_analyst(symbol: str) -> int:
    """Store the Markets analyst panel (targets, ratings, surprises, estimates) for one symbol."""
    from . import yahoo_info
    from .services import analyst_service

    doc = analyst_service.fetch_analyst(symbol)
    if not analyst_service.has_data(doc):
        raise RuntimeError(f"Yahoo returned no analyst data for {symbol}")  # never store an empty result
    yahoo_info.put("analyst", symbol, doc)
    return 1


def run_snapshot(key: str) -> int:
    from . import cache, snapshot
    rows = snapshot.run(key)
    for name in SNAPSHOT_CACHES:
        cache.clear_all(name)
    return rows


HANDLERS: dict[str, Callable[[str], int]] = {
    "universe": run_universe,
    "history": run_history,
    "snapshot": run_snapshot,
    "ciks": run_ciks,
    "facts": run_facts,
    "frames": run_frames,
    "yahoo_info": run_yahoo_info,
    "analyst": run_analyst,
}


# ---------------------------------------------------------------------------
# Scheduled entry points (APScheduler only enqueues; this thread does the calls)
# ---------------------------------------------------------------------------

def queue_history_rotation(today: datetime | None = None) -> None:
    """Re-fetch a fifth of the universe's history each weekday, so every symbol
    gets fresh adjusted closes (dividends, splits) once a week."""
    day = (today or datetime.now(timezone.utc)).weekday()
    if day > 4:
        return
    with store.connect() as conn:
        syms = [r[0] for r in conn.execute(
            "SELECT symbol FROM security WHERE history_at IS NOT NULL ORDER BY symbol")]
    for sym in syms[day::5]:
        enqueue("history", sym, PRIORITY_HISTORY)


def queue_universe() -> None:
    enqueue("universe", "all", PRIORITY_UNIVERSE)


def sec_enabled() -> bool:
    from .sources import source_sec
    return source_sec.identity() is not None


def queue_facts_backfill() -> None:
    """Queue companyfacts for every CIK not stored yet (resumable: stored ones are skipped).
    A CIK whose fetch failed (no XBRL facts) is not retried until something re-queues it."""
    with store.connect() as conn:
        ciks = [r[0] for r in conn.execute(
            "SELECT DISTINCT cik FROM security WHERE cik IS NOT NULL AND facts_at IS NULL ORDER BY cik")]
    for cik in ciks:
        enqueue("facts", cik, PRIORITY_FACTS, retry_failed=False)


def queue_yahoo_rotation() -> None:
    """Daily: refresh Yahoo's company fields for the ~75 symbols stored longest ago
    (plus the sector ETFs when they are due), so every one is refreshed weekly."""
    from . import yahoo_info
    from .services.sector_service import SECTOR_ETFS

    for sym in yahoo_info.rotation(extra=tuple(SECTOR_ETFS)):
        enqueue("yahoo_info", sym, PRIORITY_HISTORY)


def queue_frames(today: datetime | None = None) -> None:
    """Nightly: check SEC frames for new filings (skipped without an EDGAR identity)."""
    if sec_enabled():
        day = (today or datetime.now(timezone.utc)).date().isoformat()
        enqueue("frames", day, PRIORITY_FACTS)


def queue_ciks() -> None:
    """Refresh the ticker -> CIK map; skipped without an EDGAR identity (Admin says so)."""
    if sec_enabled():
        enqueue("ciks", "all", PRIORITY_UNIVERSE)


def queue_snapshot(now: datetime | None = None) -> None:
    """Every 15 min: queue a snapshot while the US market is open."""
    from .snapshot import in_market_hours
    if in_market_hours(now):
        enqueue("snapshot", "intraday", PRIORITY_SNAPSHOT)


def queue_close_snapshot() -> None:
    """After the close: a snapshot that also writes today's daily bar."""
    enqueue("snapshot", "close", PRIORITY_SNAPSHOT)


# ---------------------------------------------------------------------------
# Bookkeeping: source_health
# ---------------------------------------------------------------------------

_seen_requests: dict[str, int] = {}


def _mark_success(source: str) -> None:
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO source_health (source, last_success) VALUES (?, ?) "
            "ON CONFLICT (source) DO UPDATE SET last_success = excluded.last_success",
            (source, _now()))


def _last_success(source: str) -> datetime | None:
    with store.connect() as conn:
        row = conn.execute("SELECT last_success FROM source_health WHERE source = ?",
                           (source,)).fetchone()
    return datetime.fromisoformat(row[0].replace("Z", "+00:00")) if row and row[0] else None


def record_source_health() -> None:
    """Persist each Yahoo bucket's request count for today, circuit state and last error.

    Counts every Yahoo request the process made (pages included), so Admin has
    one daily request log to check the budget against.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc)
    for name, st in rate_limit.status().items():
        delta = st["requests"] - _seen_requests.get(name, 0)
        _seen_requests[name] = st["requests"]
        failures = st["consecutiveErrors"] + st["consecutive429"]
        open_until = None
        if st["state"] == "open":
            open_until = (now + timedelta(seconds=st["openForSeconds"])).strftime("%Y-%m-%dT%H:%M:%SZ")
        stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        with store.connect() as conn:
            conn.execute(
                "INSERT INTO source_health (source, day, requests_today, failures, open_until, "
                "last_error, last_error_at, last_success) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (source) DO UPDATE SET "
                "requests_today = CASE WHEN day = excluded.day "
                "  THEN requests_today + excluded.requests_today ELSE excluded.requests_today END, "
                "day = excluded.day, failures = excluded.failures, open_until = excluded.open_until, "
                "last_error = COALESCE(excluded.last_error, last_error), "
                "last_error_at = COALESCE(excluded.last_error_at, last_error_at), "
                "last_success = COALESCE(excluded.last_success, last_success)",
                (name, today, delta, failures, open_until, st["lastError"] if failures else None,
                 stamp if failures else None, stamp if delta and not failures else None),
            )


# ---------------------------------------------------------------------------
# The thread
# ---------------------------------------------------------------------------

_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None
_current: str | None = None


def run_one() -> bool:
    """Run the next queued task. Returns False when the queue is empty."""
    global _current
    task = _next_task()
    if task is None:
        return False
    task_id, kind, key = task
    handler = HANDLERS.get(kind)
    if handler is None:
        _fail(task_id, f"unknown task kind {kind!r}")
        return True
    _current = f"{kind}:{key}"
    try:
        with rate_limit.bulk():
            rows = handler(key)
        _finish(task_id)
        record_source_health()
        logger.info("fetcher: %s %s -> %d rows", kind, key, rows)
    except YFRateLimitError:
        # A circuit (Yahoo or SEC) is open: wait it out without spending the task's attempts.
        record_source_health()
        wait = max((st["openForSeconds"] for st in rate_limit.status().values()), default=30.0)
        logger.warning("fetcher: %s rate-limited; pausing %.0f s", kind, wait)
        _stop.wait(max(wait, 1.0))
    except Exception as exc:
        _fail(task_id, f"{type(exc).__name__}: {exc}")
        record_source_health()
        logger.warning("fetcher: %s %s failed: %s", kind, key, exc)
    finally:
        _current = None
    return True


def _loop(start_delay: float) -> None:
    if _stop.wait(start_delay):
        return
    universe_at = _last_success("constituents")
    if universe_at is None or datetime.now(timezone.utc) - universe_at > UNIVERSE_MAX_AGE:
        queue_universe()
    ciks_at = _last_success("sec_ciks")
    if ciks_at is None or datetime.now(timezone.utc) - ciks_at > UNIVERSE_MAX_AGE:
        queue_ciks()
    logged = time.monotonic()
    while not _stop.is_set():
        try:
            busy = run_one()
            if not busy and time.monotonic() - logged > HEALTH_EVERY:
                record_source_health()
                logged = time.monotonic()
        except Exception as exc:  # the DB itself failed; don't spin
            logger.error("fetcher loop error: %s", exc)
            busy = False
        if not busy:
            _wake.wait(IDLE_WAIT)
            _wake.clear()


def start(start_delay: float) -> threading.Thread:
    """Start the fetcher thread once."""
    global _thread
    if _thread is None or not _thread.is_alive():
        _stop.clear()
        _thread = threading.Thread(target=_loop, args=(start_delay,), name="fetcher", daemon=True)
        _thread.start()
    return _thread


def stop() -> None:
    _stop.set()
    _wake.set()


def status() -> dict:
    """Backfill progress and queue state, for Admin."""
    with store.connect() as conn:
        total, done = conn.execute(
            "SELECT COUNT(*), COUNT(history_at) FROM security").fetchone()
        pending, failed = conn.execute(
            "SELECT COALESCE(SUM(attempts < ?), 0), COALESCE(SUM(attempts >= ?), 0) FROM fetch_queue",
            (MAX_ATTEMPTS, MAX_ATTEMPTS)).fetchone()
        errors = [dict(kind=k, key=key, error=e) for k, key, e in conn.execute(
            "SELECT kind, key, last_error FROM fetch_queue WHERE attempts >= ? ORDER BY id LIMIT 20",
            (MAX_ATTEMPTS,))]
        health = [dict(source=r[0], day=r[1], requestsToday=r[2], lastSuccess=r[3],
                       lastError=r[4], openUntil=r[5]) for r in conn.execute(
            "SELECT source, day, requests_today, last_success, last_error, open_until "
            "FROM source_health WHERE source NOT LIKE 'series:%' ORDER BY source")]
    return {
        "running": _thread is not None and _thread.is_alive(),
        "current": _current,
        "backfill": {"total": total, "done": done},
        "queue": {"pending": pending, "failed": failed, "errors": errors},
        "universeAt": next((h["lastSuccess"] for h in health if h["source"] == "constituents"), None),
        "sources": health,
        "sec": sec_status(),
    }


def sec_status() -> dict:
    """SEC fundamentals for Admin: whether an EDGAR identity is set, and CIK coverage."""
    with store.connect() as conn:
        ciks, total, done = conn.execute(
            "SELECT COUNT(cik), COUNT(DISTINCT cik), COUNT(DISTINCT CASE WHEN facts_at IS NOT NULL THEN cik END) "
            "FROM security").fetchone()
        stamps = dict(conn.execute(
            "SELECT source, last_success FROM source_health WHERE source IN ('sec_ciks', 'sec_facts', 'sec_frames')"))
    return {"identity": sec_enabled(), "ciks": ciks, "ciksAt": stamps.get("sec_ciks"),
            "framesAt": stamps.get("sec_frames"),
            "facts": {"total": total, "done": done, "lastAt": stamps.get("sec_facts")}}
