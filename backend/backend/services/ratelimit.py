"""Outbound rate limiting for third-party data providers — Phase 41 (task B1).

A cold cache fans out hard: warming the screener or loading a macro tab can fire
dozens of FRED or Finnhub requests within a second or two. Both providers apply
per-key quotas, and tripping one degrades every panel at once — the failure is
also invisible, because `fetch_fred_series` swallows exceptions and returns an
empty result.

This throttles at the call site rather than adding retry logic: a bounded number
of concurrent requests plus a minimum gap between consecutive ones. It is
deliberately a blocking (thread-based) limiter, since the provider clients are
synchronous and already run under `asyncio.to_thread`.
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)


class RateLimiter:
    """Bounded concurrency plus a minimum interval between request starts."""

    def __init__(self, name: str, min_interval: float, max_concurrent: int) -> None:
        self.name = name
        self.min_interval = min_interval
        self._semaphore = threading.Semaphore(max_concurrent)
        self._lock = threading.Lock()
        self._last_start = 0.0

    def acquire(self) -> None:
        self._semaphore.acquire()
        # Space out starts. Held under its own lock so waiting threads queue in
        # order rather than all waking and firing together.
        with self._lock:
            gap = time.monotonic() - self._last_start
            if gap < self.min_interval:
                time.sleep(self.min_interval - gap)
            self._last_start = time.monotonic()

    def release(self) -> None:
        self._semaphore.release()

    def __enter__(self) -> "RateLimiter":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


# FRED's documented ceiling is 120 requests/minute per key. 60ms between starts
# with 4 in flight leaves generous headroom while barely affecting a warm run.
fred_limiter = RateLimiter("fred", min_interval=0.06, max_concurrent=4)

# Finnhub's free tier is 60 calls/minute — appreciably tighter, so 1.05s apart
# and strictly serial.
finnhub_limiter = RateLimiter("finnhub", min_interval=1.05, max_concurrent=1)
