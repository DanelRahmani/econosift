"""Shared TTL caching helpers for external data calls."""
from __future__ import annotations

import asyncio
import functools
import json
import time
from datetime import datetime
from cachetools import TTLCache

# 60-minute cache for external API responses.
_CACHE_TTL = 60 * 60
_CACHE_MAXSIZE = 2048

_caches: dict[str, TTLCache] = {}
_locks: dict[str, asyncio.Lock] = {}


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


def cached(name: str | None = None):
    """Cache a *synchronous* function's result for 60 minutes."""

    def decorator(func):
        cache_name = name or func.__qualname__
        _get_cache(cache_name)  # ensure the cache exists

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Resolve the cache by name at call time so tests (and any runtime
            # reset) that clear/replace _caches[name] actually take effect.
            cache = _get_cache(cache_name)
            key = _make_key(args, kwargs)
            if key in cache:
                _record(cache_name, True)
                return cache[key]
            _record(cache_name, False)
            result = func(*args, **kwargs)
            cache[key] = result
            return result

        return wrapper

    return decorator


def async_cached(name: str | None = None):
    """Cache an *async* function's result for 60 minutes."""

    def decorator(func):
        cache_name = name or func.__qualname__
        _get_cache(cache_name)  # ensure the cache exists
        lock = _locks.setdefault(cache_name, asyncio.Lock())

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache = _get_cache(cache_name)
            key = _make_key(args, kwargs)
            if key in cache:
                _record(cache_name, True)
                return cache[key]
            async with lock:
                if key in cache:
                    _record(cache_name, True)
                    return cache[key]
                _record(cache_name, False)
                result = await func(*args, **kwargs)
                cache[key] = result
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

    def _get_from_db(self, key: str):
        """Return deserialized value from SQLite, or None on miss/failure."""
        try:
            from backend.database import SessionLocal
            from backend.db_models import CacheEntry
            db = SessionLocal()
            try:
                row = db.get(CacheEntry, (self._name, key))
                if row is not None:
                    return json.loads(row.value_json)
                return None
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
                    created_at=datetime.utcnow(),
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
        """Write to both memory and DB."""
        self._memory[key] = value
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
