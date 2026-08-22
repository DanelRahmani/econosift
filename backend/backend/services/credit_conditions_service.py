"""Credit & funding conditions — Phase 39.

Four high-evidence indicators that the platform did not previously carry:

* **SOFR - IORB** — reserve scarcity. Repo printing above the Fed's administered
  floor is the cleanest sign that bank reserves have moved from abundant to
  scarce. Spliced with IOER before 2021-07-29 (IORB replaced IOER on that date;
  the two series are contiguous).
* **SLOOS net % tightening C&I standards** (``DRTSCILM``) — Lown & Morgan (2006,
  JMCB) find lending standards predict output declines better than the funds
  rate itself; Bassett, Chosak, Driscoll & Zakrajsek (2014, JME) isolate the
  credit-supply shock. Quarterly.
* **Excess Bond Premium** (Gilchrist & Zakrajsek 2012, AER) — the component of
  corporate spreads not explained by default risk, i.e. a direct read on
  intermediary risk appetite. Published monthly by the Federal Reserve Board as
  a CSV (not on FRED), which also ships the GZ credit spread and the associated
  recession probability.
* **NFCI / ANFCI** (Chicago Fed) — weekly composite financial conditions. ANFCI
  is orthogonalised to the business cycle, so it isolates financial conditions
  that are loose or tight *relative to* where the economy is.
"""
from __future__ import annotations

import asyncio
import io
import logging

import httpx
import pandas as pd

from ..cache import async_cached
from ..config import FRED_API_KEY
from . import macro_expansion_service as mes

log = logging.getLogger(__name__)

# IORB starts 2021-07-29; IOER covers 2008-10-09..2021-07-28.
_SERIES = ("SOFR", "IORB", "IOER", "DRTSCILM", "NFCI", "ANFCI")
_START = "2008-01-01"

_EBP_URL = "https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv"

# Interpretation thresholds.
_SOFR_IORB_STRESS = 0.10   # pp above the floor = clear reserve scarcity
_SLOOS_TIGHT = 20.0        # net % tightening historically associated with contraction
_EBP_STRESS = 0.50         # EBP in std-dev-like units; >0.5 = impaired risk appetite
_NFCI_TIGHT = 0.0          # index is normalised so 0 = average conditions


def _latest(pts: list[dict]) -> float | None:
    """Most recent non-None value in a [{date, value}] series."""
    for pt in reversed(pts):
        v = pt.get("value")
        if v is not None:
            return v
    return None


def _clean(pts: list[dict]) -> list[dict]:
    return [p for p in pts if p.get("value") is not None]


def _spliced_floor(iorb: list[dict], ioer: list[dict]) -> list[dict]:
    """IOER before IORB starts, IORB thereafter — the administered floor."""
    iorb_clean = _clean(iorb)
    if not iorb_clean:
        return _clean(ioer)
    first_iorb = iorb_clean[0]["date"]
    out = [p for p in _clean(ioer) if p["date"] < first_iorb]
    out.extend(iorb_clean)
    out.sort(key=lambda p: p["date"])
    return out


def _spread(minuend: list[dict], subtrahend: list[dict]) -> list[dict]:
    """Date-aligned difference of two series."""
    sub_map = {p["date"]: p["value"] for p in _clean(subtrahend)}
    return [
        {"date": p["date"], "value": round(p["value"] - sub_map[p["date"]], 4)}
        for p in _clean(minuend)
        if p["date"] in sub_map
    ]


def _fetch_ebp_sync() -> list[dict]:
    """Download the Fed's Excess Bond Premium CSV.

    Direct CSV download (no HTML scraping). Columns: date, gz_spread, ebp,
    est_prob. Returns [] on any failure so the caller can degrade gracefully —
    the cache guard then refuses to persist a partial payload.
    """
    try:
        resp = httpx.get(_EBP_URL, timeout=45, headers={"User-Agent": "axiom-finance/1.0"})
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if df.empty or "ebp" not in df.columns:
            log.warning("EBP CSV missing expected columns: %s", list(df.columns))
            return []
        df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        out: list[dict] = []
        for _, row in df.iterrows():
            def _f(col: str) -> float | None:
                v = row.get(col)
                return None if pd.isna(v) else round(float(v), 4)

            out.append({
                "date": str(row["date"].date()),
                "ebp": _f("ebp"),
                "gz_spread": _f("gz_spread"),
                "est_prob": _f("est_prob"),
            })
        return out
    except Exception as exc:
        log.warning("EBP download failed: %s", exc)
        return []


