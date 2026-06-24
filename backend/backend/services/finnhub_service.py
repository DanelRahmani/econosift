"""Thin Finnhub API client for Phase 4 Economic Calendar (and future phases).

All public functions return [] on any error or when no API key is configured —
callers never need to guard against exceptions from this module.
"""
from __future__ import annotations

import requests

from ..cache import cached
from ..config import FINNHUB_API_KEY

_BASE = "https://finnhub.io/api/v1"


def _get(path: str, params: dict) -> dict | None:
    """Low-level GET helper.  Returns parsed JSON or None on any failure."""
    if not FINNHUB_API_KEY:
        return None
    try:
        resp = requests.get(
            _BASE + path,
            params={**params, "token": FINNHUB_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


@cached("finnhub_economic_calendar")
def economic_calendar(start: str, end: str) -> list[dict]:
    """Fetch macro economic calendar events from Finnhub.

    Returns a list of event dicts (Finnhub shape) or [] if unavailable.
    """
    data = _get("/calendar/economic", {"from": start, "to": end})
    if not isinstance(data, dict):
        return []
    return data.get("economicCalendar") or []


@cached("finnhub_ipo_calendar")
def ipo_calendar(start: str, end: str) -> list[dict]:
    """Fetch IPO calendar from Finnhub.

    Returns a list of IPO dicts or [] if unavailable.
    """
    data = _get("/calendar/ipo", {"from": start, "to": end})
    if not isinstance(data, dict):
        return []
    return data.get("ipoCalendar") or []


@cached("finnhub_earnings_calendar")
def earnings_calendar(start: str, end: str) -> list[dict]:
    """Fetch earnings calendar from Finnhub.

    Returns a list of earnings dicts or [] if unavailable.
    """
    data = _get("/calendar/earnings", {"from": start, "to": end})
    if not isinstance(data, dict):
        return []
    return data.get("earningsCalendar") or []
