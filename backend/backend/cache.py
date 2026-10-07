"""Shared TTL caching helpers for external data calls."""
from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import logging
import threading
import time
import weakref
from datetime import datetime, timezone
from cachetools import TTLCache

log = logging.getLogger(__name__)

# 60-minute cache for external API responses.
_CACHE_TTL = 60 * 60
_CACHE_MAXSIZE = 2048
# Stale-while-revalidate: a persisted entry past its TTL but younger than this
# is served at once while a background call refreshes it.
_STALE_MAX = 24 * 60 * 60
# After a failed background refresh, keep serving the stale entry this long
# before trying again, so a down source is not hit on every request.
_REFRESH_RETRY = 5 * 60
# A value computed from a stale input is rebuilt after this long, by when the
# input's own refresh has usually landed.
_STALE_INPUT_RETRY = 60
# A refresh request (P1-20) recomputes an entry only if it is older than this,
# so repeated clicks and concurrent endpoints sharing an input hit the source once.
_REFRESH_MIN_AGE = 60

def _utcnow() -> datetime:
    """Naive UTC now — matches CacheEntry.created_at, which is stored naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_caches: dict[str, TTLCache] = {}


class _ThreadLock:
    """threading.Lock that can be weakly referenced (the C lock cannot)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __enter__(self) -> "_ThreadLock":
        self._lock.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self._lock.release()


class _KeyLocks:
    """Single-flight locks per (cache name, key).

    A lock per *function* would make every cold call to that function wait for
    whichever call is in flight, whatever its arguments — on a cold start that
    queued all FRED and World Bank fetches app-wide behind one another. A lock
    lives only while someone holds it, so the registry does not grow.
    """

    def __init__(self, factory) -> None:
        self._factory = factory
        self._locks: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._guard = threading.Lock()

    def get(self, key):
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = self._factory()
                self._locks[key] = lock
            return lock


_locks = _KeyLocks(asyncio.Lock)
_sync_locks = _KeyLocks(_ThreadLock)

# Registry of live HybridCache instances so clear_all() can flush their
# private in-memory tier (the decorators keep two memory layers + the DB).
_hybrid_caches: list["HybridCache"] = []


def _get_cache(name: str) -> TTLCache:
    if name not in _caches:
        _caches[name] = TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL)
    return _caches[name]


# Hit/miss counters keyed by cache name, for the health dashboard.
_stats: dict[str, dict[str, int]] = {}


def _record(name: str, hit: bool) -> None:
    s = _stats.setdefault(name, {"hits": 0, "misses": 0, "stale": 0})
    s["hits" if hit else "misses"] += 1


def stats() -> dict:
    """Per-cache hit/miss counts and current size, for /api/admin/health."""
    out = {}
    for name, s in _stats.items():
        total = s["hits"] + s["misses"]
        out[name] = {
            "hits": s["hits"],
            "misses": s["misses"],
            "hitRate": round(s["hits"] / total, 4) if total else None,
            "staleServed": s["stale"],
            "size": len(_caches[name]) if name in _caches else 0,
        }
    return out


def provenance_gaps() -> dict:
    """Persistent cache entries that predate source annotations (P2-33).

    A cache whose dict entries carry a ``"provenance"`` map shows its function
    now attaches one, so its dict entries without a map were cached before the
    upgrade and will serve without sources until they expire. Caches that never
    attach a map, list values and error payloads are not counted.
    Returns ``{"total": n, "byName": {cache_name: n}}``.
    """
    seen: dict[str, list[int]] = {}  # name -> [with a map, without one]
    try:
        from backend.database import SessionLocal
        from backend.db_models import CacheEntry
        with SessionLocal() as db:
            rows = db.query(CacheEntry.cache_name, CacheEntry.value_json).all()
    except Exception:
        return {"total": 0, "byName": {}}
    for name, raw in rows:
        if not raw or not raw.startswith("{"):
            continue  # not a dict
        if '"provenance"' in raw:  # cheap: Admin polls this, so parse only rows without a map
            seen.setdefault(name, [0, 0])[0] += 1
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if "error" not in value:
            seen.setdefault(name, [0, 0])[1] += 1
    by_name = {n: c[1] for n, c in seen.items() if c[0] and c[1]}
    return {"total": sum(by_name.values()), "byName": by_name}


