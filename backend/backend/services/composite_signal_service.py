"""Composite risk dial — Phase 43 (task D3).

The platform computes the excess bond premium, SLOOS lending standards,
SOFR-IORB reserve scarcity, ANFCI, the term spread and trend — each in its own
tab, none of them combined. Single-signal timing is where blowups come from; an
ensemble is the defensible construction, for reasons that are well established:

* Goyal & Welch (2008) showed most individual predictors fail out of sample.
* Campbell & Thompson (2008) showed that shrinking coefficients and imposing
  sign constraints recovers a small but real part of that — which is why this
  shrinks hard toward zero rather than trusting the raw z-scores.
* McLean & Pontiff (2016) found predictors decay ~58% after publication, so a
  conservative prior on any single input is the right default.

The output is a continuous exposure multiplier, never a binary in/out call. It
is a research aid: the underlying indicators mostly proxy for risk premia, so a
"risk-off" reading means risk is being repriced, not that free money is on offer.
"""
from __future__ import annotations

import logging

import numpy as np

from ..cache import async_cached
from ..config import FRED_API_KEY
from . import macro_expansion_service as mes

log = logging.getLogger(__name__)

# Series pulled for the dial. Kept small and each independently defensible.
_SERIES = ("ANFCI", "DRTSCILM", "T10Y3M", "BAMLH0A0HYM2", "SOFR", "IORB")
_START = "1990-01-01"

_EBP_URL = "https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv"

# Shrinkage applied to every z-score. 0.5 is deliberately aggressive: the
# out-of-sample literature says raw in-sample loadings are roughly twice as
# confident as they deserve to be.
_SHRINKAGE = 0.5

# Exposure multiplier bounds. Never 0 and never levered — a dial, not a switch.
_MIN_EXPOSURE = 0.4
_MAX_EXPOSURE = 1.2

# Trailing window for the z-score, in observations of that series.
_Z_WINDOW = 120


def _zscore(values: list[float], window: int = _Z_WINDOW) -> float | None:
    """Z-score of the latest observation against its trailing window."""
    clean = [v for v in values if v is not None and np.isfinite(v)]
    if len(clean) < 24:
        return None
    tail = clean[-window:]
    mu = float(np.mean(tail))
    sd = float(np.std(tail, ddof=1))
    if sd <= 0:
        return None
    return float((clean[-1] - mu) / sd)


def _series_values(pts: list[dict]) -> list[float]:
    return [p["value"] for p in pts if p.get("value") is not None]


async def _fetch_ebp() -> list[float]:
    """Excess bond premium, monthly, from the Fed's CSV."""
    import asyncio

    from .credit_conditions_service import _fetch_ebp_sync

    rows = await asyncio.to_thread(_fetch_ebp_sync)
    return [r["ebp"] for r in rows if r.get("ebp") is not None]


def _is_empty(result: dict) -> bool:
    return not result or not result.get("available")


