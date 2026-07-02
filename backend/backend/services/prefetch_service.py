"""Prefetch service: staggered background warming of slow-changing cached data.

Calls the app's own API endpoints via httpx so data flows through the normal
@cached / @async_cached pipeline and lands in both memory and SQLite.

Categories are processed sequentially; within each category, calls are
spaced by a configurable stagger delay to avoid API rate limits.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

STAGGER_S = 1.5
STAGGER_HEAVY = 5.0   # Extra spacing for treemap / screener / ticker batch calls
BASE_URL = "http://localhost:8000/api"

# Tiers that need extra rate-limit spacing (index in the task list)
_HEAVY_TIERS: set[int] | None = None  # computed lazily when tasks are built

# ---------------------------------------------------------------------------
# Helper: build index constituent ticker tasks (dynamically resolved)
# ---------------------------------------------------------------------------

def _build_index_ticker_tasks() -> list[tuple[str, str, str, dict | None]]:
    """Build price + quote prefetch tasks for Dow 30 and Nasdaq 100.

    Dow tickers are fetched first; NDX tickers that already appear in the
    Dow are skipped to avoid redundant API calls.
    """
    tasks: list[tuple[str, str, str, dict | None]] = []
    try:
        from .constituents import constituent_symbols

        dow = constituent_symbols("dow") or []
        ndx = constituent_symbols("ndx") or []

        # Deduplicate: NDX tickers not already in Dow
        dow_set = set(dow)
        ndx_only = [s for s in ndx if s not in dow_set]

        # Batch prices in groups of 10
        for label, symbols, prefix in [
            ("Dow 30", dow, "Dow"),
            ("Nasdaq 100", ndx_only, "NDX"),
        ]:
            if not symbols:
                continue
            for i in range(0, len(symbols), 10):
                batch = symbols[i:i + 10]
                batch_str = ",".join(batch)
                start = i + 1
                end = min(i + 10, len(symbols))
                tasks.append((
                    f"Ticker — {prefix} prices {start}–{end}",
                    "GET", "/market/prices",
                    {"tickers": batch_str, "period": "1y"},
                ))

        # Quotes for all unique tickers (top 30 most important)
        all_unique = dow + ndx_only
        for sym in all_unique[:30]:
            tasks.append((
                f"Ticker — {sym} quote",
                "GET", f"/market/quote/{sym}", None,
            ))

        # Market caps for all at once
        if all_unique:
            tasks.append((
                f"Ticker — Dow+NDX market caps ({len(all_unique)} tickers)",
                "GET", "/treemap", {"index": "dow", "period": "1d"},
            ))

    except Exception as exc:
        logger.warning("_build_index_ticker_tasks failed: %s", exc)

    return tasks


# ---------------------------------------------------------------------------
# Prefetch task definitions — each is a (label, HTTP method, path, params)
# ---------------------------------------------------------------------------

def _prefetch_tasks() -> list[tuple[str, str, str, dict | None]]:
    """Return ordered list of (label, method, path, params) to prefetch."""
    return [
        # ── Tier 1: Atlas country-level data ───────────────────────────
        ("Atlas — GDP growth timeline", "GET", "/atlas/timeline",    {"indicator": "gdp_growth",  "start": 2000, "end": 2024}),
        ("Atlas — Inflation timeline",  "GET", "/atlas/timeline",    {"indicator": "inflation",   "start": 2000, "end": 2024}),
        ("Atlas — Unemployment",        "GET", "/atlas/timeline",    {"indicator": "unemployment","start": 2000, "end": 2024}),
        ("Atlas — Debt/GDP",            "GET", "/atlas/timeline",    {"indicator": "debt_gdp",    "start": 2000, "end": 2024}),
        ("Atlas — Current Account",     "GET", "/atlas/timeline",    {"indicator": "current_account", "start": 2000, "end": 2024}),
        ("Atlas — GDP per capita",      "GET", "/atlas/timeline",    {"indicator": "gdp_per_capita",  "start": 2000, "end": 2024}),
        ("Atlas — Regions",             "GET", "/atlas/regions",     None),
        ("Atlas — Indicators",          "GET", "/atlas/indicators",   None),

        # ── Tier 2: Sovereign risk & central banks ────────────────────
        ("Country Risk",                "GET", "/macro/country-risk", None),
        ("Central Banks",               "GET", "/macro/centralbanks", None),

        # ── Tier 3: Macro-economic FRED data (US, updates monthly) ───
        ("Macro — Rates & Yields",      "GET", "/macro/rates",       None),
        ("Macro — Inflation",           "GET", "/macro/inflation",   None),
        ("Macro — Employment",          "GET", "/macro/employment",  None),
        ("Macro — Housing",             "GET", "/macro/housing",     None),
        ("Macro — Leading Indicators",  "GET", "/macro/leading",     {"base_year": 2020}),
        ("Macro — Financial Conditions","GET", "/macro/financial-conditions", None),
        ("Macro — Commodities",         "GET", "/macro/commodities", None),
        ("Macro — FX Heatmap",          "GET", "/macro/fx/heatmap",  None),
        ("Macro — Regime",              "GET", "/macro/regime",      None),

        # ── Tier 4: Market-level data ────────────────────────────────
        ("Sector Returns",              "GET", "/sector/returns",     None),
        ("Sector Fundamentals",         "GET", "/sector/fundamentals", None),
        ("Sector Rotation",             "GET", "/sector/rotation",   None),
        ("Credit Pulse",                "GET", "/credit/pulse",      None),
        ("Yield Curves",                "GET", "/yield/curves",      None),
        ("Policy Tracker",              "GET", "/policy/tracker",    None),
        ("Sovereign Risk",              "GET", "/sovereign/risk",    None),
        ("Fear & Greed",                "GET", "/dashboard/fear-greed", None),
        ("Market Breadth",              "GET", "/dashboard/breadth", {"index": "sp500"}),
        ("Indices",                     "GET", "/dashboard/indices",  None),
        ("Movers",                      "GET", "/dashboard/movers",  None),

        # ── Tier 5: FX & research ────────────────────────────────────
        ("FX — Latest rates",           "GET", "/macro/fx",          {"base": "USD", "targets": "EUR,GBP,JPY,CHF,AUD,CAD"}),
        ("FX — PPP",                    "GET", "/macro/fx/ppp",      None),
        ("Fama-French Factors",         "GET", "/macro/fama-french", None),

        # ── Tier 6: Popular tickers ──────────────────────────────────
        ("Ticker — AAPL+MSFT prices",   "GET", "/market/prices",     {"tickers": "AAPL,MSFT", "period": "1y"}),
        ("Ticker — GOOGL+AMZN prices",  "GET", "/market/prices",     {"tickers": "GOOGL,AMZN", "period": "1y"}),
        ("Ticker — NVDA+SPY prices",    "GET", "/market/prices",     {"tickers": "NVDA,SPY", "period": "1y"}),
        ("Ticker — AAPL quote",         "GET", "/market/quote/AAPL",  None),
        ("Ticker — MSFT quote",         "GET", "/market/quote/MSFT",  None),
        ("Ticker — GOOGL quote",        "GET", "/market/quote/GOOGL", None),
        ("Ticker — NVDA quote",         "GET", "/market/quote/NVDA",  None),

        # ── Tier 7: Index constituents (Dow 30 + Nasdaq 100, deduplicated) ──
        *_build_index_ticker_tasks(),

        # ── Tier 8: Treemaps & Screener universes (rate-limited) ─────
        ("Treemap — S&P 500",           "GET", "/treemap",           {"index": "sp500", "period": "1d"}),
        ("Treemap — Nasdaq 100",        "GET", "/treemap",           {"index": "ndx",   "period": "1d"}),
        ("Treemap — Dow 30",            "GET", "/treemap",           {"index": "dow",   "period": "1d"}),
        ("Screener — S&P 500 universe", "GET", "/screener/universe", {"index": "sp500"}),
        ("Screener — Nasdaq 100",       "GET", "/screener/universe", {"index": "ndx"}),
        ("Screener — Dow 30",           "GET", "/screener/universe", {"index": "dow"}),
        ("Dashboard — NDX breadth",     "GET", "/dashboard/breadth", {"index": "ndx"}),
        ("Dashboard — Dow breadth",     "GET", "/dashboard/breadth", {"index": "dow"}),

        # ── Tier 9: Calendar & events ────────────────────────────────
        ("Calendar — Current week",     "GET", "/calendar",          {"index": "sp500"}),

        # ── Tier 10: Wiki ────────────────────────────────────────────
        ("Wiki — Terms",                "GET", "/wiki/terms",        None),
        ("Wiki — Categories",           "GET", "/wiki/categories",   None),
    ]


# ---------------------------------------------------------------------------
# Prefetch runner
# ---------------------------------------------------------------------------

_prefetch_state: dict = {
    "running": False,
    "started_at": None,
    "completed_at": None,
    "total": 0,
    "done": 0,
    "ok": 0,
    "failed": 0,
    "current": None,
    "errors": [],
}


async def _prefetch_one(client: httpx.AsyncClient, label: str, method: str, path: str, params: dict | None) -> None:
    """Run a single prefetch API call, updating global state."""
    _prefetch_state["current"] = label
    try:
        if method == "GET":
            resp = await client.get(BASE_URL + path, params=params, timeout=120.0)
        else:
            resp = await client.post(BASE_URL + path, json=params or {}, timeout=120.0)
        if resp.status_code < 400:
            _prefetch_state["ok"] += 1
        else:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
        logger.info("Prefetch OK: %s", label)
    except Exception as exc:
        _prefetch_state["failed"] += 1
        err_msg = f"{type(exc).__name__}: {exc}"
        _prefetch_state["errors"].append({"label": label, "error": err_msg[:200]})
        logger.warning("Prefetch FAILED: %s — %s", label, err_msg[:200])
    finally:
        _prefetch_state["done"] += 1
        _prefetch_state["current"] = None


def _ensure_bulk_data() -> None:
    """Start a background bulk-data download if the World Bank parquet files are
    missing, so Atlas and other bulk-backed views have local data to read.

    Best-effort and non-blocking — the live API fallback covers the gap while
    the download runs. No-op if bulk data already exists or a run is in flight.
    """
    try:
        from .bulk_data_service import (
            DATA_DIR as _BULK_DIR,
            is_bulk_running,
            refresh_all_bulk_data,
        )
        if is_bulk_running() or any(_BULK_DIR.glob("wb_*.parquet")):
            return
        logger.info("Prefetch: no World Bank bulk data found — starting background download")
        asyncio.create_task(asyncio.to_thread(refresh_all_bulk_data))
    except Exception as exc:
        logger.warning("Prefetch: bulk-data kickoff failed: %s", exc)


async def run_prefetch() -> dict:
    """Run all prefetch tasks with staggered spacing. Returns immediately."""
    if _prefetch_state["running"]:
        return {"status": "already_running", "progress": get_prefetch_status()}

    tasks = _prefetch_tasks()
    _prefetch_state.update(
        running=True,
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
        total=len(tasks),
        done=0,
        ok=0,
        failed=0,
        current=None,
        errors=[],
    )

    # Build heavy-tier index set: treemap, screener, and ticker batch calls
    # get extra spacing to avoid yfinance rate limits.
    _HEAVY_KEYWORDS = ("Treemap", "Screener", "Dow 30 prices", "Nasdaq 100 prices",
                        "Dow+NDX market caps")

    async def _runner():
        try:
            _ensure_bulk_data()  # kick a background bulk download if none present
            async with httpx.AsyncClient() as client:
                for idx, (label, method, path, params) in enumerate(tasks):
                    await _prefetch_one(client, label, method, path, params)
                    if _prefetch_state["done"] < len(tasks):
                        # Heavy tasks get longer spacing to respect API rate limits
                        is_heavy = any(kw in label for kw in _HEAVY_KEYWORDS)
                        delay = STAGGER_HEAVY if is_heavy else STAGGER_S
                        await asyncio.sleep(delay)
        finally:
            _prefetch_state["running"] = False
            _prefetch_state["completed_at"] = datetime.now(timezone.utc).isoformat()

    asyncio.create_task(_runner())
    return {"status": "started", "progress": get_prefetch_status()}


def get_prefetch_status() -> dict:
    """Return current prefetch progress for the admin panel."""
    return {
        "running": _prefetch_state["running"],
        "started_at": _prefetch_state["started_at"],
        "completed_at": _prefetch_state["completed_at"],
        "total": _prefetch_state["total"],
        "done": _prefetch_state["done"],
        "ok": _prefetch_state["ok"],
        "failed": _prefetch_state["failed"],
        "current": _prefetch_state["current"],
        "errors": _prefetch_state["errors"][-10:],
    }