def _make_key(args, kwargs) -> tuple:
    return args + tuple(sorted(kwargs.items()))


# ---------------------------------------------------------------------------
# Fetch times — "when was the data in this response actually fetched?"
#
# A response assembled at 14:05 from an entry cached at 13:10 was fetched at
# 13:10. Each cached entry remembers when it was computed (or, if it was built
# from older cached inputs, the oldest of those), and every cache read during
# a request reports that time to a request-scoped log. ``oldest_fetch()`` then
# gives the age of the stalest data the response contains.
# ---------------------------------------------------------------------------

_fetch_times: dict[str, TTLCache] = {}
_fetch_log: contextvars.ContextVar[list[float] | None] = contextvars.ContextVar("fetch_log", default=None)
_stale_hook: contextvars.ContextVar = contextvars.ContextVar("stale_hook", default=None)
# Set by _Computing to a one-element list; flipped to True when the computation
# reads a stale value, so its result is not cached as fresh.
_used_stale: contextvars.ContextVar[list[bool] | None] = contextvars.ContextVar("used_stale", default=None)


def start_fetch_log(on_stale=None) -> None:
    """Begin collecting fetch times for the current request/context.

    ``on_stale(fetched_at)`` is called whenever a stale entry is served while
    it is refreshed in the background, so the response can say so.
    """
    _fetch_log.set([])
    _stale_hook.set(on_stale)


def oldest_fetch() -> float | None:
    """Epoch seconds of the oldest data read since ``start_fetch_log()``, or
    None if nothing cached was read (or no log was started)."""
    log = _fetch_log.get()
    return min(log) if log else None


def _note_fetch(ts: float | None) -> None:
    log = _fetch_log.get()
    if log is not None and ts is not None:
        log.append(ts)


def _times(name: str) -> TTLCache:
    if name not in _fetch_times:
        _fetch_times[name] = TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL)
    return _fetch_times[name]


def _hit(name: str, raw_key) -> None:
    """Record a cache hit and report when that entry's data was fetched."""
    _record(name, True)
    _note_fetch(_times(name).get(raw_key))


class _Computing:
    """Collects the fetch times of whatever a cached function reads while it
    computes, so the new entry is dated by its oldest input."""

    def __enter__(self):
        self._inner: list[float] = []
        self._stale = [False]
        self._token = _fetch_log.set(self._inner)
        self._stale_token = _used_stale.set(self._stale)
        return self

    def __exit__(self, *exc):
        _fetch_log.reset(self._token)
        _used_stale.reset(self._stale_token)
        return False

    def fetched_at(self) -> float:
        return min(self._inner, default=time.time())

    @property
    def used_stale(self) -> bool:
        return self._stale[0]


# Set for a request the user asked to refresh (P1-20 page Refresh button):
# every cached function it reads is recomputed, see ``_refresh_due``. Threads
# and tasks started for background refreshes get a fresh context, so it does
# not leak into them.
_refresh: contextvars.ContextVar[bool] = contextvars.ContextVar("cache_refresh", default=False)


def set_refresh(on: bool) -> None:
    """Bypass the cache for the rest of the current request/context."""
    _refresh.set(on)


def _refresh_due(name: str, raw_key) -> bool:
    """In a refresh request: True unless this key's in-memory entry was fetched
    within ``_REFRESH_MIN_AGE`` (then it is served as a normal hit)."""
    if not _refresh.get():
        return False
    if raw_key not in _get_cache(name):
        return True
    fetched = _times(name).get(raw_key)
    return fetched is None or time.time() - fetched >= _REFRESH_MIN_AGE


def _mark_used_stale() -> None:
    flag = _used_stale.get()
    if flag is not None:
        flag[0] = True


# ---------------------------------------------------------------------------
# Stale-while-revalidate state, per (cache name, key). An entry is added when a
# stale persisted value is first served and removed once a refresh stores a
# fresh one. While a refresh runs (or just failed), callers get the stale
# value without waiting for the key lock.
# ---------------------------------------------------------------------------

