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
from .. import provenance as pv
from ..cache import cached
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

def _build_prior_year(bundle: dict) -> dict | None:
    """Extract t-1 (prior-year) financial statements from DataFrames in bundle.

    yfinance DataFrames have date columns sorted latest-first, so column index 1
    is the prior year.  Returns a dict with ``financials``, ``balance_sheet``,
    ``cashflow``, ``info`` keys or None if DataFrames lack a second column.
    """
    fin_df = bundle.get("financials_df")
    bs_df = bundle.get("balance_sheet_df")
    cf_df = bundle.get("cashflow_df")

    # Need at least one DataFrame with ≥2 columns to build prior year
    has_prior = False
    for df in (fin_df, bs_df, cf_df):
        if df is not None and hasattr(df, "columns") and len(df.columns) >= 2:
            has_prior = True
            break
    if not has_prior:
        return None

    def _col_to_dict(df, col_idx: int) -> dict:
        if df is None or not hasattr(df, "columns") or col_idx >= len(df.columns):
            return {}
        col = df.columns[col_idx]
        out: dict = {}
        for idx, val in df[col].items():
            try:
                out[str(idx)] = None if (val is None or (hasattr(val, "__float__") and
                    (float(val) != float(val)))) else float(val)
            except Exception:
                continue
        return out

    prior_info = bundle.get("info", {}) or {}
    return {
        "financials": _col_to_dict(fin_df, 1),
        "balance_sheet": _col_to_dict(bs_df, 1),
        "cashflow": _col_to_dict(cf_df, 1),
        "info": prior_info,
    }


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

    # F2: ROA improved YoY (needs the prior year — set below). Piotroski's
    # profitability block is ROA > 0, CFO > 0, ΔROA > 0 and accruals; the old
    # "positive ROA" test only repeated F1 (audit C-24).
    f2: bool | None = None

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

    # Fix 5: Auto-build prior_year from DataFrames (second column = t-1) when not
    # explicitly passed.  yfinance DataFrames have date columns, latest first.
    if prior_year is None:
        prior_year = _build_prior_year(bundle)

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

        # F2: ΔROA > 0
        py_net_income = _clean(_g(py_fin, "Net Income", "Net Income Common Stockholders"))
        py_ta_2 = _clean(_g(py_bs, "Total Assets"))
        if (net_income is not None and total_assets and total_assets > 0
                and py_net_income is not None and py_ta_2 and py_ta_2 > 0):
            f2 = (net_income / total_assets) > (py_net_income / py_ta_2)

        # F7: No dilution — share count did not increase YoY. Both counts come
        # from the balance-sheet columns (t and t-1): the prior-year "info" is
        # today's info again, so comparing info share counts always passed
        # (audit C-10).
        shares = _clean(_g(bs, "Ordinary Shares Number", "Share Issued"))
        py_shares = _clean(_g(py_bs, "Ordinary Shares Number", "Share Issued"))
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
        "higherROA": f2,
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
        "interpretation": _piotroski_band(score, max_score),
        "criteria": criteria,
    }


def _piotroski_band(score: int, max_score: int) -> str:
    """Strong / Average / Weak scaled to the tests evaluated (the classic 8-9 / 4-7 / 0-3 are fractions of 9)."""
    if not max_score:
        return "Insufficient data"
    frac = score / max_score
    return "Strong" if frac >= 7 / 9 else ("Average" if frac >= 4 / 9 else "Weak")


# ---------------------------------------------------------------------------
# 4. Beneish M-Score
# ---------------------------------------------------------------------------

def beneish_m(bundle: dict) -> dict:
    """Beneish M-Score (8-variable), reusing the ``/corporate/health`` computation.

    The index variables need the current and the prior fiscal year, which the
    bundle carries as the raw statement DataFrames (``financials_df`` etc.,
    newest column first). Returns that service's dict (``mScore``,
    ``manipulationLikely``, ``interpretation``, ``indexes``, ...); ``mScore`` is
    None with a ``note`` when the history is missing or the company is a bank
    (receivables, gross margin and asset-quality indexes do not apply to one).
    """
    from .dcf_engine import is_bank
    from .corporate_health_service import _beneish
    if is_bank(bundle.get("info") or {}):
        return {"mScore": None, "note": "Beneish M-Score is not meaningful for banks: its receivables, "
                                         "gross-margin and asset-quality indexes do not describe a lender."}
    result = _beneish(bundle.get("financials_df"), bundle.get("balance_sheet_df"), bundle.get("cashflow_df"),
                      bundle.get("financials_q_df"), bundle.get("balance_sheet_q_df"), bundle.get("cashflow_q_df"))
    if result.get("mScore") is None:
        result["note"] = ("Beneish M-Score needs two fiscal years of statements (t and t-1) and at least six "
                          "of the eight indexes; Yahoo did not supply enough of them.")
    return result


