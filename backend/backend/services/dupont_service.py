"""Sector DuPont Analysis — Phase 27.

Decompose ROE into Net Profit Margin × Asset Turnover × Equity Multiplier
for each GICS sector using aggregated S&P 500 yfinance financials.
"""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

from .. import provenance as pv
from ..cache import cached
from . import constituents

logger = logging.getLogger(__name__)


def _clean(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return round(f, 6) if math.isfinite(f) else None
    except Exception:
        return None


def _fetch_one(ticker: str, sector: str) -> dict | None:
    """Fetch DuPont components for a single ticker from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        # Income statement — get most recent annual row
        fin = stock.financials
        if fin is None or fin.empty:
            return None
        # Use the first column (most recent annual)
        ni = _clean(fin.loc["Net Income"].iloc[0]) if "Net Income" in fin.index else None
        rev = _clean(fin.loc["Total Revenue"].iloc[0]) if "Total Revenue" in fin.index else None

        # Balance sheet
        bs = stock.balance_sheet
        if bs is None or bs.empty:
            return None
        ta = _clean(bs.loc["Total Assets"].iloc[0]) if "Total Assets" in bs.index else None
        eq = _clean(bs.loc["Stockholders Equity"].iloc[0]) if "Stockholders Equity" in bs.index else None

        if ni is None or rev is None or ta is None or eq is None:
            return None
        if rev == 0 or ta == 0 or eq == 0:
            return None

        margin = ni / rev
        turnover = rev / ta
        leverage = ta / eq
        roe = margin * turnover * leverage

        return {
            "ticker": ticker,
            "sector": sector,
            "netMargin": round(margin, 6),
            "assetTurnover": round(turnover, 6),
            "equityMultiplier": round(leverage, 4),
            "roe": round(roe, 6),
        }
    except Exception:
        logger.debug("DuPont fetch failed for %s", ticker, exc_info=True)
        return None


@cached("sector_dupont")
def get_sector_dupont() -> dict:
    """Compute median DuPont decomposition by GICS sector for the S&P 500."""
    sp500 = constituents.get_constituents("sp500")
    if not sp500:
        return {"sectors": [], "asOf": None, "tickerCount": 0, "error": "No S&P 500 constituents available"}

    # Group tickers by sector
    sector_tickers: dict[str, list[str]] = {}
    for c in sp500:
        sector = c.get("sector", "Unknown") or "Unknown"
        sector_tickers.setdefault(sector, []).append(c["symbol"])

    # Fetch DuPont components for all tickers in parallel
    all_rows: list[dict] = []
    all_tickers: list[tuple[str, str]] = []
    for sector, tickers in sector_tickers.items():
        for t in tickers:
            all_tickers.append((t, sector))

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(_fetch_one, t, s): (t, s) for t, s in all_tickers}
        for fut in as_completed(futures):
            try:
                row = fut.result()
                if row is not None:
                    all_rows.append(row)
            except Exception:
                logger.debug("DuPont worker failed", exc_info=True)

    if not all_rows:
        return {"sectors": [], "asOf": None, "tickerCount": 0, "error": "No financial data retrieved"}

    # Aggregate by sector: median of each component
    sector_data: dict[str, dict[str, list[float]]] = {}
    for row in all_rows:
        sec = row["sector"]
        if sec not in sector_data:
            sector_data[sec] = {"margin": [], "turnover": [], "leverage": [], "roe": []}
        sector_data[sec]["margin"].append(row["netMargin"])
        sector_data[sec]["turnover"].append(row["assetTurnover"])
        sector_data[sec]["leverage"].append(row["equityMultiplier"])
        sector_data[sec]["roe"].append(row["roe"])

    sectors: list[dict] = []
    for sec, vals in sorted(sector_data.items()):
        n = len(vals["margin"])
        margin_med = round(float(sorted(vals["margin"])[n // 2]), 6)
        turnover_med = round(float(sorted(vals["turnover"])[n // 2]), 6)
        leverage_med = round(float(sorted(vals["leverage"])[n // 2]), 4)
        roe_med = round(float(sorted(vals["roe"])[n // 2]), 6)

        sectors.append({
            "sector": sec,
            "netMargin": margin_med,
            "assetTurnover": turnover_med,
            "equityMultiplier": leverage_med,
            "roe": roe_med,
            "tickerCount": n,
        })

    statements = pv.ref(
        "yahoo", None, "Annual income statement and balance sheet of each S&P 500 member (Net Income, Total Revenue, "
        "Total Assets, Stockholders Equity)", frequency="annual",
        note="Each company's most recent fiscal year as Yahoo reports it; fiscal year-ends differ across companies.")
    members = pv.ref("wikipedia", None, "Current S&P 500 constituents and their GICS sectors")
    prov: dict = {
        "*": pv.derived(
            "Per company: netMargin = Net Income ÷ Total Revenue, assetTurnover = Total Revenue ÷ Total Assets, "
            "equityMultiplier = Total Assets ÷ Stockholders Equity, roe = the product of the three; each sector "
            "value is the median across its companies (the upper-middle value when the count is even)",
            [statements, members], title="Sector DuPont decomposition"),
    }
    medians = {
        "netMargin": ("median of Net Income ÷ Total Revenue across the sector's companies", "Net profit margin"),
        "assetTurnover": ("median of Total Revenue ÷ Total Assets across the sector's companies", "Asset turnover"),
        "equityMultiplier": ("median of Total Assets ÷ Stockholders Equity across the sector's companies",
                             "Equity multiplier"),
        "roe": ("median of (Net Income ÷ Total Revenue × Revenue ÷ Assets × Assets ÷ Equity) across the sector's "
                "companies; not the product of the three medians", "Return on equity"),
    }
    for row in sectors:
        for field, (formula, title) in medians.items():
            prov[f"sectors.{row['sector']}.{field}"] = pv.derived(formula, [statements, members], title=title)
    return pv.attach({
        "sectors": sectors,
        "asOf": None,  # yfinance financials are as-reported
        "tickerCount": len(all_rows),
        "note": "Median values per GICS sector from S&P 500 constituents",
    }, prov)