class _Stale:
    __slots__ = ("value", "fetched", "refreshing", "retry_at")

    def __init__(self, value, fetched: float) -> None:
        self.value = value
        self.fetched = fetched
        self.refreshing = False
        self.retry_at = 0.0


_stale: TTLCache = TTLCache(maxsize=4 * _CACHE_MAXSIZE, ttl=_STALE_MAX)
_stale_guard = threading.Lock()
_refresh_tasks: set = set()     # strong refs, so pending refresh tasks aren't GC'd
_refresh_threads: set = set()


def _serve_stale(name: str, st: _Stale):
    """Return a stale value, reporting its true fetch time."""
    _record(name, True)
    _stats[name]["stale"] += 1
    _note_fetch(st.fetched)
    _flag_stale(st.fetched)
    return st.value


def _flag_stale(fetched: float) -> None:
    """Tell the enclosing computation and the request that stale data was used."""
    _mark_used_stale()
    hook = _stale_hook.get()
    if hook is not None:
        hook(fetched)


def _hold_stale(ck, value, fetched: float) -> None:
    """Keep a value computed from stale inputs as this key's stale entry, to be
    rebuilt after ``_STALE_INPUT_RETRY``."""
    with _stale_guard:
        st = _stale.get(ck)
        if st is None:
            st = _stale[ck] = _Stale(value, fetched)
        st.value, st.fetched = value, fetched
        st.refreshing = False
        st.retry_at = time.time() + _STALE_INPUT_RETRY


def _servable_stale(ck) -> _Stale | None:
    """The stale entry for ``ck`` if it can be served without the key lock:
    a refresh is in flight, or the last one failed recently."""
    st = _stale.get(ck)
    if st is None or time.time() - st.fetched > _STALE_MAX:
        return None
    if st.refreshing or time.time() < st.retry_at:
        return st
    return None


def _claim_refresh(ck, value, fetched: float) -> tuple[_Stale, bool]:
    """Record a stale value for ``ck``. ``refreshing`` is set on the returned
    entry; ``start`` is True if this caller should run the refresh."""
    with _stale_guard:
        st = _stale.get(ck)
        if st is None:
            st = _stale[ck] = _Stale(value, fetched)
        elif fetched > st.fetched:  # keep the newer of the held and stored values
            st.value, st.fetched = value, fetched
        start = not st.refreshing and time.time() >= st.retry_at
        if start:
            st.refreshing = True
        return st, start


def _refresh_done(ck, ok: bool) -> None:
    with _stale_guard:
        st = _stale.get(ck)
        if ok:
            _stale.pop(ck, None)
        elif st is not None and st.refreshing:  # failed (not just held stale)
            st.refreshing = False
            st.retry_at = time.time() + _REFRESH_RETRY


def _held_value(name: str, raw_key, entry):
    """For a refresh whose source failed: the value already held (memory, else
    the persistent ``entry``), reported with its real fetch time; else None."""
    cache = _get_cache(name)
    if raw_key in cache:
        _hit(name, raw_key)
        return cache[raw_key]
    if entry is None:
        return None
    value, fetched, fresh = entry
    _note_fetch(fetched)
    if not fresh:
        _flag_stale(fetched)
    return value


def _is_empty_result(result) -> bool:
    """Default predicate: treat None, empty containers and failure envelopes
    as 'no data'.

    Empty/failed results must never be cached — otherwise a transient source
    failure (or a fetch made before API keys were entered) poisons the cache
    permanently, since the persistent tier survives restarts. A dict carrying
    a truthy ``error`` key or ``status == "unavailable"`` is a failure envelope
    even though it is non-empty.
    """
    if result is None:
        return True
    if isinstance(result, (dict, list, tuple, set, str)) and len(result) == 0:
        return True
    if isinstance(result, dict) and (result.get("error") or result.get("status") == "unavailable"):
        return True
    return False


