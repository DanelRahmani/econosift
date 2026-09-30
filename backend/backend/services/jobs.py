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
# Job: refresh_daily_prices
# ---------------------------------------------------------------------------

def refresh_daily_prices() -> None:
    """Fetch 1-year OHLCV history for up to 100 tracked tickers and upsert into daily_price."""
    job_id = log_job_start("refresh_daily_prices")
    try:
        from .yfinance_service import get_ohlc_frame, get_close_frame
        from ..db_models import DailyPrice

        tickers = _get_all_tracked_tickers()
        if not tickers:
            log_job_success(job_id, 0)
            return

        batch = tickers[:100]
        ohlc_frames = get_ohlc_frame(tuple(batch), "1y")
        close_frame = get_close_frame(tuple(batch), "1y")

        rows = 0
        with _get_session()() as session:
            for sym, df in ohlc_frames.items():
                for date_idx, row in df.iterrows():
                    adj_close = None
                    if sym in close_frame.columns:
                        adj_close = _safe_float(close_frame[sym].get(date_idx))
                    date_val = date_idx.date() if hasattr(date_idx, "date") else date_idx
                    session.merge(DailyPrice(
                        symbol=sym,
                        date=date_val,
                        open=_safe_float(row.get("Open")),
                        high=_safe_float(row.get("High")),
                        low=_safe_float(row.get("Low")),
                        close=_safe_float(row.get("Close")),
                        adj_close=adj_close,
                        volume=_safe_int(row.get("Volume")),
                    ))
                    rows += 1
            session.commit()

        log_job_success(job_id, rows)
        logger.info("refresh_daily_prices: %d rows updated", rows)
    except Exception as exc:
        logger.error("refresh_daily_prices failed: %s", exc)
        log_job_failure(job_id, str(exc))


# ---------------------------------------------------------------------------
# Job: refresh_daily_quotes
# ---------------------------------------------------------------------------

def refresh_daily_quotes() -> None:
    """Fetch latest fundamental snapshot for up to 50 tracked tickers and upsert into daily_quote."""
    job_id = log_job_start("refresh_daily_quotes")
    try:
        from .yfinance_service import get_quote, get_info
        from ..db_models import DailyQuote

        tickers = _get_all_tracked_tickers()
        today = datetime.now(timezone.utc).date()
        rows = 0

        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with _get_session()() as session:
            for sym in tickers[:50]:
                try:
                    q = get_quote(sym)
                    if not q:
                        continue
                    info: dict = {}
                    try:
                        info = get_info(sym) or {}
                    except Exception:
                        pass
                    stmt = sqlite_insert(DailyQuote).values(
                        symbol=sym,
                        date=today,
                        price=_safe_float(q.get("price")),
                        market_cap=_safe_float(info.get("marketCap")),
                        pe=_safe_float(info.get("trailingPE")),
                        forward_pe=_safe_float(info.get("forwardPE")),
                        div_yield=_safe_float(info.get("dividendYield")),
                        beta=_safe_float(info.get("beta")),
                        high52=_safe_float(info.get("fiftyTwoWeekHigh")),
                        low52=_safe_float(info.get("fiftyTwoWeekLow")),
                        avg_vol_20d=_safe_float(
                            info.get("averageVolume20days")
                            or info.get("averageDailyVolume10Day")
                        ),
                        updated_at=_now_utc(),
                    ).on_conflict_do_update(
                        index_elements=["symbol"],
                        set_={
                            "date": today,
                            "price": _safe_float(q.get("price")),
                            "market_cap": _safe_float(info.get("marketCap")),
                            "pe": _safe_float(info.get("trailingPE")),
                            "forward_pe": _safe_float(info.get("forwardPE")),
                            "div_yield": _safe_float(info.get("dividendYield")),
                            "beta": _safe_float(info.get("beta")),
                            "high52": _safe_float(info.get("fiftyTwoWeekHigh")),
                            "low52": _safe_float(info.get("fiftyTwoWeekLow")),
                            "avg_vol_20d": _safe_float(info.get("averageVolume20days") or info.get("averageDailyVolume10Day")),
                            "updated_at": _now_utc(),
                        },
                    )
                    session.execute(stmt)
                    rows += 1
                except Exception as exc:
                    logger.debug("refresh_daily_quotes skip %s: %s", sym, exc)
                    continue
            session.commit()

        log_job_success(job_id, rows)
        logger.info("refresh_daily_quotes: %d rows updated", rows)
    except Exception as exc:
        logger.error("refresh_daily_quotes failed: %s", exc)
        log_job_failure(job_id, str(exc))


