"""Shared TTL caching helpers for external data calls."""
from __future__ import annotations

import asyncio
import functools
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
        cache = _get_cache(cache_name)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
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
        cache = _get_cache(cache_name)
        lock = _locks.setdefault(cache_name, asyncio.Lock())

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
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