def cached(name: str | None = None, skip_if=None):
    """Cache a *synchronous* function's result for 60 minutes.

    Two-tier: in-memory TTLCache (fast) → SQLite CacheEntry (persistent).
    Survives container restarts via the database tier.

    ``skip_if`` is a predicate ``result -> bool``; when it returns True the
    result is returned but NOT cached (defaults to :func:`_is_empty_result`).
    """
    import json as _json

    def decorator(func):
        cache_name = name or func.__qualname__
        _get_cache(cache_name)  # ensure the in-memory cache exists
        persistent = HybridCache(cache_name, ttl_sec=_CACHE_TTL, maxsize=_CACHE_MAXSIZE)
        is_empty = skip_if or _is_empty_result

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = _get_cache(cache_name)
            raw_key = _make_key(args, kwargs)
            if _refresh_due(cache_name, raw_key):
                ck = (cache_name, raw_key)
                with _sync_locks.get(ck):
                    if not _refresh_due(cache_name, raw_key):  # refreshed while we waited
                        _hit(cache_name, raw_key)
                        return cache[raw_key]
                    return refresh_now(ck, args, kwargs)
            if raw_key in cache:
                _hit(cache_name, raw_key)
                return cache[raw_key]

            # Single-flight: on a cold cache, concurrent callers would each hit
            # the upstream source (thundering herd against rate-limited APIs).
            ck = (cache_name, raw_key)
            st = _servable_stale(ck)
            if st is not None:
                return _serve_stale(cache_name, st)

            with _sync_locks.get(ck):
                if raw_key in cache:
                    _hit(cache_name, raw_key)
                    return cache[raw_key]

                # Tier 2: SQLite (survives restarts)
                str_key = _json.dumps(raw_key, default=str, sort_keys=True)
                entry = persistent.get_entry(str_key)
                if entry is not None and entry[2]:
                    db_val, fetched, _ = entry
                    cache[raw_key] = db_val  # promote to memory
                    _times(cache_name)[raw_key] = fetched
                    _hit(cache_name, raw_key)
                    return db_val
                held = _stale.get(ck)  # e.g. a value built from stale inputs
                if held is not None and time.time() - held.fetched > _STALE_MAX:
                    held = None
                if entry is not None or held is not None:
                    value, fetched = entry[:2] if entry is not None else (held.value, held.fetched)
                    st, start = _claim_refresh(ck, value, fetched)
                    if start:
                        t = threading.Thread(target=refresh, args=(ck, str_key, args, kwargs),
                                             daemon=True, name=f"swr-{cache_name}")
                        _refresh_threads.add(t)
                        t.start()
                    return _serve_stale(cache_name, st)

                _record(cache_name, False)
                return compute(ck, str_key, args, kwargs)[0]

        def compute(ck, str_key, args, kwargs):
            """Call ``func`` and cache a non-empty result; returns ``(result,
            cached_fresh)``. Caller holds the key lock."""
            with _Computing() as computing:
                result = func(*args, **kwargs)
            fetched = computing.fetched_at()
            _note_fetch(fetched)
            if is_empty(result):
                return result, False  # don't cache empty/failed results
            if computing.used_stale:
                # Built from inputs that are being refreshed: as stale as they
                # are, so hold it as stale rather than fresh for a full TTL.
                _hold_stale(ck, result, fetched)
                _flag_stale(fetched)
                return result, False
            _get_cache(cache_name)[ck[1]] = result
            _times(cache_name)[ck[1]] = fetched
            persistent.set(str_key, result, fetched)  # persist to DB
            return result, True

        def refresh_now(ck, args, kwargs):
            """Recompute for a refresh request; caller holds the key lock. If
            the source fails, the value already held is served, not nothing."""
            str_key = _json.dumps(ck[1], default=str, sort_keys=True)
            _record(cache_name, False)
            try:
                result, fresh = compute(ck, str_key, args, kwargs)
            except Exception:
                log.warning("refresh of %s failed", cache_name, exc_info=True)
                held = _held_value(cache_name, ck[1], persistent.get_entry(str_key))
                if held is None:
                    raise
                return held
            if fresh:
                _refresh_done(ck, True)
            if not is_empty(result):
                return result
            held = _held_value(cache_name, ck[1], persistent.get_entry(str_key))
            return result if held is None else held

        def refresh(ck, str_key, args, kwargs):
            # A new thread starts with an empty context, so nothing it reads
            # reports into the request that served the stale value.
            ok = False
            try:
                with _sync_locks.get(ck):
                    ok = compute(ck, str_key, args, kwargs)[1]
            except Exception:
                log.warning("background refresh of %s failed", cache_name, exc_info=True)
            finally:
                _refresh_done(ck, ok)
                _refresh_threads.discard(threading.current_thread())

        return wrapper

    return decorator