# ---------------------------------------------------------------------------
# 5. Ohlson O-Score
# ---------------------------------------------------------------------------

def _gnp_price_index() -> float | None:
    """US GDP price deflator rebased to 1968 = 100 (Ohlson's SIZE scaling).

    Built from FRED GDPDEF: latest quarter / 1968 average × 100. Cached for
    the process lifetime of the cache TTL; None if FRED is unreachable (the
    O-score is then not computed rather than mis-scaled).
    """
    return _gnp_price_index_cached()


@cached("gnp_price_index_1968")
def _gnp_price_index_cached() -> float | None:
    try:
        from .macro_expansion_service import _fetch_fred_series_sync
        pts = _fetch_fred_series_sync(["GDPDEF"], start="1968-01-01").get("GDPDEF", [])
    except Exception:
        return None
    base = [p["value"] for p in pts if p["date"].startswith("1968")]
    if not base or not pts:
        return None
    return float(pts[-1]["value"]) / (sum(base) / len(base)) * 100.0


def _statements_to_usd(bundle: dict) -> tuple[float | None, str]:
    """(USD per statement-currency unit, that currency); the rate is None when no FX rate exists."""
    info = bundle.get("info") or {}
    fx = bundle.get("_fx") or {}  # a bundle already converted by dcf_engine.to_price_currency
    # When the conversion's FX lookup failed (rate None) the statements are still in the source currency.
    ccy = (fx.get("to") if fx.get("rate") is not None else fx.get("from"))         or info.get("financialCurrency") or info.get("currency")
    if not ccy or ccy == "USD":
        return 1.0, ccy or "USD"
    from .dcf_engine import _fx_rate
    return _fx_rate(ccy, "USD"), ccy


