"""Policy Intelligence Service — CB divergence scores, stance classification, carry differentials.

Phase 18A Task 3.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..cache import async_cached
from . import macro_expansion_service as mes

_CB_CONFIG: dict[str, tuple[str, ...]] = {
    "Fed": ("FEDFUNDS",),
    "ECB": ("ECBMRRFR", "IRSTCI01EZM156N"),
    "BoE": ("IRSTCI01GBM156N", "IR3TIB01GBM156N"),
    "BoJ": ("IRSTCI01JPM156N", "IR3TIB01JPM156N"),
    "BoC": ("IRSTCI01CAM156N", "IR3TIB01CAM156N"),
    "RBA": ("IRSTCI01AUM156N", "IR3TIB01AUM156N"),
    "SNB": ("IRSTCI01CHM156N", "IR3TIB01CHM156N"),
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


async def _fetch_cb_series() -> dict:
    """Fetch all CB FRED series (async — fetch_fred_series is already async)."""
    return await mes.fetch_fred_series(_ALL_SERIES, start=_START)


@async_cached("policy_tracker")
async def get_policy_tracker() -> dict:
    """Return CB divergence table + carry differentials."""
    data = await _fetch_cb_series()

    divergence: list[dict] = []
    rates: dict[str, float | None] = {}

    for cb_name, candidates in _CB_CONFIG.items():
        pts = _pick_series(data, candidates)
        cur = _latest(pts)
        r3m = _rate_n_months_ago(pts, 3)
        r12m = _rate_n_months_ago(pts, 12)

        ch3 = round(cur - r3m, 4) if cur is not None and r3m is not None else None
        ch12 = round(cur - r12m, 4) if cur is not None and r12m is not None else None

        rates[cb_name] = cur
        divergence.append(
            {
                "cb": cb_name,
                "current_rate": cur,
                "change_3m": ch3,
                "change_12m": ch12,
                "stance": _stance(ch12),
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

    return {"divergence": divergence, "carry_differentials": carry}
