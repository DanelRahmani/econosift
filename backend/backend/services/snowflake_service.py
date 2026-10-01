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

from .. import provenance as pv
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



def _fallback_value_inputs(info: dict) -> tuple[float | None, float | None]:
    """(EV/EBITDA, P/B) for a ticker outside the screener cache.

    ADRs (TSM, NVO) quote in USD but report in TWD/DKK, so Yahoo's
    enterpriseToEbitda / priceToBook mix currencies; rebuild them in the price
    currency (audit M-01). Same-currency tickers keep Yahoo's values.
    """
    if info.get("financialCurrency") in (None, info.get("currency")):
        return _safe(info.get("enterpriseToEbitda")), _safe(info.get("priceToBook"))
    from .metrics import market_multiples
    v = market_multiples({"info": info})["values"]
    return v["evEbitda"], v["pbRatio"]

# Yahoo sector names -> the GICS names the screener cache uses (index constituent lists are GICS).
_YAHOO_TO_GICS = {
    "Technology": "Information Technology", "Healthcare": "Health Care",
    "Financial Services": "Financials", "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples", "Basic Materials": "Materials",
}
MIN_PEERS = 10


def _sector_peers(sector: str | None, industry: str | None,
                  all_peers: list[dict]) -> tuple[list[dict], str | None]:
    """(peers, scope) with scope "sector" | "industry"; ([], None) when there is no honest peer set.

    Yahoo and GICS sector names are mapped to one vocabulary on both sides. Unlike
    :func:`_peers_for` this never falls back to the whole universe (audit M-13: TSM was
    ranked against all 527 cached stocks).
    """
    gics = lambda n: _YAHOO_TO_GICS.get(n, n)  # noqa: E731
    if sector:
        same = [r for r in all_peers if r.get("sector") and gics(r["sector"]) == gics(sector)]
        if len(same) >= MIN_PEERS:
            return same, "sector"
    if industry:
        same = [r for r in all_peers if r.get("industry") == industry]
        if len(same) >= MIN_PEERS:
            return same, "industry"
    return [], None


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

NOT_MEANINGFUL_MULTIPLE = "not meaningful: negative multiple"


def _multiple_component(label: str, weight: float, value: float | None, peer_values: list[float]) -> dict:
    """Value-axis component for a "lower is better" multiple (P/E, EV/EBITDA, EV/FCF, P/B).

    A zero or negative multiple means negative earnings / cash flow / book, not
    "cheap": a ranked-lowest -4.85x EV/FCF used to score 9.2/10 (audit M-02).
    Such a value is scored None (dropped from the axis average) with a reason,
    and non-positive peer values are left out of the ranking so they cannot
    push positive multiples down the percentile either.
    """
    if value is not None and value <= 0:
        return {"label": label, "weight": weight, "score": None, "value": value,
                "reason": NOT_MEANINGFUL_MULTIPLE}
    return {"label": label, "weight": weight, "value": value,
            "score": _percentile(value, [p for p in peer_values if p > 0], invert=True)}


