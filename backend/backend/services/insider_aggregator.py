"""Insider Trading Aggregator — Phase 27.

Aggregate Form 4 insider transactions across S&P 500 constituents:
buy/sell ratio, cluster buying detection, and sector sentiment scores.
🟡 compute tier — EDGAR rate-limited, ~100s for full run.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import date, timedelta

from ..cache import cached
from . import constituents
from . import edgar_service

logger = logging.getLogger(__name__)


def _form4_for_ticker(ticker: str, sector: str) -> list[dict]:
    """Fetch Form 4 transactions for a ticker and attach sector info."""
    try:
        result = edgar_service._fetch_form4_sync(ticker, max_transactions=None)
        time.sleep(0.15)  # rate-limit EDGAR
        transactions = result.get("transactions", [])
        for tx in transactions:
            tx["ticker"] = ticker
            tx["sector"] = sector
        return transactions
    except Exception:
        logger.debug("Form4 fetch failed for %s", ticker, exc_info=True)
        return []


@cached("insider_aggregate")
def get_insider_aggregate() -> dict:
    """Aggregate Form 4 data across all S&P 500 constituents.
    
    Returns buy/sell ratio, cluster buys, sector sentiment, and top trades.
    First run is slow (100+ seconds due to EDGAR rate limiting).
    Subsequent calls use cache.
    """
    if not edgar_service._edgar_ready():
        return {"error": edgar_service._NO_IDENTITY, "asOf": None}
    sp500 = constituents.get_constituents("sp500")
    if not sp500:
        return {"error": "No S&P 500 constituents available", "asOf": None}

    # Map ticker -> sector
    ticker_sectors: dict[str, str] = {}
    for c in sp500:
        ticker_sectors[c["symbol"]] = c.get("sector", "Unknown") or "Unknown"

    all_txs: list[dict] = []
    total = len(ticker_sectors)
    for i, (ticker, sector) in enumerate(ticker_sectors.items()):
        if i % 50 == 0:
            logger.info("Insider aggregate: %d/%d tickers processed", i, total)
        txs = _form4_for_ticker(ticker, sector)
        all_txs.extend(txs)

    if not all_txs:
        return {"error": "No Form 4 data retrieved", "asOf": str(date.today()), "tickersChecked": total}

    # Aggregate: buy/sell ratios
    buys = [tx for tx in all_txs if tx.get("transactionType") == "Buy"]
    sells = [tx for tx in all_txs if tx.get("transactionType") == "Sell"]
    total_buy_value = sum(tx.get("totalValue", 0) or 0 for tx in buys)
    total_sell_value = sum(tx.get("totalValue", 0) or 0 for tx in sells)
    buy_count = len(buys)
    sell_count = len(sells)
    buy_sell_ratio = round(buy_count / sell_count, 2) if sell_count > 0 else None
    value_ratio = round(total_buy_value / total_sell_value, 2) if total_sell_value > 0 else None

    # Cluster detection: ≥3 unique insiders buying the same ticker within 30 days
    cutoff = date.today() - timedelta(days=30)
    recent_buys: dict[str, list[dict]] = defaultdict(list)
    for tx in buys:
        tx_date_str = tx.get("date", "")
        try:
            tx_date = date.fromisoformat(tx_date_str[:10])
        except (ValueError, TypeError):
            continue
        if tx_date >= cutoff:
            insider = tx.get("insiderName", "Unknown")
            ticker = tx.get("ticker", "")
            if ticker:
                recent_buys[ticker].append(tx)

    cluster_buys: list[dict] = []
    for ticker, txs in recent_buys.items():
        unique_insiders = set(tx.get("insiderName", "") for tx in txs)
        if len(unique_insiders) >= 3:
            total_val = sum(tx.get("totalValue", 0) or 0 for tx in txs)
            dates = sorted(set(tx.get("date", "")[:10] for tx in txs))
            cluster_buys.append({
                "ticker": ticker,
                "insiderCount": len(unique_insiders),
                "transactionCount": len(txs),
                "totalValue": round(total_val, 2),
                "dateRange": f"{dates[0]} to {dates[-1]}" if dates else "",
            })

    cluster_buys.sort(key=lambda x: x["insiderCount"], reverse=True)

    # Sector sentiment: net buy ratio per sector
    sector_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"buys": 0, "sells": 0, "buyValue": 0.0, "sellValue": 0.0})
    for tx in all_txs:
        sec = tx.get("sector", "Unknown")
        if tx.get("transactionType") == "Buy":
            sector_stats[sec]["buys"] += 1
            sector_stats[sec]["buyValue"] += tx.get("totalValue", 0) or 0
        else:
            sector_stats[sec]["sells"] += 1
            sector_stats[sec]["sellValue"] += tx.get("totalValue", 0) or 0

    sector_sentiment: list[dict] = []
    for sec, stats in sorted(sector_stats.items()):
        total_tx = stats["buys"] + stats["sells"]
        net_ratio = round((stats["buys"] - stats["sells"]) / total_tx, 3) if total_tx > 0 else 0
        sector_sentiment.append({
            "sector": sec,
            "buys": int(stats["buys"]),
            "sells": int(stats["sells"]),
            "netBuyRatio": net_ratio,
            "totalBuyValue": round(stats["buyValue"], 0),
            "totalSellValue": round(stats["sellValue"], 0),
        })

    # Top individual trades (by value)
    top_trades = sorted(all_txs, key=lambda tx: tx.get("totalValue", 0) or 0, reverse=True)[:20]
    top_trades_clean: list[dict] = []
    for tx in top_trades:
        top_trades_clean.append({
            "ticker": tx.get("ticker", ""),
            "insiderName": tx.get("insiderName", "Unknown"),
            "title": tx.get("title"),
            "transactionType": tx.get("transactionType"),
            "shares": tx.get("shares"),
            "pricePerShare": tx.get("pricePerShare"),
            "totalValue": tx.get("totalValue"),
            "date": tx.get("date", "")[:10] if tx.get("date") else None,
            "sector": tx.get("sector"),
        })

    return {
        "asOf": str(date.today()),
        "tickersChecked": total,
        "tickersWithData": len(set(tx.get("ticker") for tx in all_txs)),
        "totalTransactions": len(all_txs),
        "buyCount": buy_count,
        "sellCount": sell_count,
        "buySellRatio": buy_sell_ratio,
        "totalBuyValue": round(total_buy_value, 0),
        "totalSellValue": round(total_sell_value, 0),
        "valueRatio": value_ratio,
        "clusterBuys": cluster_buys[:10],
        "sectorSentiment": sector_sentiment,
        "topTrades": top_trades_clean[:20],
    }