def async_cached(name: str | None = None, skip_if=None):
    """Cache an *async* function's result for 60 minutes.

    Two-tier: in-memory TTLCache (fast) → SQLite CacheEntry (persistent).
    Survives container restarts via the database tier.

    ``skip_if`` is a predicate ``result -> bool``; when it returns True the
    result is returned but NOT cached (defaults to :func:`_is_empty_result`).
    """
    import json as _json

    def decorator(func):
        cache_name = name or func.__qualname__
        _get_cache(cache_name)  # ensure the in-memory cache exists
        persistent = HybridCache(cache_name, ttl_sec=_CACHE_TTL, maxsize=_CACHE_MAXSIZE)
        is_empty = skip_if or _is_empty_result

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache = _get_cache(cache_name)
            raw_key = _make_key(args, kwargs)
            if _refresh_due(cache_name, raw_key):
                ck = (cache_name, raw_key)
                async with _locks.get(ck):
                    if not _refresh_due(cache_name, raw_key):  # refreshed while we waited
                        _hit(cache_name, raw_key)
                        return cache[raw_key]
                    return await refresh_now(ck, args, kwargs)
            if raw_key in cache:
                _hit(cache_name, raw_key)
                return cache[raw_key]

            ck = (cache_name, raw_key)
            st = _servable_stale(ck)
            if st is not None:
                return _serve_stale(cache_name, st)

            async with _locks.get(ck):
                if raw_key in cache:
                    _hit(cache_name, raw_key)
                    return cache[raw_key]

                # Tier 2: SQLite (survives restarts). In a worker thread: while
                # the warm-up jobs hold SQLite's write lock a DB call can wait
                # for seconds, and on the event loop that froze every request.
                str_key = _json.dumps(raw_key, default=str, sort_keys=True)
                entry = await asyncio.to_thread(persistent.get_entry, str_key)
                if entry is not None and entry[2]:
                    db_val, fetched, _ = entry
                    cache[raw_key] = db_val  # promote to memory
                    _times(cache_name)[raw_key] = fetched
                    _hit(cache_name, raw_key)
                    return db_val
                held = _stale.get(ck)  # e.g. a value built from stale inputs
                if held is not None and time.time() - held.fetched > _STALE_MAX:
                    held = None
                if entry is not None or held is not None:
                    value, fetched = entry[:2] if entry is not None else (held.value, held.fetched)
                    st, start = _claim_refresh(ck, value, fetched)
                    if start:
                        # A fresh context: the refresh outlives this request and
                        # must not report into its fetch log or headers.
                        task = asyncio.get_running_loop().create_task(
                            refresh(ck, str_key, args, kwargs), context=contextvars.Context())
                        _refresh_tasks.add(task)
                        task.add_done_callback(_refresh_tasks.discard)
                    return _serve_stale(cache_name, st)

                _record(cache_name, False)
                return (await compute(ck, str_key, args, kwargs))[0]

        async def compute(ck, str_key, args, kwargs):
            """Call ``func`` and cache a non-empty result; returns ``(result,
            cached_fresh)``. Caller holds the key lock."""
            with _Computing() as computing:
                result = await func(*args, **kwargs)
            fetched = computing.fetched_at()
            _note_fetch(fetched)
            if is_empty(result):
                return result, False  # don't cache empty/failed results
            if computing.used_stale:
                # Built from inputs that are being refreshed: as stale as they
                # are, so hold it as stale rather than fresh for a full TTL.
                _hold_stale(ck, result, fetched)
                _flag_stale(fetched)
                return result, False
            _get_cache(cache_name)[ck[1]] = result
            _times(cache_name)[ck[1]] = fetched
            await asyncio.to_thread(persistent.set, str_key, result, fetched)  # persist to DB
            return result, True

        async def refresh_now(ck, args, kwargs):
            """Recompute for a refresh request; caller holds the key lock. If
            the source fails, the value already held is served, not nothing."""
            str_key = _json.dumps(ck[1], default=str, sort_keys=True)
            _record(cache_name, False)
            try:
                result, fresh = await compute(ck, str_key, args, kwargs)
            except Exception:
                log.warning("refresh of %s failed", cache_name, exc_info=True)
                entry = await asyncio.to_thread(persistent.get_entry, str_key)
                held = _held_value(cache_name, ck[1], entry)
                if held is None:
                    raise
                return held
            if fresh:
                _refresh_done(ck, True)
            if not is_empty(result):
                return result
            entry = await asyncio.to_thread(persistent.get_entry, str_key)
            held = _held_value(cache_name, ck[1], entry)
            return result if held is None else held

        async def refresh(ck, str_key, args, kwargs):
            ok = False
            try:
                async with _locks.get(ck):
                    ok = (await compute(ck, str_key, args, kwargs))[1]
            except Exception:
                log.warning("background refresh of %s failed", cache_name, exc_info=True)
            finally:
                _refresh_done(ck, ok)

        return wrapper

    return decorator


