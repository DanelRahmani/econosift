"""Credit market pulse — IG/HY OAS, BBB spread, funding stress signal via FRED."""
from __future__ import annotations

import asyncio

from ..cache import async_cached
from . import macro_expansion_service as mes

_SERIES = ("BAMLC0A0CM", "BAMLH0A0HYM2", "BAMLC0A4CBBBOAS", "SOFR", "DTB3", "TEDRATE")
_START = "2000-01-01"

# Thresholds (percentile-based, approximate historical norms)
_HY_STRESS = 7.0  # HY OAS > 700 bps = stress
_IG_WIDE = 2.0    # IG OAS > 200 bps = wide


async def _fetch_series() -> dict:
    return await mes.fetch_fred_series(_SERIES, _START)


def _latest(series: list[dict]) -> float | None:
    for pt in reversed(series):
        if pt.get("value") is not None:
            return pt["value"]
    return None


def _signal(value: float | None, tight: float, wide: float) -> str:
    if value is None:
        return "unknown"
    if value < tight:
        return "tight"
    if value > wide:
        return "wide"
    return "normal"


@async_cached("credit_pulse")
async def get_credit_pulse() -> dict:
    data = await _fetch_series()
    ig = data.get("BAMLC0A0CM", [])
    hy = data.get("BAMLH0A0HYM2", [])
    bbb = data.get("BAMLC0A4CBBBOAS", [])
    sofr = data.get("SOFR", [])
    dtb3 = data.get("DTB3", [])
    ted = data.get("TEDRATE", [])

    ig_cur = _latest(ig)
    hy_cur = _latest(hy)
    bbb_cur = _latest(bbb)
    sofr_v = _latest(sofr)
    dtb3_v = _latest(dtb3)
    # Prefer live SOFR-DTB3; fall back to last TEDRATE observation
    if sofr_v is not None and dtb3_v is not None:
        fund_spread = round(sofr_v - dtb3_v, 4)
    else:
        fund_spread = _latest(ted)

    # Funding spread history: splice TEDRATE (pre-2023) + SOFR-DTB3 (post-2023)
    sofr_map = {pt["date"]: pt["value"] for pt in sofr if pt.get("value") is not None}
    dtb3_map = {pt["date"]: pt["value"] for pt in dtb3 if pt.get("value") is not None}
    ted_pts = [pt for pt in ted if pt.get("value") is not None]
    fund_hist: list[dict] = []
    for pt in ted_pts:
        fund_hist.append({"date": pt["date"], "value": pt["value"]})
    seen = {p["date"] for p in fund_hist}
    for d, sv in sorted(sofr_map.items()):
        if d not in seen and d in dtb3_map:
            fund_hist.append({"date": d, "value": round(sv - dtb3_map[d], 4)})
    fund_hist.sort(key=lambda x: x["date"])

    return {
        "current": {
            "ig_oas": ig_cur,
            "hy_oas": hy_cur,
            "bbb_spread": bbb_cur,
            "funding_spread": fund_spread,
            "hy_ig_ratio": round(hy_cur / ig_cur, 2) if ig_cur and hy_cur and ig_cur > 0 else None,
        },
        "history": {
            "ig_oas": [p for p in ig if p.get("value") is not None],
            "hy_oas": [p for p in hy if p.get("value") is not None],
            "bbb_spread": [p for p in bbb if p.get("value") is not None],
            "funding_spread": fund_hist,
        },
        "signals": {
            "ig_oas": _signal(ig_cur, 0.8, _IG_WIDE),
            "hy_oas": _signal(hy_cur, 3.0, _HY_STRESS),
            "stress": bool(
                (hy_cur is not None and hy_cur > _HY_STRESS)
                or (fund_spread is not None and fund_spread > 0.5)
            ),
        },
    }
