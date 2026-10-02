"""Short Interest service — Phase 30.

Fetches short interest data via yfinance .info (primary) with Finnhub
fallback for tickers/universe, computes squeeze scores, and aggregates by sector.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from .. import provenance as pv
from ..cache import async_cached
from ..config import FINNHUB_API_KEY

log = logging.getLogger(__name__)

_BASE = "https://finnhub.io/api/v1"

# Hard-coded large-cap sample (NOT the full S&P 500) -- ~500 per-ticker yfinance
# .info calls are too heavy for one request, so the label says so honestly.
_DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "XOM",
    "DIS", "NFLX", "ADBE", "CRM", "CSCO", "INTC", "VZ", "PFE", "KO",
    "PEP", "TMO", "ABT", "NKE", "MRK", "WFC", "ORCL", "IBM", "AMD",
    "QCOM", "TXN", "AVGO", "COST", "CVX", "LLY", "ABBV", "MCD",
]


def _fetch_yf_short(ticker: str) -> dict | None:
    """Fetch short interest from yfinance .info dict (free, always available)."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        si_pct = info.get("shortPercentOfFloat")  # decimal e.g. 0.0098 = 0.98%
        if si_pct is not None:
            si_pct = round(float(si_pct) * 100, 2)  # convert to %
        days = info.get("shortRatio")  # days to cover
        if days is not None:
            days = round(float(days), 2)
        # Yahoo reports the FINRA settlement date as an epoch; the data is
        # ~2 weeks old, so stamping today's date would overstate freshness.
        settle = info.get("dateShortInterest")
        settlement_date = (datetime.utcfromtimestamp(settle).date().isoformat()
                           if isinstance(settle, (int, float)) and settle > 0 else None)
        return {
            "shortPercent": si_pct,
            "daysToCover": days,
            "settlementDate": settlement_date,
        }
    except Exception as exc:
        log.debug("yfinance short interest failed for %s: %s", ticker, exc)
        return None


async def _fetch_finnhub_short(ticker: str) -> dict | None:
    """Fetch short interest from Finnhub (premium tier only)."""
    if not FINNHUB_API_KEY:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_BASE}/stock/short-interest",
                params={"symbol": ticker, "token": FINNHUB_API_KEY},
            )
            if resp.status_code == 403:
                return None  # premium only
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data:
                si = data.get("shortPercent")
                return {
                    "shortPercent": round(si, 2) if si is not None else None,
                    "daysToCover": data.get("daysToCover"),
                    "settlementDate": data.get("settlementDate"),
                }
            return None
    except Exception as exc:
        log.debug("Finnhub short interest failed for %s: %s", ticker, exc)
        return None


def _compute_squeeze_score(si_pct: float | None, days: float | None) -> float | None:
    """Heuristic squeeze score: higher = more squeeze potential."""
    if si_pct is None or days is None:
        return None
    return round(si_pct * max(days, 0.1), 2)


# Sector mapping (simple, based on ticker)
_TICKER_SECTORS: dict[str, str] = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Consumer Discretionary", "NVDA": "Technology", "META": "Technology",
    "TSLA": "Consumer Discretionary", "BRK-B": "Financials",
    "JPM": "Financials", "V": "Financials", "JNJ": "Healthcare",
    "WMT": "Consumer Staples", "PG": "Consumer Staples", "MA": "Financials",
    "UNH": "Healthcare", "HD": "Consumer Discretionary", "BAC": "Financials",
    "XOM": "Energy", "DIS": "Communication Services", "NFLX": "Communication Services",
    "ADBE": "Technology", "CRM": "Technology", "CSCO": "Technology",
    "INTC": "Technology", "VZ": "Communication Services", "PFE": "Healthcare",
    "KO": "Consumer Staples", "PEP": "Consumer Staples", "TMO": "Healthcare",
    "ABT": "Healthcare", "NKE": "Consumer Discretionary", "MRK": "Healthcare",
    "WFC": "Financials", "ORCL": "Technology", "IBM": "Technology",
    "AMD": "Technology", "QCOM": "Technology", "TXN": "Technology",
    "AVGO": "Technology", "COST": "Consumer Staples", "CVX": "Energy",
    "LLY": "Healthcare", "ABBV": "Healthcare", "MCD": "Consumer Discretionary",
}