class HybridCache:
    """
    Two-tier cache: in-memory TTLCache (fast) → SQLite CacheEntry (persistent).
    Falls back gracefully if DB is unavailable.
    """

    def __init__(self, name: str, ttl_sec: int = 3600, maxsize: int = 2048,
                 stale_sec: int = _STALE_MAX):
        self._memory = TTLCache(maxsize=maxsize, ttl=ttl_sec)
        self._name = name
        self._ttl_sec = ttl_sec
        self._stale_sec = max(stale_sec, ttl_sec)
        self._hit_miss = {"hits_mem": 0, "hits_db": 0, "misses": 0}
        # key -> epoch seconds the value held for that key was fetched
        self._fetched = TTLCache(maxsize=maxsize, ttl=ttl_sec)
        _hybrid_caches.append(self)

    def _read_db(self, key: str) -> tuple | None:
        """``(value, fetched_at)`` from SQLite for a row younger than the stale
        window, or None on miss/failure. ``fetched_at`` is epoch seconds."""
        try:
            from backend.database import SessionLocal
            from backend.db_models import CacheEntry
            db = SessionLocal()
            try:
                row = db.get(CacheEntry, (self._name, key))
                if row is None:
                    return None
                created = getattr(row, "created_at", None)
                if created is None:
                    return json.loads(row.value_json), time.time()
                # Rows past the stale window are deleted, not served: without an
                # age limit on the persistent tier a row would be served forever.
                if (_utcnow() - created).total_seconds() > self._stale_sec:
                    db.delete(row)
                    db.commit()
                    return None
                return json.loads(row.value_json), created.replace(tzinfo=timezone.utc).timestamp()
            finally:
                db.close()
        except Exception:
            return None  # DB unavailable — degrade gracefully

    def _get_from_db(self, key: str):
        """Return the deserialized value from SQLite if it is within its TTL,
        or None on miss/failure. Stale rows are kept for :meth:`get_entry`."""
        entry = self._read_db(key)
        if entry is None or time.time() - entry[1] > self._ttl_sec:
            return None
        self._fetched[key] = entry[1]
        return entry[0]

    def _set_in_db(self, key: str, value, fetched_at: float | None = None) -> None:
        """Persist value to SQLite; non-fatal on failure.

        ``fetched_at`` (epoch seconds) dates the row by when its data was
        fetched, which can be earlier than now if it was built from older
        cached inputs; the row then also expires with those inputs.
        """
        try:
            from backend.database import SessionLocal
            from backend.db_models import CacheEntry
            created = (datetime.fromtimestamp(fetched_at, timezone.utc).replace(tzinfo=None)
                       if fetched_at is not None else _utcnow())
            db = SessionLocal()
            try:
                entry = CacheEntry(
                    cache_name=self._name,
                    key=key,
                    value_json=json.dumps(value, default=str),
                    created_at=created,
                )
                db.merge(entry)
                db.commit()
            finally:
                db.close()
        except Exception:
            pass  # Memory write already succeeded; DB failure is non-fatal

    def _delete_from_db(self, key: str) -> None:
        """Remove a key from SQLite; non-fatal on failure."""
        try:
            from backend.database import SessionLocal
            from backend.db_models import CacheEntry
            db = SessionLocal()
            try:
                row = db.get(CacheEntry, (self._name, key))
                if row:
                    db.delete(row)
                    db.commit()
            finally:
                db.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str):
        """Return value from memory first, then DB, then None."""
        # Tier 1: memory
        if key in self._memory:
            self._hit_miss["hits_mem"] += 1
            return self._memory[key]

        # Tier 2: SQLite
        val = self._get_from_db(key)
        if val is not None:
            self._memory[key] = val  # Promote to memory
            self._hit_miss["hits_db"] += 1
            return val

        self._hit_miss["misses"] += 1
        return None

    def set(self, key: str, value, fetched_at: float | None = None) -> None:
        """Write to both memory and DB.  Skips DB for non-JSON-serializable types (e.g. DataFrames)."""
        self._memory[key] = value
        self._fetched[key] = fetched_at if fetched_at is not None else time.time()
        # Only persist JSON-serializable values — DataFrames/numpy arrays can't round-trip
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return  # non-serializable — memory-only is fine
        self._set_in_db(key, value, fetched_at)

    def get_entry(self, key: str) -> tuple | None:
        """``(value, fetched_at, fresh)``, including a stale row younger than
        the stale window (``fresh`` False), or None. Memory holds fresh values only."""
        if key in self._memory:
            self._hit_miss["hits_mem"] += 1
            return self._memory[key], self._fetched.get(key) or time.time(), True
        entry = self._read_db(key)
        if entry is None:
            self._hit_miss["misses"] += 1
            return None
        value, fetched = entry
        fresh = time.time() - fetched <= self._ttl_sec
        if fresh:
            self._memory[key] = value
            self._fetched[key] = fetched
        self._hit_miss["hits_db"] += 1
        return value, fetched, fresh

    def invalidate(self, key: str) -> None:
        """Remove from both layers."""
        self._memory.pop(key, None)
        self._delete_from_db(key)

    def stats(self) -> dict:
        return {
            "name": self._name,
            "hits_mem": self._hit_miss["hits_mem"],
            "hits_db": self._hit_miss["hits_db"],
            "misses": self._hit_miss["misses"],
            "memory_size": len(self._memory),
            "ttl_sec": self._ttl_sec,
        }


