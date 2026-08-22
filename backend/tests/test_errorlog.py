"""Tests for the error ring buffer — Phase 41 (task B2)."""
from __future__ import annotations

import logging

import pytest

from backend.services import errorlog


@pytest.fixture(autouse=True)
def _fresh_buffer():
    errorlog.install()
    errorlog.clear()
    yield
    errorlog.clear()


def test_warnings_are_captured():
    logging.getLogger("backend.services.cot_service").warning("COT parse failed")

    entries = errorlog.recent()
    assert len(entries) == 1
    assert entries[0]["message"] == "COT parse failed"
    assert entries[0]["level"] == "WARNING"


def test_source_is_the_module_leaf_not_the_full_path():
    logging.getLogger("backend.services.atlas_service").warning("boom")
    assert errorlog.recent()[0]["source"] == "atlas_service"


def test_info_and_debug_are_ignored():
    log = logging.getLogger("backend.services.quiet")
    log.info("routine")
    log.debug("noisy")
    assert errorlog.recent() == []


def test_errors_and_exceptions_are_captured():
    log = logging.getLogger("backend.services.thing")
    log.error("bad")
    try:
        raise ValueError("kaboom")
    except ValueError:
        log.exception("while fetching")

    levels = {e["level"] for e in errorlog.recent()}
    assert levels == {"ERROR"}
    assert len(errorlog.recent()) == 2


def test_entries_are_returned_newest_first():
    log = logging.getLogger("backend.services.order")
    for i in range(5):
        log.warning("msg-%d", i)

    messages = [e["message"] for e in errorlog.recent()]
    assert messages[0] == "msg-4"
    assert messages[-1] == "msg-0"


def test_buffer_is_bounded_and_drops_the_oldest():
    log = logging.getLogger("backend.services.flood")
    for i in range(errorlog.MAX_ENTRIES + 50):
        log.warning("m%d", i)

    entries = errorlog.recent(limit=errorlog.MAX_ENTRIES + 100)
    assert len(entries) == errorlog.MAX_ENTRIES
    # Newest survived, oldest evicted.
    assert entries[0]["message"] == f"m{errorlog.MAX_ENTRIES + 49}"
    assert all(e["message"] != "m0" for e in entries)


def test_limit_is_respected():
    log = logging.getLogger("backend.services.lim")
    for i in range(20):
        log.warning("m%d", i)
    assert len(errorlog.recent(limit=5)) == 5


def test_long_messages_are_truncated():
    logging.getLogger("backend.services.big").warning("x" * 5000)
    assert len(errorlog.recent()[0]["message"]) == 500


def test_formatted_messages_are_rendered():
    """Records carry args lazily; the buffer must store the rendered text."""
    logging.getLogger("backend.services.fmt").warning("failed for %s: %s", "GDP", "404")
    assert errorlog.recent()[0]["message"] == "failed for GDP: 404"


def test_stats_summarise_by_source():
    logging.getLogger("backend.services.a").warning("one")
    logging.getLogger("backend.services.a").warning("two")
    logging.getLogger("backend.services.b").warning("three")

    stats = errorlog.stats()
    assert stats["total"] == 3
    assert stats["bySource"]["a"] == 2
    assert stats["bySource"]["b"] == 1
    assert stats["capacity"] == errorlog.MAX_ENTRIES


def test_stats_are_empty_when_nothing_logged():
    stats = errorlog.stats()
    assert stats["total"] == 0
    assert stats["oldest"] is None and stats["newest"] is None


def test_install_is_idempotent():
    """Calling install twice must not double-record every message."""
    errorlog.install()
    errorlog.install()
    logging.getLogger("backend.services.once").warning("single")
    assert len(errorlog.recent()) == 1


def test_a_broken_record_does_not_propagate():
    """A handler that raises would break the call site it was observing.

    Driven against the handler directly rather than through logging: pytest's
    own capture plugin also formats the record and would raise first, which
    would be testing pytest rather than this module.
    """
    class Exploding:
        def __str__(self):
            raise RuntimeError("bad repr")

    record = logging.LogRecord(
        name="backend.services.boom", level=logging.WARNING, pathname=__file__,
        lineno=1, msg="%s", args=(Exploding(),), exc_info=None,
    )

    handler = errorlog._RingBufferHandler(level=logging.WARNING)
    handler.emit(record)   # must not raise

    assert errorlog.recent() == []
