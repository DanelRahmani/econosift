"""Funding and Liquidity service using FRED data."""
from __future__ import annotations

import logging

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

    return {
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
    }
