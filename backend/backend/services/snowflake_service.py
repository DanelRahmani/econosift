"""Snowflake Composite Score service — Phase 9.

Scores each stock 0–10 on 5 axes, sector-normalised via percentile ranking
within the screener cache peer universe (union of dow + ndx + sp500).

Two entry-points:
  compute_snowflake(ticker)        — full scoring with yfinance historical data
  compute_snowflake_batch(tickers) — lightweight cache-only scores for screener
"""
from __future__ import annotations

import math
import sqlite3
from typing import Any

import yfinance as yf

from ..cache import cached
from . import screener_cache
from .fundamentals import piotroski_f, ohlson_o, _unpack
from .discount_rates import wacc as compute_wacc, risk_free_rate
from .metrics import _clean


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(v: Any) -> float | None:
    """Coerce to float, return None for NaN/Inf/None."""
    return _clean(v)


def _percentile(value: float | None, peers: list[float], invert: bool = False) -> float | None:
    """Percentile rank of *value* within *peers* → 0.0–10.0 score.

    ``invert=True`` means lower values are better (e.g. P/E).
    Returns None if value is None or peer list is empty.
    """
    if value is None or not peers:
        return None
    rank = sum(1 for p in peers if p < value)
    pct = rank / len(peers)  # 0.0 – 1.0
    if invert:
        pct = 1.0 - pct
    return round(pct * 10.0, 2)


def _threshold_score(value: float | None, thresholds: list[tuple[float, float]]) -> float | None:
    """Map *value* to a 0–10 score via a list of (min_value, score) breakpoints.

    Thresholds must be sorted descending by min_value.  The first entry whose
    min_value ≤ value is used.
    """
    if value is None:
        return None
    for min_val, score in thresholds:
        if value >= min_val:
            return score
    return thresholds[-1][1] if thresholds else None


def _weighted_avg(components: list[dict]) -> float | None:
    """Weighted average of {score, weight} dicts, skipping None scores.

    Renormalises weights to the available subset.
    """
    total_w = 0.0
    total_ws = 0.0
    for c in components:
        s = c.get("score")
        w = c.get("weight", 1.0)
        if s is not None:
            total_ws += s * w
            total_w += w
    if total_w == 0:
        return None
    return round(total_ws / total_w, 2)


def _cagr_score(value: float | None) -> float | None:
    """Score a 3-year CAGR (as decimal, e.g. 0.15 = 15%) on 0–10 scale."""
    if value is None:
        return None
    pct = value * 100.0
    thresholds = [(20, 10.0), (15, 8.0), (10, 6.0), (5, 4.0), (0, 2.0)]
    for min_pct, score in thresholds:
        if pct >= min_pct:
            return score
    return 0.0


def _interest_coverage_score(value: float | None) -> float | None:
    """Score interest coverage (EBIT / interest expense) on 0–10."""
    if value is None:
        return None
    thresholds = [(10.0, 10.0), (5.0, 7.0), (3.0, 4.5), (1.0, 2.0), (0.0, 0.5)]
    for minimum, score in thresholds:
        if value >= minimum:
            return score
    return 0.0


def _roic_wacc_score(roic: float | None, wacc_val: float | None) -> float | None:
    """Score ROIC − WACC spread on 0–10."""
    if roic is None or wacc_val is None:
        return None
    spread = roic - wacc_val
    thresholds = [(0.15, 10.0), (0.10, 8.0), (0.05, 6.0), (0.0, 4.0), (-0.05, 2.0)]
    for minimum, score in thresholds:
        if spread >= minimum:
            return score
    return 0.0


def _payout_score(payout: float | None) -> float | None:
    """Score payout ratio (0–1 decimal). Lower is better for sustainability."""
    if payout is None:
        return None
    if payout <= 0:
        return None  # no dividend
    thresholds = [(0.0, 10.0), (0.25, 9.0), (0.40, 7.0), (0.60, 5.0), (0.80, 2.0)]
    # Invert — lower payout is safer
    for max_val, score in [(0.25, 10.0), (0.40, 8.0), (0.60, 5.0), (0.80, 2.0)]:
        if payout <= max_val:
            return score
    return 1.0


