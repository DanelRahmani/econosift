"""Policy Intelligence Service — CB divergence scores, stance classification, carry differentials.

Phase 18A Task 3.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

from .. import provenance as pv
from ..cache import async_cached
from ..sources import source_bis
from . import macro_expansion_service as mes

_CB_CONFIG: dict[str, tuple[str, ...]] = {
    "Fed": ("FEDFUNDS",),
    "ECB": ("ECBDFR", "IRSTCI01EZM156N"),
    "BoE": ("IRSTCI01GBM156N", "IR3TIB01GBM156N"),
    "BoJ": ("IRSTCI01JPM156N", "IR3TIB01JPM156N"),
    "BoC": ("IRSTCI01CAM156N", "IR3TIB01CAM156N"),
    "RBA": ("IRSTCI01AUM156N", "IR3TIB01AUM156N"),
    "SNB": ("IRSTCI01CHM156N", "IR3TIB01CHM156N"),
}

# BIS reference area of each bank's policy rate (WS_CBPOL) and what that rate is.
# BIS is the primary source; the FRED/OECD candidates above are the labelled fallback.
_BIS_AREA: dict[str, str] = {
    "Fed": "US", "ECB": "XM", "BoE": "GB", "BoJ": "JP", "BoC": "CA", "RBA": "AU", "SNB": "CH",
}
_BIS_RATE_TYPE: dict[str, str] = {
    "Fed": "target-range midpoint",
    "ECB": "deposit facility rate",
    "BoE": "Bank Rate",
    "BoJ": "overnight call-rate target",
    "BoC": "overnight rate target",
    "RBA": "cash rate target",
    "SNB": "SNB policy rate",
}

# De-duplicated flat tuple of all series IDs
_ALL_SERIES: tuple[str, ...] = tuple(dict.fromkeys(s for sids in _CB_CONFIG.values() for s in sids))

_START = "2005-01-01"
_MAX_STALE_DAYS = 120


def _latest(pts: list[dict]) -> float | None:
    """Return the value of the last non-null data point."""
    for pt in reversed(pts):
        v = pt.get("value")
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _pick_series(data: dict, candidates: tuple[str, ...]) -> list[dict]:
    """Return the freshest non-stale series among candidates.

    Iterates all candidates and picks the one whose last data point is most
    recent. Falls back to the freshest available if every candidate is stale.
    """
    # Naive UTC: compared against naive datetimes parsed via strptime below.
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=_MAX_STALE_DAYS)
    best_pts: list[dict] = []
    best_date = datetime(2000, 1, 1)

    for sid in candidates:
        pts = [p for p in data.get(sid, []) if p.get("value") is not None]
        if not pts:
            continue
        try:
            last = datetime.strptime(pts[-1]["date"][:10], "%Y-%m-%d")
        except (ValueError, KeyError):
            continue
        if last > best_date:
            best_pts = pts
            best_date = last

    # Return the freshest series found; the caller gets an empty list only if
    # no series had any data at all.
    # Honour staleness: if the best series is older than the cutoff, still
    # return it (the stance will degrade gracefully), but prefer a fresh series
    # if one existed.  The loop above already picks the most-recent candidate,
    # which is the desired behaviour.
    return best_pts


def _is_stale(pts: list[dict]) -> bool:
    """True when the chosen series' last observation is past the cutoff
    (the picker returns a stale series when no fresh one exists)."""
    if not pts:
        return False
    last = datetime.strptime(pts[-1]["date"][:10], "%Y-%m-%d")
    return (datetime.now(timezone.utc).replace(tzinfo=None) - last).days > _MAX_STALE_DAYS


def _rate_n_months_ago(pts: list[dict], months: int) -> float | None:
    """Find the last value at or before `months` months before the final point."""
    if not pts:
        return None
    try:
        end_date = datetime.strptime(pts[-1]["date"][:10], "%Y-%m-%d")
    except (ValueError, KeyError):
        return None
    target = end_date - timedelta(days=30 * months)
    for pt in reversed(pts):
        try:
            d = datetime.strptime(pt["date"][:10], "%Y-%m-%d")
        except (ValueError, KeyError):
            continue
        if d <= target and pt.get("value") is not None:
            try:
                return float(pt["value"])
            except (TypeError, ValueError):
                continue
    return None


def _stance(change_12m: float | None) -> str:
    if change_12m is None:
        return "unknown"
    if change_12m > 0.25:
        return "tightening"
    if change_12m < -0.25:
        return "easing"
    return "on_hold"


# Series that are the bank's own policy rate; the rest are OECD money-market rates.
_POLICY_RATE_SERIES = {
    "FEDFUNDS": ("Effective federal funds rate", "monthly"),
    "ECBDFR": ("ECB deposit facility rate", "daily"),
}


def _proxy_rate_type(sid: str | None) -> str:
    """What a FRED/OECD fallback series actually is, for the table's Rate column."""
    if sid == "FEDFUNDS":
        return "effective fed funds (proxy)"
    if sid == "ECBDFR":
        return "deposit facility rate (FRED)"
    if sid and sid.startswith("IRSTCI"):
        return "money-market proxy (OECD)"
    if sid and sid.startswith("IR3TIB"):
        return "3-month interbank proxy (OECD)"
    return "unavailable"