def ohlson_o(bundle: dict) -> dict:
    """Ohlson O-Score (1980 logit model, 9 coefficients).

    O = -1.32 - 0.407*SIZE + 6.03*TLTA - 1.43*WCTA + 0.076*CLCA
        - 1.72*OENEG - 2.37*NITA - 1.83*FUTL + 0.285*INTWO - 0.521*CHIN

    where:
        SIZE  = log(Total Assets in USD millions / GNP Price Index, 1968 = 100)
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

    # SIZE = log(total assets in $ millions / GNP price-level index, 1968=100),
    # as in Ohlson (1980). log of raw dollars made SIZE ~20 larger, and with
    # its −0.407 coefficient pushed every O-score so low that the default
    # probability read ~0 for all firms (audit C-11). The index is a US dollar
    # deflator, so statements in another currency are converted first (audit M-15).
    price_index = _gnp_price_index()
    if price_index is None or total_assets <= 0:
        return {"oScore": None, "probDefault": None}
    to_usd, ccy = _statements_to_usd(bundle)
    if to_usd is None:
        return {"oScore": None, "probDefault": None,
                "reason": f"No {ccy}/USD exchange rate available to express total assets in US dollars"}
    size = _clean(math.log(total_assets * to_usd / 1e6 / (price_index / 100.0)))
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

    from .dcf_engine import is_bank
    if is_bank(info):  # receivables are loans and there is no inventory or cost of goods (audit M-23)
        why = "not meaningful for banks: receivables are loans, not trade credit"
        return {"ccc": None, "dso": None, "dio": None, "dpo": None,
                "unavailable": {"ccc": why, "dso": why, "dio": why, "dpo": why}}

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


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def _stmt_date(bundle: dict, name: str) -> str | None:
    """Period end of the latest annual statement column."""
    df = bundle.get(name)
    try:
        return str(df.columns[0])[:10] if df is not None and len(df.columns) else None
    except Exception:
        return None


def provenance(bundle: dict, root: str = "fundamentals") -> dict:
    """Provenance keys (under ``root``) for an :func:`extended_fundamentals` result."""
    def k(*parts: str) -> str:
        return ".".join(p for p in (root, *parts) if p)

    sym = bundle.get("ticker") or ""
    info = bundle.get("info") or {}
    inc = pv.yahoo(sym, "Income statement, latest fiscal year", frequency="annual",
                   observed=_stmt_date(bundle, "financials_df"))
    bal = pv.yahoo(sym, "Balance sheet, latest fiscal year", frequency="annual",
                   observed=_stmt_date(bundle, "balance_sheet_df"))
    cfs = pv.yahoo(sym, "Cash-flow statement, latest fiscal year", frequency="annual",
                   observed=_stmt_date(bundle, "cashflow_df"))
    snap = pv.yahoo(sym, "Quote and key-statistics snapshot (Ticker.info)")
    prior = "prior fiscal year (the previous annual column)"

    def d(formula: str, inputs: list, title: str, **kw) -> dict:
        return pv.derived(formula, inputs, title=title, **kw)

    prov: dict = {k(): d("ROIC, DuPont, Piotroski F-Score, Ohlson O-Score and cash conversion cycle from Yahoo's "
                         "annual statements", [inc, bal, cfs], title="Extended fundamentals")}

    # ROIC: the 21% tax rate is used when info.effectiveTaxRate is missing or 0.
    tax_fallback = (_clean(info.get("effectiveTaxRate")) or 0.0) == 0.0
    tax_flag = ("fallback",) if tax_fallback else ()
    tax_note = "21% tax rate assumed: Yahoo's effectiveTaxRate is missing." if tax_fallback else None
    prov[k("roic", "nopat")] = d("EBIT (Operating Income if missing) × (1 − info.effectiveTaxRate, 21% if missing)",
                                 [inc, snap], title="NOPAT", flags=tax_flag, note=tax_note)
    prov[k("roic", "investedCapital")] = d(
        "total debt + stockholders' equity − cash (balance sheet, else info.totalDebt / totalStockholderEquity / "
        "totalCash)", [bal, snap], title="Invested capital")
    prov[k("roic", "roic")] = d("NOPAT / invested capital", [k("roic", "nopat"), k("roic", "investedCapital")],
                                title="Return on invested capital", flags=tax_flag, note=tax_note)

    for grp, formula in (
        ("threeFactor", "ROE = net margin (net income / revenue) × asset turnover (revenue / total assets) × "
                        "equity multiplier (total assets / equity)"),
        ("fiveFactor", "ROE = tax burden (net income / pretax income) × interest burden (pretax income / EBIT) × "
                       "operating margin (EBIT / revenue) × asset turnover × equity multiplier"),
    ):
        prov[k("dupont", grp)] = d(formula + "; year-end balance-sheet figures", [inc, bal], title=f"DuPont ({grp})")

    piotroski = {
        "positiveNetIncome": "net income > 0",
        "higherROA": "net income / total assets > the prior year's",
        "positiveOperatingCF": "operating cash flow > 0",
        "accrualQuality": "operating cash flow > net income",
        "lowerLTDebtRatio": "long-term debt / total assets < the prior year's",
        "higherCurrentRatio": "current assets / current liabilities > the prior year's",
        "noNewShares": "shares outstanding (balance sheet) ≤ the prior year's × 1.01",
        "higherGrossMargin": "gross profit / revenue > the prior year's",
        "higherAssetTurnover": "revenue / total assets > the prior year's",
    }
    prov[k("piotroski")] = d(
        f"count of the nine Piotroski tests that pass; a test needing the {prior} is skipped, and dropped from "
        "maxScore, if that column or a line item is missing", [inc, bal, cfs], title="Piotroski F-Score")
    for key, test in piotroski.items():
        prov[k("piotroski", "criteria", key)] = d(f"{test} (latest fiscal year vs {prior})", [inc, bal, cfs],
                                                  title=key)

    prov[k("beneish")] = d(
        "M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI + 4.679·TATA − "
        "0.327·LVGI from the latest two annual statements (the same computation as /corporate/health); missing "
        "indexes take the neutral value 1.0 (at most two, TATA required); M > −2.22 flags likely manipulation; "
        "not computed for banks", [inc, bal, cfs], title="Beneish M-Score")
    gnp = pv.fred("GDPDEF", "US GDP implicit price deflator", frequency="quarterly",
                  note="Rebased to 1968 average = 100 and used in place of Ohlson's GNP price index.")
    prov[k("ohlson", "oScore")] = d(
        "−1.32 − 0.407·SIZE + 6.03·TLTA − 1.43·WCTA + 0.076·CLCA − 1.72·OENEG − 2.37·NITA − 1.83·FUTL + 0.285·INTWO "
        "− 0.521·CHIN; SIZE = ln(total assets in US-dollar millions / (price index / 100)), TLTA = liabilities / assets, "
        "WCTA = working capital / assets, CLCA = current liabilities / current assets, OENEG = 1 if liabilities > "
        "assets, NITA = net income / assets, FUTL = operating cash flow / liabilities, INTWO = 1 if net income < 0 "
        "(this year only), CHIN = 0; a ratio that cannot be computed contributes 0",
        [inc, bal, cfs, gnp], title="Ohlson O-Score",
        note="CHIN is fixed at 0 and INTWO uses only the latest year, so this is an approximation of Ohlson (1980).")
    prov[k("ohlson", "probDefault")] = d("1 / (1 + e^(−O-score))", [k("ohlson", "oScore")],
                                         title="Ohlson default probability")
    for key, formula in (
        ("dso", "accounts receivable / revenue × 365"),
        ("dio", "inventory / cost of revenue × 365"),
        ("dpo", "accounts payable / cost of revenue × 365"),
        ("ccc", "DSO + DIO − DPO (DSO − DPO when there is no inventory)"),
    ):
        prov[k("cashConversionCycle", key)] = d(formula, [inc, bal], title=key.upper() + " (days)")
    return prov