def _fcf_coverage_score(div_yield: float | None, fcf_yield: float | None) -> float | None:
    """Score FCF coverage of dividend. Coverage = fcfYield / divYield.

    ``div_yield`` is in percent (yfinance ``dividendYield``, e.g. 2.43) while
    ``fcf_yield`` is a fraction (FCF / market cap, e.g. 0.014); dividing them
    as-is made coverage ~100x too small, so every payer got the minimum
    score (audit C-03).
    """
    if div_yield is None or div_yield <= 0 or fcf_yield is None or fcf_yield <= 0:
        return None
    coverage = fcf_yield / (div_yield / 100.0)
    thresholds = [(3.0, 10.0), (2.0, 8.0), (1.5, 6.0), (1.0, 4.0), (0.7, 2.0)]
    for minimum, score in thresholds:
        if coverage >= minimum:
            return score
    return 0.5


def _div_consistency_score(years_with_div: int) -> float:
    """Score based on number of years with dividend in last 5."""
    return round(min(years_with_div / 5.0, 1.0) * 10.0, 1)


# ---------------------------------------------------------------------------
# Sector peer loading
# ---------------------------------------------------------------------------

def _load_all_peers() -> list[dict]:
    """Return all rows from screener cache (union of all cached indices)."""
    conn = screener_cache._get_conn()
    cur = conn.execute("SELECT * FROM screener_cache.fundamentals" if False else
                       "SELECT * FROM fundamentals")
    col_names = [d[0] for d in cur.description]
    rows = []
    for db_row in cur.fetchall():
        d = dict(zip(col_names, db_row))
        rows.append(d)
    return rows


def _peers_for(sector: str | None, industry: str | None,
               all_peers: list[dict]) -> list[dict]:
    """Return sector peers, falling back to industry then all if < 10."""
    if sector:
        sector_peers = [r for r in all_peers if r.get("sector") == sector]
        if len(sector_peers) >= 10:
            return sector_peers
    if industry:
        industry_peers = [r for r in all_peers if r.get("industry") == industry]
        if len(industry_peers) >= 10:
            return industry_peers
    return all_peers


def _col_values(peers: list[dict], col: str) -> list[float]:
    """Extract non-None float values for *col* from peers list."""
    out = []
    for r in peers:
        v = r.get(col)
        if v is not None:
            try:
                f = float(v)
                if math.isfinite(f):
                    out.append(f)
            except (TypeError, ValueError):
                pass
    return out


# ---------------------------------------------------------------------------
# Axis scorers (full mode)
# ---------------------------------------------------------------------------

def _axis_value(row: dict, peers: list[dict]) -> tuple[float | None, list[dict]]:
    peg = None
    pe = _safe(row.get("pe"))
    eps_g = _safe(row.get("eps_growth") or row.get("epsGrowth"))
    if pe is not None and eps_g is not None and eps_g > 0:
        peg = min(pe / (eps_g * 100.0), 50.0)

    components = [
        {"label": "P/E", "weight": 0.25,
         "score": _percentile(pe, _col_values(peers, "pe"), invert=True),
         "value": pe},
        {"label": "EV/EBITDA", "weight": 0.20,
         "score": _percentile(_safe(row.get("ev_ebitda") or row.get("evEbitda")),
                               _col_values(peers, "ev_ebitda"), invert=True),
         "value": _safe(row.get("ev_ebitda") or row.get("evEbitda"))},
        {"label": "EV/FCF", "weight": 0.15,
         "score": _percentile(_safe(row.get("ev_fcf") or row.get("evFcf")),
                               _col_values(peers, "ev_fcf"), invert=True),
         "value": _safe(row.get("ev_fcf") or row.get("evFcf"))},
        {"label": "FCF Yield", "weight": 0.20,
         "score": _percentile(_safe(row.get("fcf_yield") or row.get("fcfYield")),
                               _col_values(peers, "fcf_yield")),
         "value": _safe(row.get("fcf_yield") or row.get("fcfYield"))},
        {"label": "P/B", "weight": 0.10,
         "score": _percentile(_safe(row.get("pb")),
                               _col_values(peers, "pb"), invert=True),
         "value": _safe(row.get("pb"))},
        {"label": "PEG", "weight": 0.10,
         "score": _percentile(peg,
                               [min(r.get("pe") / (r.get("eps_growth") or r.get("epsGrowth") or 0.001 * 100), 50)
                                for r in peers
                                if r.get("pe") and (r.get("eps_growth") or r.get("epsGrowth")) and
                                (r.get("eps_growth") or r.get("epsGrowth")) > 0],
                               invert=True),
         "value": peg},
    ]
    return _weighted_avg(components), components


