"""Record and read daily metric snapshots (see ``db_models.MetricSnapshot``).

Used where a signal needs a percentile against its own history but no free
source publishes that history (SPY put/call open interest, per-ticker IV30).
All calls degrade to a no-op / empty history if the database is unavailable.
"""
from __future__ import annotations

import logging
from datetime import date

log = logging.getLogger(__name__)


def record(metric: str, key: str, value: float, day: date) -> None:
    """Upsert one day's value (last write of the day wins)."""
    try:
        from ..database import SessionLocal
        from ..db_models import MetricSnapshot
        db = SessionLocal()
        try:
            db.merge(MetricSnapshot(metric=metric, key=key, date=day, value=float(value)))
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        # A lost snapshot is a permanent gap in the history, so say so.
        log.warning("snapshot record failed for %s/%s: %s", metric, key, exc)


def keys(metric: str) -> list[str]:
    """Every key that has at least one snapshot of ``metric``."""
    try:
        from ..database import SessionLocal
        from ..db_models import MetricSnapshot
        db = SessionLocal()
        try:
            rows = db.query(MetricSnapshot.key).filter(MetricSnapshot.metric == metric).distinct().all()
            return sorted(r[0] for r in rows)
        finally:
            db.close()
    except Exception:
        log.debug("snapshot keys failed for %s", metric, exc_info=True)
        return []


def history(metric: str, key: str, limit: int = 252) -> list[tuple[date, float]]:
    """Most recent ``limit`` snapshots, oldest first."""
    try:
        from ..database import SessionLocal
        from ..db_models import MetricSnapshot
        db = SessionLocal()
        try:
            rows = (db.query(MetricSnapshot)
                    .filter(MetricSnapshot.metric == metric, MetricSnapshot.key == key)
                    .order_by(MetricSnapshot.date.desc())
                    .limit(limit).all())
            return [(r.date, r.value) for r in reversed(rows)]
        finally:
            db.close()
    except Exception:
        log.debug("snapshot history failed for %s/%s", metric, key, exc_info=True)
        return []