def _axis_value(row: dict, peers: list[dict]) -> tuple[float | None, list[dict]]:
    peg = None
    pe = _safe(row.get("pe"))
    eps_g = _safe(row.get("eps_growth") or row.get("epsGrowth"))
    if pe is not None and eps_g is not None and eps_g > 0:
        peg = min(pe / (eps_g * 100.0), 50.0)

    components = [
        _multiple_component("P/E", 0.25, pe, _col_values(peers, "pe")),
        _multiple_component("EV/EBITDA", 0.20, _safe(row.get("ev_ebitda") or row.get("evEbitda")),
                            _col_values(peers, "ev_ebitda")),
        _multiple_component("EV/FCF", 0.15, _safe(row.get("ev_fcf") or row.get("evFcf")),
                            _col_values(peers, "ev_fcf")),
        {"label": "FCF Yield", "weight": 0.20,
         "score": _percentile(_safe(row.get("fcf_yield") or row.get("fcfYield")),
                               _col_values(peers, "fcf_yield")),
         "value": _safe(row.get("fcf_yield") or row.get("fcfYield"))},
        _multiple_component("P/B", 0.10, _safe(row.get("pb")), _col_values(peers, "pb")),
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


def _axis_health(row: dict, peers: list[dict], info: dict, bundle: dict) -> tuple[float | None, list[dict]]:
    altman = _safe(row.get("altman_z") or row.get("altmanZ"))
    roic_val = _safe(row.get("roic"))
    cur_ratio = _safe(row.get("current_ratio") or row.get("currentRatio"))
    de = _safe(row.get("debt_to_equity") or row.get("debtToEquity"))

    # Piotroski F-Score: the full nine tests; the prior year comes from the statement DataFrames in the bundle
    pio_result = piotroski_f(bundle)
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
         "value": (fcf_yield / (div_yield / 100.0)) if fcf_yield and div_yield else None},
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
            "ev_ebitda": _fallback_value_inputs(info)[0],
            "ev_fcf": None,
            "fcf_yield": None,
            "pb": _fallback_value_inputs(info)[1],
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

    # Peers are chosen once the sector is known (a ticker outside the cache gets it from Yahoo).
    peers, peer_scope = _sector_peers(sector, industry, all_peers)
    n_peers = len(peers)
    peer_note = None if peers else (
        "No peer set: the sector is unknown or fewer than 10 cached stocks share it, so percentile-ranked "
        "components are not scored (the whole universe is not used instead).")

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
    bs_raw = cf_raw = None
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
    # Statement DataFrames (newest column first) let piotroski_f build the prior year: all nine tests.
    for key, df in (("financials_df", fin_df), ("balance_sheet_df", bs_raw), ("cashflow_df", cf_raw)):
        if df is not None and not df.empty:
            bundle[key] = df

    # Score axes
    val_score, val_comps = _axis_value(row, peers)
    growth_score, growth_comps = _axis_growth(row, peers, info)
    perf_score, perf_comps = _axis_performance(row, peers, fin_df)
    health_score, health_comps = _axis_health(row, peers, info, bundle)
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

    return pv.attach({
        "ticker": ticker,
        "sector": sector,
        "industry": industry,
        "sectorPeers": n_peers,
        "peerGroup": {"scope": peer_scope, "n": n_peers, "reason": peer_note},
        "overallScore": overall,
        "verdict": _verdict(overall) if overall is not None else "Unknown",
        "scores": scores,
        "rewards": rewards,
        "risks": risks,
        "axisDetails": axis_details,
    }, _provenance(
        ticker, bool(cache_rows),
        peer_scope or "none", n_peers))


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


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

_PCT = "percentile rank among peers = share of peers with a strictly lower value × 10"

# axis -> [(component label, weight, formula)]
_COMPONENT_FORMULAS: dict[str, list[tuple[str, float, str]]] = {
    "value": [
        ("P/E", 0.25, f"{_PCT}, inverted (lower P/E scores higher); trailing P/E"),
        ("EV/EBITDA", 0.20, f"{_PCT}, inverted; enterpriseToEbitda"),
        ("EV/FCF", 0.15, f"{_PCT}, inverted; enterprise value / free cash flow"),
        ("FCF Yield", 0.20, f"{_PCT}; free cash flow / market cap"),
        ("P/B", 0.10, f"{_PCT}, inverted; priceToBook"),
        ("PEG", 0.10, f"{_PCT}, inverted; PEG = P/E / (earnings growth × 100), capped at 50, only if growth > 0"),
    ],
    "growth": [
        ("Revenue Growth", 0.30, f"{_PCT}; revenueGrowth (latest quarter vs the same quarter a year earlier)"),
        ("EPS Growth", 0.30, f"{_PCT}; earningsGrowth (latest quarter year over year)"),
        ("Fwd PE Improvement", 0.20, f"{_PCT}; trailing P/E − forward P/E"),
        ("R&D Intensity", 0.20, "info.researchAndDevelopment / info.totalRevenue ÷ 15% × 10, capped at 10"),
    ],
    "performance": [
        ("ROE", 0.25, f"{_PCT}; returnOnEquity"),
        ("Gross Margin", 0.20, f"{_PCT}; annual gross profit / revenue"),
        ("Net Margin", 0.15, f"{_PCT}; profitMargins"),
        ("3Y Revenue CAGR", 0.20, "(newest annual revenue / revenue three fiscal years earlier)^(1/3) − 1, then "
                                  "≥20% → 10, ≥15% → 8, ≥10% → 6, ≥5% → 4, ≥0% → 2, else 0"),
        ("3Y Earnings CAGR", 0.20, "the same CAGR on annual net income (not per share), same thresholds"),
    ],
    "health": [
        ("Altman Z", 0.15, f"{_PCT}; Altman Z-Score"),
        ("Piotroski F-Score", 0.20, "Piotroski tests passed / tests evaluated × 10"),
        ("Ohlson O-Score", 0.15, "(1 − Ohlson default probability) × 10"),
        ("ROIC", 0.10, f"{_PCT}; return on invested capital"),
        ("ROIC−WACC Spread", 0.15, "ROIC − WACC: ≥15pp → 10, ≥10pp → 8, ≥5pp → 6, ≥0 → 4, ≥ −5pp → 2, else 0"),
        ("Current Ratio", 0.10, f"{_PCT}; current ratio capped at 4"),
        ("D/E Ratio", 0.10, f"{_PCT}, inverted; debtToEquity"),
        ("Interest Coverage", 0.10, "info.ebit / |info.interestExpense| (999 if no debt, −1 if EBIT ≤ 0): ≥10 → 10, "
                                    "≥5 → 7, ≥3 → 4.5, ≥1 → 2, ≥0 → 0.5, else 0"),
    ],
    "dividend": [
        ("Dividend Yield", 0.30, f"{_PCT} among dividend-paying peers"),
        ("Payout Ratio", 0.25, "payoutRatio ≤25% → 10, ≤40% → 8, ≤60% → 5, ≤80% → 2, else 1"),
        ("FCF Coverage", 0.25, "FCF yield / dividend yield: ≥3 → 10, ≥2 → 8, ≥1.5 → 6, ≥1 → 4, ≥0.7 → 2, else 0.5"),
        ("Dividend Consistency", 0.20, "number of the last five 12-month windows containing a dividend ÷ 5 × 10"),
        ("No Dividend", 1.0, "non-payers score 0 on this axis"),
    ],
}