@async_cached("composite_risk_dial", skip_if=_is_empty)
async def get_composite_dial() -> dict:
    """Blend the standalone risk indicators into one shrunk exposure multiplier."""
    if not FRED_API_KEY:
        return {"available": False, "reason": "FRED API key required"}

    data = await mes.fetch_fred_series(_SERIES, start=_START)
    ebp_values = await _fetch_ebp()

    # Each component: (label, z-score, sign, why it points that way).
    # `sign` is +1 when a HIGH reading means MORE risk (so less exposure).
    components: list[dict] = []

    def add(key: str, label: str, values: list[float], sign: int, rationale: str) -> None:
        z = _zscore(values)
        if z is None:
            return
        components.append({
            "key": key,
            "label": label,
            "z": round(z, 3),
            "sign": sign,
            "contribution": round(sign * z, 3),
            "rationale": rationale,
        })

    add("ebp", "Excess Bond Premium", ebp_values, +1,
        "High EBP means intermediary risk appetite is impaired (Gilchrist-Zakrajsek 2012).")
    add("anfci", "ANFCI", _series_values(data.get("ANFCI", [])), +1,
        "Positive means financial conditions are tighter than the business cycle warrants.")
    add("sloos", "SLOOS C&I tightening", _series_values(data.get("DRTSCILM", [])), +1,
        "Banks tightening standards predicts output declines (Lown & Morgan 2006).")
    add("hy_oas", "High-yield OAS", _series_values(data.get("BAMLH0A0HYM2", [])), +1,
        "Wide spreads mean credit risk is being repriced.")
    add("term_spread", "10y-3m term spread", _series_values(data.get("T10Y3M", [])), -1,
        "A LOW or inverted spread is the risk signal, so the sign is inverted.")

    # SOFR - IORB has to be differenced before z-scoring: the level is an
    # administered-rate spread that sits near zero by construction.
    sofr = {p["date"]: p["value"] for p in data.get("SOFR", []) if p.get("value") is not None}
    iorb = {p["date"]: p["value"] for p in data.get("IORB", []) if p.get("value") is not None}
    spread = [sofr[d] - iorb[d] for d in sorted(set(sofr) & set(iorb))]
    add("sofr_iorb", "SOFR - IORB", spread, +1,
        "Repo above the Fed's floor means reserves are scarce.")

    if not components:
        return {"available": False, "reason": "no component had enough history"}

    # Average the signed z-scores, then shrink toward zero.
    raw = float(np.mean([c["contribution"] for c in components]))
    shrunk = raw * _SHRINKAGE

    # Map to an exposure multiplier: +1 shrunk sd of risk removes ~30% exposure.
    exposure = float(np.clip(1.0 - 0.30 * shrunk, _MIN_EXPOSURE, _MAX_EXPOSURE))

    if shrunk > 0.5:
        regime = "risk-off"
    elif shrunk < -0.5:
        regime = "risk-on"
    else:
        regime = "neutral"

    return {
        "available": True,
        "compositeZ": round(raw, 3),
        "shrunkZ": round(shrunk, 3),
        "exposureMultiplier": round(exposure, 3),
        "regime": regime,
        "components": components,
        "componentsUsed": len(components),
        "componentsPossible": 6,
        "settings": {
            "shrinkage": _SHRINKAGE,
            "zWindow": _Z_WINDOW,
            "minExposure": _MIN_EXPOSURE,
            "maxExposure": _MAX_EXPOSURE,
        },
        "method": (
            "Each component is z-scored against its trailing 120 observations, "
            "signed so positive always means more risk, averaged over whatever "
            "components have enough history, then shrunk 50% toward zero "
            "(Campbell-Thompson). The exposure multiplier is "
            "clip(1 - 0.30 * shrunk_z, 0.4, 1.2)."
        ),
        "caveat": (
            "This is a research aid, not an allocation instruction. These "
            "indicators mostly proxy for risk premia, so a risk-off reading "
            "means risk is being repriced — you are being paid to hold it, not "
            "warned to avoid it. Shrinkage is deliberately heavy because "
            "individual predictors decay badly out of sample (Goyal & Welch "
            "2008; McLean & Pontiff 2016)."
        ),
    }


# ---------------------------------------------------------------------------
# Self-evaluation
#
# A dial that suggests an exposure multiplier has to show its own record, or it
# is just an opinion with a number attached. This builds the dial historically
# — z-scored on a trailing window at each month, so it is walk-forward rather
# than fitted with hindsight — and compares scaling SPY exposure by it against
# simply holding SPY, net of turnover costs.
#
# If it loses, that is reported. Hiding a losing self-test would make the dial
# marketing rather than research.
# ---------------------------------------------------------------------------

def _rolling_z(values: list[float], window: int = _Z_WINDOW) -> list[float | None]:
    """Z-score at each point against its own trailing window (no hindsight)."""
    out: list[float | None] = []
    for i in range(len(values)):
        if i < 24:
            out.append(None)
            continue
        tail = values[max(0, i - window + 1): i + 1]
        mu = float(np.mean(tail))
        sd = float(np.std(tail, ddof=1))
        out.append(float((values[i] - mu) / sd) if sd > 0 else None)
    return out


def _to_monthly(pts: list[dict]):
    import pandas as pd

    rows = [(p["date"], p["value"]) for p in pts if p.get("value") is not None]
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in rows}).sort_index()
    return s.resample("ME").last().dropna()


