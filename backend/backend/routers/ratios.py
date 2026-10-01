"""Financial ratios + risk scores."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter

from .. import provenance as pv
from ..services import yfinance_service as yfs
from ..services import metrics

router = APIRouter(prefix="/api/ratios", tags=["ratios"])


@router.get("/{ticker}")
async def ratios(ticker: str, period: str = "1y", risk_free: float = 0.04):
    sym = ticker.upper()
    bench = yfs.benchmark_for(sym)

    bundle = await asyncio.to_thread(yfs.get_info, sym)
    payload = metrics.compute_ratios(bundle)

    frame = await asyncio.to_thread(
        yfs.get_close_frame, tuple(dict.fromkeys([sym, bench])), period)
    beta = sharpe = sortino = None
    if frame is not None and not frame.empty and sym in frame.columns:
        bench_series = frame[bench] if bench in frame.columns else None
        m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
        beta, sharpe, sortino = m.get("beta"), m.get("sharpe"), m.get("sortino")

    return pv.attach({
        "ticker": sym,
        "benchmark": bench,
        "beta": beta,
        "sharpe": sharpe,
        "sortino": sortino,
        "zScore": payload["zScore"],
        "liquidity": payload["liquidity"],
        "leverage": payload["leverage"],
        "efficiency": payload["efficiency"],
        "profitability": payload["profitability"],
        "valuation": payload["valuation"],
        "unavailable": payload["unavailable"],
    }, {**ratio_provenance(sym, bundle), **risk_provenance(sym, bench, frame, period, risk_free)})


def stmt_date(bundle: dict, name: str) -> str | None:
    """Period end of the latest annual statement (``financials_df`` / ``balance_sheet_df`` / ``cashflow_df``)."""
    df = bundle.get(name)
    try:
        return str(df.columns[0])[:10] if df is not None and len(df.columns) else None
    except Exception:
        return None


# Ratio -> (formula, statements it reads: i income, b balance sheet, c cash flow, q Ticker.info snapshot).
_RATIO_FORMULAS = {
    "liquidity.currentRatio": ("current assets / current liabilities", "b"),
    "liquidity.quickRatio": ("(current assets − inventory) / current liabilities (inventory counted as 0 if missing)", "b"),
    "liquidity.cashRatio": ("cash and equivalents / current liabilities", "b"),
    "liquidity.operatingCFRatio": ("operating cash flow / current liabilities", "bc"),
    "leverage.debtToEquity": ("total debt / stockholders' equity; if the balance sheet has no total debt, "
                              "Yahoo's own debtToEquity from the info snapshot is used instead", "bq"),
    "leverage.debtToAssets": ("total debt / total assets", "bq"),
    "leverage.interestCoverage": ("operating income (EBIT if missing) / |interest expense|", "i"),
    "leverage.netDebtEbitda": ("(total debt − cash) / EBITDA (statement EBITDA, else info ebitda)", "ibq"),
    "efficiency.assetTurnover": ("total revenue / total assets (year-end assets)", "ib"),
    "efficiency.inventoryTurnover": ("cost of revenue / inventory", "ib"),
    "efficiency.receivablesTurnover": ("total revenue / accounts receivable", "ib"),
    "efficiency.dso": ("accounts receivable × 365 / total revenue", "ib"),
    "profitability.grossMargin": ("gross profit / total revenue", "i"),
    "profitability.operatingMargin": ("operating income (EBIT if missing) / total revenue", "i"),
    "profitability.netMargin": ("net income / total revenue", "i"),
    "profitability.ebitdaMargin": ("EBITDA (statement, else info ebitda) / total revenue", "iq"),
    "profitability.roa": ("net income / total assets (year-end)", "ib"),
    "profitability.roe": ("net income / stockholders' equity (year-end)", "ib"),
    "profitability.fcfMargin": ("statement free cash flow / total revenue; if the cash-flow statement has none, "
                                "Yahoo's trailing-12-month freeCashflow / totalRevenue", "icq"),
    "zScore": ("Altman Z = 1.2·(current assets − current liabilities)/TA + 1.4·retained earnings/TA + 3.3·EBIT/TA "
               "+ 0.6·market cap/total liabilities + 1.0·revenue/TA, TA = total assets; None if any input is missing",
               "ibq"),
}

# Valuation ratio -> Yahoo Ticker.info field it is read from.
_VALUATION_FIELDS = {
    "peRatio": "trailingPE", "forwardPE": "forwardPE", "pbRatio": "priceToBook",
    "psRatio": "priceToSalesTrailing12Months", "evEbitda": "enterpriseToEbitda",
    "evRevenue": "enterpriseToRevenue", "dividendYield": "dividendYield", "eps": "trailingEps",
}


def ratio_provenance(sym: str, bundle: dict, prefix: str = "") -> dict:
    """Provenance for a ``metrics.compute_ratios`` payload; ``prefix`` places it under a parent key."""
    p = f"{prefix}." if prefix else ""
    snap = pv.yahoo(sym, "Quote and key-statistics snapshot (Ticker.info)")
    src = {
        "i": pv.yahoo(sym, "Income statement, latest fiscal year", frequency="annual",
                      observed=stmt_date(bundle, "financials_df")),
        "b": pv.yahoo(sym, "Balance sheet, latest fiscal year", frequency="annual",
                      observed=stmt_date(bundle, "balance_sheet_df")),
        "c": pv.yahoo(sym, "Cash-flow statement, latest fiscal year", frequency="annual",
                      observed=stmt_date(bundle, "cashflow_df")),
        "q": snap,
    }
    prov = {prefix or "*": pv.yahoo(sym, "Company fundamentals: annual statements and the info snapshot")}
    for key, (formula, needs) in _RATIO_FORMULAS.items():
        prov[p + key] = pv.derived(formula, [src[c] for c in needs], title=key.split(".")[-1],
                                   observed=src[needs[0]].get("observed"))
    for key, field in _VALUATION_FIELDS.items():
        prov[f"{p}valuation.{key}"] = pv.yahoo(sym, f"info.{field}")
    # ADRs / cross-listings: these four are rebuilt from statement figures converted to the price currency.
    if bundle.get("info", {}).get("financialCurrency") not in (None, bundle.get("info", {}).get("currency")):
        for key, formula in _CROSS_CURRENCY_FORMULAS.items():
            prov[f"{p}valuation.{key}"] = pv.derived(formula, [src["q"], src["b"], src["i"]], title=key)
    return prov


_CROSS_CURRENCY_FORMULAS = {
    "psRatio": "market cap / (TTM revenue × FX to the price currency)",
    "pbRatio": "market cap / (stockholders' equity × FX to the price currency)",
    "evEbitda": "EV / (EBITDA × FX), EV = market cap + (debt − cash) × FX",
    "evRevenue": "EV / (TTM revenue × FX), EV = market cap + (debt − cash) × FX",
}


def risk_provenance(sym: str, bench: str, frame, period: str, risk_free: float) -> dict:
    """beta / sharpe / sortino computed from ``period`` of adjusted closes against the benchmark."""
    inputs = [pv.yahoo(sym, f"Daily adjusted close, {period}", frequency="daily",
                       observed=pv.last_date(frame[sym]) if frame is not None and sym in frame.columns else None),
              pv.yahoo(bench, f"Benchmark daily adjusted close, {period}", frequency="daily",
                       observed=pv.last_date(frame[bench]) if frame is not None and bench in frame.columns else None)]
    rf = f"rf = the risk_free request parameter (server default 0.04), here {risk_free:g}"
    return {
        "beta": pv.derived(f"cov(r, r_{bench}) / var(r_{bench}) of daily log returns over the common days",
                           inputs, title="Beta"),
        "sharpe": pv.derived(f"(mean(r) × 252 − rf) / (stdev(r, ddof=1) × √252), r = daily log return; {rf}",
                             inputs, title="Sharpe ratio"),
        "sortino": pv.derived(f"(mean(r) × 252 − rf) / (√mean(min(r − rf/252, 0)²) × √252); {rf}",
                              inputs, title="Sortino ratio"),
    }
