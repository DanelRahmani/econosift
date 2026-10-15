"""Phase 65 item 5: no Yahoo stampede at boot; Yahoo crons run outside US hours.

At container start the screener warm-up (~500 tickers x .info) plus four
immediate jobs hit Yahoo together with the user's first page load.
"""
import os
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from backend.services import jobs

ET = ZoneInfo("America/New_York")
YAHOO_JOBS = {"history_rotation", "refresh_daily_quotes", "refresh_fx_rates", "screener_warm_all"}


def _scheduled_jobs():
    sched = MagicMock()
    with patch.dict(os.environ, {"SCHEDULER_ENABLED": "true"}), \
         patch("apscheduler.schedulers.background.BackgroundScheduler", return_value=sched), \
         patch("threading.Thread"):
        jobs.start_scheduler()
    return {c.kwargs["id"]: c.args[1] for c in sched.add_job.call_args_list}


def test_startup_runs_no_yahoo_job():
    names = {fn.__name__ for fn in jobs.STARTUP_JOBS}
    assert names and not names & YAHOO_JOBS
    assert jobs.STARTUP_DELAY >= 60


def test_yahoo_crons_never_fire_during_us_market_hours():
    triggers = _scheduled_jobs()
    assert YAHOO_JOBS <= set(triggers)
    start = datetime(2026, 10, 12, tzinfo=ET)  # a Monday
    for job_id in YAHOO_JOBS:
        t, prev, fires = triggers[job_id], None, 0
        now = start
        while now < start + timedelta(days=7):
            nxt = t.get_next_fire_time(prev, now)
            if nxt is None or nxt >= start + timedelta(days=7):
                break
            local = nxt.astimezone(ET)
            in_hours = local.weekday() < 5 and time(9, 30) <= local.time() <= time(16, 0)
            assert not in_hours, f"{job_id} fires at {local:%a %H:%M} ET"
            prev, now, fires = nxt, nxt + timedelta(seconds=1), fires + 1
        assert fires, job_id


def test_lifespan_does_not_warm_screener(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.services import screener_service

    called = []
    monkeypatch.setattr(screener_service, "warm_all", lambda: called.append(1))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    with TestClient(app):
        pass
    assert called == []
