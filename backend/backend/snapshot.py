"""Bulk quote snapshot of the tracked universe (Phase 66, plan §2.2 / §8.1).

One `yf.screen` pass (5 calls of 250, sorted by market cap) covers every
S&P 500 + NDX + Dow member. A member the screen misses is filled with a
throttled chart download; if the screen itself fails, the whole universe is.
Runs on the fetcher thread every 15 min in US market hours and twice after
the close, when it also writes today's bar into price_daily.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from yfinance.exceptions import YFRateLimitError

from . import store

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
EXCHANGES = ["NMS", "NYQ", "NGM", "NCM", "ASE", "BTS", "PCX"]
CAP_FLOOR = 4e9         # smallest member was $9.1B in 65.0
PAGE = 250
MAX_PAGES = 10
FILL_CHUNK = 50
INTRADAY_KEEP = timedelta(days=10)
SPLIT_TOLERANCE = 0.02  # previous close vs stored close; dividends don't move raw closes

# quote_latest column -> Yahoo screen field. Any field may be missing.
FIELDS = {
    "price": "regularMarketPrice", "change": "regularMarketChange",
    "change_pct": "regularMarketChangePercent", "open": "regularMarketOpen",
    "high": "regularMarketDayHigh", "low": "regularMarketDayLow",
    "prev_close": "regularMarketPreviousClose", "volume": "regularMarketVolume",
    "market_cap": "marketCap", "shares": "sharesOutstanding", "pe": "trailingPE",
    "forward_pe": "forwardPE", "eps_ttm": "epsTrailingTwelveMonths", "pb": "priceToBook",
    "div_yield": "dividendYield", "high52": "fiftyTwoWeekHigh", "low52": "fiftyTwoWeekLow",
    "avg_vol_3m": "averageDailyVolume3Month", "avg_vol_10d": "averageDailyVolume10Day",
}


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def screen(universe: set[str]) -> dict[str, dict]:
    """Screen pages until every universe member is covered or results run out."""
    import yfinance as yf
    from yfinance import EquityQuery as Q

    query = Q("and", [Q("is-in", ["exchange", *EXCHANGES]), Q("gt", ["intradaymarketcap", CAP_FLOOR])])
    got: dict[str, dict] = {}
    for page in range(MAX_PAGES):
        res = yf.screen(query, offset=page * PAGE, size=PAGE, sortField="intradaymarketcap",
                        sortAsc=False) or {}
        quotes = res.get("quotes") or []
        for q in quotes:
            if q.get("symbol") in universe:
                got[q["symbol"]] = q
        if not quotes or universe <= set(got) or (page + 1) * PAGE >= (res.get("total") or 0):
            break
    return got


def _row_from_screen(q: dict) -> dict:
    row = {col: _num(q.get(key)) for col, key in FIELDS.items()}
    ts = q.get("regularMarketTime")
    row.update(symbol=q["symbol"], ts=int(ts) if _num(ts) is not None else None,
               market_state=q.get("marketState"), source="yahoo_screen")
    return row


def download_quotes(symbols: list[str]) -> list[dict]:
    """Today's 15-minute bars for ``symbols`` in chunks, reduced to quote rows (no prev close)."""
    import yfinance as yf

    rows: list[dict] = []
    for i in range(0, len(symbols), FILL_CHUNK):
        chunk = symbols[i:i + FILL_CHUNK]
        df = yf.download(chunk, period="1d", interval="15m", threads=False, progress=False,
                         group_by="ticker", auto_adjust=False)
        if df is None or df.empty:
            continue
        for sym in chunk:
            try:
                bars = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
            except KeyError:
                continue
            bars = bars.dropna(subset=["Close"])
            if bars.empty:
                continue
            row = {col: None for col in FIELDS}
            row.update(symbol=sym, price=_num(bars["Close"].iloc[-1]), open=_num(bars["Open"].iloc[0]),
                       high=_num(bars["High"].max()), low=_num(bars["Low"].min()),
                       volume=_num(bars["Volume"].sum()), ts=int(bars.index[-1].timestamp()),
                       market_state=None, source="yahoo_chart")
            rows.append(row)
    return rows


def _check_splits(rows: list[dict]) -> list[str]:
    """Symbols whose previous close disagrees with the stored one (a split, or a gap)."""
    from . import fetcher

    with_prev = {r["symbol"]: r for r in rows if r.get("prev_close") and r.get("ts")}
    if not with_prev:
        return []
    out = []
    with store.connect() as conn:
        for sym, r in with_prev.items():
            day = datetime.fromtimestamp(r["ts"], ET).date().isoformat()
            stored = conn.execute(
                "SELECT close FROM price_daily WHERE symbol = ? AND date < ? ORDER BY date DESC LIMIT 1",
                (sym, day)).fetchone()
            if stored and stored[0] and abs(r["prev_close"] / stored[0] - 1) > SPLIT_TOLERANCE:
                out.append(sym)
    for sym in out:
        fetcher.enqueue("history", sym, fetcher.PRIORITY_REFETCH)
    return out


def run(key: str) -> int:
    """``key`` is 'intraday' or 'close' (also writes today's daily bar)."""
    with store.connect() as conn:
        universe = {r[0] for r in conn.execute("SELECT symbol FROM security")}
    if not universe:
        raise RuntimeError("no universe yet")

    try:
        rows = [_row_from_screen(q) for q in screen(universe).values()]
    except YFRateLimitError:
        raise
    except Exception as exc:  # screen broke: fall back to chart downloads for everyone
        logger.warning("snapshot: screen failed (%s); falling back to chart downloads", exc)
        rows = []
    missing = sorted(universe - {r["symbol"] for r in rows})
    if missing:
        rows += download_quotes(missing)
    rows = [r for r in rows if r.get("price") is not None]
    if not rows:
        raise RuntimeError("snapshot returned no quotes")  # never store an empty result

    fetched = _now()
    for r in rows:
        r["fetched_at"] = fetched
    store.upsert("quote_latest", rows, ("symbol",))
    store.upsert("quote_intraday", [dict(symbol=r["symbol"], ts=r["ts"], price=r["price"],
                                         volume=r["volume"]) for r in rows if r.get("ts")],
                 ("symbol", "ts"))
    cutoff = int((datetime.now(timezone.utc) - INTRADAY_KEEP).timestamp())
    with store.connect() as conn:
        conn.execute("DELETE FROM quote_intraday WHERE ts < ?", (cutoff,))
    store.upsert("security", [dict(symbol=r["symbol"], shares_outstanding=r["shares"])
                              for r in rows if r.get("shares")], ("symbol",))

    refetch = _check_splits(rows)
    if refetch:
        logger.info("snapshot: previous close disagrees with stored history for %s; re-fetching", refetch)

    if key == "close":
        bars = [dict(symbol=r["symbol"], date=datetime.fromtimestamp(r["ts"], ET).date().isoformat(),
                     open=r["open"], high=r["high"], low=r["low"], close=r["price"],
                     adj_close=r["price"], volume=r["volume"])
                for r in rows if r.get("ts") and r["symbol"] not in refetch]
        store.upsert("price_daily", bars, ("symbol", "date"))
    return len(rows)


def in_market_hours(now: datetime | None = None) -> bool:
    t = (now or datetime.now(timezone.utc)).astimezone(ET)
    return t.weekday() < 5 and (9, 30) <= (t.hour, t.minute) <= (16, 0)
