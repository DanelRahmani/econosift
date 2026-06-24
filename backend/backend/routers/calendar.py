"""Economic Calendar router — Phase 4.

GET /api/calendar?index=dow&start=YYYY-MM-DD&end=YYYY-MM-DD

Defaults: current week (Monday → Sunday).  The index is normalised through the
same ALIASES map used by dashboard and treemap routers.
"""
from __future__ import annotations

import asyncio
import datetime

from fastapi import APIRouter

from ..services import constituents
from ..services import calendar_service

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

_INDICES = {"sp500", "ndx", "dow"}


def _norm_index(index: str) -> str:
    key = constituents.ALIASES.get(index.strip().lower(), index.strip().lower())
    return key if key in _INDICES else "dow"


def _current_week() -> tuple[str, str]:
    """Return (Monday, Sunday) of the current ISO week as 'YYYY-MM-DD' strings."""
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


@router.get("")
async def get_calendar(
    index: str = "dow",
    start: str | None = None,
    end: str | None = None,
):
    """Return aggregated economic calendar (macro, earnings, dividends, IPOs)."""
    norm_index = _norm_index(index)
    if start is None or end is None:
        default_start, default_end = _current_week()
        start = start or default_start
        end = end or default_end
    return await asyncio.to_thread(calendar_service.calendar, norm_index, start, end)