@async_cached("short_interest")
async def get_short_interest(ticker: str | None = None, universe: str | None = None) -> dict:
    """Fetch short interest data.

    If ticker is provided, returns data for that single ticker.
    If universe is 'sp500', returns data for the default universe.
    Otherwise returns data for the ticker AAPL as default.
    Uses yfinance as primary source (free), Finnhub as optional premium fallback.
    """
    tickers_to_fetch: list[str] = []
    universe_label = None
    if ticker:
        tickers_to_fetch = [ticker.upper()]
    elif universe == "sp500":
        tickers_to_fetch = list(_DEFAULT_UNIVERSE)
        universe_label = f"S&P 500 sample ({len(tickers_to_fetch)} large caps)"
    else:
        tickers_to_fetch = ["AAPL"]

    # Fetch from yfinance in thread pool (yfinance is sync, blocking)
    def _fetch_all_yf(ts: list[str]) -> list[dict | None]:
        return [_fetch_yf_short(t) for t in ts]

    yf_results = await asyncio.to_thread(_fetch_all_yf, tickers_to_fetch)

    items = []
    for t, r in zip(tickers_to_fetch, yf_results):
        if r is None:
            continue
        si_pct = r.get("shortPercent")
        days = r.get("daysToCover")
        squeeze = _compute_squeeze_score(si_pct, days)
        sector = _TICKER_SECTORS.get(t, "Other")
        items.append({
            "ticker": t,
            "shortFloat": si_pct,
            "daysToCover": days,
            "squeezeScore": squeeze,
            "sector": sector,
            "asOf": r.get("settlementDate"),
        })

    # Sort by short % of float descending
    items.sort(key=lambda x: x["shortFloat"] or 0, reverse=True)

    # Most shorted (top 10)
    most_shorted = [i for i in items if i["shortFloat"] is not None][:10]

    # Squeeze candidates (short% > 25 and days-to-cover >5)
    squeeze_candidates = [
        i for i in items
        if i["shortFloat"] is not None and i["shortFloat"] > 25
        and i["daysToCover"] is not None and i["daysToCover"] > 5
    ]
    squeeze_candidates.sort(key=lambda x: x["squeezeScore"] or 0, reverse=True)

    # Sector aggregates
    sector_agg: dict[str, list[float]] = {}
    for i in items:
        if i["shortFloat"] is not None:
            sector_agg.setdefault(i["sector"], []).append(i["shortFloat"])
    sector_summary = [
        {
            "sector": s,
            "avgShortFloat": round(sum(vals) / len(vals), 2),
            "maxShortFloat": round(max(vals), 2),
            "tickerCount": len(vals),
        }
        for s, vals in sorted(sector_agg.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
    ]

    as_of = max((i["asOf"] for i in items if i.get("asOf")), default=None)
    return pv.attach({
        # Latest exchange settlement date among the tickers (published twice a
        # month, about two weeks in arrears).
        "asOf": as_of,
        "source": "yfinance",
        "universe": universe_label,
        "universeCount": len(tickers_to_fetch),
        "items": items,
        "mostShorted": most_shorted,
        "squeezeCandidates": squeeze_candidates,
        "sectorSummary": sector_summary,
    }, _provenance(as_of, {"items": items, "mostShorted": most_shorted,
                           "squeezeCandidates": squeeze_candidates}))


def _provenance(as_of: str | None, groups: dict[str, list[dict]]) -> dict:
    """Per-ticker Yahoo short-interest refs under items / mostShorted / squeezeCandidates."""
    prov: dict = {"*": pv.ref(
        "yahoo", None, "Short interest (shortPercentOfFloat, shortRatio, dateShortInterest)",
        frequency="semi-monthly", observed=as_of,
        note="Exchange-reported short interest as republished by Yahoo, about two weeks in arrears; "
             "each ticker carries its own settlement date.")}
    prov["sectorSummary"] = pv.derived(
        "mean / max of shortFloat over the tickers in each sector; sector comes from a hard-coded ticker map",
        ["*"], title="Sector short-interest summary", observed=as_of)
    squeeze = pv.derived("shortFloat (%) × max(daysToCover, 0.1)", ["*"], title="Squeeze score (heuristic)")
    sector = pv.ref("econosift", None, "Sector label from a hard-coded ticker map (\"Other\" if unmapped)")
    for group, rows in groups.items():
        for i in rows:
            t = i["ticker"]
            prov[f"{group}.{t}"] = pv.yahoo(t, "Short interest: % of float short and days to cover",
                                            units="% of float; days", frequency="semi-monthly",
                                            observed=i.get("asOf"))
            prov[f"{group}.{t}.squeezeScore"] = squeeze
            prov[f"{group}.{t}.sector"] = sector
    return prov
