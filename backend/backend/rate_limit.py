"""Global per-source rate limiter + circuit breaker for external market data.

Every yfinance HTTP request goes through ``YfData._make_request``; wrapping it
once puts *all* Yahoo traffic (downloads, ``.info``, options, screen) behind a
token bucket, whatever thread or service makes the call.

Yahoo gets two buckets, because its endpoints tolerate very different loads
(docs/plans/REFACTOR_PROPOSALS.md §8.2). Price history (``/v8/finance/chart``,
used by every download, quote and breadth/treemap fan-out) ran clean at 10
concurrent calls/s, so it gets 8/s, burst 16. Everything else (quoteSummary
``.info``, quote, options, screen, crumb) is what Yahoo throttles first, so it
gets 2/s, burst 4. A single 2/s bucket for both starved every page behind the
cold 500-ticker chart fan-outs.

A 429 opens that bucket's circuit at once, with an exponentially growing
cooldown; while it is open, calls fail fast with ``YFRateLimitError`` instead
of hitting Yahoo again, so callers serve what they have stored. The buckets
trip separately: Yahoo can rate-limit the crumb/quoteSummary path while chart
still answers.

Requests made inside :func:`bulk` (large batch downloads) are low priority:
they take a token only when no in-page request is waiting, so a two-ticker
chart never queues behind a cold 500-ticker fan-out.
"""
from __future__ import annotations

import contextlib
import functools
import logging
import random
import threading
import time

from yfinance.exceptions import YFRateLimitError

log = logging.getLogger(__name__)

COOLDOWN_429 = 30.0          # first cooldown after a 429, doubled on each repeat
COOLDOWN_MAX = 15 * 60.0
ERROR_THRESHOLD = 5          # consecutive non-429 failures that open the circuit
ERROR_COOLDOWN = 60.0

_local = threading.local()


@contextlib.contextmanager
def bulk():
    """Mark this thread's Yahoo requests as low priority (batch downloads)."""
    prev = getattr(_local, "bulk", False)
    _local.bulk = True
    try:
        yield
    finally:
        _local.bulk = prev


def is_bulk() -> bool:
    return getattr(_local, "bulk", False)


class SourceGuard:
    """Token bucket (``rate`` per second, ``burst`` capacity) + circuit breaker."""

    def __init__(self, name: str, rate: float, burst: int, *, jitter: float = 0.0,
                 clock=time.monotonic, sleep=time.sleep):
        self.name = name
        self.rate = rate
        self.burst = burst
        self.jitter = jitter
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._tokens = float(burst)
        self._last = clock()
        self._open_until = 0.0
        self._consecutive_429 = 0
        self._consecutive_errors = 0
        self._last_error: str | None = None
        self._requests = 0  # since process start; the Phase 66 target is a few hundred per day
        self._high_waiting = 0  # normal-priority requests waiting for a token

    # -- circuit ---------------------------------------------------------------
    def _open(self, seconds: float, reason: str) -> None:
        self._open_until = self._clock() + seconds
        self._last_error = reason
        log.warning("%s circuit open for %.0fs: %s", self.name, seconds, reason)

    def _record_429(self) -> None:
        with self._lock:
            self._consecutive_429 += 1
            cooldown = min(COOLDOWN_429 * 2 ** (self._consecutive_429 - 1), COOLDOWN_MAX)
            self._open(cooldown, "HTTP 429 (rate limited)")

    def _record_error(self, exc: Exception) -> None:
        with self._lock:
            self._consecutive_errors += 1
            if self._consecutive_errors >= ERROR_THRESHOLD:
                self._open(ERROR_COOLDOWN, f"{self._consecutive_errors} consecutive errors: {exc!r}"[:200])

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_429 = 0
            self._consecutive_errors = 0

    # -- bucket ----------------------------------------------------------------
    def _acquire(self, low: bool = False) -> None:
        queued = False
        try:
            while True:
                with self._lock:
                    now = self._clock()
                    if now < self._open_until:
                        raise YFRateLimitError()
                    self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
                    self._last = now
                    if self._tokens >= 1 and not (low and self._high_waiting):
                        self._tokens -= 1
                        self._requests += 1
                        return
                    if not low and not queued:
                        self._high_waiting += 1
                        queued = True
                    # A bulk request yielding to a queued one re-checks after one token's time.
                    wait = max(1 - self._tokens, 0.0) / self.rate or 1 / self.rate
                self._sleep(wait + (random.uniform(0, self.jitter) if self.jitter else 0.0))
        finally:
            if queued:
                with self._lock:
                    self._high_waiting -= 1

    def call(self, fn, *args, **kwargs):
        self._acquire(low=is_bulk())
        try:
            result = fn(*args, **kwargs)
        except YFRateLimitError:
            self._record_429()
            raise
        except Exception as exc:
            self._record_error(exc)
            raise
        if getattr(result, "status_code", None) == 429:
            self._record_429()
        else:
            self._record_success()
        return result

    def status(self) -> dict:
        with self._lock:
            remaining = max(0.0, self._open_until - self._clock())
            return {
                "state": "open" if remaining else "closed",
                "openForSeconds": round(remaining, 1),
                "consecutive429": self._consecutive_429,
                "consecutiveErrors": self._consecutive_errors,
                "lastError": self._last_error,
                "requests": self._requests,
                "ratePerSecond": self.rate,
                "burst": self.burst,
            }


YAHOO_CHART = SourceGuard("yahoo_chart", rate=8.0, burst=16, jitter=0.05)
YAHOO_API = SourceGuard("yahoo_api", rate=2.0, burst=4, jitter=0.1)
# SEC EDGAR allows 10 requests/s per caller; half of that leaves room for the
# edgartools Form 4 / 13F paths, which don't pass this guard (§8.2).
SEC = SourceGuard("sec", rate=5.0, burst=5)


def guard_for_url(url: str) -> SourceGuard:
    return YAHOO_CHART if "/finance/chart/" in (url or "") else YAHOO_API


def install_yfinance_guard() -> None:
    """Route every yfinance HTTP request through its Yahoo bucket (idempotent)."""
    from yfinance.data import YfData

    original = YfData._make_request
    if getattr(original, "_econosift_guard", False):
        return

    @functools.wraps(original)
    def guarded(self, *args, **kwargs):
        url = kwargs.get("url", args[0] if args else "")
        return guard_for_url(url).call(original, self, *args, **kwargs)

    guarded._econosift_guard = True
    YfData._make_request = guarded


def status() -> dict:
    return {g.name: g.status() for g in (YAHOO_CHART, YAHOO_API, SEC)}