def clear_all(name: str | None = None) -> dict:
    """Flush cached data from both memory tiers and the SQLite tier.

    Pass ``name`` to flush a single cache; ``None`` flushes everything. Used by
    the Admin "Clear cache & re-warm" action to purge poisoned/empty entries.
    Returns ``{"entries": <db rows deleted>, "memory_caches": <caches cleared>}``,
    plus ``"error"`` when the SQLite tier could not be flushed.
    """
    mem_cleared = 0
    for cname, c in list(_caches.items()):
        if name is None or cname == name:
            c.clear()
            mem_cleared += 1
    for hc in list(_hybrid_caches):
        if name is None or hc._name == name:
            hc._memory.clear()
            hc._fetched.clear()
    for tname, t in list(_fetch_times.items()):
        if name is None or tname == name:
            t.clear()
    with _stale_guard:
        for ck in list(_stale.keys()):
            if name is None or ck[0] == name:
                _stale.pop(ck, None)

    entries = 0
    result: dict = {}
    try:
        from backend.database import SessionLocal
        from backend.db_models import CacheEntry
        db = SessionLocal()
        try:
            q = db.query(CacheEntry)
            if name is not None:
                q = q.filter(CacheEntry.cache_name == name)
            entries = q.delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        # The persistent rows are still there and will be served again, so a
        # failed flush (e.g. SQLite locked by a running job) must not read as
        # a successful one.
        result["error"] = f"persistent cache not cleared: {exc}"

    return {"entries": entries, "memory_caches": mem_cleared, **result}
