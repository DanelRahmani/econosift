"""Corporate Health Monitor — Phase 27.

Altman Z-Score, Piotroski F-Score, and Beneish M-Score for any ticker.
Pure calculation from yfinance balance sheet / income statement / cash flow.
"""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import yfinance as yf

from ..cache import cached
from . import constituents

logger = logging.getLogger(__name__)


def _latest_val(df, row_name: str) -> float | None:
    """Get the most recent annual value for a row from a yfinance DataFrame."""
    try:
        if df is None or df.empty:
            return None
        if row_name not in df.index:
            return None
        v = df.loc[row_name].iloc[0]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)
    except Exception:
        return None


def _prior_val(df, row_name: str) -> float | None:
    """Get the prior-year value (t-1) from a yfinance DataFrame.

    Uses .iloc[1] on the annual DataFrame (second column = prior year).
    Returns None if only one column of data is available.
    """
    try:
        if df is None or df.empty or row_name not in df.index:
            return None
        if df.shape[1] < 2:
            return None
        v = float(df.loc[row_name].iloc[1])
        return v if not math.isnan(v) else None
    except Exception:
        return None


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


# ---------------------------------------------------------------------------
# Altman Z-Score (5-factor model for public manufacturing firms)
# Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
# ---------------------------------------------------------------------------

def _altman_z(fin, bs, info: dict) -> dict:
    """Compute Altman Z-Score and its 5 components."""
    # Balance sheet items
    total_assets = _latest_val(bs, "Total Assets")
    total_liabilities = _latest_val(bs, "Total Liabilities Net Minority Interest")
    if total_liabilities is None:
        total_liabilities = _latest_val(bs, "Total Liabilities")
    current_assets = _latest_val(bs, "Current Assets")
    current_liabilities = _latest_val(bs, "Current Liabilities")
    retained_earnings = _latest_val(bs, "Retained Earnings")
    working_capital = (current_assets - current_liabilities) if (current_assets is not None and current_liabilities is not None) else None

    # Income statement items
    ebit = _latest_val(fin, "EBIT")
    revenue = _latest_val(fin, "Total Revenue")

    # Market value of equity
    market_cap = info.get("marketCap")
    if market_cap is None:
        market_cap = info.get("currentMarketCap")

    # Components
    x1 = _safe_div(working_capital, total_assets)
    x2 = _safe_div(retained_earnings, total_assets)
    x3 = _safe_div(ebit, total_assets)
    x4 = _safe_div(market_cap, total_liabilities)
    x5 = _safe_div(revenue, total_assets)

    z = None
    if all(v is not None for v in [x1, x2, x3, x4, x5]):
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

    # Interpretation
    zone = "unknown"
    if z is not None:
        if z > 2.99:
            zone = "Safe"
        elif z > 1.81:
            zone = "Grey"
        else:
            zone = "Distress"

    return {
        "zScore": round(z, 4) if z is not None else None,
        "zone": zone,
        "components": {
            "x1_workingCapitalToAssets": round(x1, 6) if x1 is not None else None,
            "x2_retainedEarningsToAssets": round(x2, 6) if x2 is not None else None,
            "x3_ebitToAssets": round(x3, 6) if x3 is not None else None,
            "x4_marketValueToLiabilities": round(x4, 4) if x4 is not None else None,
            "x5_salesToAssets": round(x5, 4) if x5 is not None else None,
        },
        "isFinancial": False,
    }


# ---------------------------------------------------------------------------
# Piotroski F-Score (9-point fundamental strength)
# ---------------------------------------------------------------------------

