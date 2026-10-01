"""Funding and Liquidity service using FRED data."""
from __future__ import annotations

import logging
from datetime import date

from .. import provenance as pv
from ..cache import async_cached
from ..config import FRED_API_KEY
from . import macro_expansion_service as mes

log = logging.getLogger(__name__)

_FUNDING_SERIES = ("M2SL", "SOFR", "CPF3M", "FEDFUNDS")
_START = "2024-01-01"


def _latest(pts: list[dict]) -> float | None:
    for pt in reversed(pts):
        v = pt.get("value")
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _provenance(m2_pts: list[dict], sofr_pts: list[dict], cpf3m_pts: list[dict], ff_pts: list[dict],
                cp_spread: list[dict], sofr_ff_spread: list[dict]) -> dict:
    def last(pts: list[dict]) -> str | None:
        dates = [p["date"] for p in pts if p.get("value") is not None]
        return dates[-1] if dates else None

    m2 = pv.fred("M2SL", "M2 money stock", units="billions of USD", frequency="monthly", observed=last(m2_pts))
    sofr = pv.fred("SOFR", "Secured Overnight Financing Rate", units="%", frequency="daily",
                   observed=last(sofr_pts))
    cpf3m = pv.fred("CPF3M", "3-month AA financial commercial paper rate", units="%", frequency="monthly",
                    observed=last(cpf3m_pts))
    ff = pv.fred("FEDFUNDS", "Effective federal funds rate", units="%", frequency="monthly",
                 observed=last(ff_pts))
    cp_obs = last(cp_spread)
    if cp_obs and (date.today() - date.fromisoformat(cp_obs[:10])).days > 120:
        cpf3m["flags"] = ["stale"]
    cp = pv.derived("CPF3M - FEDFUNDS, on dates where both have a value (percentage points)", [cpf3m, ff],
                    title="Commercial paper spread", observed=cp_obs, flags=cpf3m.get("flags", ()))
    sf = pv.derived("SOFR - FEDFUNDS, on dates where both have a value (percentage points); FEDFUNDS is "
                    "monthly, so only its dates are compared", [sofr, ff],
                    title="SOFR - fed funds spread", observed=last(sofr_ff_spread))
    return {
        "*": pv.ref("fred", None, "Federal Reserve Economic Data"),
        "m2": m2, "sofr": sofr, "cp_spread": cp, "sofr_ff_spread": sf,
        "kpis.m2_latest": m2, "kpis.sofr_latest": sofr, "kpis.cp_spread_latest": cp,
        "kpis.sofr_ff_latest": sf,
    }


@async_cached("funding_liquidity")
async def get_funding_liquidity() -> dict:
    """Fetch M2SL, SOFR, CP spread, and SOFR-FF spread from FRED."""
    if not FRED_API_KEY:
        return {"error": "FRED API key required"}

    data = await mes.fetch_fred_series(_FUNDING_SERIES, start=_START)

    m2_pts = data.get("M2SL", [])
    sofr_pts = data.get("SOFR", [])
    cpf3m_pts = data.get("CPF3M", [])
    ff_pts = data.get("FEDFUNDS", [])

    # CP spread = CPF3M - FEDFUNDS (align by date)
    ff_map = {p["date"]: p["value"] for p in ff_pts if p.get("value") is not None}
    cp_spread: list[dict] = []
    for p in cpf3m_pts:
        if p.get("value") is not None and p["date"] in ff_map:
            cp_spread.append({
                "date": p["date"],
                "value": round(p["value"] - ff_map[p["date"]], 4),
            })

    # SOFR-FF spread
    sofr_map = {p["date"]: p["value"] for p in sofr_pts if p.get("value") is not None}
    sofr_ff_spread: list[dict] = []
    for p in ff_pts:
        if p.get("value") is not None and p["date"] in sofr_map:
            sofr_ff_spread.append({
                "date": p["date"],
                "value": round(sofr_map[p["date"]] - p["value"], 4),
            })

    return pv.attach({
        "m2": m2_pts,
        "sofr": sofr_pts,
        "cp_spread": cp_spread,
        "sofr_ff_spread": sofr_ff_spread,
        "kpis": {
            "m2_latest": _latest(m2_pts),
            "sofr_latest": _latest(sofr_pts),
            "cp_spread_latest": _latest(cp_spread),
            "sofr_ff_latest": _latest(sofr_ff_spread),
        },
    }, _provenance(m2_pts, sofr_pts, cpf3m_pts, ff_pts, cp_spread, sofr_ff_spread))
