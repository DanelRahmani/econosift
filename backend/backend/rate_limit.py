"""Global per-source rate limiter + circuit breaker for external market data.

Every yfinance HTTP request goes through ``YfData._make_request``; wrapping it
once puts *all* Yahoo traffic (downloads, ``.info``, options, screen) behind a
single token bucket, whatever thread or service makes the call.

Rate from the Phase 65.0 measurements (docs/plans/REFACTOR_PROPOSALS.md §8.2):
200 chart calls ran clean up to 3/s, so Yahoo gets 2/s with a burst of 4.
A 429 opens the circuit at once, with an exponentially growing cooldown;
while it is open, calls fail fast with ``YFRateLimitError`` instead of
hitting Yahoo again, so callers serve what they have stored.
"""
from __future__ import annotations

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
    def _acquire(self) -> None:
        while True:
            with self._lock:
                now = self._clock()
                if now < self._open_until:
                    raise YFRateLimitError()
                self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait = (1 - self._tokens) / self.rate
            self._sleep(wait + (random.uniform(0, self.jitter) if self.jitter else 0.0))

    def call(self, fn, *args, **kwargs):
        self._acquire()
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
                "ratePerSecond": self.rate,
                "burst": self.burst,
            }


YAHOO = SourceGuard("yahoo", rate=2.0, burst=4, jitter=0.1)


def install_yfinance_guard() -> None:
    """Route every yfinance HTTP request through :data:`YAHOO` (idempotent)."""
    from yfinance.data import YfData

    original = YfData._make_request
    if getattr(original, "_econosift_guard", False):
        return

    @functools.wraps(original)
    def guarded(self, *args, **kwargs):
        return YAHOO.call(original, self, *args, **kwargs)

    guarded._econosift_guard = True
    YfData._make_request = guarded


def status() -> dict:
    return {"yahoo": YAHOO.status()}
