"""M&A / Corporate Actions service — Phase 30.

Tracks announced merger & acquisition deals, deal values, and sector
activity using Finnhub news and yfinance corporate actions.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta

from ..cache import async_cached
from ..config import FINNHUB_API_KEY

log = logging.getLogger(__name__)

_BASE = "https://finnhub.io/api/v1"

# Known sectors for categorizing deals (based on ticker mapping)
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


def _extract_tickers(text: str) -> list[str]:
    """Extract potential ticker symbols from news text (1-5 uppercase letters)."""
    if not text:
        return []
    # Match 1-5 uppercase letters, excluding common false positives
    false_positives = {"A", "I", "THE", "IN", "TO", "OF", "ON", "IS", "IT", "AT", "BE",
                       "AND", "OR", "FOR", "CEO", "CFO", "IPO", "M&A", "US", "UK", "EU",
                       "NEW", "YORK", "BANK", "CORP", "INC", "LTD", "LLC", "NYSE", "NASDAQ"}
    matches = re.findall(r'\b([A-Z]{1,5})\b', text)
    return [m for m in matches if m not in false_positives]


def _guess_sector(tickers: list[str]) -> str:
    """Guess sector from ticker list."""
    for t in tickers:
        if t in _TICKER_SECTOR:
            return _TICKER_SECTOR[t]
    return "Other"


@async_cached("ma_tracker")
async def get_ma_data() -> dict:
    """Fetch M&A news and corporate actions data."""
    today = datetime.now().date()
    start = str(today - timedelta(days=90))
    end = str(today)

    deals = []
    monthly_volume: dict[str, dict] = {}  # month -> {count, totalValue}

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
                            summary = item.get("summary", "")
                            text = f"{headline} {summary}"
                            tickers_found = _extract_tickers(text)
                            sector = _guess_sector(tickers_found)
                            # Extract deal value if mentioned
                            value_match = re.search(r'\$(\d+(?:\.\d+)?)\s*(billion|B|million|M)', text, re.IGNORECASE)
                            deal_value = None
                            if value_match:
                                num = float(value_match.group(1))
                                unit = value_match.group(2).lower()
                                if unit in ("billion", "b"):
                                    deal_value = num * 1000  # convert to millions
                                else:
                                    deal_value = num

                            date_str = item.get("datetime", "")
                            if isinstance(date_str, (int, float)):
                                from datetime import datetime as dt
                                date_str = dt.fromtimestamp(date_str).isoformat()
                            month_key = date_str[:7] if date_str and isinstance(date_str, str) else str(today)[:7]

                            date_val = date_str[:10] if isinstance(date_str, str) and len(date_str) >= 10 else str(today)

                            deals.append({
                                "date": date_val,
                                "headline": headline[:120],
                                "acquirer": tickers_found[0] if tickers_found else "Unknown",
                                "target": tickers_found[1] if len(tickers_found) > 1 else "Unknown",
                                "value": deal_value,
                                "sector": sector,
                                "source": item.get("source", "Finnhub"),
                                "url": item.get("url", ""),
                            })

                            # Monthly aggregation
                            if month_key not in monthly_volume:
                                monthly_volume[month_key] = {"count": 0, "totalValue": 0}
                            monthly_volume[month_key]["count"] += 1
                            if deal_value:
                                monthly_volume[month_key]["totalValue"] += deal_value
        except Exception as exc:
            log.debug("Finnhub M&A news failed: %s", exc)

    # Sort deals by date descending
    deals.sort(key=lambda d: d["date"], reverse=True)

    # Sector heatmap
    sector_agg: dict[str, dict] = {}
    for d in deals:
        s = d["sector"]
        if s not in sector_agg:
            sector_agg[s] = {"dealCount": 0, "totalValue": 0}
        sector_agg[s]["dealCount"] += 1
        if d["value"]:
            sector_agg[s]["totalValue"] += d["value"]

    sector_heatmap = [
        {
            "sector": s,
            "dealCount": v["dealCount"],
            "avgValue": round(v["totalValue"] / v["dealCount"], 0) if v["dealCount"] > 0 and v["totalValue"] > 0 else None,
        }
        for s, v in sorted(sector_agg.items(), key=lambda x: x[1]["dealCount"], reverse=True)
    ]

    # Monthly volume chart data
    monthly_chart = [
        {"month": k, "count": v["count"], "totalValue": v["totalValue"] if v["totalValue"] > 0 else None}
        for k, v in sorted(monthly_volume.items())
    ]

    return {
        "asOf": str(today),
        "source": "Finnhub",
        "deals": deals,
        "monthlyVolume": monthly_chart,
        "sectorHeatmap": sector_heatmap,
    }
