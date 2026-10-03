"""Insider Trading Aggregator — Phase 27.

Aggregate open-market insider trades across S&P 500 constituents:
buy/sell ratio, cluster buying detection, and sector sentiment scores.
Trades come from the SEC's quarterly insider transactions data set
(:mod:`insider_dataset`), one ~11 MB download per quarter.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd

from .. import provenance as pv
from ..cache import cached
from . import constituents
from . import edgar_service
from . import insider_dataset

logger = logging.getLogger(__name__)

_CLUSTER_DAYS = 30


def _key(symbol: str) -> str:
    """Compare tickers without share-class separators: filings write "BRK.B",
    the constituents list "BRK-B"."""
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


@cached("insider_aggregate")
def get_insider_aggregate() -> dict:
    """Aggregate the newest quarter of insider trades across the S&P 500."""
    if not edgar_service._edgar_ready():
        return {"error": edgar_service._NO_IDENTITY, "asOf": None}
    sp500 = constituents.get_constituents("sp500")
    if not sp500:
        return {"error": "No S&P 500 constituents available", "asOf": None}
    try:
        latest = insider_dataset.load_latest()
    except Exception as exc:
        logger.warning("Insider data set failed: %s", exc)
        return {"error": f"Could not load the SEC insider transactions data set: {exc}", "asOf": None}
    if latest is None:
        return {"error": "No SEC insider transactions data set is available", "asOf": None}
    quarter, trades, url = latest
    return aggregate(trades, sp500, quarter, url, built_at=insider_dataset.built_at(quarter))


def aggregate(trades: pd.DataFrame, sp500: list[dict], quarter: str, url: str | None = None,
              built_at: str | None = None) -> dict:
    """Aggregate the reduced trades of one quarterly data set (see
    :func:`insider_dataset.reduce_dataset`) over the given constituents.
    Only trades dated inside the quarter count; late filings of older
    trades are left out."""
    start, end = insider_dataset.quarter_start(quarter), insider_dataset.quarter_end(quarter)
    members = {_key(c["symbol"]): c for c in sp500}
    total = len(members)

    all_txs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for r in trades.itertuples(index=False):
        if not r.date or not (start.isoformat() <= r.date <= end.isoformat()):
            continue
        # A filing can list several share classes ("HEI, HEI.A"); count the trade once.
        member = next((members[k] for k in map(_key, str(r.symbols).split(",")) if k in members), None)
        if member is None or (r.accession, r.sk) in seen:
            continue
        seen.add((r.accession, r.sk))
        all_txs.append({
            "ticker": member["symbol"],
            "sector": member.get("sector") or "Unknown",
            "insiderName": r.insiderName,
            "title": r.title or None,
            "transactionType": "Buy" if r.code == "P" else "Sell",
            "shares": float(r.shares),
            "pricePerShare": float(r.price) if r.price else None,
            "totalValue": round(float(r.shares) * float(r.price), 2),
            "date": r.date,
        })

    if not all_txs:
        return {"error": f"No open-market insider trades by S&P 500 insiders in {quarter}",
                "asOf": end.isoformat(), "tickersChecked": total}

    # Aggregate: buy/sell ratios
    buys = [tx for tx in all_txs if tx.get("transactionType") == "Buy"]
    sells = [tx for tx in all_txs if tx.get("transactionType") == "Sell"]
    total_buy_value = sum(tx.get("totalValue", 0) or 0 for tx in buys)
    total_sell_value = sum(tx.get("totalValue", 0) or 0 for tx in sells)
    buy_count = len(buys)
    sell_count = len(sells)
    buy_sell_ratio = round(buy_count / sell_count, 2) if sell_count > 0 else None
    value_ratio = round(total_buy_value / total_sell_value, 2) if total_sell_value > 0 else None

    # Cluster detection: ≥3 unique insiders buying the same ticker in the quarter's last 30 days
    cutoff = end - timedelta(days=_CLUSTER_DAYS)
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

    filings = pv.ref("sec_edgar", None, f"Insider transactions data set {quarter} (Forms 3, 4 and 5 filed in "
                     f"the quarter)", frequency="quarterly", observed=end.isoformat(),
                     url=url or "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets",
                     note="Non-derivative open-market purchases (code P) and sales (code S) from original Form 4s "
                          "(amendments excluded), dated inside the quarter. A joint filing counts once, under its "
                          "first reporting owner. Value = shares × reported price; a trade filed without a price "
                          "counts with value 0.")
    members = pv.ref("wikipedia", None, "Current S&P 500 constituents with GICS sector")
    prov = {
        "*": pv.derived("open-market purchases (code P) and sales (code S) across S&P 500 insiders",
                        [filings, members], title="Insider activity"),
        "buySellRatio": pv.derived("number of buys / number of sells", ["*"], title="Buy/sell ratio"),
        "valueRatio": pv.derived("buy value / sell value (value = shares × price)", ["*"], title="Value ratio"),
        "clusterBuys": pv.derived(f"companies where 3 or more different insiders bought in the last {_CLUSTER_DAYS} days of the quarter",
                                  ["*"], title="Cluster buys"),
        "sectorSentiment": pv.derived("buys and sells per GICS sector", ["*"], title="Sector sentiment"),
        "topTrades": pv.derived("largest transactions by value", ["*"], title="Top trades"),
    }
    if built_at:  # a stored data set: fetched when it was written, not at request time (P3-35)
        filings["fetchedAt"] = prov["*"]["fetchedAt"] = built_at
    return pv.attach({
        "asOf": end.isoformat(),
        "dataset": quarter,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
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
    }, prov)
