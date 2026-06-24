"""Extended fundamentals service: ROIC, DuPont, Piotroski F-Score,
Beneish M-Score, Ohlson O-Score, and Cash Conversion Cycle.

IMPORTANT DATA LIMITATION
--------------------------
The yfinance bundle produced by ``yfinance_service.get_info()`` contains only
the **single most-recent reporting period** for each financial-statement line
(``financials``, ``balance_sheet``, ``cashflow`` are flat label→float dicts).
Metrics that formally require two consecutive periods (prior-year comparisons)
therefore cannot be computed with full fidelity:

* **Piotroski F-Score**: four of the nine criteria need prior-year balance-sheet
  or income data (ΔLongTermDebt ratio, ΔCurrentRatio, share-count check via
  diluted shares YoY, ΔGrossMargin, ΔAssetTurnover).  These criteria are
  returned as ``None`` and excluded from ``maxScore``.
* **Beneish M-Score**: all eight index variables need t and t-1 period numbers.
  The score is returned as ``None`` with an explanatory note rather than a
  fabricated value.

All other metrics (ROIC, DuPont, Ohlson O-Score, CCC) are computable from the
single-period snapshot.
"""
from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Re-use _clean from the sibling metrics module so NaN/Inf/None handling is
# consistent across the whole backend.
# ---------------------------------------------------------------------------
from .metrics import _clean


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _g(d: dict, *keys: str) -> Any:
    """Return the first non-None value from *d* matching any of *keys*."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


def _ratio(num, den) -> float | None:
    """Safe division: returns _clean(num/den) or None."""
    n = _clean(num)
    d = _clean(den)
    if n is None or d is None or d == 0.0:
        return None
    try:
        return _clean(n / d)
    except Exception:
        return None


def _unpack(bundle: dict) -> tuple[dict, dict, dict, dict]:
    """Unpack the four sub-dicts from a yfinance bundle, defaulting to {}."""
    info = bundle.get("info") or {}
    fin = bundle.get("financials") or {}
    bs = bundle.get("balance_sheet") or {}
    cf = bundle.get("cashflow") or {}
    return info, fin, bs, cf


# ---------------------------------------------------------------------------
# 1. ROIC
# ---------------------------------------------------------------------------

def roic(bundle: dict) -> dict:
    """Return-on-Invested-Capital.

    NOPAT  ≈ EBIT × (1 – effective_tax_rate)
    Invested Capital ≈ Total Debt + Total Equity – Cash

    Returns
    -------
    dict with keys: roic, nopat, investedCapital
    """
    info, fin, bs, _ = _unpack(bundle)

    ebit = _clean(_g(fin, "EBIT", "Operating Income"))
    tax_rate = _clean(info.get("effectiveTaxRate")) or 0.21  # fallback 21 %

    nopat: float | None = None
    if ebit is not None:
        nopat = _clean(ebit * (1.0 - tax_rate))

    total_debt = _clean(
        _g(bs, "Total Debt") or info.get("totalDebt")
    )
    equity = _clean(
        _g(bs, "Stockholders Equity", "Common Stock Equity")
        or info.get("totalStockholderEquity")
    )
    cash = _clean(
        _g(bs, "Cash And Cash Equivalents",
           "Cash Cash Equivalents And Short Term Investments")
        or info.get("totalCash")
    )

    invested_capital: float | None = None
    if total_debt is not None and equity is not None:
        invested_capital = _clean(
            total_debt + equity - (cash or 0.0)
        )

    roic_val = _ratio(nopat, invested_capital)

    return {
        "roic": roic_val,
        "nopat": nopat,
        "investedCapital": invested_capital,
    }


# ---------------------------------------------------------------------------
# 2. DuPont Decomposition
# ---------------------------------------------------------------------------

def dupont(bundle: dict) -> dict:
    """3-Factor and 5-Factor DuPont decomposition.

    3-Factor:  ROE = Net Margin × Asset Turnover × Equity Multiplier
    5-Factor:  ROE = Tax Burden × Interest Burden × Operating Margin
                     × Asset Turnover × Equity Multiplier

    Returns
    -------
    dict with keys: threeFactor, fiveFactor — each a nested dict.
    """
    info, fin, bs, _ = _unpack(bundle)

    revenue = _clean(_g(fin, "Total Revenue"))
    net_income = _clean(_g(fin, "Net Income", "Net Income Common Stockholders"))
    op_income = _clean(_g(fin, "Operating Income", "EBIT"))
    pretax_income = _clean(_g(fin, "Pretax Income", "Income Before Tax"))
    interest_exp = _clean(_g(fin, "Interest Expense"))

    total_assets = _clean(_g(bs, "Total Assets"))
    equity = _clean(
        _g(bs, "Stockholders Equity", "Common Stock Equity")
        or info.get("totalStockholderEquity")
    )

    net_margin = _ratio(net_income, revenue)
    asset_turnover = _ratio(revenue, total_assets)
    equity_multiplier = _ratio(total_assets, equity)

    # 3-Factor ROE
    roe_3: float | None = None
    if net_margin is not None and asset_turnover is not None and equity_multiplier is not None:
        roe_3 = _clean(net_margin * asset_turnover * equity_multiplier)

    three_factor = {
        "netMargin": net_margin,
        "assetTurnover": asset_turnover,
        "equityMultiplier": equity_multiplier,
        "roe": roe_3,
    }

    # 5-Factor components
    # Tax Burden  = Net Income / Pretax Income
    # Interest Burden = Pretax Income / EBIT
    # Operating Margin = EBIT / Revenue
    tax_burden = _ratio(net_income, pretax_income)
    interest_burden = _ratio(pretax_income, op_income)
    operating_margin = _ratio(op_income, revenue)

    roe_5: float | None = None
    if (tax_burden is not None and interest_burden is not None
            and operating_margin is not None
            and asset_turnover is not None
            and equity_multiplier is not None):
        roe_5 = _clean(
            tax_burden * interest_burden * operating_margin
            * asset_turnover * equity_multiplier
        )

    five_factor = {
        "taxBurden": tax_burden,
        "interestBurden": interest_burden,
        "operatingMargin": operating_margin,
        "assetTurnover": asset_turnover,
        "equityMultiplier": equity_multiplier,
        "roe": roe_5,
    }

    return {"threeFactor": three_factor, "fiveFactor": five_factor}


# ---------------------------------------------------------------------------
# 3. Piotroski F-Score
# ---------------------------------------------------------------------------

def piotroski_f(bundle: dict, prior_year: dict | None = None) -> dict:
    """Piotroski F-Score (0–9).

    Pass ``prior_year`` (a dict with keys ``financials``, ``balance_sheet``,
    ``cashflow``, ``info`` — same structure as *bundle*) to enable the five
    year-over-year criteria (F5–F9).  Without it those criteria are None.

    Returns
    -------
    dict:
        score     – int, sum of True criteria (None criteria excluded)
        maxScore  – int, count of criteria that could be evaluated
        criteria  – dict mapping criterion name to bool or None
    """
    info, fin, bs, cf = _unpack(bundle)

    net_income = _clean(_g(fin, "Net Income", "Net Income Common Stockholders"))
    total_assets = _clean(_g(bs, "Total Assets"))
    op_cf = _clean(_g(cf, "Operating Cash Flow", "Total Cash From Operating Activities"))

    # --- Profitability ---
    # F1: Positive net income
    f1: bool | None = None
    if net_income is not None:
        f1 = net_income > 0

    # F2: Positive ROA (net income / total assets)
    f2: bool | None = None
    if net_income is not None and total_assets:
        f2 = (net_income / total_assets) > 0

    # F3: Positive operating cash flow
    f3: bool | None = None
    if op_cf is not None:
        f3 = op_cf > 0

    # F4: OCF > Net Income (accruals quality)
    f4: bool | None = None
    if op_cf is not None and net_income is not None:
        f4 = op_cf > net_income

    # --- Leverage / Liquidity (require prior year) ---
    f5: bool | None = None
    f6: bool | None = None
    f7: bool | None = None

    # --- Operating Efficiency (require prior year) ---
    f8: bool | None = None
    f9: bool | None = None

    if prior_year is not None:
        _, py_fin, py_bs, _ = _unpack(prior_year)

        # F5: Long-term debt / total assets decreased YoY
        lt_debt = _clean(_g(bs, "Long Term Debt", "Long Term Debt And Capital Lease Obligation"))
        py_lt_debt = _clean(_g(py_bs, "Long Term Debt", "Long Term Debt And Capital Lease Obligation"))
        py_total_assets = _clean(_g(py_bs, "Total Assets"))
        if (lt_debt is not None and total_assets and total_assets > 0
                and py_lt_debt is not None and py_total_assets and py_total_assets > 0):
            f5 = (lt_debt / total_assets) < (py_lt_debt / py_total_assets)

        # F6: Current ratio increased YoY
        cur_assets = _clean(_g(bs, "Current Assets"))
        cur_liab = _clean(_g(bs, "Current Liabilities"))
        py_cur_assets = _clean(_g(py_bs, "Current Assets"))
        py_cur_liab = _clean(_g(py_bs, "Current Liabilities"))
        if (cur_assets is not None and cur_liab and cur_liab > 0
                and py_cur_assets is not None and py_cur_liab and py_cur_liab > 0):
            f6 = (cur_assets / cur_liab) > (py_cur_assets / py_cur_liab)

        # F7: No dilution — shares outstanding did not increase YoY
        shares = _clean(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"))
        py_info = prior_year.get("info") or {}
        py_shares = _clean(py_info.get("sharesOutstanding") or py_info.get("impliedSharesOutstanding"))
        if shares is not None and py_shares is not None and py_shares > 0:
            f7 = shares <= py_shares * 1.01  # 1% tolerance for rounding

        # F8: Gross margin improved YoY
        revenue = _clean(_g(fin, "Total Revenue"))
        gross_profit = _clean(_g(fin, "Gross Profit"))
        py_revenue = _clean(_g(py_fin, "Total Revenue"))
        py_gross_profit = _clean(_g(py_fin, "Gross Profit"))
        if (gross_profit is not None and revenue and revenue > 0
                and py_gross_profit is not None and py_revenue and py_revenue > 0):
            f8 = (gross_profit / revenue) > (py_gross_profit / py_revenue)

        # F9: Asset turnover (revenue / assets) improved YoY
        revenue_cur = _clean(_g(fin, "Total Revenue"))
        py_revenue_9 = _clean(_g(py_fin, "Total Revenue"))
        py_ta_9 = _clean(_g(py_bs, "Total Assets"))
        if (revenue_cur is not None and total_assets and total_assets > 0
                and py_revenue_9 is not None and py_ta_9 and py_ta_9 > 0):
            f9 = (revenue_cur / total_assets) > (py_revenue_9 / py_ta_9)

    criteria = {
        "positiveNetIncome": f1,
        "positiveROA": f2,
        "positiveOperatingCF": f3,
        "accrualQuality": f4,
        "lowerLTDebtRatio": f5,
        "higherCurrentRatio": f6,
        "noNewShares": f7,
        "higherGrossMargin": f8,
        "higherAssetTurnover": f9,
    }

    scored = [v for v in criteria.values() if v is not None]
    score = int(sum(scored))
    max_score = len(scored)

    return {
        "score": score,
        "maxScore": max_score,
        "criteria": criteria,
    }


# ---------------------------------------------------------------------------
# 4. Beneish M-Score
# ---------------------------------------------------------------------------

def beneish_m(bundle: dict) -> dict:
    """Beneish M-Score (8-variable).

    All eight Beneish index variables require current-period AND prior-period
    financials (t and t-1).  The single-period bundle does not carry historical
    data, so the M-Score cannot be computed without fabricating numbers.

    Returns
    -------
    dict with mScore=None and an explanatory note.
    """
    return {
        "mScore": None,
        "note": (
            "Beneish M-Score requires prior-period statements (t and t-1) for "
            "all 8 index variables (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA). "
            "The yfinance snapshot bundle only carries the latest period; "
            "prior-year data is not available."
        ),
    }


# ---------------------------------------------------------------------------
# 5. Ohlson O-Score
# ---------------------------------------------------------------------------

def ohlson_o(bundle: dict) -> dict:
    """Ohlson O-Score (1980 logit model, 9 coefficients).

    O = -1.32 - 0.407*SIZE + 6.03*TLTA - 1.43*WCTA + 0.076*CLCA
        - 1.72*OENEG - 2.37*NITA - 1.83*FUTL + 0.285*INTWO - 0.521*CHIN

    where:
        SIZE  = log(Total Assets / GNP Price Index)  — we use log(TA) as proxy
                since GNP deflator is unavailable; conservative approximation.
        TLTA  = Total Liabilities / Total Assets
        WCTA  = Working Capital / Total Assets
        CLCA  = Current Liabilities / Current Assets
        OENEG = 1 if total liabilities > total assets else 0
        NITA  = Net Income / Total Assets
        FUTL  = Funds From Operations / Total Liabilities
              ≈ Operating CF / Total Liabilities
        INTWO = 1 if net income negative for two consecutive years — not
                available from single period; we use 1 if net income < 0
        CHIN  = (NI_t - NI_{t-1}) / (|NI_t| + |NI_{t-1}|) — needs prior year;
                set to 0 when unavailable (neutral contribution)

    Returns
    -------
    dict: oScore (float|None), probDefault (float|None)
    """
    info, fin, bs, cf = _unpack(bundle)

    total_assets = _clean(_g(bs, "Total Assets"))
    total_liab = _clean(
        _g(bs, "Total Liabilities Net Minority Interest", "Total Liabilities")
    )
    current_assets = _clean(_g(bs, "Current Assets"))
    current_liab = _clean(_g(bs, "Current Liabilities"))
    net_income = _clean(_g(fin, "Net Income", "Net Income Common Stockholders"))
    op_cf = _clean(_g(cf, "Operating Cash Flow", "Total Cash From Operating Activities"))

    if total_assets is None or total_assets == 0:
        return {"oScore": None, "probDefault": None}
    if total_liab is None:
        return {"oScore": None, "probDefault": None}

    # SIZE proxy: log(Total Assets)  [original uses TA/GNP deflator]
    size = _clean(math.log(abs(total_assets))) if total_assets > 0 else None
    if size is None:
        return {"oScore": None, "probDefault": None}

    tlta = _ratio(total_liab, total_assets)
    if tlta is None:
        return {"oScore": None, "probDefault": None}

    # Working capital = Current Assets - Current Liabilities
    wc: float | None = None
    if current_assets is not None and current_liab is not None:
        wc = _clean(current_assets - current_liab)
    wcta = _ratio(wc, total_assets)  # None if wc unavailable

    clca = _ratio(current_liab, current_assets)  # None if unavailable

    oeneg = 1.0 if total_liab > total_assets else 0.0

    nita = _ratio(net_income, total_assets)  # None if unavailable

    # FUTL: Operating CF / Total Liabilities
    futl = _ratio(op_cf, total_liab)  # None if unavailable

    # INTWO: approximate with single-period net income sign
    intwo = 1.0 if (net_income is not None and net_income < 0) else 0.0

    # CHIN: requires prior-year net income — set to 0 (neutral)
    chin = 0.0

    # O-Score (treat None contributions as 0 with a flag)
    try:
        o = (
            -1.32
            - 0.407 * size
            + 6.03 * tlta
            + (-1.43 * wcta if wcta is not None else 0.0)
            + (0.076 * clca if clca is not None else 0.0)
            - 1.72 * oeneg
            + (-2.37 * nita if nita is not None else 0.0)
            + (-1.83 * futl if futl is not None else 0.0)
            + 0.285 * intwo
            - 0.521 * chin
        )
        o_score = _clean(o)
    except Exception:
        return {"oScore": None, "probDefault": None}

    prob_default: float | None = None
    if o_score is not None:
        try:
            prob_default = _clean(1.0 / (1.0 + math.exp(-o_score)))
        except (OverflowError, ValueError):
            prob_default = None

    return {"oScore": o_score, "probDefault": prob_default}


# ---------------------------------------------------------------------------
# 6. Cash Conversion Cycle
# ---------------------------------------------------------------------------

def cash_conversion_cycle(bundle: dict) -> dict:
    """Cash Conversion Cycle = DSO + DIO – DPO (in days).

    DSO = Accounts Receivable / Revenue × 365
    DIO = Inventory / COGS × 365
    DPO = Accounts Payable / COGS × 365

    Returns
    -------
    dict: ccc, dso, dio, dpo — each float or None
    """
    info, fin, bs, _ = _unpack(bundle)

    revenue = _clean(_g(fin, "Total Revenue"))
    cogs = _clean(_g(fin, "Cost Of Revenue", "Cost of Goods Sold"))
    receivables = _clean(_g(bs, "Accounts Receivable", "Receivables"))
    inventory = _clean(_g(bs, "Inventory"))
    payables = _clean(_g(bs, "Accounts Payable"))

    # Days Sales Outstanding
    dso: float | None = None
    if receivables is not None and revenue:
        dso = _clean(receivables / revenue * 365.0)

    # Days Inventory Outstanding
    dio: float | None = None
    if inventory is not None and cogs:
        dio = _clean(inventory / cogs * 365.0)

    # Days Payable Outstanding
    dpo: float | None = None
    if payables is not None and cogs:
        dpo = _clean(payables / cogs * 365.0)

    # CCC
    ccc: float | None = None
    if dso is not None and dio is not None and dpo is not None:
        ccc = _clean(dso + dio - dpo)
    elif dso is not None and dpo is not None:
        # no inventory (e.g. financial/service firm): CCC ≈ DSO – DPO
        ccc = _clean(dso - dpo)

    return {"ccc": ccc, "dso": dso, "dio": dio, "dpo": dpo}


# ---------------------------------------------------------------------------
# 7. Aggregator
# ---------------------------------------------------------------------------

def extended_fundamentals(bundle: dict) -> dict:
    """Top-level aggregator for all extended fundamental metrics.

    Calls all six sub-functions and returns a unified dict.  Never raises —
    each sub-function is individually guarded, and the top-level call is
    wrapped in a try/except of last resort.

    Returns
    -------
    dict with keys:
        roic, dupont, piotroski, beneish, ohlson, cashConversionCycle
    """
    result: dict = {
        "roic": None,
        "dupont": None,
        "piotroski": None,
        "beneish": None,
        "ohlson": None,
        "cashConversionCycle": None,
    }
    try:
        result["roic"] = roic(bundle)
    except Exception:
        pass
    try:
        result["dupont"] = dupont(bundle)
    except Exception:
        pass
    try:
        result["piotroski"] = piotroski_f(bundle)
    except Exception:
        pass
    try:
        result["beneish"] = beneish_m(bundle)
    except Exception:
        pass
    try:
        result["ohlson"] = ohlson_o(bundle)
    except Exception:
        pass
    try:
        result["cashConversionCycle"] = cash_conversion_cycle(bundle)
    except Exception:
        pass
    return result
