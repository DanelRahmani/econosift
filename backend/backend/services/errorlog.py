"""In-memory ring buffer of recent backend warnings — Phase 41 (task B2).

Every service in this codebase degrades quietly by design: a failed source logs
a warning and returns an empty result so one dead provider cannot take a page
down. The cost is that failures are invisible — they land in container logs
nobody reads, and the UI shows an empty panel with no way to tell "no data
exists" apart from "the fetch broke".

This attaches a logging handler to the root logger and keeps the last N
WARNING+ records in memory, so the Admin page can surface them. It is
deliberately not persisted: this is a live-ops view of the running process, not
an audit trail.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone

MAX_ENTRIES = 200

_buffer: deque[dict] = deque(maxlen=MAX_ENTRIES)
_lock = threading.Lock()


class _RingBufferHandler(logging.Handler):
    """Records WARNING+ into the ring buffer. Never raises into the caller."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(
                    record.created, tz=timezone.utc
                ).isoformat(),
                "level": record.levelname,
                # `backend.services.cot_service` -> `cot_service`, which is what
                # a reader actually wants to see.
                "source": record.name.rsplit(".", 1)[-1],
                "message": record.getMessage()[:500],
            }
            with _lock:
                _buffer.append(entry)
        except Exception:
            # A logging handler that throws would break the call it was
            # observing — the one place where swallowing is correct.
            pass


_handler: _RingBufferHandler | None = None


def install() -> None:
    """Attach the handler to the root logger. Safe to call more than once."""
    global _handler
    if _handler is not None:
        return
    _handler = _RingBufferHandler(level=logging.WARNING)
    logging.getLogger().addHandler(_handler)


def recent(limit: int = 100) -> list[dict]:
    """Most recent entries, newest first."""
    with _lock:
        items = list(_buffer)
    return list(reversed(items))[:limit]


def clear() -> None:
    with _lock:
        _buffer.clear()


def stats() -> dict:
    with _lock:
        items = list(_buffer)
    by_source: dict[str, int] = {}
    for it in items:
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1
    return {
        "total": len(items),
        "capacity": MAX_ENTRIES,
        "bySource": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        "oldest": items[0]["timestamp"] if items else None,
        "newest": items[-1]["timestamp"] if items else None,
    }
