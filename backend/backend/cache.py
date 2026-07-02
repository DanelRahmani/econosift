"""Shared TTL caching helpers for external data calls."""
from __future__ import annotations

import asyncio
import functools
import json
import threading
import time
from datetime import datetime, timezone
from cachetools import TTLCache

# 60-minute cache for external API responses.
_CACHE_TTL = 60 * 60
_CACHE_MAXSIZE = 2048

def _utcnow() -> datetime:
    """Naive UTC now — matches CacheEntry.created_at, which is stored naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_caches: dict[str, TTLCache] = {}
_locks: dict[str, asyncio.Lock] = {}
_sync_locks: dict[str, threading.Lock] = {}
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
    s = _stats.setdefault(name, {"hits": 0, "misses": 0})
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
            "size": len(_caches[name]) if name in _caches else 0,
        }
    return out


def _make_key(args, kwargs) -> tuple:
    return args + tuple(sorted(kwargs.items()))


def _is_empty_result(result) -> bool:
    """Default predicate: treat None and empty containers as 'no data'.

    Empty/failed results must never be cached — otherwise a transient source
    failure (or a fetch made before API keys were entered) poisons the cache
    permanently, since the persistent tier survives restarts.
    """
    if result is None:
        return True
    if isinstance(result, (dict, list, tuple, set, str)) and len(result) == 0:
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
        lock = _sync_locks.setdefault(cache_name, threading.Lock())
        persistent = HybridCache(cache_name, ttl_sec=_CACHE_TTL, maxsize=_CACHE_MAXSIZE)
        is_empty = skip_if or _is_empty_result

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = _get_cache(cache_name)
            raw_key = _make_key(args, kwargs)
            if raw_key in cache:
                _record(cache_name, True)
                return cache[raw_key]

            # Single-flight: on a cold cache, concurrent callers would each hit
            # the upstream source (thundering herd against rate-limited APIs).
            with lock:
                if raw_key in cache:
                    _record(cache_name, True)
                    return cache[raw_key]

                # Tier 2: SQLite (survives restarts)
                str_key = _json.dumps(raw_key, default=str, sort_keys=True)
                db_val = persistent.get(str_key)
                if db_val is not None:
                    _record(cache_name, True)
                    cache[raw_key] = db_val  # promote to memory
                    return db_val

                _record(cache_name, False)
                result = func(*args, **kwargs)
                if is_empty(result):
                    return result  # don't cache empty/failed results
                cache[raw_key] = result
                persistent.set(str_key, result)  # persist to DB
                return result

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
        lock = _locks.setdefault(cache_name, asyncio.Lock())
        persistent = HybridCache(cache_name, ttl_sec=_CACHE_TTL, maxsize=_CACHE_MAXSIZE)
        is_empty = skip_if or _is_empty_result

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache = _get_cache(cache_name)
            raw_key = _make_key(args, kwargs)
            if raw_key in cache:
                _record(cache_name, True)
                return cache[raw_key]

            async with lock:
                if raw_key in cache:
                    _record(cache_name, True)
                    return cache[raw_key]

                # Tier 2: SQLite (survives restarts)
                str_key = _json.dumps(raw_key, default=str, sort_keys=True)
                db_val = persistent.get(str_key)
                if db_val is not None:
                    _record(cache_name, True)
                    cache[raw_key] = db_val  # promote to memory
                    return db_val

                _record(cache_name, False)
                result = await func(*args, **kwargs)
                if is_empty(result):
                    return result  # don't cache empty/failed results
                cache[raw_key] = result
                persistent.set(str_key, result)  # persist to DB
                return result

        return wrapper

    return decorator


class HybridCache:
    """
    Two-tier cache: in-memory TTLCache (fast) → SQLite CacheEntry (persistent).
    Falls back gracefully if DB is unavailable.
    """

    def __init__(self, name: str, ttl_sec: int = 3600, maxsize: int = 2048):
        self._memory = TTLCache(maxsize=maxsize, ttl=ttl_sec)
        self._name = name
        self._ttl_sec = ttl_sec
        self._hit_miss = {"hits_mem": 0, "hits_db": 0, "misses": 0}
        _hybrid_caches.append(self)

    def _get_from_db(self, key: str):
        """Return deserialized value from SQLite, or None on miss/failure."""
        try:
            from backend.database import SessionLocal
            from backend.db_models import CacheEntry
            db = SessionLocal()
            try:
                row = db.get(CacheEntry, (self._name, key))
                if row is None:
                    return None
                # Enforce TTL on the persistent tier too. Without this, a stale
                # (or empty/poisoned) row is served forever, since the in-memory
                # TTLCache expiry never applied to the DB. Expired rows are
                # deleted so the next call re-fetches fresh data.
                created = getattr(row, "created_at", None)
                if created is not None:
                    age = (_utcnow() - created).total_seconds()
                    if age > self._ttl_sec:
                        db.delete(row)
                        db.commit()
                        return None
                return json.loads(row.value_json)
            finally:
                db.close()
        except Exception:
            return None  # DB unavailable — degrade gracefully

    def _set_in_db(self, key: str, value) -> None:
        """Persist value to SQLite; non-fatal on failure."""
        try:
            from backend.database import SessionLocal
            from backend.db_models import CacheEntry
            db = SessionLocal()
            try:
                entry = CacheEntry(
                    cache_name=self._name,
                    key=key,
                    value_json=json.dumps(value, default=str),
                    created_at=_utcnow(),
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

    def set(self, key: str, value) -> None:
        """Write to both memory and DB.  Skips DB for non-JSON-serializable types (e.g. DataFrames)."""
        self._memory[key] = value
        # Only persist JSON-serializable values — DataFrames/numpy arrays can't round-trip
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return  # non-serializable — memory-only is fine
        self._set_in_db(key, value)

    def get_stale_while_revalidate(self, key: str, max_age_sec: int = 300):
        """
        Return cached value immediately (even if stale by age).
        Expects data stored via set_with_timestamp so the envelope
        ``{"_ts": float, "_data": ...}`` is present.
        Returns the ``_data`` portion only.
        """
        raw = self.get(key)
        if raw is None:
            return None

        if isinstance(raw, dict) and "_ts" in raw and "_data" in raw:
            return raw["_data"]

        return raw

    def set_with_timestamp(self, key: str, value) -> None:
        """Store value wrapped with current timestamp for SWR staleness checks."""
        self.set(key, {"_ts": time.time(), "_data": value})

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
    Returns ``{"entries": <db rows deleted>, "memory_caches": <caches cleared>}``.
    """
    mem_cleared = 0
    for cname, c in list(_caches.items()):
        if name is None or cname == name:
            c.clear()
            mem_cleared += 1
    for hc in list(_hybrid_caches):
        if name is None or hc._name == name:
            hc._memory.clear()

    entries = 0
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
    except Exception:
        pass

    return {"entries": entries, "memory_caches": mem_cleared}
