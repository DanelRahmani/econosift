"""Economic Calendar service — Phase 4.

Aggregates four event streams into a unified calendar:
  - Macro: central-bank meetings (cb_meetings.json) + FRED release dates + Finnhub economic calendar
  - Earnings: per-ticker yfinance earnings_dates fan-out over an index universe
  - Dividends: per-ticker yfinance ex-dividend dates
  - IPOs: Finnhub IPO calendar

All public functions are cached 60 min and are safe to call from
``asyncio.to_thread``.  Every event shares the same dict schema; missing fields
default to None so callers never need to guard for missing keys.
"""
from __future__ import annotations

import json
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import yfinance as yf

from ..cache import cached
from ..config import FINNHUB_API_KEY, FRED_API_KEY
from ..services import constituents as _constituents
from ..services import finnhub_service

# ---------------------------------------------------------------------------
# Common event schema
# ---------------------------------------------------------------------------

_EVENT_KEYS = (
    "date", "category", "title", "ticker", "country", "impact",
    "time", "epsEstimate", "epsActual", "revenueEstimate", "surprisePct",
    "beatMiss", "amount", "exchange",
)


def _event(**kwargs) -> dict:
    """Build a calendar event with all schema keys present (defaults to None)."""
    ev: dict = {k: None for k in _EVENT_KEYS}
    ev.update(kwargs)
    return ev


# ---------------------------------------------------------------------------
# Central-bank meetings
# ---------------------------------------------------------------------------

@cached("cb_meetings")
def _load_cb_meetings() -> list[dict]:
    """Load cb_meetings.json from backend/data/.  Returns [] on any error."""
    try:
        path = pathlib.Path(__file__).resolve().parents[2] / "data" / "cb_meetings.json"
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Macro events
# ---------------------------------------------------------------------------

_FINNHUB_IMPACT = {"low": 1, "medium": 2, "high": 3}