def _axis_growth(row: dict, peers: list[dict], info: dict) -> tuple[float | None, list[dict]]:
    rev_g = _safe(row.get("revenue_growth") or row.get("revenueGrowth"))
    eps_g = _safe(row.get("eps_growth") or row.get("epsGrowth"))
    fwd_pe = _safe(row.get("forward_pe") or row.get("forwardPE"))
    pe = _safe(row.get("pe"))
    pe_improvement = (pe - fwd_pe) if (pe is not None and fwd_pe is not None) else None

    # R&D intensity from yfinance info
    rd = _safe(info.get("researchAndDevelopment"))
    rev_info = _safe(info.get("totalRevenue"))
    rd_intensity: float | None = None
    if rd is not None and rev_info is not None and rev_info > 0:
        rd_intensity = rd / rev_info

    # Peer R&D intensity not available in cache — skip percentile, use absolute
    rd_score: float | None = None
    if rd_intensity is not None:
        rd_score = min(rd_intensity / 0.15 * 10.0, 10.0)  # 15%+ R&D = max score

    components = [
        {"label": "Revenue Growth", "weight": 0.30,
         "score": _percentile(rev_g, _col_values(peers, "revenue_growth")),
         "value": rev_g},
        {"label": "EPS Growth", "weight": 0.30,
         "score": _percentile(eps_g, _col_values(peers, "eps_growth")),
         "value": eps_g},
        {"label": "Fwd PE Improvement", "weight": 0.20,
         "score": _percentile(pe_improvement,
                               [r.get("pe") - r.get("forward_pe")
                                for r in peers
                                if r.get("pe") is not None and r.get("forward_pe") is not None]),
         "value": pe_improvement},
        {"label": "R&D Intensity", "weight": 0.20,
         "score": rd_score,
         "value": rd_intensity},
    ]
    return _weighted_avg(components), components


def _axis_performance(row: dict, peers: list[dict], fin_df) -> tuple[float | None, list[dict]]:
    roe = _safe(row.get("roe"))
    gm = _safe(row.get("gross_margin") or row.get("grossMargin"))
    nm = _safe(row.get("net_margin") or row.get("netMargin"))

    # 3Y CAGR from financials DataFrame (columns = dates, index = line items)
    rev_cagr: float | None = None
    eps_cagr: float | None = None
    if fin_df is not None:
        try:
            cols = sorted(fin_df.columns, reverse=True)  # newest first
            if len(cols) >= 4:
                # Revenue CAGR: (newest / oldest) ^ (1/3) - 1
                rev_row = None
                for key in ["Total Revenue", "Revenue"]:
                    if key in fin_df.index:
                        rev_row = fin_df.loc[key]
                        break
                if rev_row is not None:
                    r_new = _safe(rev_row[cols[0]])
                    r_old = _safe(rev_row[cols[3]])
                    if r_new and r_old and r_old > 0 and r_new > 0:
                        rev_cagr = (r_new / r_old) ** (1 / 3) - 1

                # EPS (Net Income) CAGR
                ni_row = None
                for key in ["Net Income", "Net Income Common Stockholders"]:
                    if key in fin_df.index:
                        ni_row = fin_df.loc[key]
                        break
                if ni_row is not None:
                    ni_new = _safe(ni_row[cols[0]])
                    ni_old = _safe(ni_row[cols[3]])
                    if ni_new and ni_old and ni_old > 0 and ni_new > 0:
                        eps_cagr = (ni_new / ni_old) ** (1 / 3) - 1
        except Exception:
            pass

    components = [
        {"label": "ROE", "weight": 0.25,
         "score": _percentile(roe, _col_values(peers, "roe")),
         "value": roe},
        {"label": "Gross Margin", "weight": 0.20,
         "score": _percentile(gm, _col_values(peers, "gross_margin")),
         "value": gm},
        {"label": "Net Margin", "weight": 0.15,
         "score": _percentile(nm, _col_values(peers, "net_margin")),
         "value": nm},
        {"label": "3Y Revenue CAGR", "weight": 0.20,
         "score": _cagr_score(rev_cagr),
         "value": rev_cagr},
        {"label": "3Y Earnings CAGR", "weight": 0.20,
         "score": _cagr_score(eps_cagr),
         "value": eps_cagr},
    ]
    return _weighted_avg(components), components


