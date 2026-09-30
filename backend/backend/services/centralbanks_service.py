"""Central Banks policy rate history + meeting countdown — Phase 16."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date

from ..cache import async_cached
from . import macro_expansion_service as mes

log = logging.getLogger(__name__)

_START = "2005-01-01"
_MAX_STALE_DAYS = 120

CB_SERIES: dict[str, list[str]] = {
    "Fed": ["FEDFUNDS"],
    "ECB": ["ECBMRRFR", "ECBDFR", "IRSTCI01EZM156N"],
    "BoE": ["IRSTCI01GBM156N", "IR3TIB01GBM156N"],
    "BoJ": ["IRSTCI01JPM156N", "IR3TIB01JPM156N"],
    "BoC": ["IRSTCI01CAM156N", "IR3TIB01CAM156N"],
    "RBA": ["IRSTCI01AUM156N", "IR3TIB01AUM156N"],
    "SNB": ["IRSTCI01CHM156N", "IR3TIB01CHM156N"],
}

_CB_MEETINGS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "cb_meetings.json")
)


def _load_meetings() -> list[dict]:
    try:
        with open(_CB_MEETINGS_PATH) as f:
            return json.load(f)
    except Exception:
        log.exception("Failed to load cb_meetings.json")
        return []


def _next_meeting(bank: str, meetings: list[dict]) -> tuple[str | None, int | None]:
    today = date.today()
    future = [m for m in meetings if m.get("bank") == bank and date.fromisoformat(m["date"]) >= today]
    if not future:
        return None, None
    future.sort(key=lambda m: m["date"])
    nxt = future[0]["date"]
    return nxt, (date.fromisoformat(nxt) - today).days


def _pick_series(cb: str, all_data: dict[str, list[dict]]) -> str:
    today = date.today()
    for sid in CB_SERIES[cb]:
        records = all_data.get(sid, [])
        if not records:
            continue
        last_date = date.fromisoformat(records[-1]["date"])
        if (today - last_date).days <= _MAX_STALE_DAYS:
            return sid
    for sid in CB_SERIES[cb]:
        if all_data.get(sid):
            return sid
    return CB_SERIES[cb][0]


def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@async_cached("centralbanks")
async def get_centralbanks() -> dict:
    all_sids: list[str] = []
    for sids in CB_SERIES.values():
        for sid in sids:
            if sid not in all_sids:
                all_sids.append(sid)
    if "WALCL" not in all_sids:
        all_sids.append("WALCL")

    raw = await mes.fetch_fred_series(tuple(all_sids), start=_START)
    meetings = await asyncio.to_thread(_load_meetings)

    chosen: dict[str, str] = {cb: _pick_series(cb, raw) for cb in CB_SERIES}

    current: dict[str, dict] = {}
    for cb, sid in chosen.items():
        records = raw.get(sid, [])
        rate = _to_float(records[-1]["value"]) if records else None
        nxt_date, days = _next_meeting(cb, meetings)
        # The picker falls back to a stale series when nothing fresh exists;
        # date it and flag it so an old print is never read as current.
        last_date = records[-1]["date"] if records else None
        current[cb] = {
            "rate":         round(rate, 4) if rate is not None else None,
            "series":       sid,
            "asOf":         last_date,
            "stale":        bool(last_date and (date.today() - date.fromisoformat(last_date[:10])).days > _MAX_STALE_DAYS),
            "next_meeting": nxt_date,
            "days_until":   days,
        }

    history_map: dict[str, dict[str, float | None]] = {}
    for cb, sid in chosen.items():
        for rec in raw.get(sid, []):
            d = rec["date"]
            if d not in history_map:
                history_map[d] = {}
            history_map[d][cb] = _to_float(rec["value"])

    history = [{"date": d, **vals} for d, vals in sorted(history_map.items())]

    balance_sheet = []
    for rec in raw.get("WALCL", []):
        v = _to_float(rec["value"])
        if v is not None:
            balance_sheet.append({"date": rec["date"], "value": round(v / 1_000_000, 4)})

    return {"history": history, "current": current, "balance_sheet": balance_sheet}