def _piotroski(fin, bs, cf, fin_q=None, bs_q=None, cf_q=None) -> dict:
    """Compute Piotroski F-Score with all 9 criteria.

    Parameters
    ----------
    fin, bs, cf : Annual financial statement DataFrames
    fin_q, bs_q, cf_q : Quarterly DataFrames (fallback if annual only has 1 column)
    """
    net_income = _latest_val(fin, "Net Income")
    total_assets = _latest_val(bs, "Total Assets")
    current_assets = _latest_val(bs, "Current Assets")
    current_liabilities = _latest_val(bs, "Current Liabilities")
    total_liabilities = _latest_val(bs, "Total Liabilities Net Minority Interest")
    if total_liabilities is None:
        total_liabilities = _latest_val(bs, "Total Liabilities")
    long_term_debt = _latest_val(bs, "Long Term Debt")
    revenue = _latest_val(fin, "Total Revenue")
    gross_profit = _latest_val(fin, "Gross Profit")
    operating_cash_flow = _latest_val(cf, "Operating Cash Flow")
    shares = _latest_val(bs, "Ordinary Shares Number")
    if shares is None:
        shares = _latest_val(bs, "Share Issued")

    # Helper: try annual _prior_val, fall back to quarterly (4 quarters back)
    def _prior(df_annual, df_quarterly, row_name: str) -> float | None:
        v = _prior_val(df_annual, row_name)
        if v is not None:
            return v
        if df_quarterly is not None and row_name in df_quarterly.index and df_quarterly.shape[1] >= 4:
            try:
                vq = float(df_quarterly.loc[row_name].iloc[3])
                return vq if not math.isnan(vq) else None
            except Exception:
                pass
        return None

    criteria: dict[str, bool | None] = {}
    score = 0

    # 1. Positive net income
    c1 = net_income is not None and net_income > 0
    criteria["positiveNetIncome"] = c1
    if c1:
        score += 1

    # 2. Positive operating cash flow
    c2 = operating_cash_flow is not None and operating_cash_flow > 0
    criteria["positiveOperatingCF"] = c2
    if c2:
        score += 1

    # 3. ROA increasing (vs prior year)
    roa = _safe_div(net_income, total_assets)
    ni_prior = _prior(fin, fin_q, "Net Income")
    ta_prior = _prior(bs, bs_q, "Total Assets")
    roa_prior = _safe_div(ni_prior, ta_prior)

    c3 = roa is not None and (roa_prior is None or roa > roa_prior)
    criteria["roaIncreasing"] = c3
    if c3:
        score += 1

    # 4. Operating CF > Net Income (quality of earnings)
    c4 = (operating_cash_flow is not None and net_income is not None
          and operating_cash_flow > net_income)
    criteria["operatingCFGreaterThanNI"] = c4
    if c4:
        score += 1

    # 5. Decreasing long-term debt ratio
    ltd_to_assets = _safe_div(long_term_debt, total_assets)
    ltd_prior = _prior(bs, bs_q, "Long Term Debt")
    ta_prior2 = _prior(bs, bs_q, "Total Assets")
    ltd_ratio_prior = _safe_div(ltd_prior, ta_prior2)

    c5 = ltd_to_assets is not None and (ltd_ratio_prior is None or ltd_to_assets <= ltd_ratio_prior)
    criteria["decreasingLeverage"] = c5
    if c5:
        score += 1

    # 6. Increasing current ratio
    cr = _safe_div(current_assets, current_liabilities)
    ca_prior = _prior(bs, bs_q, "Current Assets")
    cl_prior = _prior(bs, bs_q, "Current Liabilities")
    cr_prior = _safe_div(ca_prior, cl_prior)

    c6 = cr is not None and (cr_prior is None or cr > cr_prior)
    criteria["increasingCurrentRatio"] = c6
    if c6:
        score += 1

    # 7. No share dilution
    shares_prior = _prior(bs, bs_q, "Ordinary Shares Number")
    if shares_prior is None:
        shares_prior = _prior(bs, bs_q, "Share Issued")

    c7 = shares is not None and (shares_prior is None or shares <= shares_prior)
    criteria["noShareDilution"] = c7
    if c7:
        score += 1

    # 8. Increasing gross margin
    gm = _safe_div(gross_profit, revenue)
    gp_prior = _prior(fin, fin_q, "Gross Profit")
    rev_prior = _prior(fin, fin_q, "Total Revenue")
    gm_prior = _safe_div(gp_prior, rev_prior)

    c8 = gm is not None and (gm_prior is None or gm > gm_prior)
    criteria["increasingGrossMargin"] = c8
    if c8:
        score += 1

    # 9. Increasing asset turnover
    turnover = _safe_div(revenue, total_assets)
    rev_prior2 = _prior(fin, fin_q, "Total Revenue")
    ta_prior3 = _prior(bs, bs_q, "Total Assets")
    turnover_prior = _safe_div(rev_prior2, ta_prior3)

    c9 = turnover is not None and (turnover_prior is None or turnover > turnover_prior)
    criteria["increasingAssetTurnover"] = c9
    if c9:
        score += 1

    return {
        "score": score,
        "maxScore": 9,
        "interpretation": "Strong" if score >= 7 else ("Average" if score >= 4 else "Weak"),
        "criteria": criteria,
    }


