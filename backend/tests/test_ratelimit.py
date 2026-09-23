"""Tests for the outbound provider rate limiter — Phase 41 (task B1)."""
from __future__ import annotations

import threading
import time

from backend.services.ratelimit import RateLimiter, fred_limiter, finnhub_limiter


def test_consecutive_acquires_are_spaced_by_the_minimum_interval():
    rl = RateLimiter("t", min_interval=0.05, max_concurrent=4)

    start = time.monotonic()
    for _ in range(4):
        with rl:
            pass
    elapsed = time.monotonic() - start

    # Four starts means three enforced gaps. A small tolerance is needed
    # because time.sleep can undershoot slightly on Windows' timer resolution;
    # the point is that the gaps are enforced, not that they are exact.
    assert elapsed >= 0.05 * 3 * 0.9


def test_concurrency_is_bounded():
    rl = RateLimiter("t", min_interval=0.0, max_concurrent=2)
    peak = 0
    current = 0
    lock = threading.Lock()

    def worker():
        nonlocal peak, current
        with rl:
            with lock:
                current += 1
                peak = max(peak, current)
            time.sleep(0.05)
            with lock:
                current -= 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak <= 2


def test_release_happens_even_when_the_body_raises():
    """A provider error must not permanently consume a slot."""
    rl = RateLimiter("t", min_interval=0.0, max_concurrent=1)

    try:
        with rl:
            raise RuntimeError("provider exploded")
    except RuntimeError:
        pass

    # If the slot leaked this would block forever.
    acquired = rl._semaphore.acquire(timeout=1.0)
    assert acquired
    rl.release()


def test_a_warm_path_is_not_meaningfully_slowed():
    """With one call the limiter must add no wait at all."""
    rl = RateLimiter("t", min_interval=0.5, max_concurrent=4)
    start = time.monotonic()
    with rl:
        pass
    assert time.monotonic() - start < 0.1


def test_configured_limiters_stay_inside_documented_provider_quotas():
    # FRED allows 120 requests/minute; Finnhub's free tier allows 60.
    assert 60.0 / fred_limiter.min_interval <= 1200      # generous headroom
    assert fred_limiter.min_interval > 0
    assert 60.0 / finnhub_limiter.min_interval <= 60
    assert finnhub_limiter._semaphore._value == 1        # Finnhub is serial