def evaluate_dial(
    component_series: dict[str, "pd.Series"],
    signs: dict[str, int],
    spx: "pd.Series",
    cost_bps: float = 10.0,
) -> dict:
    """Compare dial-scaled SPY exposure against buy-and-hold. Pure compute."""
    import pandas as pd

    frame = pd.DataFrame(component_series).dropna(how="all")
    if frame.empty or spx.empty:
        return {"available": False, "reason": "insufficient history"}

    # Walk-forward z per component, then the signed shrunk average.
    z_cols = {}
    for key in frame.columns:
        vals = frame[key].tolist()
        z_cols[key] = _rolling_z(vals)
    z_frame = pd.DataFrame(z_cols, index=frame.index)

    signed = z_frame.copy()
    for key in signed.columns:
        signed[key] = signed[key] * signs.get(key, 1)

    composite = signed.mean(axis=1, skipna=True) * _SHRINKAGE
    exposure = (1.0 - 0.30 * composite).clip(_MIN_EXPOSURE, _MAX_EXPOSURE).dropna()

    spx_m = spx.reindex(exposure.index, method="ffill")
    market_ret = spx_m.pct_change().shift(-1)     # return earned AFTER the reading

    aligned = pd.DataFrame({"exposure": exposure, "ret": market_ret}).dropna()
    if len(aligned) < 24:
        return {"available": False, "reason": "fewer than 24 usable months"}

    turnover = aligned["exposure"].diff().abs()
    turnover = turnover.astype(float).fillna(0.0)
    cost = turnover * (cost_bps / 10_000.0)

    timed_net = aligned["exposure"] * aligned["ret"] - cost
    static = aligned["ret"]

    def _stats(r: "pd.Series") -> dict:
        eq = (1.0 + r).cumprod()
        years = len(r) / 12.0
        cagr = float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 and eq.iloc[-1] > 0 else None
        vol = float(r.std(ddof=1) * np.sqrt(12))
        dd = float((eq / eq.cummax() - 1).min())
        return {
            "cagr": round(cagr, 6) if cagr is not None else None,
            "vol": round(vol, 6),
            "sharpe": round(cagr / vol, 4) if cagr is not None and vol > 0 else None,
            "maxDrawdown": round(dd, 6),
        }

    timed_stats = _stats(timed_net)
    static_stats = _stats(static)
    beats = (
        timed_stats["sharpe"] is not None
        and static_stats["sharpe"] is not None
        and timed_stats["sharpe"] > static_stats["sharpe"]
    )

    return {
        "available": True,
        "months": int(len(aligned)),
        "start": str(aligned.index[0].date()),
        "end": str(aligned.index[-1].date()),
        "timed": timed_stats,
        "static": static_stats,
        "beatsStatic": bool(beats),
        "avgExposure": round(float(aligned["exposure"].mean()), 3),
        "totalCostDrag": round(float(cost.sum()), 6),
        "verdict": (
            "The dial improved risk-adjusted return over this window."
            if beats else
            "The dial did NOT beat simply holding the index over this window, "
            "net of costs. Reported because a self-test only means something if "
            "a negative result is shown too."
        ),
    }


@async_cached("composite_dial_backtest", skip_if=_is_empty)
async def get_dial_backtest(cost_bps: float = 10.0) -> dict:
    """Walk-forward evaluation of the dial as an equity-exposure overlay."""
    if not FRED_API_KEY:
        return {"available": False, "reason": "FRED API key required"}

    import asyncio

    from . import yfinance_service as yfs

    data = await mes.fetch_fred_series(_SERIES, start=_START)

    # One EBP download, not two — an earlier draft fetched it via _fetch_ebp()
    # and then again through _fetch_ebp_sync for the dated rows.
    from .credit_conditions_service import _fetch_ebp_sync
    raw_ebp = await asyncio.to_thread(_fetch_ebp_sync)

    series = {
        "ebp": _to_monthly([{"date": r["date"], "value": r["ebp"]} for r in raw_ebp]),
        "anfci": _to_monthly(data.get("ANFCI", [])),
        "sloos": _to_monthly(data.get("DRTSCILM", [])),
        "hy_oas": _to_monthly(data.get("BAMLH0A0HYM2", [])),
        "term_spread": _to_monthly(data.get("T10Y3M", [])),
    }
    signs = {"ebp": 1, "anfci": 1, "sloos": 1, "hy_oas": 1, "term_spread": -1}

    spx_frame = await asyncio.to_thread(yfs.get_close_frame, ("SPY",), "max")
    if spx_frame is None or spx_frame.empty or "SPY" not in spx_frame.columns:
        return {"available": False, "reason": "SPY price history unavailable"}
    spx = _to_monthly(
        [{"date": str(i.date()), "value": float(v)} for i, v in spx_frame["SPY"].dropna().items()]
    )

    result = await asyncio.to_thread(evaluate_dial, series, signs, spx, cost_bps)
    result["costBps"] = cost_bps
    result["note"] = (
        "Walk-forward: each component is z-scored against its own trailing "
        "window at every month, never the full sample, and the exposure applies "
        "to the FOLLOWING month's return. Costs are charged on changes in "
        "exposure."
    )
    return result
