"""The default executor behind asyncio.to_thread must be sized for I/O.

Python sizes it min(32, cpu + 4): 8 threads on a 4-vCPU CI runner. Slow
upstream fetches (S&P 500 breadth, World Bank) hold those threads for
minutes, and the cache reads its SQLite tier through to_thread too, so once
eight fetches were in flight even cache hits stopped answering (seen in CI:
no data endpoint completed for 8.5 minutes while /api/health stayed up).
"""
import asyncio
import threading

from backend.main import IO_THREADS, install_io_executor


def test_more_blocking_calls_than_the_cpu_sized_default_run_at_once():
    # 40 > 32, the default's ceiling on any machine: every call must be
    # running concurrently for the barrier to open.
    parties = 40
    assert IO_THREADS >= parties
    barrier = threading.Barrier(parties, timeout=10)

    async def main():
        install_io_executor()
        await asyncio.gather(*(asyncio.to_thread(barrier.wait) for _ in range(parties)))

    asyncio.run(main())
