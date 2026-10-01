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
from collections import deque

log = logging.getLogger(__name__)


class RateLimiter:
    """Bounded concurrency, a minimum interval between request starts, and
    optionally at most ``max_per_window`` starts in any ``window`` seconds.

    The interval alone does not hold a per-minute quota: with several callers
    queued, starts run back to back at the interval for as long as the burst
    lasts.
    """

    def __init__(self, name: str, min_interval: float, max_concurrent: int,
                 max_per_window: int | None = None, window: float = 60.0) -> None:
        self.name = name
        self.min_interval = min_interval
        self.max_per_window = max_per_window
        self.window = window
        self._semaphore = threading.Semaphore(max_concurrent)
        self._lock = threading.Lock()
        self._last_start = 0.0
        self._starts: deque[float] = deque()

    def acquire(self) -> None:
        self._semaphore.acquire()
        # Space out starts. Held under its own lock so waiting threads queue in
        # order rather than all waking and firing together.
        with self._lock:
            gap = time.monotonic() - self._last_start
            if gap < self.min_interval:
                time.sleep(self.min_interval - gap)
            if self.max_per_window:
                now = time.monotonic()
                while self._starts and now - self._starts[0] >= self.window:
                    self._starts.popleft()
                if len(self._starts) >= self.max_per_window:
                    time.sleep(self._starts[0] + self.window - now)
                    self._starts.popleft()
            self._last_start = time.monotonic()
            if self.max_per_window:
                self._starts.append(self._last_start)

    def release(self) -> None:
        self._semaphore.release()

    def __enter__(self) -> "RateLimiter":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


# FRED's documented ceiling is 120 requests/minute per key. The 60ms gap keeps
# short bursts smooth; the 110/minute window is what actually holds the quota
# (a cold start makes ~200 FRED calls, and without it FRED rate-limited us).
fred_limiter = RateLimiter("fred", min_interval=0.06, max_concurrent=4, max_per_window=110)

# Finnhub's free tier is 60 calls/minute — appreciably tighter, so 1.05s apart
# and strictly serial.
finnhub_limiter = RateLimiter("finnhub", min_interval=1.05, max_concurrent=1)