@cached("macro_events")
def macro_events(start: str, end: str) -> list[dict]:
    """Merge central-bank meetings, FRED releases, and Finnhub economic calendar."""
    events: list[dict] = []

    # (a) Central-bank meetings
    for entry in _load_cb_meetings():
        d = entry.get("date", "")
        if start <= d <= end:
            events.append(_event(
                date=d,
                category="macro",
                title=entry.get("title", "CB Meeting"),
                country=entry.get("country"),
                impact=3,
            ))

    # (b) FRED release calendar (requires API key)
    if FRED_API_KEY:
        try:
            resp = requests.get(
                "https://api.stlouisfed.org/fred/releases/dates",
                params={
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "include_release_dates_with_no_data": "false",
                    "realtime_start": start,
                    "realtime_end": end,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            for rel in data.get("release_dates", []):
                d = rel.get("date", "")
                if start <= d <= end:
                    events.append(_event(
                        date=d,
                        category="macro",
                        title=rel.get("release_name", "FRED Release"),
                        country="US",
                    ))
        except Exception:
            pass

    # (c) Finnhub economic calendar
    for item in finnhub_service.economic_calendar(start, end):
        d = item.get("time", "") or item.get("date", "")
        # Finnhub returns full datetime strings; trim to date.
        if d and len(d) >= 10:
            d = d[:10]
        if not d or not (start <= d <= end):
            continue
        raw_impact = (item.get("impact") or "").lower()
        events.append(_event(
            date=d,
            category="macro",
            title=item.get("event") or item.get("name", "Economic Event"),
            country=(item.get("country") or "").upper() or None,
            impact=_FINNHUB_IMPACT.get(raw_impact),
        ))

    events.sort(key=lambda e: e["date"])
    return events


# ---------------------------------------------------------------------------
# Per-ticker yfinance work
# ---------------------------------------------------------------------------

def _ts_to_date(ts) -> str | None:
    """Convert a pandas Timestamp, unix-seconds int, or date string to 'YYYY-MM-DD'.

    yfinance returns exDividendDate as a unix-seconds integer; earnings_dates
    index entries are pandas Timestamps.  We try unit='s' first for integers,
    then fall back to a generic parse.
    """
    if ts is None:
        return None
    try:
        # Integer or float → assume unix seconds (yfinance convention)
        if isinstance(ts, (int, float)):
            return pd.to_datetime(ts, unit="s", utc=True).strftime("%Y-%m-%d")
        # pandas Timestamp / datetime / string → generic parse
        return pd.to_datetime(ts).strftime("%Y-%m-%d")
    except Exception:
        return None


def _fetch_ticker_events(sym: str) -> dict:
    """Fetch earnings and dividend events for a single ticker via yfinance.

    Returns {"earnings": [...], "dividends": [...]} with the common event schema.
    Never raises; on any failure returns empty lists.
    """
    earnings_events: list[dict] = []
    dividend_events: list[dict] = []

    try:
        ticker = yf.Ticker(sym)

        # --- Earnings dates ------------------------------------------------
        try:
            df = ticker.earnings_dates
            if df is not None and not df.empty:
                for ts, row in df.iterrows():
                    date_str = _ts_to_date(ts)
                    if not date_str:
                        continue

                    # Column names vary across yfinance versions; be defensive.
                    def _col(df, *names):
                        for n in names:
                            if n in df.columns:
                                return n
                        return None

                    est_col = _col(df, "EPS Estimate", "Earnings Estimate", "epsEstimate")
                    rep_col = _col(df, "Reported EPS", "EPS Actual", "epsActual")
                    surp_col = _col(df, "Surprise(%)", "Surprise", "surprisePct")

                    eps_est = None
                    eps_act = None
                    surp_pct = None
                    beat_miss = None

                    try:
                        if est_col:
                            v = row[est_col]
                            eps_est = None if pd.isna(v) else float(v)
                    except Exception:
                        pass

                    try:
                        if rep_col:
                            v = row[rep_col]
                            eps_act = None if pd.isna(v) else float(v)
                    except Exception:
                        pass

                    try:
                        if surp_col:
                            v = row[surp_col]
                            surp_pct = None if pd.isna(v) else float(v)
                    except Exception:
                        pass

                    # Beat/miss logic
                    if eps_act is not None and eps_est is not None:
                        if eps_act > eps_est:
                            beat_miss = "beat"
                        elif eps_act < eps_est:
                            beat_miss = "miss"
                        else:
                            beat_miss = "inline"

                    earnings_events.append(_event(
                        date=date_str,
                        category="earnings",
                        title=sym,
                        ticker=sym,
                        epsEstimate=eps_est,
                        epsActual=eps_act,
                        surprisePct=surp_pct,
                        beatMiss=beat_miss,
                    ))
        except Exception:
            pass

        # --- Ex-dividend date ----------------------------------------------
        try:
            info = ticker.info or {}
            ex_div_ts = info.get("exDividendDate")
            if ex_div_ts:
                date_str = _ts_to_date(ex_div_ts)
                if date_str:
                    div_amount = None
                    try:
                        v = info.get("dividendRate")
                        div_amount = None if v is None else float(v)
                    except Exception:
                        pass
                    dividend_events.append(_event(
                        date=date_str,
                        category="dividend",
                        title=sym,
                        ticker=sym,
                        amount=div_amount,
                    ))
        except Exception:
            pass

    except Exception:
        pass

    return {"earnings": earnings_events, "dividends": dividend_events}


# ---------------------------------------------------------------------------
# Internal fan-out (shared by earnings + dividends)
# ---------------------------------------------------------------------------

@cached("all_ticker_events")
def _all_ticker_events(index: str, start: str, end: str) -> dict[str, dict]:
    """Fan-out _fetch_ticker_events over all index constituents (max 10 threads).

    Returns {symbol: {"earnings": [...], "dividends": [...]}} filtered to range.
    """
    members = _constituents.get_constituents(index)
    if not members:
        return {}

    # Build symbol->name map for title enrichment
    name_map = {m["symbol"]: m["name"] for m in members}
    symbols = list(name_map.keys())

    raw: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_ticker_events, sym): sym for sym in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                result = fut.result()
                raw[sym] = result
            except Exception:
                raw[sym] = {"earnings": [], "dividends": []}

    # Filter to date range and enrich titles with company name
    filtered: dict[str, dict] = {}
    for sym, events in raw.items():
        name = name_map.get(sym, sym)

        earnings = [
            {**ev, "title": f"{name} Earnings"}
            for ev in events.get("earnings", [])
            if ev.get("date") and start <= ev["date"] <= end
        ]
        dividends = [
            {**ev, "title": f"{name} Ex-Dividend"}
            for ev in events.get("dividends", [])
            if ev.get("date") and start <= ev["date"] <= end
        ]
        filtered[sym] = {"earnings": earnings, "dividends": dividends}

    return filtered


# ---------------------------------------------------------------------------
# Public aggregation functions
# ---------------------------------------------------------------------------

@cached("earnings_events")
def earnings_events(index: str, start: str, end: str) -> list[dict]:
    """Return earnings events for all index constituents in [start, end]."""
    all_events = _all_ticker_events(index, start, end)
    out: list[dict] = []
    for sym_events in all_events.values():
        out.extend(sym_events.get("earnings", []))
    out.sort(key=lambda e: e["date"])
    return out


@cached("dividend_events")
def dividend_events(index: str, start: str, end: str) -> list[dict]:
    """Return dividend events for all index constituents in [start, end]."""
    all_events = _all_ticker_events(index, start, end)
    out: list[dict] = []
    for sym_events in all_events.values():
        out.extend(sym_events.get("dividends", []))
    out.sort(key=lambda e: e["date"])
    return out


@cached("ipo_events")
def ipo_events(start: str, end: str) -> list[dict]:
    """Return IPO events from Finnhub in [start, end].  Empty without API key."""
    out: list[dict] = []
    for item in finnhub_service.ipo_calendar(start, end):
        d = item.get("date", "")
        if not d or not (start <= d <= end):
            continue
        # Finnhub price is a string like "17.00" or a range "14.00-16.00".
        price = None
        try:
            raw_price = item.get("price")
            if raw_price not in (None, ""):
                price = float(str(raw_price).split("-")[0])
        except Exception:
            price = None
        out.append(_event(
            date=d,
            category="ipo",
            title=item.get("name") or item.get("symbol", "IPO"),
            ticker=item.get("symbol"),
            exchange=item.get("exchange"),
            amount=price,
        ))
    out.sort(key=lambda e: e["date"])
    return out


@cached("calendar")
def calendar(index: str, start: str, end: str) -> dict:
    """Aggregate all four event streams into a single calendar response."""
    return {
        "index": index,
        "start": start,
        "end": end,
        "macro": macro_events(start, end),
        "earnings": earnings_events(index, start, end),
        "dividends": dividend_events(index, start, end),
        "ipos": ipo_events(start, end),
        "sources": {
            "finnhub": bool(FINNHUB_API_KEY),
            "fred": bool(FRED_API_KEY),
            "cbMeetings": True,
        },
    }