def _picked_sid(data: dict, candidates: tuple[str, ...]) -> str | None:
    """Series id ``_pick_series`` chose: the candidate with the latest last point
    (first listed wins ties)."""
    best_sid, best_date = None, ""
    for sid in candidates:
        pts = [p for p in data.get(sid, []) if p.get("value") is not None]
        if pts and pts[-1]["date"][:10] > best_date:
            best_sid, best_date = sid, pts[-1]["date"][:10]
    return best_sid


def _bis_note(compilation: str | None) -> str | None:
    """First clause of the BIS compilation note (which rate BIS reports)."""
    if not compilation:
        return None
    return re.split(r"[;.]\s|\n", compilation.strip())[0][:200]


def _provenance(data: dict, divergence: list[dict], pairs: list[tuple], bis: dict | None = None) -> dict:
    """Source map for the policy tracker (see provenance.py)."""
    bis = bis or {}
    prov: dict = {
        "*": pv.ref("bis", "WS_CBPOL",
                    "Central-bank policy rates (BIS; FRED/OECD only as a labelled fallback)",
                    units="percent"),
    }
    for d in divergence:
        cb = d["cb"]
        row = f"divergence.{cb}"
        if d.get("rateSource") == "bis":
            flags = ["stale"] if d.get("stale") else []
            prov[row] = pv.ref("bis", "WS_CBPOL", f"{cb}: {d['rateType']}", units="percent",
                               observed=d.get("asOf"), flags=flags,
                               note=_bis_note((bis.get(_BIS_AREA[cb]) or {}).get("compilation")))
            sid = None
        else:
            sid = _picked_sid(data, _CB_CONFIG[cb])
        if sid:
            fallback = "fallback: BIS had no current value"
            if sid in _POLICY_RATE_SERIES:
                title, freq = _POLICY_RATE_SERIES[sid]
                flags, note = [], fallback
            else:
                title = ("OECD immediate (call money/interbank) rate" if sid.startswith("IRSTCI")
                         else "OECD 3-month interbank rate")
                freq = "monthly"
                flags = ["proxy"]
                note = (f"This is the OECD money-market rate for {cb}'s market, not the announced "
                        f"policy rate, and can differ from it. {fallback}.")
            if d.get("stale"):
                flags.append("stale")
            prov[row] = pv.fred(sid, f"{cb}: {title}", units="percent", frequency=freq,
                                observed=d.get("asOf"), flags=flags, note=note)
        for key, months in (("change_3m", 3), ("change_12m", 12)):
            prov[f"{row}.{key}"] = pv.derived(
                f"latest rate - rate {months} months (30-day months) before the last observation",
                [row], title=f"{cb} {months}-month rate change", observed=d.get("asOf"))
        prov[f"{row}.stance"] = pv.derived(
            "tightening if 12m change > +0.25pp, easing if < -0.25pp, otherwise on_hold; unknown without a 12m change",
            [f"{row}.change_12m"], title=f"{cb} policy stance", observed=d.get("asOf"))
        prov[f"{row}.divergence_rank"] = pv.derived(
            "rank of the 12-month rate change, most tightening = 1", [f"{row}.change_12m"],
            title=f"{cb} divergence rank", observed=d.get("asOf"))
    for pair, base_cb, quote_cb in pairs:
        prov[f"carry_differentials.{pair}"] = pv.derived(
            f"{base_cb} rate - {quote_cb} rate (latest values; ECB/BoE/BoJ/BoC/RBA/SNB minus Fed)",
            [f"divergence.{base_cb}", f"divergence.{quote_cb}"], title=f"{pair} carry differential")
    return prov


