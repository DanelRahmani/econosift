"""Credit market pulse — IG/HY OAS, BBB spread, funding stress signal via FRED."""
from __future__ import annotations

import asyncio

from .. import provenance as pv
from ..cache import async_cached
from . import macro_expansion_service as mes

# BBB OAS is BAMLC0A4CBBB on FRED; the "...OAS"-suffixed id does not exist and
# silently returned nothing, leaving bbb_spread permanently null.
_SERIES = ("BAMLC0A0CM", "BAMLH0A0HYM2", "BAMLC0A4CBBB", "SOFR", "DTB3", "TEDRATE")
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


def _last_obs(series: list[dict]) -> str | None:
    for pt in reversed(series):
        if pt.get("value") is not None:
            return str(pt["date"])[:10]
    return None


def _provenance(data: dict) -> dict:
    """Source map for the credit pulse (see provenance.py)."""
    obs = {sid: _last_obs(data.get(sid, [])) for sid in _SERIES}
    prov: dict = {"*": pv.ref("fred", None, "ICE BofA credit spreads and US funding rates", frequency="daily")}
    fields = {
        "ig_oas": ("BAMLC0A0CM", "ICE BofA US Corporate Index option-adjusted spread (investment grade)"),
        "hy_oas": ("BAMLH0A0HYM2", "ICE BofA US High Yield Index option-adjusted spread"),
        "bbb_spread": ("BAMLC0A4CBBB", "ICE BofA BBB US Corporate Index option-adjusted spread"),
    }
    for key, (sid, title) in fields.items():
        for block in ("current", "history"):
            prov[f"{block}.{key}"] = pv.fred(sid, title, units="percentage points", frequency="daily",
                                             observed=obs[sid])
    both = [d for d in (obs["SOFR"], obs["DTB3"]) if d]
    older = min(both) if len(both) == 2 else None
    prov["current.funding_spread"] = pv.derived(
        "SOFR - DTB3 (secured overnight financing rate minus 3-month T-bill secondary-market rate), "
        "latest value of each", [pv.fred("SOFR", "Secured Overnight Financing Rate", units="percent",
                                        frequency="daily", observed=obs["SOFR"]),
                                 pv.fred("DTB3", "3-month Treasury bill secondary-market rate",
                                         units="percent", frequency="daily", observed=obs["DTB3"])],
        title="Funding spread", observed=older)
    prov["history.funding_spread"] = pv.derived(
        "TEDRATE where it exists (to Jan 2022), otherwise SOFR - DTB3 on dates where both exist. "
        "The two definitions differ, so the series is spliced, not continuous.",
        [pv.fred("TEDRATE", "TED spread (3-month LIBOR minus 3-month T-bill)", units="percent",
                 frequency="daily", observed=obs["TEDRATE"], flags=["stale"],
                 note="Discontinued with LIBOR in January 2022."),
         pv.fred("SOFR", "Secured Overnight Financing Rate", units="percent", frequency="daily",
                 observed=obs["SOFR"]),
         pv.fred("DTB3", "3-month Treasury bill secondary-market rate", units="percent",
                 frequency="daily", observed=obs["DTB3"])],
        title="Funding spread history", observed=older)
    ratio_dates = [d for d in (obs["BAMLH0A0HYM2"], obs["BAMLC0A0CM"]) if d]
    ratio_obs = min(ratio_dates) if len(ratio_dates) == 2 else None
    prov["current.hy_ig_ratio"] = pv.derived(
        "HY OAS / IG OAS", ["current.hy_oas", "current.ig_oas"], title="HY to IG spread ratio",
        observed=ratio_obs)
    prov["signals"] = pv.derived(
        "ig_oas: tight < 0.8, wide > 2.0 (pp); hy_oas: tight < 3.0, wide > 7.0 (pp); "
        "stress = HY OAS > 7.0 or funding spread > 0.5. Thresholds are approximate fixed norms.",
        ["current.ig_oas", "current.hy_oas", "current.funding_spread"], title="Credit signals")
    return prov


@async_cached("credit_pulse")
async def get_credit_pulse() -> dict:
    data = await _fetch_series()
    ig = data.get("BAMLC0A0CM", [])
    hy = data.get("BAMLH0A0HYM2", [])
    bbb = data.get("BAMLC0A4CBBB", [])
    sofr = data.get("SOFR", [])
    dtb3 = data.get("DTB3", [])
    ted = data.get("TEDRATE", [])

    ig_cur = _latest(ig)
    hy_cur = _latest(hy)
    bbb_cur = _latest(bbb)
    sofr_v = _latest(sofr)
    dtb3_v = _latest(dtb3)
    # Live SOFR-DTB3 only. TEDRATE ended in Jan 2022 with LIBOR, so its last
    # print must not stand in for a current reading (audit D-16).
    fund_spread = round(sofr_v - dtb3_v, 4) if sofr_v is not None and dtb3_v is not None else None

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

    return pv.attach({
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
    }, _provenance(data))
