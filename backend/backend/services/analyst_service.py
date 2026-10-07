"""Analyst-data service: price targets, consensus ratings, earnings surprises,
forward estimates, and growth estimates — all sourced from yfinance.

All attribute accesses are guarded; the function never raises.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf

from .. import provenance as pv
from ..cache import cached


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean(x: Any) -> float | None:
    """Convert to float, return None for NaN/inf/unconvertible."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _safe_df(t: Any, attr: str) -> pd.DataFrame | None:
    """Return DataFrame from a Ticker attribute/method; None on any error."""
    try:
        if hasattr(t, attr):
            df = getattr(t, attr)
            if callable(df):
                df = df()
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
    except Exception:
        pass
    return None


def _safe_call(t: Any, method: str, *args, **kwargs) -> pd.DataFrame | None:
    """Call a Ticker method; return None on any error."""
    try:
        fn = getattr(t, method, None)
        if callable(fn):
            result = fn(*args, **kwargs)
            if isinstance(result, pd.DataFrame) and not result.empty:
                return result
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("analyst")
def analyst_data(ticker: str) -> dict:
    """Return a rich analyst-data bundle for *ticker*.

    All sub-keys fall back to None / [] so callers never see KeyError or NaN.
    """
    t = yf.Ticker(ticker)

    # ── 1. Pull .info once ──────────────────────────────────────────────────
    info: dict = {}
    try:
        info = t.get_info() or {}
    except Exception:
        try:
            info = t.info or {}
        except Exception:
            info = {}

    currency: str = info.get("currency") or "USD"

    # Current price
    price: float | None = _clean(info.get("currentPrice") or info.get("regularMarketPrice"))

    # ── 2. Price-target band ────────────────────────────────────────────────
    mean_price = _clean(info.get("targetMeanPrice"))
    high_price = _clean(info.get("targetHighPrice"))
    low_price = _clean(info.get("targetLowPrice"))
    median_price = _clean(info.get("targetMedianPrice"))
    analyst_count = info.get("numberOfAnalystOpinions")
    if analyst_count is not None:
        try:
            analyst_count = int(analyst_count)
        except (TypeError, ValueError):
            analyst_count = None

    upside_pct: float | None = None
    if mean_price is not None and price and price > 0:
        upside_pct = _clean((mean_price - price) / price)

    price_target = {
        "meanPrice": mean_price,
        "highPrice": high_price,
        "lowPrice": low_price,
        "medianPrice": median_price,
        "numberOfAnalysts": analyst_count,
        "upsidePct": upside_pct,
    }

    # ── 3. Consensus rating ─────────────────────────────────────────────────
    rec_mean = _clean(info.get("recommendationMean"))
    rec_key: str | None = info.get("recommendationKey") or None

    # Recommendation history (DataFrame: index=period, cols=strongBuy/buy/hold/sell/strongSell)
    rec_history: list[dict] = []
    recs_df = _safe_df(t, "recommendations")
    if recs_df is not None:
        try:
            # Keep most-recent ~12 rows; ensure expected columns exist
            expected_cols = {"strongBuy", "buy", "hold", "sell", "strongSell"}
            available = expected_cols & set(recs_df.columns)
            tail = recs_df.tail(12)
            for period_label, row in tail.iterrows():
                entry: dict = {"period": str(period_label)}
                for col in expected_cols:
                    entry[col] = int(row[col]) if col in available and pd.notna(row.get(col)) else 0
                rec_history.append(entry)
        except Exception:
            rec_history = []

    consensus = {
        "recommendationMean": rec_mean,
        "recommendationKey": rec_key,
        "history": rec_history,
    }

    # ── 4. Earnings surprises (up to 8 quarters) ────────────────────────────
    earning_surprises: list[dict] = []

    # Try earnings_dates attribute first, then get_earnings_dates() method
    ed_df: pd.DataFrame | None = _safe_df(t, "earnings_dates")
    if ed_df is None:
        ed_df = _safe_call(t, "get_earnings_dates")

    if ed_df is not None:
        try:
            # Normalize column names: strip whitespace
            ed_df.columns = [str(c).strip() for c in ed_df.columns]

            # Identify estimate / actual / surprise columns (name varies across yf versions)
            def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
                for c in candidates:
                    if c in df.columns:
                        return c
                return None

            est_col = _find_col(ed_df, ["EPS Estimate", "Eps Estimate", "epsestimate"])
            act_col = _find_col(ed_df, ["Reported EPS", "Reported Eps", "reportedeps"])
            surp_col = _find_col(ed_df, ["Surprise(%)", "Surprise", "surprisePct"])

            # Filter to rows with an actual reported value
            if act_col and not ed_df[act_col].isna().all():
                filtered = ed_df[ed_df[act_col].notna()].head(8)
                for dt_idx, row in filtered.iterrows():
                    try:
                        dt_str = pd.to_datetime(str(dt_idx)).strftime("%Y-%m-%d")
                    except Exception:
                        dt_str = str(dt_idx)[:10]

                    eps_est = _clean(row[est_col]) if est_col else None
                    eps_act = _clean(row[act_col])
                    surp = _clean(row[surp_col]) if surp_col else None

                    # Compute surprise (percent) if missing but both estimates available
                    if surp is None and eps_est is not None and eps_act is not None and eps_est != 0:
                        surp = _clean((eps_act - eps_est) / abs(eps_est) * 100.0)  # percent, like Yahoo's Surprise(%)

                    earning_surprises.append({
                        "date": dt_str,
                        "epsEstimate": eps_est,
                        "epsActual": eps_act,
                        "surprisePct": surp,
                    })
        except Exception:
            earning_surprises = []

    # ── 5. Forward estimates ────────────────────────────────────────────────
    estimates: dict = {}

    # Try DataFrame attributes first
    ee_df = _safe_df(t, "earnings_estimate")
    if ee_df is None:
        ee_df = _safe_df(t, "earningsEstimate")

    re_df = _safe_df(t, "revenue_estimate")
    if re_df is None:
        re_df = _safe_df(t, "revenueEstimate")

    if ee_df is not None:
        try:
            ee_dict: dict = {}
            for period, row in ee_df.iterrows():
                period_data: dict = {}
                for col in ee_df.columns:
                    period_data[str(col)] = _clean(row[col])
                ee_dict[str(period)] = period_data
            if ee_dict:
                estimates["earningsEstimate"] = ee_dict
        except Exception:
            pass

    if re_df is not None:
        try:
            re_dict: dict = {}
            for period, row in re_df.iterrows():
                period_data = {}
                for col in re_df.columns:
                    period_data[str(col)] = _clean(row[col])
                re_dict[str(period)] = period_data
            if re_dict:
                estimates["revenueEstimate"] = re_dict
        except Exception:
            pass

    # Fallback: scalar fields from info
    for key in ("forwardEps", "forwardPE", "revenueGrowth",
                "earningsGrowth", "earningsQuarterlyGrowth"):
        val = _clean(info.get(key))
        if val is not None:
            estimates.setdefault(key, val)

    # ── 6. Growth estimates ─────────────────────────────────────────────────
    growth_estimates: dict | None = None
    ge_df = _safe_df(t, "growth_estimates")
    if ge_df is None:
        ge_df = _safe_df(t, "growthEstimates")

    if ge_df is not None:
        try:
            ge_dict: dict = {}
            for period, row in ge_df.iterrows():
                period_data = {}
                for col in ge_df.columns:
                    period_data[str(col)] = _clean(row[col])
                ge_dict[str(period)] = period_data
            if ge_dict:
                growth_estimates = ge_dict
        except Exception:
            growth_estimates = None

    # ── Assemble final payload ───────────────────────────────────────────────
    return {
        "ticker": ticker.upper(),
        "currency": currency,
        "price": price,
        "priceTarget": price_target,
        "consensus": consensus,
        "earningsSurprises": earning_surprises,
        "estimates": estimates,
        "growthEstimates": growth_estimates,
        "asOf": date.today().isoformat(),
    }