# ---------------------------------------------------------------------------
# Job: refresh_fx_rates
# ---------------------------------------------------------------------------

def refresh_fx_rates() -> None:
    """Fetch last 5 days of G10 FX spot rates from yfinance and upsert into daily_fx."""
    job_id = log_job_start("refresh_fx_rates")
    try:
        import yfinance as yf
        from ..db_models import DailyFX

        G10_PAIRS = [
            ("EUR", "USD"), ("GBP", "USD"), ("JPY", "USD"), ("CHF", "USD"),
            ("AUD", "USD"), ("NZD", "USD"), ("CAD", "USD"), ("NOK", "USD"), ("SEK", "USD"),
        ]
        rows = 0
        with _get_session()() as session:
            for base, quote in G10_PAIRS:
                try:
                    ticker_sym = f"{base}{quote}=X"
                    t = yf.Ticker(ticker_sym)
                    hist = t.history(period="5d")
                    if hist.empty:
                        continue
                    for date_idx, row in hist.iterrows():
                        date_val = date_idx.date() if hasattr(date_idx, "date") else date_idx
                        session.merge(DailyFX(
                            base_ccy=base,
                            quote_ccy=quote,
                            date=date_val,
                            rate=_safe_float(row.get("Close")),
                        ))
                        rows += 1
                except Exception as exc:
                    logger.debug("refresh_fx_rates skip %s/%s: %s", base, quote, exc)
                    continue
            session.commit()

        log_job_success(job_id, rows)
        logger.info("refresh_fx_rates: %d rows updated", rows)
    except Exception as exc:
        logger.error("refresh_fx_rates failed: %s", exc)
        log_job_failure(job_id, str(exc))


# ---------------------------------------------------------------------------
# Job: refresh_daily_macro
# ---------------------------------------------------------------------------

def refresh_daily_macro() -> None:
    """Fetch key FRED macro indicators and upsert into daily_macro table (US only)."""
    job_id = log_job_start("refresh_daily_macro")
    try:
        from ..db_models import DailyMacro
        from .macro_expansion_service import _fetch_fred_series_sync
        from datetime import date as _date, timedelta

        today = _date.today()
        series_ids = [
            "CPIAUCSL", "UNRATE", "GDPC1", "FEDFUNDS", "DGS10",
            "PAYEMS", "M2SL", "INDPRO", "MORTGAGE30US", "CSUSHPINSA",
        ]
        start_str = (today - timedelta(days=90)).isoformat()
        raw = _fetch_fred_series_sync(series_ids, start=start_str)

        rows = 0
        with _get_session()() as session:
            for indicator_id, points in raw.items():
                for pt in points:
                    if pt.get("value") is None:
                        continue
                    session.merge(DailyMacro(
                        indicator_id=indicator_id,
                        country="US",
                        date=_date.fromisoformat(pt["date"]),
                        value=pt["value"],
                    ))
                    rows += 1
            session.commit()

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
        if feargreed_service._put_call().get("ratio") is not None:
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

        scheduler.add_job(
            refresh_daily_prices,
            CronTrigger(hour=16, minute=0),
            id="refresh_daily_prices",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            refresh_daily_quotes,
            CronTrigger(hour=17, minute=0),
            id="refresh_daily_quotes",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            refresh_fx_rates,
            CronTrigger(hour="9,15,21", minute=0),
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

        scheduler.start()
        logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))

        # Fire each job once at startup so tables are populated immediately
        import threading
        def _run_startup_jobs():
            for fn, name in [
                (refresh_daily_prices, "refresh_daily_prices"),
                (refresh_daily_quotes, "refresh_daily_quotes"),
                (refresh_fx_rates,     "refresh_fx_rates"),
                (refresh_daily_macro,  "refresh_daily_macro"),
            ]:
                try:
                    logger.info("Running startup job: %s", name)
                    fn()
                except Exception as exc:
                    logger.warning("Startup job %s failed: %s", name, exc)
            # Bulk data runs async after a delay to let FRED/yfinance warm up
            import time as _time
            _time.sleep(10)
            try:
                logger.info("Running startup job: refresh_bulk_data")
                refresh_bulk_data()
            except Exception as exc:
                logger.warning("Startup job refresh_bulk_data failed: %s", exc)
        threading.Thread(target=_run_startup_jobs, daemon=True).start()

        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed - scheduler disabled")
        return None
    except Exception as exc:
        logger.error("Scheduler startup failed: %s", exc)
        return None
