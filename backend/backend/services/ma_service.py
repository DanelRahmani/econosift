"""M&A / Corporate Actions service — Phase 30.

Tracks merger & acquisition news using Finnhub merger-category market news.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .. import provenance as pv
from ..cache import async_cached
from ..config import FINNHUB_API_KEY

log = logging.getLogger(__name__)

_BASE = "https://finnhub.io/api/v1"

# Known sectors for categorizing tickers (based on ticker mapping)
_TICKER_SECTOR: dict[str, str] = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Consumer Discretionary", "NVDA": "Technology", "META": "Technology",
    "TSLA": "Consumer Discretionary", "JPM": "Financials", "V": "Financials",
    "JNJ": "Healthcare", "WMT": "Consumer Staples", "XOM": "Energy",
    "CVX": "Energy", "PFE": "Healthcare", "MRK": "Healthcare",
    "DIS": "Communication Services", "NFLX": "Communication Services",
    "BAC": "Financials", "WFC": "Financials", "CSCO": "Technology",
    "INTC": "Technology", "T": "Communication Services", "VZ": "Communication Services",
    "UNH": "Healthcare", "HD": "Consumer Discretionary", "NKE": "Consumer Discretionary",
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "ABBV": "Healthcare", "LLY": "Healthcare", "ABT": "Healthcare",
    "ORCL": "Technology", "IBM": "Technology", "AMD": "Technology",
    "QCOM": "Technology", "TXN": "Technology", "AVGO": "Technology",
    "COST": "Consumer Staples", "MCD": "Consumer Discretionary",
    "ADBE": "Technology", "CRM": "Technology", "MA": "Financials",
}


def _guess_sector(related_tickers: list[str]) -> str | None:
    """Return sector for the first known ticker in the list, or None."""
    for t in related_tickers:
        if t in _TICKER_SECTOR:
            return _TICKER_SECTOR[t]
    return None


@async_cached("ma_tracker")
async def get_ma_data() -> dict:
    """Fetch M&A news from Finnhub merger-category market news."""
    today = datetime.now().date()

    news_items = []

    # Try Finnhub merger news
    if FINNHUB_API_KEY:
        try:
            import httpx
            log.info("Fetching Finnhub merger news...")
            async with httpx.AsyncClient(timeout=15) as client:
                # Finnhub general news with merger category
                resp = await client.get(
                    f"{_BASE}/news",
                    params={
                        "category": "merger",
                        "token": FINNHUB_API_KEY,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    log.info("Finnhub merger news status=%d type=%s", resp.status_code, type(data).__name__)
                    if isinstance(data, list):
                        log.info("Got %d merger news items", len(data))
                        for item in data[:50]:  # limit to 50
                            headline = item.get("headline", "")
                            # Parse date from unix timestamp
                            date_val = None
                            ts = item.get("datetime")
                            if isinstance(ts, (int, float)):
                                try:
                                    dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)
                                    date_val = dt_obj.date().isoformat()
                                except (ValueError, OSError, OverflowError):
                                    date_val = None

                            # Parse Finnhub's related tickers
                            related_str = item.get("related", "")
                            related = []
                            if related_str:
                                related = [t.strip().upper() for t in related_str.split(",") if t.strip()]

                            # Determine sector only if we have related tickers
                            sector = None
                            if related:
                                sector = _guess_sector(related)

                            news_items.append({
                                "date": date_val,
                                "headline": headline[:160],
                                "related": related,
                                "sector": sector,
                                "source": item.get("source", "Finnhub"),
                                "url": item.get("url", ""),
                            })
        except Exception as exc:
            log.debug("Finnhub M&A news failed: %s", exc)

    # Sort: newest first (items with date), then items without date
    # Using a key that puts None dates last by replacing None with a very small string
    news_items.sort(key=lambda item: item["date"] or "0000-00-00", reverse=True)

    # Monthly count: items with a date only, ascending months
    monthly_counts_map: dict[str, int] = {}
    for item in news_items:
        if item["date"]:
            month_key = item["date"][:7]  # YYYY-MM
            monthly_counts_map[month_key] = monthly_counts_map.get(month_key, 0) + 1

    monthly_count = [
        {"month": k, "count": v}
        for k, v in sorted(monthly_counts_map.items())
    ]

    # Sector count: items with sector not null, desc by count
    sector_counts_map: dict[str, int] = {}
    for item in news_items:
        if item["sector"]:
            sector_counts_map[item["sector"]] = sector_counts_map.get(item["sector"], 0) + 1

    sector_count = [
        {"sector": k, "count": v}
        for k, v in sorted(sector_counts_map.items(), key=lambda x: x[1], reverse=True)
    ]

    news_ref = pv.ref(
        "finnhub", "news?category=merger",
        "Merger-category market news (latest items)",
        url="https://finnhub.io/docs/api/market-news",
        note="News articles about mergers, not a deal database: no acquirer, target or deal value is inferred."
    )
    return pv.attach({
        "asOf": str(today),
        "source": "Finnhub",
        "news": news_items,
        "monthlyCount": monthly_count,
        "sectorCount": sector_count,
    }, {
        "*": news_ref,
        "news": news_ref,
        "monthlyCount": pv.derived(
            "number of merger-news items per month",
            [news_ref], title="Monthly merger news count"
        ),
        "sectorCount": pv.derived(
            "number of merger-news items per sector of a Finnhub-tagged ticker "
            "(fixed ticker→sector map); untagged items are not counted",
            [news_ref], title="Merger news by sector"
        ),
    })