def provenance(result: dict, root: str = "analyst") -> dict:
    """Provenance keys (under ``root``) for an :func:`analyst_data` result."""
    def k(*parts: str) -> str:
        return ".".join(p for p in (root, *parts) if p)

    sym = result.get("ticker") or ""
    dates = [e["date"] for e in result.get("earningsSurprises") or [] if e.get("date")]
    prov: dict = {
        k(): pv.yahoo(sym, "Analyst data: price targets, consensus, earnings surprises and estimates",
                      note="Yahoo Finance aggregates these from contributing brokers."),
        k("price"): pv.yahoo(sym, "info.currentPrice (else regularMarketPrice)", units=result.get("currency")),
        k("priceTarget"): pv.yahoo(sym, "info.targetMeanPrice / targetHighPrice / targetLowPrice / targetMedianPrice "
                                        "and numberOfAnalystOpinions", units=result.get("currency")),
        k("priceTarget", "upsidePct"): pv.derived("(mean target price − current price) / current price",
                                                  [k("priceTarget"), k("price")], title="Upside to mean target"),
        k("consensus"): pv.yahoo(sym, "info.recommendationMean and recommendationKey"),
        k("consensus", "history"): pv.yahoo(sym, "Ticker.recommendations: analyst rating counts by month",
                                            frequency="monthly"),
        k("earningsSurprises"): pv.yahoo(sym, "Ticker.earnings_dates: EPS estimate, reported EPS and surprise",
                                         frequency="quarterly", observed=max(dates) if dates else None),
        k("estimates"): pv.yahoo(sym, "Ticker.earnings_estimate and revenue_estimate; info.forwardEps, forwardPE, "
                                      "revenueGrowth, earningsGrowth, earningsQuarterlyGrowth"),
        k("growthEstimates"): pv.yahoo(sym, "Ticker.growth_estimates"),
    }
    return prov