def _axis_health(row: dict, peers: list[dict], info: dict,
                 fin_df, bundle: dict) -> tuple[float | None, list[dict]]:
    altman = _safe(row.get("altman_z") or row.get("altmanZ"))
    roic_val = _safe(row.get("roic"))
    cur_ratio = _safe(row.get("current_ratio") or row.get("currentRatio"))
    de = _safe(row.get("debt_to_equity") or row.get("debtToEquity"))

    # Piotroski F-Score (full 9/9 with prior year if available)
    prior_bundle: dict | None = None
    if fin_df is not None:
        try:
            cols = sorted(fin_df.columns, reverse=True)
            if len(cols) >= 2:
                # Build a minimal prior-year bundle from the second-most-recent column
                py_col = cols[1]
                py_fin = {str(k): _safe(fin_df.loc[k, py_col]) for k in fin_df.index}
                prior_bundle = {
                    "info": info,  # share count not year-specific here
                    "financials": py_fin,
                    "balance_sheet": {},
                    "cashflow": {},
                }
        except Exception:
            pass

    pio_result = piotroski_f(bundle, prior_year=prior_bundle)
    max_score = pio_result.get("maxScore") or 1
    pio_score = (pio_result.get("score") or 0) / max(max_score, 1) * 10.0

    # Ohlson O-Score
    ohlson_result = ohlson_o(bundle)
    prob_default = _safe(ohlson_result.get("probDefault"))
    ohlson_score = (1.0 - prob_default) * 10.0 if prob_default is not None else None

    # WACC for ROIC-WACC spread
    wacc_val: float | None = None
    try:
        beta = _safe(info.get("beta"))
        wacc_result = compute_wacc(bundle, beta)
        wacc_val = _safe(wacc_result.get("wacc"))
    except Exception:
        pass

    # Interest coverage
    ebit = _safe(info.get("ebit"))
    int_exp = _safe(info.get("interestExpense"))
    int_coverage: float | None = None
    total_debt = _safe(info.get("totalDebt"))
    if ebit is not None:
        if int_exp is not None and abs(int_exp) > 0:
            int_coverage = abs(ebit) / abs(int_exp) if ebit > 0 else -1.0
        elif total_debt is not None and total_debt == 0:
            int_coverage = 999.0  # no debt

    # Clamp current ratio for peer comparison
    cur_ratio_capped = min(cur_ratio, 4.0) if cur_ratio is not None else None
    peer_cr = [min(v, 4.0) for v in _col_values(peers, "current_ratio")]

    components = [
        {"label": "Altman Z", "weight": 0.15,
         "score": _percentile(altman, _col_values(peers, "altman_z")),
         "value": altman},
        {"label": "Piotroski F-Score", "weight": 0.20,
         "score": round(pio_score, 2),
         "value": pio_result.get("score"),
         "detail": f"{pio_result.get('score')}/{max_score}"},
        {"label": "Ohlson O-Score", "weight": 0.15,
         "score": ohlson_score,
         "value": prob_default},
        {"label": "ROIC", "weight": 0.10,
         "score": _percentile(roic_val, _col_values(peers, "roic")),
         "value": roic_val},
        {"label": "ROIC−WACC Spread", "weight": 0.15,
         "score": _roic_wacc_score(roic_val, wacc_val),
         "value": (roic_val - wacc_val) if roic_val is not None and wacc_val is not None else None},
        {"label": "Current Ratio", "weight": 0.10,
         "score": _percentile(cur_ratio_capped, peer_cr),
         "value": cur_ratio},
        {"label": "D/E Ratio", "weight": 0.10,
         "score": _percentile(de, _col_values(peers, "debt_to_equity"), invert=True),
         "value": de},
        {"label": "Interest Coverage", "weight": 0.10,
         "score": _interest_coverage_score(int_coverage),
         "value": int_coverage},
    ]
    return _weighted_avg(components), components


