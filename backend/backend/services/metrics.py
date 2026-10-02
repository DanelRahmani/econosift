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
            "returns": [], "nObs": 0,
        }

    daily_mean = r.mean()
    ann_vol = r.std(ddof=1) * math.sqrt(TRADING_DAYS)

    var95 = np.percentile(r, 5)
    tail = r[r <= var95]
    cvar95 = tail.mean() if len(tail) else var95

    # Sharpe / Sortino use simple returns and the arithmetic mean (audit M-18): the mean
    # log return understates the annual return by about sigma^2 / 2, which flipped MSFT's
    # Sharpe from +0.02 to -0.14. Volatility, VaR and beta above stay on log returns.
    prices = asset_prices.dropna()
    simple = (prices / prices.shift(1) - 1.0).dropna()
    s_ann_return = simple.mean() * TRADING_DAYS
    s_ann_vol = simple.std(ddof=1) * math.sqrt(TRADING_DAYS) if len(simple) > 1 else None

    # Downside deviation vs the daily risk-free MAR over all days (audit C-17).
    shortfall = np.minimum(simple - risk_free / TRADING_DAYS, 0.0)
    downside_dev = math.sqrt(float((shortfall ** 2).mean())) * math.sqrt(TRADING_DAYS) if len(simple) > 1 else None

    sharpe = (s_ann_return - risk_free) / s_ann_vol if s_ann_vol and s_ann_vol > 0 else None
    sortino = ((s_ann_return - risk_free) / downside_dev
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
        "nObs": int(len(r)),
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

    from .dcf_engine import is_bank  # lazy: dcf_engine imports this module
    if fcf <= 0 or is_bank(info):  # same locks as dcf_engine.two_stage_dcf (Phase 53)
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
    if equity_value <= 0:
        return None
    if shares <= 0:
        return None
    return _clean(equity_value / shares)


_AUTO = object()


def _statement_fx(info: dict) -> float | None:
    """Factor converting ``financialCurrency`` figures to the price currency.

    1.0 when the currencies match or either is unknown; None when they differ
    and no rate is available (the caller must not mix the two currencies).
    """
    fin_ccy, px_ccy = info.get("financialCurrency"), info.get("currency")
    if not fin_ccy or not px_ccy or fin_ccy == px_ccy:
        return 1.0
    from . import dcf_engine  # lazy: dcf_engine imports this module
    return dcf_engine._fx_rate(fin_ccy, px_ccy)


def altman_z(info: dict, balance: dict, financials: dict, statement_to_price_fx=_AUTO):
    """Altman Z-Score for public manufacturing firms.

    ``marketCap`` is in the price currency while the statements are in
    ``financialCurrency`` (ADRs: TSM, NVO), so total liabilities are converted
    before ``market cap / liabilities`` (audit M-01). ``statement_to_price_fx``
    is looked up from ``info`` by default; pass 1.0 when the inputs are already
    in the price currency, or None to force "no score".
    """
    if statement_to_price_fx is _AUTO:
        statement_to_price_fx = _statement_fx(info)
    if statement_to_price_fx is None:
        return None
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
    # Every input is required: substituting 0 for a missing line item silently
    # drags the score toward the distress zone instead of admitting no score.
    if any(v is None for v in (ca, cl, re, ebit, mcap, tl, sales)) or not tl:
        return None
    try:
        x1 = (ca - cl) / ta
        x2 = re / ta
        x3 = ebit / ta
        x4 = mcap / (tl * statement_to_price_fx)
        x5 = sales / ta
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
        return _clean(z)
    except Exception:
        return None


def _ratio(n, d):
    if n is None or not d:
        return None
    try:
        return _clean(float(n) / float(d))
    except Exception:
        return None


def market_multiples(bundle: dict) -> dict:
    """Market-cap / EV multiples with every input in the price currency (audit M-01).

    ADRs and cross-listings quote in ``currency`` but report in
    ``financialCurrency``; Yahoo's ``enterpriseValue`` and its P/S, P/B, EV/EBITDA
    and EV/Revenue mix the two. When the currencies differ the statement-currency
    inputs go through ``dcf_engine.to_price_currency`` and the multiples are
    rebuilt (EV = market cap + total debt - total cash); when no FX rate or an
    input is missing the multiple is None with a reason. Same-currency tickers
    keep Yahoo's values.

    Returns ``{"bundle": <converted bundle>, "statementToPriceFx": 1.0 | None,
    "values": {fcfYield, evToFcf, psRatio, pbRatio, evEbitda, evRevenue, bookValue},
    "unavailable": {name: reason}}``. ``bookValue`` is per share in the price
    currency: Yahoo's for same-currency tickers, else converted equity x price /
    market cap (market cap / price is the ADR-equivalent share count). ``statementToPriceFx`` is 1.0 because the
    returned bundle is already converted, None when it could not be.
    """
    from .dcf_engine import to_price_currency  # lazy: dcf_engine imports this module
    conv = to_price_currency(bundle)
    info = conv.get("info") or {}
    fx = conv.get("_fx") or {}
    src, dst = fx.get("from"), fx.get("to")
    mixed = bool(src and dst and src != dst)
    labels = {"fcfYield": "FCF yield", "evToFcf": "EV/FCF", "psRatio": "P/S", "pbRatio": "P/B",
              "evEbitda": "EV/EBITDA", "evRevenue": "EV/Revenue", "bookValue": "book value per share"}
    mcap = _clean(info.get("marketCap"))
    fcf = _clean(info.get("freeCashflow"))

    if not mixed:
        ev = _clean(info.get("enterpriseValue"))
        values = {
            "fcfYield": _ratio(fcf, mcap),
            "evToFcf": _ratio(ev, fcf),
            "psRatio": _clean(info.get("priceToSalesTrailing12Months")),
            "pbRatio": _clean(info.get("priceToBook")),
            "evEbitda": _clean(info.get("enterpriseToEbitda")),
            "evRevenue": _clean(info.get("enterpriseToRevenue")),
            "bookValue": _clean(info.get("bookValue")),
        }
        unavailable = {}
        _drop_negative_fcf_multiple(values, unavailable, fcf)
        return {"bundle": conv, "statementToPriceFx": 1.0, "values": values, "unavailable": unavailable}

    values: dict = {k: None for k in labels}
    if fx.get("rate") is None:
        why = (f"No {src}/{dst} exchange rate available, so figures reported in {src} "
               f"cannot be converted to the {dst} price currency")
        return {"bundle": conv, "statementToPriceFx": None, "values": values,
                "unavailable": {k: why for k in labels}}

    unavailable: dict = {}

    def need(name: str, parts: dict) -> None:
        miss = [k for k, v in parts.items() if v is None]
        unavailable[name] = (f"Missing {', '.join(miss)}: statements are reported in {src} and the price "
                             f"is in {dst}, so {labels[name]} cannot be computed without it")

    debt, cash = _clean(info.get("totalDebt")), _clean(info.get("totalCash"))
    ebitda, revenue = _clean(info.get("ebitda")), _clean(info.get("totalRevenue"))
    bs = conv.get("balance_sheet") or {}
    equity = _clean(bs.get("Stockholders Equity") or bs.get("Common Stock Equity")
                    or info.get("totalStockholderEquity"))
    ev = mcap + debt - cash if None not in (mcap, debt, cash) else None
    ev_parts = {"marketCap": mcap, "totalDebt": debt, "totalCash": cash}

    if mcap is None or fcf is None:
        need("fcfYield", {"marketCap": mcap, "freeCashflow": fcf})
    else:
        values["fcfYield"] = _ratio(fcf, mcap)
    if ev is None or fcf is None:
        need("evToFcf", {**ev_parts, "freeCashflow": fcf})
    else:
        values["evToFcf"] = _ratio(ev, fcf)
    if mcap is None or not revenue:
        need("psRatio", {"marketCap": mcap, "totalRevenue": revenue or None})
    else:
        values["psRatio"] = mcap / revenue
    if mcap is None or not equity or equity <= 0:
        need("pbRatio", {"marketCap": mcap, "stockholdersEquity": equity if equity and equity > 0 else None})
    else:
        values["pbRatio"] = mcap / equity
    if ev is None or not ebitda or ebitda <= 0:
        need("evEbitda", {**ev_parts, "ebitda": ebitda if ebitda and ebitda > 0 else None})
    else:
        values["evEbitda"] = ev / ebitda
    price = _clean(info.get("currentPrice") or info.get("regularMarketPrice"))
    if None in (mcap, price) or not mcap or not equity or equity <= 0:
        need("bookValue", {"marketCap": mcap or None, "price": price,
                           "stockholdersEquity": equity if equity and equity > 0 else None})
    else:
        values["bookValue"] = equity * price / mcap
    if ev is None or not revenue:
        need("evRevenue", {**ev_parts, "totalRevenue": revenue or None})
    else:
        values["evRevenue"] = ev / revenue
    _drop_negative_fcf_multiple(values, unavailable, fcf)
    return {"bundle": conv, "statementToPriceFx": 1.0, "values": values, "unavailable": unavailable}


def _drop_negative_fcf_multiple(values: dict, unavailable: dict, fcf: float | None) -> None:
    """EV / FCF is not a multiple when FCF ≤ 0 (JPM showed −4.85); FCF yield stays as computed."""
    if fcf is not None and fcf <= 0:
        values["evToFcf"] = None
        unavailable["evToFcf"] = "not meaningful: free cash flow ≤ 0"


def compute_ratios(bundle: dict) -> dict:
    """Build the full ratios payload from a yfinance info/statements bundle.

    Cross-currency tickers (ADRs) are converted to the price currency first, so
    nothing here divides a statement-currency figure by a USD price or market
    cap. ``unavailable`` maps ``"valuation.<key>"`` / ``"zScore"`` to the reason
    a value is None because of currency (missing FX rate or input).
    """
    mm = market_multiples(bundle)
    bundle = mm["bundle"]
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
    cogs = g(fin, "Cost Of Revenue", "Reconciled Cost Of Revenue")
    # Statement FCF first so the margin divides figures from the same fiscal
    # year; Yahoo's info["freeCashflow"] is TTM and was being divided by
    # annual revenue (audit C-28).
    fcf = g(cf, "Free Cash Flow")
    fcf_revenue = revenue
    try:
        fy = f"FY{str(bundle['financials_df'].columns[0])[:4]}"
    except Exception:
        fy = "FY (latest fiscal year)"
    fcf_basis = fy
    if fcf is None:
        fcf, fcf_revenue = info.get("freeCashflow"), info.get("totalRevenue")
        fcf_basis = "TTM (Yahoo info)"

    # Net debt nets cash AND short-term investments. The combined statement line already includes
    # both, so it is preferred; otherwise add "Other Short Term Investments" to cash (never both).
    cash_and_sti = g(bs, "Cash Cash Equivalents And Short Term Investments")
    if cash_and_sti is None and cash is not None:
        cash_and_sti = cash + (g(bs, "Other Short Term Investments") or 0)

    ratio = _ratio

    liquidity = {
        "currentRatio": ratio(current_assets, current_liab),
        "quickRatio": ratio((current_assets or 0) - (inventory or 0), current_liab) if current_assets else None,
        "cashRatio": ratio(cash, current_liab),
        "operatingCFRatio": ratio(op_cf, current_liab),
    }
    leverage = {
        "debtToEquity": ratio(total_debt, equity) if total_debt else _ratio(_clean(info.get("debtToEquity")), 100),  # Yahoo reports a percent
        "debtToAssets": ratio(total_debt, total_assets),
        "interestCoverage": ratio(op_income, abs(interest_exp)) if interest_exp else None,
        "netDebtEbitda": ratio((total_debt or 0) - (cash_and_sti or 0), ebitda) if total_debt else None,
    }
    efficiency = {
        "assetTurnover": ratio(revenue, total_assets),
        # Inventory is carried at cost, so turnover uses COGS, not revenue.
        "inventoryTurnover": ratio(cogs, inventory),
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
        "fcfMargin": ratio(fcf, fcf_revenue),
    }
    valuation = {
        "peRatio": _clean(info.get("trailingPE")),
        "forwardPE": _clean(info.get("forwardPE")),
        "pbRatio": mm["values"]["pbRatio"],
        "psRatio": mm["values"]["psRatio"],
        "evEbitda": mm["values"]["evEbitda"],
        "evRevenue": mm["values"]["evRevenue"],
        "dividendYield": _clean(info.get("dividendYield")),
        "eps": _clean(info.get("trailingEps")),
    }

    z_score = altman_z(info, bs, fin, mm["statementToPriceFx"])
    unavailable = {f"valuation.{k}": why for k, why in mm["unavailable"].items()
                   if k in ("psRatio", "pbRatio", "evEbitda", "evRevenue")}
    if mm["statementToPriceFx"] is None:
        unavailable["zScore"] = next(iter(mm["unavailable"].values()))

    # A bank's receivables are loans and its cash flow is deposits and trading flows, so
    # DSO and FCF margin are not measures of collection speed or cash generation (audit M-23:
    # JPM DSO 224 days, FCF margin -81 %).
    from .dcf_engine import is_bank  # lazy: dcf_engine imports this module
    if is_bank(info):
        for k in ("dso", "receivablesTurnover"):  # receivables turnover is DSO inverted
            efficiency[k] = None
            unavailable[f"efficiency.{k}"] = "not meaningful for banks: receivables are loans, not trade credit"
        profitability["fcfMargin"] = None
        unavailable["profitability.fcfMargin"] = ("not meaningful for banks: operating cash flow is dominated "
                                                  "by deposit, loan and trading flows")

    return {
        "liquidity": liquidity,
        "leverage": leverage,
        "efficiency": efficiency,
        "profitability": profitability,
        "valuation": valuation,
        "zScore": z_score,
        "unavailable": unavailable,
        "basis": {"roe": fy, "fcfMargin": fcf_basis},
    }