def _signal(value: float | None, threshold: float, *, higher_is_worse: bool = True) -> str:
    if value is None:
        return "unknown"
    if higher_is_worse:
        return "stress" if value > threshold else "normal"
    return "stress" if value < threshold else "normal"


def _is_empty(result: dict) -> bool:
    """Never cache a payload that carries no usable indicator."""
    if not result or result.get("error"):
        return True
    kpis = result.get("kpis") or {}
    return all(kpis.get(k) is None for k in ("sofr_iorb", "sloos_ci", "ebp", "anfci"))


@async_cached("credit_conditions", skip_if=_is_empty)
async def get_credit_conditions() -> dict:
    """Reserve scarcity, lending standards, excess bond premium, NFCI/ANFCI."""
    if not FRED_API_KEY:
        return {"error": "FRED API key required"}

    fred_task = mes.fetch_fred_series(_SERIES, start=_START)
    ebp_task = asyncio.to_thread(_fetch_ebp_sync)
    data, ebp_rows = await asyncio.gather(fred_task, ebp_task)

    sofr = _clean(data.get("SOFR", []))
    floor = _spliced_floor(data.get("IORB", []), data.get("IOER", []))
    sofr_iorb = _spread(sofr, floor)

    sloos = _clean(data.get("DRTSCILM", []))
    nfci = _clean(data.get("NFCI", []))
    anfci = _clean(data.get("ANFCI", []))

    ebp_series = [{"date": r["date"], "value": r["ebp"]} for r in ebp_rows if r["ebp"] is not None]
    gz_series = [{"date": r["date"], "value": r["gz_spread"]} for r in ebp_rows if r["gz_spread"] is not None]
    gz_prob = [{"date": r["date"], "value": r["est_prob"]} for r in ebp_rows if r["est_prob"] is not None]

    sofr_iorb_v = _latest(sofr_iorb)
    sloos_v = _latest(sloos)
    ebp_v = _latest(ebp_series)
    nfci_v = _latest(nfci)
    anfci_v = _latest(anfci)
    gz_prob_v = _latest(gz_prob)

    return {
        "kpis": {
            "sofr_iorb": sofr_iorb_v,
            "sloos_ci": sloos_v,
            "ebp": ebp_v,
            "gz_spread": _latest(gz_series),
            "gz_recession_prob": gz_prob_v,
            "nfci": nfci_v,
            "anfci": anfci_v,
        },
        "history": {
            "sofr_iorb": sofr_iorb,
            "sloos_ci": sloos,
            "ebp": ebp_series,
            "gz_spread": gz_series,
            "gz_recession_prob": gz_prob,
            "nfci": nfci,
            "anfci": anfci,
        },
        "signals": {
            "sofr_iorb": _signal(sofr_iorb_v, _SOFR_IORB_STRESS),
            "sloos_ci": _signal(sloos_v, _SLOOS_TIGHT),
            "ebp": _signal(ebp_v, _EBP_STRESS),
            "anfci": _signal(anfci_v, _NFCI_TIGHT),
        },
        "asOf": {
            "sofr_iorb": sofr_iorb[-1]["date"] if sofr_iorb else None,
            "sloos_ci": sloos[-1]["date"] if sloos else None,
            "ebp": ebp_series[-1]["date"] if ebp_series else None,
            "nfci": nfci[-1]["date"] if nfci else None,
        },
        "sources": {
            "sofr_iorb": "FRED SOFR, IORB (IOER spliced pre-2021-07-29)",
            "sloos_ci": "FRED DRTSCILM — Fed Senior Loan Officer Opinion Survey, quarterly",
            "ebp": "Federal Reserve Board, Gilchrist-Zakrajsek excess bond premium (monthly CSV)",
            "nfci": "FRED NFCI / ANFCI — Chicago Fed, weekly",
        },
    }
