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
                return cache[key]
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
                return cache[key]
            async with lock:
                if key in cache:
                    return cache[key]
                result = await func(*args, **kwargs)
                cache[key] = result
                return result

        return wrapper

    return decorator
