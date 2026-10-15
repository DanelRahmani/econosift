"""Background scheduler jobs for EconoSift.

APScheduler-based daily jobs that pre-fetch data into the SQLite persistence
layer.  DB imports are deferred (lazy) to avoid circular imports at module load
time.  APScheduler startup failures are swallowed so they never crash FastAPI.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Lazily populated on first use so that tests can patch this module attribute.
SessionLocal = None  # type: ignore[assignment]


def _get_session():
    """Return the session factory, importing it on first call."""
    global SessionLocal
    if SessionLocal is None:
        from ..database import SessionLocal as _SL
        SessionLocal = _SL
    return SessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if f != f else f  # reject NaN
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Job execution logging
# ---------------------------------------------------------------------------

def log_job_start(job_name: str) -> str:
    from ..db_models import JobExecution

    job_id = str(uuid.uuid4())
    with _get_session()() as session:
        session.add(JobExecution(
            job_id=job_id,
            job_name=job_name,
            status="running",
            started_at=_now_utc(),
        ))
        session.commit()
    return job_id


def log_job_success(job_id: str, rows: int = 0) -> None:
    from ..db_models import JobExecution

    with _get_session()() as session:
        job = session.get(JobExecution, job_id)
        if job:
            job.status = "success"
            job.completed_at = _now_utc()
            job.rows_affected = rows
            session.commit()


def log_job_failure(job_id: str, error: str) -> None:
    from ..db_models import JobExecution

    with _get_session()() as session:
        job = session.get(JobExecution, job_id)
        if job:
            job.status = "failed"
            job.completed_at = _now_utc()
            job.error_message = str(error)[:1000]
            session.commit()


# ---------------------------------------------------------------------------
# Ticker universe
# ---------------------------------------------------------------------------

_cached_tickers: list[str] | None = None


def _get_all_tracked_tickers() -> list[str]:
    """Return sorted union of S&P 500 + NDX + Dow 30 symbols (cached in-process)."""
    global _cached_tickers
    if _cached_tickers is not None:
        return _cached_tickers

    from .constituents import constituent_symbols

    tickers: set[str] = set()
    for index in ("sp500", "ndx", "dow"):
        try:
            syms = constituent_symbols(index)
            tickers.update(syms)
        except Exception as exc:
            logger.warning("_get_all_tracked_tickers: could not fetch %s: %s", index, exc)

    _cached_tickers = sorted(tickers)
    return _cached_tickers


# ---------------------------------------------------------------------------
# Job: refresh_fx_rates
# ---------------------------------------------------------------------------

def refresh_fx_rates() -> None:
    """Fetch last 5 days of G10 FX spot rates from yfinance and upsert into fx_daily."""
    job_id = log_job_start("refresh_fx_rates")
    try:
        import yfinance as yf
        from .. import store

        G10_PAIRS = [
            ("EUR", "USD"), ("GBP", "USD"), ("JPY", "USD"), ("CHF", "USD"),
            ("AUD", "USD"), ("NZD", "USD"), ("CAD", "USD"), ("NOK", "USD"), ("SEK", "USD"),
        ]
        values: list[dict] = []
        for base, quote in G10_PAIRS:
            try:
                ticker_sym = f"{base}{quote}=X"
                t = yf.Ticker(ticker_sym)
                hist = t.history(period="5d")
                if hist.empty:
                    continue
                for date_idx, row in hist.iterrows():
                    date_val = date_idx.date() if hasattr(date_idx, "date") else date_idx
                    values.append(dict(
                        base=base,
                        quote=quote,
                        date=date_val.isoformat(),
                        rate=_safe_float(row.get("Close")),
                    ))
            except Exception as exc:
                logger.debug("refresh_fx_rates skip %s/%s: %s", base, quote, exc)
                continue
        rows = store.upsert("fx_daily", values, ("base", "quote", "date"))

        log_job_success(job_id, rows)
        logger.info("refresh_fx_rates: %d rows updated", rows)
    except Exception as exc:
        logger.error("refresh_fx_rates failed: %s", exc)
        log_job_failure(job_id, str(exc))


# ---------------------------------------------------------------------------
# Job: refresh_daily_macro
# ---------------------------------------------------------------------------

def refresh_daily_macro() -> None:
    """Fetch key FRED macro indicators and upsert into macro_series (US only)."""
    job_id = log_job_start("refresh_daily_macro")
    try:
        from .. import store
        from .macro_expansion_service import _fetch_fred_series_sync
        from datetime import date as _date, timedelta

        today = _date.today()
        series_ids = [
            "CPIAUCSL", "UNRATE", "GDPC1", "FEDFUNDS", "DGS10",
            "PAYEMS", "M2SL", "INDPRO", "MORTGAGE30US", "CSUSHPINSA",
        ]
        start_str = (today - timedelta(days=90)).isoformat()
        raw = _fetch_fred_series_sync(series_ids, start=start_str)

        values = [
            dict(series=indicator_id, country="US", date=pt["date"], value=pt["value"], source="FRED")
            for indicator_id, points in raw.items()
            for pt in points
            if pt.get("value") is not None
        ]
        rows = store.upsert("macro_series", values, ("series", "country", "date"))

        log_job_success(job_id, rows)
        logger.info("refresh_daily_macro: %d rows updated", rows)
    except Exception as exc:
        logger.error("refresh_daily_macro failed: %s", exc)
        log_job_failure(job_id, str(exc))


# ---------------------------------------------------------------------------
# Job: refresh_bulk_data
# ---------------------------------------------------------------------------

def refresh_bulk_data() -> None:
    """Download World Bank, Fama-French, and IMF WEO bulk datasets."""
    job_id = log_job_start("refresh_bulk_data")
    try:
        from .bulk_data_service import refresh_all_bulk_data
        status = refresh_all_bulk_data()
        total_rows = sum(v.get("rows", 0) for v in status.values())
        errors = [f"{k}: {v['error']}" for k, v in status.items() if v.get("error")]
        if errors:
            log_job_failure(job_id, "; ".join(errors))
        else:
            log_job_success(job_id, total_rows)
        logger.info("refresh_bulk_data: %d rows, %d sources", total_rows, len(status))
    except Exception as exc:
        logger.error("refresh_bulk_data failed: %s", exc)
        log_job_failure(job_id, str(exc))


# ---------------------------------------------------------------------------
# Job: record_daily_snapshots
# ---------------------------------------------------------------------------

def record_daily_snapshots() -> None:
    """Record the day's SPY put/call ratio and IV30 for tracked tickers.

    These metrics are ranked against their own recorded history, which would
    otherwise only grow on days someone opens the page. IV30 is recorded for
    SPY and every ticker that already has a history (i.e. has been viewed).
    """
    job_id = log_job_start("record_daily_snapshots")
    try:
        from . import feargreed_service, options_engine, snapshots
        rows = 0
        if feargreed_service._put_call(live=True).get("ratio") is not None:
            rows += 1
        for ticker in sorted(set(snapshots.keys("iv30")) | {"SPY"}):
            try:
                if options_engine.get_iv_metrics(ticker).get("ivHistoryDays"):
                    rows += 1
            except Exception as exc:
                logger.warning("record_daily_snapshots: IV30 for %s failed: %s", ticker, exc)
        log_job_success(job_id, rows)
        logger.info("record_daily_snapshots: %d snapshots", rows)
    except Exception as exc:
        logger.error("record_daily_snapshots failed: %s", exc)
        log_job_failure(job_id, str(exc))


# ---------------------------------------------------------------------------
# Scheduler startup
# ---------------------------------------------------------------------------

# Jobs that call Yahoo run on cron only, after the US close: at boot they
# stampeded Yahoo together with the user's first page load, and nothing
# reads their tables yet. Boot runs only the non-Yahoo jobs, staggered.
MARKET_TZ = "America/New_York"
STARTUP_DELAY = 120   # seconds after boot before the first startup job
STARTUP_GAP = 300     # seconds between startup jobs
STARTUP_JOBS = (refresh_daily_macro, refresh_bulk_data)


def start_scheduler():
    """Initialise and start APScheduler.

    Returns the running scheduler instance, or None if disabled / unavailable.
    APScheduler startup failures are caught and logged so FastAPI never crashes.
    """
    import os
    if os.getenv("SCHEDULER_ENABLED", "true").lower() != "true":
        logger.info("Scheduler disabled via SCHEDULER_ENABLED=false")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        tz = os.getenv("SCHEDULER_TIMEZONE", "UTC")
        scheduler = BackgroundScheduler(timezone=tz)

        from .screener_service import warm_all
        from .. import fetcher

        # The fetcher thread makes the calls; these only queue its work.
        scheduler.add_job(
            fetcher.queue_history_rotation,
            CronTrigger(day_of_week="mon-fri", hour=17, minute=30, timezone=MARKET_TZ),
            id="history_rotation",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            fetcher.queue_universe,
            CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=MARKET_TZ),
            id="universe_refresh",
            max_instances=1,
            replace_existing=True,
        )
        # The one Yahoo job inside market hours: 5 bulk screen calls per run.
        scheduler.add_job(
            fetcher.queue_snapshot,
            CronTrigger(day_of_week="mon-fri", hour="9-16", minute="0,15,30,45", timezone=MARKET_TZ),
            id="snapshot_intraday",
            max_instances=1,
            replace_existing=True,
        )
        # Today's bar from the closing snapshot, then a confirmation pass.
        scheduler.add_job(
            fetcher.queue_close_snapshot,
            CronTrigger(day_of_week="mon-fri", hour="16,17", minute=20, timezone=MARKET_TZ),
            id="snapshot_close",
            max_instances=1,
            replace_existing=True,
        )
        # New SEC filings: ~10 frames calls; changed companies get companyfacts re-fetched.
        scheduler.add_job(
            fetcher.queue_frames,
            CronTrigger(day_of_week="mon-fri", hour=23, minute=0, timezone=MARKET_TZ),
            id="sec_frames",
            max_instances=1,
            replace_existing=True,
        )
        # Yahoo-only company fields (estimates, targets, profile): ~75 symbols a day.
        scheduler.add_job(
            fetcher.queue_yahoo_rotation,
            CronTrigger(hour=20, minute=0, timezone=MARKET_TZ),
            id="yahoo_info_rotation",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            refresh_fx_rates,
            CronTrigger(hour="6,17,21", minute=0, timezone=MARKET_TZ),
            id="refresh_fx_rates",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            refresh_daily_macro,
            CronTrigger(hour=18, minute=0),
            id="refresh_daily_macro",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            refresh_bulk_data,
            CronTrigger(day_of_week="sun", hour=4, minute=0),
            id="refresh_bulk_data",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            record_daily_snapshots,
            # After the US close, whatever timezone the scheduler runs in.
            CronTrigger(day_of_week="mon-fri", hour=16, minute=30, timezone="America/New_York"),
            id="record_daily_snapshots",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            # The screener's ~500-ticker refresh used to run at every boot.
            warm_all,
            CronTrigger(day_of_week="mon-fri", hour=19, minute=0, timezone=MARKET_TZ),
            id="screener_warm_all",
            max_instances=1,
            replace_existing=True,
        )

        scheduler.start()
        logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))

        # Run the non-Yahoo jobs once after boot, staggered, so tables fill
        # without competing with the first page loads.
        import threading
        def _run_startup_jobs():
            import time as _time
            _time.sleep(STARTUP_DELAY)
            for i, fn in enumerate(STARTUP_JOBS):
                if i:
                    _time.sleep(STARTUP_GAP)
                try:
                    logger.info("Running startup job: %s", fn.__name__)
                    fn()
                except Exception as exc:
                    logger.warning("Startup job %s failed: %s", fn.__name__, exc)
        threading.Thread(target=_run_startup_jobs, daemon=True).start()

        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed - scheduler disabled")
        return None
    except Exception as exc:
        logger.error("Scheduler startup failed: %s", exc)
        return None