def _provenance(ticker: str, in_cache: bool, peer_scope: str, n_peers: int) -> dict:
    """Keys for /snowflake: ``scores.<axis>``, ``axisDetails.<axis>[.components.<label>]`` and the headline fields."""
    yahoo = pv.yahoo(ticker, "Quote, key statistics and annual statements (Ticker.info, financials, balance sheet, "
                             "cash flow, dividends)")
    peers = pv.ref("econosift", "screener_cache", "Screener universe cache: Yahoo fundamentals for the Dow 30, "
                   "Nasdaq-100 and S&P 500, refreshed nightly")
    row = peers if in_cache else yahoo
    cols = {"value": "P/E, EV/EBITDA, EV/FCF, FCF yield, P/B, PEG", "growth": "revenue and EPS growth, forward P/E",
            "performance": "ROE and margins, 3-year CAGRs", "health": "Altman, Piotroski, Ohlson, ROIC, WACC, ratios",
            "dividend": "yield, payout, FCF coverage, dividend history"}
    prov: dict = {
        "*": pv.derived(
            "five 0-10 axis scores (value, growth, performance, health, dividend), each a weighted mean of its "
            "component scores; most components are percentile ranks against sector peers in the screener cache",
            [row, peers, yahoo], title="Snowflake composite score"),
        "overallScore": pv.derived("mean of the available axis scores, equally weighted",
                                   [f"scores.{a}" for a in cols], title="Overall score"),
        "verdict": pv.derived("overall ≥ 8 Exceptional; ≥ 6 Strong; ≥ 4 Moderate; ≥ 2 Weak; else Poor",
                              ["overallScore"], title="Verdict"),
        "sectorPeers": pv.derived(
            f"number of screener-cache stocks in the peer group; the group is the sector (Yahoo names mapped to GICS), "
            f"else the industry, else none when fewer than 10 share either (here: {peer_scope})", [peers],
            title="Peer group size"),
        "rewards": pv.derived("the three highest component scores across all axes", ["*"],
                              title="Top rewards"),
        "risks": pv.derived("the three lowest component scores across all axes", ["*"],
                            title="Top risks"),
        "sector": pv.ref("econosift", "screener_cache", "Sector from the screener cache (index constituent list, "
                         "else Yahoo)") if in_cache else pv.yahoo(ticker, "info.sector"),
        "industry": pv.ref("econosift", "screener_cache", "Industry from the screener cache (index constituent "
                           "list, else Yahoo)") if in_cache else pv.yahoo(ticker, "info.industry"),
    }
    if not in_cache:
        prov["*"]["note"] = ("Ticker is not in the screener cache: its fields come straight from Yahoo, with "
                             "returnOnAssets standing in for ROIC and no EV/FCF, FCF yield or Altman Z.")
    for axis, what in cols.items():
        prov[f"scores.{axis}"] = prov[f"axisDetails.{axis}"] = pv.derived(
            "weighted mean of the component scores below, weights renormalised over the components that could be "
            f"scored ({what})", [f"axisDetails.{axis}.components.{c[0]}" for c in _COMPONENT_FORMULAS[axis]],
            title=f"{axis.capitalize()} axis")
        for label, weight, formula in _COMPONENT_FORMULAS[axis]:
            comp_flags = ("proxy",) if (not in_cache and label == "ROIC") else ()
            prov[f"axisDetails.{axis}.components.{label}"] = pv.derived(
                f"{formula} (weight {weight:g})", [row, peers, yahoo], title=label, flags=comp_flags,
                note="Uses returnOnAssets as a stand-in for ROIC." if comp_flags else None)
    return prov