# ---------------------------------------------------------------------------
# Beneish M-Score (8-index earnings manipulation detection)
# M = -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI
#     + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI
# ---------------------------------------------------------------------------

def _beneish(fin, bs, cf, fin_q=None, bs_q=None, cf_q=None) -> dict:
    """Compute Beneish M-Score with 8 indexes.

    Parameters
    ----------
    fin, bs, cf : Annual financial statement DataFrames
    fin_q, bs_q, cf_q : Quarterly DataFrames (fallback if annual only has 1 column)
    """
    # Current year values
    revenue = _latest_val(fin, "Total Revenue")
    cogs = _latest_val(fin, "Cost Of Revenue")
    net_income = _latest_val(fin, "Net Income")
    operating_cf = _latest_val(cf, "Operating Cash Flow")
    current_assets = _latest_val(bs, "Current Assets")
    current_liabilities = _latest_val(bs, "Current Liabilities")
    total_assets = _latest_val(bs, "Total Assets")
    total_liabilities = _latest_val(bs, "Total Liabilities Net Minority Investment")
    if total_liabilities is None:
        total_liabilities = _latest_val(bs, "Total Liabilities")
    long_term_debt = _latest_val(bs, "Long Term Debt")
    ppe = _latest_val(bs, "Net PPE")
    if ppe is None:
        ppe = _latest_val(bs, "Property Plant and Equipment")
    if ppe is None:
        ppe = _latest_val(bs, "Gross PPE")
    depreciation = _latest_val(bs, "Accumulated Depreciation")
    receivables = _latest_val(bs, "Accounts Receivable")
    sga = _latest_val(fin, "Selling General And Administration")

    # Helper: try annual _prior_val, fall back to quarterly (4 quarters back)
    def _prior(df_annual, df_quarterly, row_name: str) -> float | None:
        v = _prior_val(df_annual, row_name)
        if v is not None:
            return v
        if df_quarterly is not None and row_name in df_quarterly.index and df_quarterly.shape[1] >= 4:
            try:
                vq = float(df_quarterly.loc[row_name].iloc[3])
                return vq if not math.isnan(vq) else None
            except Exception:
                pass
        return None

    rev_prior = _prior(fin, fin_q, "Total Revenue")
    cogs_prior = _prior(fin, fin_q, "Cost Of Revenue")
    receivables_prior = _prior(bs, bs_q, "Accounts Receivable")
    ca_prior = _prior(bs, bs_q, "Current Assets")
    ppe_prior = _prior(bs, bs_q, "Net PPE")
    if ppe_prior is None:
        ppe_prior = _prior(bs, bs_q, "Property Plant and Equipment")
    if ppe_prior is None:
        ppe_prior = _prior(bs, bs_q, "Gross PPE")
    ta_prior = _prior(bs, bs_q, "Total Assets")
    dep_prior = _prior(bs, bs_q, "Accumulated Depreciation")
    cl_prior = _prior(bs, bs_q, "Current Liabilities")
    ltd_prior = _prior(bs, bs_q, "Long Term Debt")
    tl_prior = _prior(bs, bs_q, "Total Liabilities Net Minority Interest")
    if tl_prior is None:
        tl_prior = _prior(bs, bs_q, "Total Liabilities")
    sga_prior = _prior(fin, fin_q, "Selling General And Administration")
    ni_prior = _prior(fin, fin_q, "Net Income")
    ocf_prior = _prior(cf, cf_q, "Operating Cash Flow")

    indexes: dict[str, float | None] = {}

    # DSRI: Days Sales in Receivables Index
    dsri = None
    if all(v is not None for v in [receivables, revenue, receivables_prior, rev_prior]) and revenue != 0 and rev_prior != 0:
        dsri = (receivables / revenue) / (receivables_prior / rev_prior)
    indexes["dsri"] = round(dsri, 4) if dsri is not None else None

    # GMI: Gross Margin Index
    gmi = None
    if all(v is not None for v in [revenue, cogs, rev_prior, cogs_prior]):
        gm = (revenue - cogs) / revenue if revenue != 0 else None
        gm_prior = (rev_prior - cogs_prior) / rev_prior if rev_prior != 0 else None
        if gm is not None and gm_prior is not None and gm_prior != 0:
            gmi = gm_prior / gm
    indexes["gmi"] = round(gmi, 4) if gmi is not None else None

    # AQI: Asset Quality Index
    aqi = None
    if all(v is not None for v in [current_assets, ppe, total_assets, ca_prior, ppe_prior, ta_prior]):
        non_current = total_assets - current_assets - ppe
        non_current_prior = ta_prior - ca_prior - ppe_prior
        if ta_prior != 0 and non_current_prior is not None:
            aqi_ratio = non_current / total_assets if total_assets != 0 else None
            aqi_ratio_prior = non_current_prior / ta_prior
            if aqi_ratio is not None and aqi_ratio_prior is not None and aqi_ratio_prior != 0:
                aqi = aqi_ratio / aqi_ratio_prior
    indexes["aqi"] = round(aqi, 4) if aqi is not None else None

    # SGI: Sales Growth Index
    sgi = _safe_div(revenue, rev_prior)
    indexes["sgi"] = round(sgi, 4) if sgi is not None else None

    # DEPI: Depreciation Index
    depi = None
    if all(v is not None for v in [depreciation, ppe, dep_prior, ppe_prior]):
        dep_rate = depreciation / (depreciation + ppe) if (depreciation + ppe) != 0 else None
        dep_rate_prior = dep_prior / (dep_prior + ppe_prior) if (dep_prior + ppe_prior) != 0 else None
        if dep_rate is not None and dep_rate_prior is not None and dep_rate_prior != 0:
            depi = dep_rate_prior / dep_rate
    indexes["depi"] = round(depi, 4) if depi is not None else None

    # SGAI: Sales General & Administrative Index
    sgai = None
    if all(v is not None for v in [sga, revenue, sga_prior, rev_prior]) and revenue != 0 and rev_prior != 0:
        sgai = (sga / revenue) / (sga_prior / rev_prior)
    indexes["sgai"] = round(sgai, 4) if sgai is not None else None

    # TATA: Total Accruals to Total Assets
    tata = None
    if all(v is not None for v in [net_income, operating_cf, total_assets]) and total_assets != 0:
        tata = (net_income - operating_cf) / total_assets
    indexes["tata"] = round(tata, 6) if tata is not None else None

    # LVGI: Leverage Index
    lvgi = None
    if all(v is not None for v in [total_liabilities, total_assets, tl_prior, ta_prior]):
        lev = total_liabilities / total_assets if total_assets != 0 else None
        lev_prior = tl_prior / ta_prior if ta_prior != 0 else None
        if lev is not None and lev_prior is not None and lev_prior != 0:
            lvgi = lev / lev_prior
    indexes["lvgi"] = round(lvgi, 4) if lvgi is not None else None

    # M-Score computation
    coeffs = {
        "dsri": 0.920, "gmi": 0.528, "aqi": 0.404, "sgi": 0.892,
        "depi": 0.115, "sgai": -0.172, "tata": 4.679, "lvgi": -0.327,
    }
    m_score = None
    valid_components = 0
    m_parts: dict[str, float | None] = {}
    running = -4.84  # intercept
    for key, coef in coeffs.items():
        v = indexes.get(key)
        if v is not None:
            running += coef * v
            m_parts[key] = round(coef * v, 4)
            valid_components += 1
        else:
            m_parts[key] = None

    if valid_components >= 4:  # need at least half the indexes
        m_score = round(running, 4)

    # Interpretation: M > -2.22 suggests earnings manipulation
    manipulation_likely = m_score is not None and m_score > -2.22

    return {
        "mScore": m_score,
        "manipulationLikely": manipulation_likely if m_score is not None else None,
        "interpretation": "Likely manipulator" if manipulation_likely else ("Not flagged" if m_score is not None else "Insufficient data"),
        "indexes": indexes,
        "mComponents": m_parts,
        "validComponents": valid_components,
        "totalComponents": 8,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("corporate_health")
def get_corporate_health(ticker: str) -> dict:
    """Return Altman Z-Score, Piotroski F-Score, and Beneish M-Score for a ticker."""
    ticker = ticker.strip().upper()
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        fin = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow

        # Quarterly fallback for prior-year comparisons (if annual only has 1 column)
        fin_q = stock.quarterly_financials if fin is not None and fin.shape[1] < 2 else None
        bs_q = stock.quarterly_balance_sheet if bs is not None and bs.shape[1] < 2 else None
        cf_q = stock.quarterly_cashflow if cf is not None and cf.shape[1] < 2 else None

        # Validate we have enough data
        if fin is None or fin.empty:
            return {"ticker": ticker, "error": "No financial statement data available for this ticker"}
        if bs is None or bs.empty:
            return {"ticker": ticker, "error": "No balance sheet data available for this ticker"}

        # Determine if financial company (banks, insurers — Altman Z not applicable)
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        is_financial = sector in ("Financial Services", "Financial") or "Bank" in industry or "Insurance" in industry

        z_data = _altman_z(fin, bs, info)
        z_data["isFinancial"] = is_financial
        if is_financial:
            z_data["note"] = "Altman Z-Score is not applicable to financial firms. Use with caution."

        piotroski_data = _piotroski(fin, bs, cf, fin_q, bs_q, cf_q)

        beneish_data = _beneish(fin, bs, cf, fin_q, bs_q, cf_q)

        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": sector or None,
            "industry": industry or None,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "altmanZ": z_data,
            "piotroski": piotroski_data,
            "beneish": beneish_data,
            "asOf": None,
        }
    except Exception as exc:
        logger.warning("corporate_health failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "error": str(exc)}


# ---------------------------------------------------------------------------
# Earnings Quality & Accruals Monitor (Sloan 1996 accruals anomaly)
# ---------------------------------------------------------------------------

def _percentile(sorted_vals: list[float], pct: float) -> float | None:
    """Linear-interpolation percentile (matches numpy's default) over a
    pre-sorted ascending list."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = pct * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def compute_earnings_quality(rows: list[dict]) -> dict:
    """Pure computation of the Sloan (1996) accruals anomaly over a universe.

    ``rows`` is a list of already-extracted per-ticker raw inputs::

        {ticker, netIncome, operatingCashFlow, totalAssets, prevTotalAssets,
         cash, prevCash, totalLiabilities, prevTotalLiabilities,
         totalDebt, prevTotalDebt, sector}

    Any field may be ``None`` — every derived metric degrades to ``None``
    rather than raising or fabricating a value.

    Metrics per ticker
    -------------------
    - ``accrualRatio`` (Sloan accrual proxy) =
      (netIncome − operatingCashFlow) / average total assets, where average
      total assets is the mean of the current and prior total assets (or
      just the current value if the prior year is unavailable).
    - ``cashConversion`` = operatingCashFlow / netIncome, only when
      netIncome > 0 (undefined/None otherwise).
    - ``noaGrowth`` = YoY growth of Net Operating Assets, where
      NOA = (totalAssets − cash) − (totalLiabilities − totalDebt); cash and
      totalDebt default to 0 when missing, but a missing totalAssets or
      totalLiabilities (current or prior) makes NOA/noaGrowth None.
    - ``qualityScore`` (0–100, higher = better quality; None if
      accrualRatio can't be computed):
        1. start at 50
        2. += 25 * (1 − min(|accrualRatio| / 0.15, 1))  — smaller |accruals| is better
        3. += up to 15, scaled linearly from cashConversion=1 (0 bonus) to
           cashConversion>=1.5 (full 15 bonus); no bonus below 1
        4. += 10 flat if noaGrowth is not None and noaGrowth < 0.20
        5. clamp to [0, 100]
    - ``flag`` = True when accrualRatio falls in the worst (highest) decile
      of accrualRatio across the universe (90th percentile threshold,
      linear interpolation).

    Returns ``{}`` for an empty/failed universe (cache `skip_if` guard).
    """
    if not rows:
        return {}

    computed: list[dict] = []
    for r in rows:
        ticker = r.get("ticker")
        net_income = r.get("netIncome")
        operating_cf = r.get("operatingCashFlow")
        total_assets = r.get("totalAssets")
        prev_total_assets = r.get("prevTotalAssets")
        cash = r.get("cash")
        prev_cash = r.get("prevCash")
        total_liabilities = r.get("totalLiabilities")
        prev_total_liabilities = r.get("prevTotalLiabilities")
        total_debt = r.get("totalDebt")
        prev_total_debt = r.get("prevTotalDebt")
        sector = r.get("sector")

        # Average total assets (denominator for the accrual ratio)
        if total_assets is not None and prev_total_assets is not None:
            avg_assets = (total_assets + prev_total_assets) / 2.0
        elif total_assets is not None:
            avg_assets = total_assets
        else:
            avg_assets = None

        accrual_ratio = None
        if (net_income is not None and operating_cf is not None
                and avg_assets is not None and avg_assets != 0):
            accrual_ratio = (net_income - operating_cf) / avg_assets

        cash_conversion = None
        if net_income is not None and net_income > 0 and operating_cf is not None:
            cash_conversion = operating_cf / net_income

        # Net Operating Assets — cash/debt default to 0 when missing.
        cash_now = cash if cash is not None else 0.0
        debt_now = total_debt if total_debt is not None else 0.0
        cash_prior = prev_cash if prev_cash is not None else 0.0
        debt_prior = prev_total_debt if prev_total_debt is not None else 0.0

        noa = None
        if total_assets is not None and total_liabilities is not None:
            noa = (total_assets - cash_now) - (total_liabilities - debt_now)

        prev_noa = None
        if prev_total_assets is not None and prev_total_liabilities is not None:
            prev_noa = (prev_total_assets - cash_prior) - (prev_total_liabilities - debt_prior)

        noa_growth = None
        if noa is not None and prev_noa is not None and prev_noa != 0:
            noa_growth = (noa - prev_noa) / abs(prev_noa)

        computed.append({
            "ticker": ticker,
            "sector": sector,
            "accrualRatio": accrual_ratio,
            "cashConversion": cash_conversion,
            "noaGrowth": noa_growth,
        })

    n = len(computed)
    accrual_vals = sorted(c["accrualRatio"] for c in computed if c["accrualRatio"] is not None)
    decile_threshold = _percentile(accrual_vals, 0.9)

    for c in computed:
        accrual_ratio = c["accrualRatio"]
        cash_conversion = c["cashConversion"]
        noa_growth = c["noaGrowth"]

        if accrual_ratio is None:
            c["qualityScore"] = None
            c["flag"] = False
            continue

        score = 50.0
        score += 25.0 * (1.0 - min(abs(accrual_ratio) / 0.15, 1.0))
        if cash_conversion is not None and cash_conversion >= 1.0:
            score += min(max(cash_conversion - 1.0, 0.0) / 0.5, 1.0) * 15.0
        if noa_growth is not None and noa_growth < 0.20:
            score += 10.0
        score = max(0.0, min(100.0, score))

        c["qualityScore"] = round(score, 2)
        c["flag"] = decile_threshold is not None and accrual_ratio >= decile_threshold

    # Round the metric fields after decile/score computation.
    for c in computed:
        for key in ("accrualRatio", "cashConversion", "noaGrowth"):
            if c[key] is not None:
                c[key] = round(c[key], 6)

    accrual_list = [c["accrualRatio"] for c in computed if c["accrualRatio"] is not None]
    cc_list = [c["cashConversion"] for c in computed if c["cashConversion"] is not None]
    flagged_count = sum(1 for c in computed if c["flag"])

    computed.sort(key=lambda c: (c["qualityScore"] is None, -(c["qualityScore"] or 0.0)))

    return {
        "asOf": date.today().isoformat(),
        "kpis": {
            "medianAccrual": round(_median(accrual_list), 6) if accrual_list else None,
            "medianCashConversion": round(_median(cc_list), 6) if cc_list else None,
            "pctFlagged": round(100.0 * flagged_count / n, 2) if n else None,
            "n": n,
        },
        "rows": computed,
    }


def _fetch_eq_inputs(ticker: str, sector: str | None) -> dict | None:
    """Fetch raw earnings-quality inputs for a single ticker from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        fin = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow
        if fin is None or fin.empty or bs is None or bs.empty or cf is None or cf.empty:
            return None

        cash = _latest_val(bs, "Cash And Cash Equivalents")
        if cash is None:
            cash = _latest_val(bs, "Cash Cash Equivalents And Short Term Investments")
        prev_cash = _prior_val(bs, "Cash And Cash Equivalents")
        if prev_cash is None:
            prev_cash = _prior_val(bs, "Cash Cash Equivalents And Short Term Investments")

        total_liabilities = _latest_val(bs, "Total Liabilities Net Minority Interest")
        if total_liabilities is None:
            total_liabilities = _latest_val(bs, "Total Liabilities")
        prev_total_liabilities = _prior_val(bs, "Total Liabilities Net Minority Interest")
        if prev_total_liabilities is None:
            prev_total_liabilities = _prior_val(bs, "Total Liabilities")

        return {
            "ticker": ticker,
            "netIncome": _latest_val(fin, "Net Income"),
            "operatingCashFlow": _latest_val(cf, "Operating Cash Flow"),
            "totalAssets": _latest_val(bs, "Total Assets"),
            "prevTotalAssets": _prior_val(bs, "Total Assets"),
            "cash": cash,
            "prevCash": prev_cash,
            "totalLiabilities": total_liabilities,
            "prevTotalLiabilities": prev_total_liabilities,
            "totalDebt": _latest_val(bs, "Total Debt"),
            "prevTotalDebt": _prior_val(bs, "Total Debt"),
            "sector": sector,
        }
    except Exception:
        logger.debug("earnings quality fetch failed for %s", ticker, exc_info=True)
        return None


@cached("earnings_quality")
def get_earnings_quality(universe: str = "dow") -> dict:
    """Fetch + compute the Earnings Quality & Accruals Monitor for a universe.

    ``universe`` is one of "dow" | "ndx" | "sp500" (see ``constituents.py``).
    Returns ``{}`` when the universe can't be resolved or no ticker yields
    usable statement data (never fabricated).
    """
    members = constituents.get_constituents(universe)
    if not members:
        return {}

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {
            ex.submit(_fetch_eq_inputs, m["symbol"], m.get("sector")): m["symbol"]
            for m in members
        }
        for fut in as_completed(futures):
            try:
                row = fut.result()
                if row is not None:
                    rows.append(row)
            except Exception:
                logger.debug("earnings quality worker failed", exc_info=True)

    result = compute_earnings_quality(rows)
    if not result:
        return {}
    result["universe"] = universe
    return result
