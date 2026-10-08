"""Central Banks policy rate history + meeting countdown — Phase 16."""
from __future__ import annotations

import asyncio
from datetime import date

from .. import provenance as pv
from ..cache import async_cached
from ..sources import source_bis
from . import cb_meetings
from . import macro_expansion_service as mes
from .policy_service import _BIS_AREA, _BIS_RATE_TYPE, _bis_note, _proxy_rate_type

_BIS_SERIES = "WS_CBPOL"

_START = "2005-01-01"
_MAX_STALE_DAYS = 120

# FRED/OECD fallback candidates; the official BIS policy rate (``_BIS_AREA``) is tried first.
CB_SERIES: dict[str, list[str]] = {
    "Fed": ["FEDFUNDS"],
    "ECB": ["ECBDFR", "IRSTCI01EZM156N"],
    "BoE": ["IRSTCI01GBM156N", "IR3TIB01GBM156N"],
    "BoJ": ["IRSTCI01JPM156N", "IR3TIB01JPM156N"],
    "BoC": ["IRSTCI01CAM156N", "IR3TIB01CAM156N"],
    "RBA": ["IRSTCI01AUM156N", "IR3TIB01AUM156N"],
    "SNB": ["IRSTCI01CHM156N", "IR3TIB01CHM156N"],
}

def _load_meetings() -> list[dict]:
    return cb_meetings.get_meetings()


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


# FRED series -> (title, frequency, is_proxy). The OECD call-money / interbank
# series stand in for the policy rate of banks that have no FRED policy-rate series.
_SERIES_INFO = {
    "FEDFUNDS": ("Effective federal funds rate", "monthly", False),
    "ECBDFR": ("ECB deposit facility rate, euro area", "daily", False),
}


def _is_stale(records: list[dict]) -> bool:
    """True when the last observation is older than ``_MAX_STALE_DAYS``."""
    return bool(records) and (date.today() - date.fromisoformat(records[-1]["date"][:10])).days > _MAX_STALE_DAYS


def _series_info(sid: str) -> tuple[str, str, bool]:
    if sid in _SERIES_INFO:
        return _SERIES_INFO[sid]
    if sid.startswith("IRSTCI01"):
        return f"Overnight call-money / interbank rate ({sid[8:10]}), OECD via FRED", "monthly", True
    if sid.startswith("IR3TIB01"):
        return f"3-month interbank rate ({sid[8:10]}), OECD via FRED", "monthly", True
    return sid, "unknown", False


def _provenance(current: dict[str, dict], balance_sheet: list[dict], meetings: list[dict],
                bis: dict | None = None) -> dict:
    """``current.<bank>`` (rate) and ``history.<bank>`` share a ref naming the series actually picked:
    the BIS policy rate, or the FRED/OECD series that stood in for it."""
    bis = bis or {}
    prov: dict = {"*": pv.ref("bis", _BIS_SERIES,
                              "Central-bank policy rates (BIS; FRED/OECD only as a labelled fallback)",
                              units="percent")}
    for cb, cur in current.items():
        if cur["rate"] is not None:
            flags = ["stale"] if cur.get("stale") else []
            if cur.get("rateSource") == "bis":
                r = pv.ref("bis", _BIS_SERIES, f"{cb}: {cur['rateType']}", units="%", observed=cur.get("asOf"),
                           flags=flags, note=_bis_note((bis.get(_BIS_AREA[cb]) or {}).get("compilation")))
            else:
                title, freq, proxy = _series_info(cur["series"])
                note = "fallback: BIS had no current value"
                if proxy:
                    note = ("Interbank/call-money rate used as a proxy: no FRED policy-rate series is wired "
                            f"up for this bank. {note}.")
                r = pv.fred(cur["series"], title, units="%", frequency=freq, observed=cur.get("asOf"),
                            flags=(["proxy"] if proxy else []) + flags, note=note)
            prov[f"current.{cb}"] = prov[f"history.{cb}"] = r
        if cur.get("next_meeting"):
            row = next((m for m in meetings if m["bank"] == cb and m["date"] == cur["next_meeting"]), {})
            cal = pv.ref("other", None, "Central bank meeting calendar", url=row.get("source"),
                         note="From the bank's published schedule" +
                              (f", retrieved {row['retrieved']} (backend/backend/reference/cb_meetings.json)."
                               if row.get("retrieved") else ", read live from its iCal calendar."))
            cal["providerName"] = f"{cb} published meeting schedule"
            if retrieved := cb_meetings.retrieved_time([row]):
                cal["fetchedAt"] = retrieved
            prov[f"current.{cb}.next_meeting"] = cal
            prov[f"current.{cb}.days_until"] = pv.derived(
                "next meeting date minus today, in days", [f"current.{cb}.next_meeting"],
                title="Days until next meeting")
    if balance_sheet:
        prov["balance_sheet"] = pv.fred(
            "WALCL", "Federal Reserve total assets", units="trillions of USD", frequency="weekly",
            observed=balance_sheet[-1]["date"], transform="FRED value in millions of USD divided by 1,000,000")
    return prov


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

    raw, bis, meetings = await asyncio.gather(
        mes.fetch_fred_series(tuple(all_sids), start=_START),
        source_bis.get_policy_rates_bulk(tuple(_BIS_AREA.values()), since=_START),
        asyncio.to_thread(_load_meetings),
    )

    current: dict[str, dict] = {}
    points: dict[str, list[dict]] = {}
    for cb in CB_SERIES:
        proxy_sid = _pick_series(cb, raw)
        proxy_pts = raw.get(proxy_sid, [])
        bis_pts = [p for p in (bis.get(_BIS_AREA[cb]) or {}).get("points", []) if p.get("value") is not None]
        # Official BIS rate first; the proxy only when BIS has nothing current.
        if bis_pts and not _is_stale(bis_pts):
            source = "bis"
        elif proxy_pts and not _is_stale(proxy_pts):
            source = "proxy"
        elif bis_pts:
            source = "bis"
        else:
            source = "proxy"
        records = points[cb] = bis_pts if source == "bis" else proxy_pts
        sid = _BIS_SERIES if source == "bis" else proxy_sid
        rate = _to_float(records[-1]["value"]) if records else None
        nxt_date, days = _next_meeting(cb, meetings)
        # The picker falls back to a stale series when nothing fresh exists;
        # date it and flag it so an old print is never read as current.
        last_date = records[-1]["date"] if records else None
        current[cb] = {
            "rate":         round(rate, 4) if rate is not None else None,
            "series":       sid,
            "rateSource":   source,
            "rateType":     _BIS_RATE_TYPE[cb] if source == "bis" else _proxy_rate_type(proxy_sid if proxy_pts else None),
            "asOf":         last_date,
            "stale":        _is_stale(records),
            "next_meeting": nxt_date,
            "days_until":   days,
        }

    history_map: dict[str, dict[str, float | None]] = {}
    for cb, records in points.items():
        for rec in records:
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

    return pv.attach({"history": history, "current": current, "balance_sheet": balance_sheet,
                      "schedule_ends": cb_meetings.schedule_end(meetings)},
                     _provenance(current, balance_sheet, meetings, bis))
