"""Background scheduler jobs for Axiom Finance.

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
        from .yfinance_service import yfinance_service as yfs
        from ..db_models import DailyPrice

        tickers = _get_all_tracked_tickers()
        if not tickers:
            log_job_success(job_id, 0)
            return

        batch = tickers[:100]
        ohlc_frames = yfs.get_ohlc_frame(tuple(batch), "1y")
        close_frame = yfs.get_close_frame(tuple(batch), "1y")

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
        from .yfinance_service import yfinance_service as yfs
        from ..db_models import DailyQuote

        tickers = _get_all_tracked_tickers()
        today = datetime.now(timezone.utc).date()
        rows = 0

        with _get_session()() as session:
            for sym in tickers[:50]:
                try:
                    q = yfs.get_quote(sym)
                    if not q:
                        continue
                    info: dict = {}
                    try:
                        info = yfs.get_info(sym) or {}
                    except Exception:
                        pass
                    session.merge(DailyQuote(
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
                    ))
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
            CronTrigger(hour=[9, 15, 21], minute=0),
            id="refresh_fx_rates",
            max_instances=1,
            replace_existing=True,
        )

        scheduler.start()
        logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed - scheduler disabled")
        return None
    except Exception as exc:
        logger.error("Scheduler startup failed: %s", exc)
        return None
