"""Phase 68 item 6: scheduled Yahoo jobs run on the fetcher thread; APScheduler only queues them."""
import os
from unittest.mock import MagicMock, patch

import pytest

from backend import fetcher, store
from backend.services import jobs

MOVED = ("refresh_fx_rates", "record_daily_snapshots", "screener_warm_all")


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    with store.connect() as conn:
        conn.execute("DELETE FROM fetch_queue")
    yield
    with store.connect() as conn:
        conn.execute("DELETE FROM fetch_queue")


def _scheduled():
    sched = MagicMock()
    with patch.dict(os.environ, {"SCHEDULER_ENABLED": "true"}), \
         patch("apscheduler.schedulers.background.BackgroundScheduler", return_value=sched), \
         patch("threading.Thread"):
        jobs.start_scheduler()
    return {c.kwargs["id"]: c.args[0] for c in sched.add_job.call_args_list}


def test_the_scheduler_only_queues_the_yahoo_jobs():
    scheduled = _scheduled()
    for name in MOVED:
        with patch.object(fetcher, "enqueue") as enqueue:
            scheduled[name]()  # firing the cron job...
        enqueue.assert_called_once_with("job", name, fetcher.PRIORITY_ON_DEMAND)  # ...only queues it


def test_the_fetcher_runs_a_queued_job_in_the_bulk_lane():
    seen = []
    job = MagicMock(side_effect=lambda: seen.append(__import__("backend.rate_limit").rate_limit.is_bulk()))
    with patch.object(fetcher, "_scheduled_jobs", return_value={"refresh_fx_rates": job}):
        fetcher.queue_job("refresh_fx_rates")
        assert fetcher.run_one() is True
    assert seen == [True]
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM fetch_queue").fetchone()[0] == 0


def test_every_moved_job_has_a_handler_and_an_unknown_one_fails():
    assert set(MOVED) <= set(fetcher._scheduled_jobs())
    with pytest.raises(RuntimeError):
        fetcher.run_job("nope")