def _axis_dividend(row: dict, peers: list[dict], info: dict) -> tuple[float | None, list[dict]]:
    div_yield = _safe(row.get("dividend_yield") or row.get("dividendYield"))
    fcf_yield = _safe(row.get("fcf_yield") or row.get("fcfYield"))

    if not div_yield or div_yield <= 0:
        return 0.0, [{"label": "No Dividend", "weight": 1.0, "score": 0.0, "value": None}]

    payout = _safe(info.get("payoutRatio"))

    # Dividend consistency: count years with non-zero dividend in last 5
    consistency_years = 0
    try:
        ticker_obj = yf.Ticker(info.get("symbol") or "")
        hist_div = ticker_obj.dividends
        if hist_div is not None and len(hist_div) > 0:
            import pandas as pd
            hist_div.index = pd.to_datetime(hist_div.index, utc=True)
            now = pd.Timestamp.now(tz="UTC")
            for yr_offset in range(5):
                year_start = now - pd.DateOffset(years=yr_offset + 1)
                year_end = now - pd.DateOffset(years=yr_offset)
                yr_divs = hist_div[(hist_div.index >= year_start) & (hist_div.index < year_end)]
                if len(yr_divs) > 0 and yr_divs.sum() > 0:
                    consistency_years += 1
    except Exception:
        consistency_years = 3  # neutral fallback

    div_peers = [v for v in _col_values(peers, "dividend_yield") if v > 0]

    components = [
        {"label": "Dividend Yield", "weight": 0.30,
         "score": _percentile(div_yield, div_peers),
         "value": div_yield},
        {"label": "Payout Ratio", "weight": 0.25,
         "score": _payout_score(payout),
         "value": payout},
        {"label": "FCF Coverage", "weight": 0.25,
         "score": _fcf_coverage_score(div_yield, fcf_yield),
         "value": (fcf_yield / div_yield) if fcf_yield and div_yield else None},
        {"label": "Dividend Consistency", "weight": 0.20,
         "score": _div_consistency_score(consistency_years),
         "value": consistency_years},
    ]
    return _weighted_avg(components), components


# ---------------------------------------------------------------------------
# Rewards / Risks extractor
# ---------------------------------------------------------------------------

def _rewards_risks(axis_details: dict) -> tuple[list[dict], list[dict]]:
    """Return top-3 rewards (highest score) and top-3 risks (lowest score)."""
    all_components: list[dict] = []
    for axis_name, detail in axis_details.items():
        for c in detail.get("components", []):
            s = c.get("score")
            if s is not None:
                all_components.append({
                    "axis": axis_name,
                    "label": c.get("label"),
                    "score": s,
                })

    all_components.sort(key=lambda x: x["score"], reverse=True)
    rewards = all_components[:3]
    risks = all_components[-3:][::-1]  # lowest 3, worst first
    return rewards, risks


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def _verdict(score: float) -> str:
    if score >= 8:
        return "Exceptional"
    if score >= 6:
        return "Strong"
    if score >= 4:
        return "Moderate"
    if score >= 2:
        return "Weak"
    return "Poor"


# ---------------------------------------------------------------------------
# Public: full snowflake (per-ticker, with yfinance historical data)
# ---------------------------------------------------------------------------

