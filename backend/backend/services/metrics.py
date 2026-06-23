"""Quantitative finance calculations: risk, CAPM/DCF, ratios, Z-score."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def log_returns(prices: pd.Series) -> pd.Series:
    prices = prices.dropna()
    if len(prices) < 2:
        return pd.Series(dtype=float)
    return np.log(prices / prices.shift(1)).dropna()


def _clean(x):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def risk_metrics(asset_prices: pd.Series, bench_prices: pd.Series,
                 risk_free: float) -> dict:
    """Compute annualised risk metrics for one asset vs a benchmark."""
    r = log_returns(asset_prices)
    if r.empty:
        return {
            "annVolatility": None, "dailyMeanReturn": None, "var95": None,
            "cvar95": None, "sharpe": None, "sortino": None, "beta": None,
            "returns": [],
        }

    daily_mean = r.mean()
    ann_return = daily_mean * TRADING_DAYS
    ann_vol = r.std(ddof=1) * math.sqrt(TRADING_DAYS)

    var95 = np.percentile(r, 5)
    tail = r[r <= var95]
    cvar95 = tail.mean() if len(tail) else var95

    downside = r[r < 0]
    downside_dev = downside.std(ddof=1) * math.sqrt(TRADING_DAYS) if len(downside) > 1 else None

    sharpe = (ann_return - risk_free) / ann_vol if ann_vol and ann_vol > 0 else None
    sortino = ((ann_return - risk_free) / downside_dev
               if downside_dev and downside_dev > 0 else None)

    beta = None
    if bench_prices is not None and len(bench_prices) > 2:
        br = log_returns(bench_prices)
        joined = pd.concat([r, br], axis=1, join="inner").dropna()
        if len(joined) > 2:
            a = joined.iloc[:, 0]
            b = joined.iloc[:, 1]
            var_b = b.var(ddof=1)
            if var_b and var_b > 0:
                beta = a.cov(b) / var_b

    return {
        "annVolatility": _clean(ann_vol),
        "dailyMeanReturn": _clean(daily_mean),
        "var95": _clean(var95),
        "cvar95": _clean(cvar95),
        "sharpe": _clean(sharpe),
        "sortino": _clean(sortino),
        "beta": _clean(beta),
        "returns": [_clean(v) for v in r.tolist()],
    }


def capm_expected_return(beta: float, risk_free: float, market_premium: float):
    if beta is None:
        return None
    return risk_free + beta * market_premium


def dcf_target(info: dict, fcf_growth: float, terminal_growth: float,
               discount_rate: float):
    """Simple 5-year FCF DCF, returns per-share intrinsic value."""
    fcf = info.get("freeCashflow") or info.get("operatingCashflow")
    shares = info.get("sharesOutstanding")
    if not fcf or not shares or discount_rate is None:
        return None
    if discount_rate <= terminal_growth:
        return None
    try:
        fcf = float(fcf)
        shares = float(shares)
    except (TypeError, ValueError):
        return None

    pv = 0.0
    cf = fcf
    for year in range(1, 6):
        cf = cf * (1 + fcf_growth)
        pv += cf / ((1 + discount_rate) ** year)

    terminal = cf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv += terminal / ((1 + discount_rate) ** 5)

    total_debt = float(info.get("totalDebt") or 0)
    cash = float(info.get("totalCash") or 0)
    equity_value = pv - total_debt + cash
    if shares <= 0:
        return None
    return _clean(equity_value / shares)


def altman_z(info: dict, balance: dict, financials: dict):
    """Altman Z-Score for public manufacturing firms."""
    ta = balance.get("Total Assets")
    tl = balance.get("Total Liabilities Net Minority Interest") or balance.get("Total Liabilities")
    ca = balance.get("Current Assets")
    cl = balance.get("Current Liabilities")
    re = balance.get("Retained Earnings")
    ebit = financials.get("EBIT") or financials.get("Operating Income")
    sales = financials.get("Total Revenue")
    mcap = info.get("marketCap")

    if not ta or ta == 0:
        return None
    try:
        wc = (ca or 0) - (cl or 0)
        x1 = wc / ta
        x2 = (re or 0) / ta
        x3 = (ebit or 0) / ta
        x4 = (mcap or 0) / tl if tl else 0
        x5 = (sales or 0) / ta
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
        return _clean(z)
    except Exception:
        return None


def compute_ratios(bundle: dict) -> dict:
    """Build the full ratios payload from a yfinance info/statements bundle."""
    info = bundle.get("info", {}) or {}
    bs = bundle.get("balance_sheet", {}) or {}
    fin = bundle.get("financials", {}) or {}
    cf = bundle.get("cashflow", {}) or {}

    def g(d, *keys):
        for k in keys:
            v = d.get(k)
            if v is not None:
                return v
        return None

    revenue = g(fin, "Total Revenue")
    gross_profit = g(fin, "Gross Profit")
    op_income = g(fin, "Operating Income", "EBIT")
    net_income = g(fin, "Net Income", "Net Income Common Stockholders")
    ebitda = g(fin, "EBITDA") or info.get("ebitda")
    interest_exp = g(fin, "Interest Expense")

    total_assets = g(bs, "Total Assets")
    total_liab = g(bs, "Total Liabilities Net Minority Interest", "Total Liabilities")
    current_assets = g(bs, "Current Assets")
    current_liab = g(bs, "Current Liabilities")
    inventory = g(bs, "Inventory")
    cash = g(bs, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
    receivables = g(bs, "Accounts Receivable", "Receivables")
    total_debt = g(bs, "Total Debt") or info.get("totalDebt")
    equity = g(bs, "Stockholders Equity", "Common Stock Equity") or info.get("totalStockholderEquity")

    op_cf = g(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
    fcf = info.get("freeCashflow") or g(cf, "Free Cash Flow")

    def ratio(n, d):
        if n is None or not d:
            return None
        try:
            return _clean(float(n) / float(d))
        except Exception:
            return None

    liquidity = {
        "currentRatio": ratio(current_assets, current_liab),
        "quickRatio": ratio((current_assets or 0) - (inventory or 0), current_liab) if current_assets else None,
        "cashRatio": ratio(cash, current_liab),
        "operatingCFRatio": ratio(op_cf, current_liab),
    }
    leverage = {
        "debtToEquity": ratio(total_debt, equity) if total_debt else _clean(info.get("debtToEquity")),
        "debtToAssets": ratio(total_debt, total_assets),
        "interestCoverage": ratio(op_income, abs(interest_exp)) if interest_exp else None,
        "netDebtEbitda": ratio((total_debt or 0) - (cash or 0), ebitda) if total_debt else None,
    }
    efficiency = {
        "assetTurnover": ratio(revenue, total_assets),
        "inventoryTurnover": ratio(revenue, inventory),
        "receivablesTurnover": ratio(revenue, receivables),
        "dso": ratio((receivables or 0) * 365, revenue) if receivables and revenue else None,
    }
    profitability = {
        "grossMargin": ratio(gross_profit, revenue),
        "operatingMargin": ratio(op_income, revenue),
        "netMargin": ratio(net_income, revenue),
        "ebitdaMargin": ratio(ebitda, revenue),
        "roa": ratio(net_income, total_assets),
        "roe": ratio(net_income, equity),
        "fcfMargin": ratio(fcf, revenue),
    }
    valuation = {
        "peRatio": _clean(info.get("trailingPE")),
        "forwardPE": _clean(info.get("forwardPE")),
        "pbRatio": _clean(info.get("priceToBook")),
        "psRatio": _clean(info.get("priceToSalesTrailing12Months")),
        "evEbitda": _clean(info.get("enterpriseToEbitda")),
        "evRevenue": _clean(info.get("enterpriseToRevenue")),
        "dividendYield": _clean(info.get("dividendYield")),
        "eps": _clean(info.get("trailingEps")),
    }

    return {
        "liquidity": liquidity,
        "leverage": leverage,
        "efficiency": efficiency,
        "profitability": profitability,
        "valuation": valuation,
        "zScore": altman_z(info, bs, fin),
    }
