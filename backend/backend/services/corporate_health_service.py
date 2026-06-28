"""Corporate Health Monitor — Phase 27.

Altman Z-Score, Piotroski F-Score, and Beneish M-Score for any ticker.
Pure calculation from yfinance balance sheet / income statement / cash flow.
"""
from __future__ import annotations

import logging
import math

import yfinance as yf

from ..cache import cached

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

def _piotroski(fin, bs, cf) -> dict:
    """Compute Piotroski F-Score with all 9 criteria."""
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
    # Use net_income / total_assets for current year
    roa = _safe_div(net_income, total_assets)
    # Prior year
    try:
        ni_prior = float(fin.loc["Net Income"].iloc[1]) if "Net Income" in fin.index and fin.shape[1] > 1 else None
        ta_prior = float(bs.loc["Total Assets"].iloc[1]) if "Total Assets" in bs.index and bs.shape[1] > 1 else None
        roa_prior = _safe_div(ni_prior, ta_prior)
    except Exception:
        roa_prior = None

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
    try:
        ltd_prior = float(bs.loc["Long Term Debt"].iloc[1]) if "Long Term Debt" in bs.index and bs.shape[1] > 1 else None
        ta_prior2 = float(bs.loc["Total Assets"].iloc[1]) if "Total Assets" in bs.index and bs.shape[1] > 1 else None
        ltd_ratio_prior = _safe_div(ltd_prior, ta_prior2)
    except Exception:
        ltd_ratio_prior = None

    c5 = ltd_to_assets is not None and (ltd_ratio_prior is None or ltd_to_assets <= ltd_ratio_prior)
    criteria["decreasingLeverage"] = c5
    if c5:
        score += 1

    # 6. Increasing current ratio
    cr = _safe_div(current_assets, current_liabilities)
    try:
        ca_prior = float(bs.loc["Current Assets"].iloc[1]) if "Current Assets" in bs.index and bs.shape[1] > 1 else None
        cl_prior = float(bs.loc["Current Liabilities"].iloc[1]) if "Current Liabilities" in bs.index and bs.shape[1] > 1 else None
        cr_prior = _safe_div(ca_prior, cl_prior)
    except Exception:
        cr_prior = None

    c6 = cr is not None and (cr_prior is None or cr > cr_prior)
    criteria["increasingCurrentRatio"] = c6
    if c6:
        score += 1

    # 7. No share dilution
    try:
        shares_prior = float(bs.loc["Ordinary Shares Number"].iloc[1]) if "Ordinary Shares Number" in bs.index and bs.shape[1] > 1 else None
        if shares_prior is None:
            shares_prior = float(bs.loc["Share Issued"].iloc[1]) if "Share Issued" in bs.index and bs.shape[1] > 1 else None
    except Exception:
        shares_prior = None

    c7 = shares is not None and (shares_prior is None or shares <= shares_prior)
    criteria["noShareDilution"] = c7
    if c7:
        score += 1

    # 8. Increasing gross margin
    gm = _safe_div(gross_profit, revenue)
    try:
        gp_prior = float(fin.loc["Gross Profit"].iloc[1]) if "Gross Profit" in fin.index and fin.shape[1] > 1 else None
        rev_prior = float(fin.loc["Total Revenue"].iloc[1]) if "Total Revenue" in fin.index and fin.shape[1] > 1 else None
        gm_prior = _safe_div(gp_prior, rev_prior)
    except Exception:
        gm_prior = None

    c8 = gm is not None and (gm_prior is None or gm > gm_prior)
    criteria["increasingGrossMargin"] = c8
    if c8:
        score += 1

    # 9. Increasing asset turnover
    turnover = _safe_div(revenue, total_assets)
    try:
        rev_prior2 = float(fin.loc["Total Revenue"].iloc[1]) if "Total Revenue" in fin.index and fin.shape[1] > 1 else None
        ta_prior3 = float(bs.loc["Total Assets"].iloc[1]) if "Total Assets" in bs.index and bs.shape[1] > 1 else None
        turnover_prior = _safe_div(rev_prior2, ta_prior3)
    except Exception:
        turnover_prior = None

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

def _beneish(fin, bs, cf) -> dict:
    """Compute Beneish M-Score with 8 indexes."""
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

    # Prior year values
    def _prior(df, row_name: str) -> float | None:
        try:
            if df is None or df.empty or row_name not in df.index or df.shape[1] < 2:
                return None
            v = float(df.loc[row_name].iloc[1])
            return v if not math.isnan(v) else None
        except Exception:
            return None

    rev_prior = _prior(fin, "Total Revenue")
    cogs_prior = _prior(fin, "Cost Of Revenue")
    receivables_prior = _prior(bs, "Accounts Receivable")
    ca_prior = _prior(bs, "Current Assets")
    ppe_prior = _prior(bs, "Net PPE")
    if ppe_prior is None:
        ppe_prior = _prior(bs, "Property Plant and Equipment")
    if ppe_prior is None:
        ppe_prior = _prior(bs, "Gross PPE")
    ta_prior = _prior(bs, "Total Assets")
    dep_prior = _prior(bs, "Accumulated Depreciation")
    cl_prior = _prior(bs, "Current Liabilities")
    ltd_prior = _prior(bs, "Long Term Debt")
    tl_prior = _prior(bs, "Total Liabilities Net Minority Interest")
    if tl_prior is None:
        tl_prior = _prior(bs, "Total Liabilities")
    sga_prior = _prior(fin, "Selling General And Administration")
    ni_prior = _prior(fin, "Net Income")
    ocf_prior = _prior(cf, "Operating Cash Flow")

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

        piotroski_data = _piotroski(fin, bs, cf)

        beneish_data = _beneish(fin, bs, cf)

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