@cached("snowflake_full")
def compute_snowflake(ticker: str) -> dict:
    """Full snowflake scoring for a single ticker.  Cached 60 min."""
    ticker = ticker.upper().strip()

    # Load all peers from screener cache
    all_peers = _load_all_peers()

    # Load the target row from cache
    cache_rows = screener_cache.get_rows([ticker])
    if cache_rows:
        row = cache_rows[0]
        sector = row.get("sector")
        industry = row.get("industry")
    else:
        # Ticker not in cache — build a minimal row from yfinance info
        row = {}
        sector = None
        industry = None

    peers = _peers_for(sector, industry, all_peers)
    n_peers = len([p for p in peers if p.get("sector") == sector]) if sector else len(peers)

    # Fetch yfinance info (cached via cache.py)
    yf_ticker = yf.Ticker(ticker)
    try:
        info = yf_ticker.info or {}
    except Exception:
        info = {}

    # If row is empty, populate basic fields from yfinance info
    if not row:
        row = {
            "pe": _safe(info.get("trailingPE")),
            "forward_pe": _safe(info.get("forwardPE")),
            "ev_ebitda": _safe(info.get("enterpriseToEbitda")),
            "ev_fcf": None,
            "fcf_yield": None,
            "pb": _safe(info.get("priceToBook")),
            "eps_growth": _safe(info.get("earningsGrowth")),
            "revenue_growth": _safe(info.get("revenueGrowth")),
            "roe": _safe(info.get("returnOnEquity")),
            "gross_margin": _safe(info.get("grossMargins")),
            "net_margin": _safe(info.get("profitMargins")),
            "roic": _safe(info.get("returnOnAssets")),  # proxy
            "current_ratio": _safe(info.get("currentRatio")),
            "debt_to_equity": _safe(info.get("debtToEquity")),
            "dividend_yield": _safe(info.get("dividendYield")),
            "altman_z": None,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
        sector = info.get("sector")
        industry = info.get("industry")

    # Fetch historical financials (for 3Y CAGR + full Piotroski)
    fin_df = None
    try:
        fin_df = yf_ticker.financials  # index = line items, columns = dates
    except Exception:
        pass

    # Build a bundle for fundamentals functions
    bs_data = {}
    cf_data = {}
    fin_data = {}
    try:
        bs_raw = yf_ticker.balance_sheet
        if bs_raw is not None and not bs_raw.empty:
            cols = sorted(bs_raw.columns, reverse=True)
            bs_data = {str(k): _safe(bs_raw.loc[k, cols[0]]) for k in bs_raw.index}
    except Exception:
        pass
    try:
        cf_raw = yf_ticker.cashflow
        if cf_raw is not None and not cf_raw.empty:
            cols = sorted(cf_raw.columns, reverse=True)
            cf_data = {str(k): _safe(cf_raw.loc[k, cols[0]]) for k in cf_raw.index}
    except Exception:
        pass
    if fin_df is not None and not fin_df.empty:
        cols = sorted(fin_df.columns, reverse=True)
        fin_data = {str(k): _safe(fin_df.loc[k, cols[0]]) for k in fin_df.index}

    bundle = {"info": info, "financials": fin_data, "balance_sheet": bs_data, "cashflow": cf_data}

    # Score axes
    val_score, val_comps = _axis_value(row, peers)
    growth_score, growth_comps = _axis_growth(row, peers, info)
    perf_score, perf_comps = _axis_performance(row, peers, fin_df)
    health_score, health_comps = _axis_health(row, peers, info, fin_df, bundle)
    div_score, div_comps = _axis_dividend(row, peers, info)

    scores = {
        "value": val_score,
        "growth": growth_score,
        "performance": perf_score,
        "health": health_score,
        "dividend": div_score,
    }
    valid_scores = [s for s in scores.values() if s is not None]
    overall = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else None

    axis_details = {
        "value": {"score": val_score, "components": val_comps},
        "growth": {"score": growth_score, "components": growth_comps},
        "performance": {"score": perf_score, "components": perf_comps},
        "health": {"score": health_score, "components": health_comps},
        "dividend": {"score": div_score, "components": div_comps},
    }

    rewards, risks = _rewards_risks(axis_details)

    return {
        "ticker": ticker,
        "sector": sector,
        "industry": industry,
        "sectorPeers": n_peers,
        "overallScore": overall,
        "verdict": _verdict(overall) if overall is not None else "Unknown",
        "scores": scores,
        "rewards": rewards,
        "risks": risks,
        "axisDetails": axis_details,
    }


# ---------------------------------------------------------------------------
# Public: batch snowflake (cache-only, for screener SparkCards)
# ---------------------------------------------------------------------------

@cached("snowflake_batch")
def compute_snowflake_batch(tickers_key: str) -> dict:
    """Lightweight snowflake scores from screener cache only.

    ``tickers_key`` is a comma-joined sorted ticker string (cache key).
    Returns {ticker: {overallScore, scores}}.
    """
    tickers = [t.strip().upper() for t in tickers_key.split(",") if t.strip()]
    if not tickers:
        return {}

    all_peers = _load_all_peers()
    rows = screener_cache.get_rows(tickers)
    row_by_sym: dict[str, dict] = {r["symbol"]: r for r in rows}

    result: dict[str, dict] = {}
    for ticker in tickers:
        row = row_by_sym.get(ticker)
        if row is None:
            continue
        sector = row.get("sector")
        industry = row.get("industry")
        peers = _peers_for(sector, industry, all_peers)

        val_score, _ = _axis_value(row, peers)

        rev_g = _safe(row.get("revenueGrowth"))
        eps_g = _safe(row.get("epsGrowth"))
        fwd_pe = _safe(row.get("forwardPE"))
        pe = _safe(row.get("pe"))
        pe_improvement = (pe - fwd_pe) if (pe is not None and fwd_pe is not None) else None
        growth_components = [
            {"score": _percentile(rev_g, _col_values(peers, "revenue_growth")), "weight": 0.35},
            {"score": _percentile(eps_g, _col_values(peers, "eps_growth")), "weight": 0.35},
            {"score": _percentile(pe_improvement,
                                   [r.get("pe") - r.get("forward_pe")
                                    for r in peers
                                    if r.get("pe") is not None and r.get("forward_pe") is not None]),
             "weight": 0.30},
        ]
        growth_score = _weighted_avg(growth_components)

        roe = _safe(row.get("roe"))
        gm = _safe(row.get("grossMargin"))
        nm = _safe(row.get("netMargin"))
        perf_components = [
            {"score": _percentile(roe, _col_values(peers, "roe")), "weight": 0.40},
            {"score": _percentile(gm, _col_values(peers, "gross_margin")), "weight": 0.30},
            {"score": _percentile(nm, _col_values(peers, "net_margin")), "weight": 0.30},
        ]
        perf_score = _weighted_avg(perf_components)

        altman = _safe(row.get("altmanZ"))
        roic_val = _safe(row.get("roic"))
        cur_ratio = _safe(row.get("currentRatio"))
        de = _safe(row.get("debtToEquity"))
        health_components = [
            {"score": _percentile(altman, _col_values(peers, "altman_z")), "weight": 0.25},
            {"score": _percentile(roic_val, _col_values(peers, "roic")), "weight": 0.25},
            {"score": _percentile(min(cur_ratio, 4.0) if cur_ratio else None,
                                   [min(v, 4.0) for v in _col_values(peers, "current_ratio")]), "weight": 0.25},
            {"score": _percentile(de, _col_values(peers, "debt_to_equity"), invert=True), "weight": 0.25},
        ]
        health_score = _weighted_avg(health_components)

        div_yield = _safe(row.get("dividendYield"))
        div_score = 0.0
        if div_yield and div_yield > 0:
            div_peers = [v for v in _col_values(peers, "dividend_yield") if v > 0]
            div_score = _percentile(div_yield, div_peers) or 0.0

        scores = {
            "value": val_score,
            "growth": growth_score,
            "performance": perf_score,
            "health": health_score,
            "dividend": div_score,
        }
        valid = [s for s in scores.values() if s is not None]
        overall = round(sum(valid) / len(valid), 2) if valid else None

        result[ticker] = {
            "overallScore": overall,
            "scores": scores,
        }

    return result