async def _fetch_cb_series() -> dict:
    """Fetch all CB FRED series (async — fetch_fred_series is already async)."""
    return await mes.fetch_fred_series(_ALL_SERIES, start=_START)


@async_cached("policy_tracker")
async def get_policy_tracker() -> dict:
    """Return CB divergence table + carry differentials."""
    data, bis = await asyncio.gather(
        _fetch_cb_series(),
        source_bis.get_policy_rates_bulk(tuple(_BIS_AREA.values())),
    )

    divergence: list[dict] = []
    rates: dict[str, float | None] = {}

    for cb_name, candidates in _CB_CONFIG.items():
        bis_pts = [p for p in (bis.get(_BIS_AREA[cb_name]) or {}).get("points", [])
                   if p.get("value") is not None]
        proxy_pts = _pick_series(data, candidates)
        # Official BIS rate first; the proxy only when BIS has nothing current.
        if bis_pts and not _is_stale(bis_pts):
            pts, source = bis_pts, "bis"
        elif proxy_pts and not _is_stale(proxy_pts):
            pts, source = proxy_pts, "proxy"
        elif bis_pts:
            pts, source = bis_pts, "bis"
        else:
            pts, source = proxy_pts, "proxy"
        rate_type = (_BIS_RATE_TYPE[cb_name] if source == "bis"
                     else _proxy_rate_type(_picked_sid(data, candidates)))
        cur = _latest(pts)
        r3m = _rate_n_months_ago(pts, 3)
        r12m = _rate_n_months_ago(pts, 12)

        ch3 = round(cur - r3m, 4) if cur is not None and r3m is not None else None
        ch12 = round(cur - r12m, 4) if cur is not None and r12m is not None else None

        rates[cb_name] = cur
        divergence.append(
            {
                "cb": cb_name,
                "rateSource": source,
                "rateType": rate_type,
                "current_rate": cur,
                "change_3m": ch3,
                "change_12m": ch12,
                "stance": _stance(ch12),
                "asOf": pts[-1]["date"][:10] if pts else None,
                "stale": _is_stale(pts),
            }
        )

    # Rank most-tightening first (descending by 12m change)
    divergence.sort(key=lambda d: (d["change_12m"] is None, -(d["change_12m"] or 0)))
    for i, d in enumerate(divergence):
        d["divergence_rank"] = i + 1

    # G10 carry differentials: base_rate − quote_rate
    pairs = [
        ("EURUSD", "ECB", "Fed"),
        ("GBPUSD", "BoE", "Fed"),
        ("JPYUSD", "BoJ", "Fed"),
        ("CADUSD", "BoC", "Fed"),
        ("AUDUSD", "RBA", "Fed"),
        ("CHFUSD", "SNB", "Fed"),
    ]
    carry: dict[str, float | None] = {}
    for pair, base_cb, quote_cb in pairs:
        b, q = rates.get(base_cb), rates.get(quote_cb)
        carry[pair] = round(b - q, 4) if b is not None and q is not None else None

    return pv.attach({"divergence": divergence, "carry_differentials": carry},
                     _provenance(data, divergence, pairs, bis))
