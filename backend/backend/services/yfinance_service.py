"""Thin, cached wrapper around yfinance."""
from __future__ import annotations

import logging
import re
import time
import pandas as pd
import yfinance as yf

from .. import cache
from ..cache import cached

log = logging.getLogger(__name__)

# Map common exchange suffixes to a sensible benchmark index.
_BENCHMARK_BY_SUFFIX = {
    "DE": "^GDAXI", "PA": "^FCHI", "AS": "^AEX", "MI": "FTSEMIB.MI",
    "MC": "^IBEX", "L": "^FTSE", "T": "^N225", "HK": "^HSI",
    "SS": "000001.SS", "SZ": "399001.SZ", "KS": "^KS11", "TO": "^GSPTSE",
    "AX": "^AXJO", "SW": "^SSMI", "ST": "^OMX", "BR": "^BFX", "SA": "^BVSP",
    "NS": "^NSEI", "BO": "^BSESN", "MX": "^MXX", "VI": "^ATX", "NZ": "^NZ50", "CO": "^OMXC25",
    "HE": "^OMXH25", "LS": "PSI20.LS", "IR": "^ISEQ", "TA": "^TA125.TA", "JO": "^J203.JO",
}
DEFAULT_BENCHMARK = "^GSPC"


def has_local_benchmark(ticker: str) -> bool:
    """True when a suffixed (non-US) ticker maps to its own local index rather than the S&P 500."""
    return "." in ticker and ticker.rsplit(".", 1)[-1].upper() in _BENCHMARK_BY_SUFFIX


def benchmark_for(ticker: str) -> str:
    if "." in ticker:
        suffix = ticker.rsplit(".", 1)[-1].upper()
        return _BENCHMARK_BY_SUFFIX.get(suffix, DEFAULT_BENCHMARK)
    return DEFAULT_BENCHMARK


# ---------------------------------------------------------------------------
# Daily prices, quotes and market caps come from econosift.db (Phase 67).
# The fetcher thread is the only code that downloads them; a page asking for a
# symbol that isn't stored yet queues its history and gets the rest now.
# ---------------------------------------------------------------------------

_CLOSE_HOUR_ET = 16


def _period_start(period: str) -> tuple[str | None, int | None]:
    """``(start ISO date, last N bars)`` for a yfinance period string."""
    today = pd.Timestamp.today().normalize()
    if period in ("max", "", None):
        return None, None
    if period == "ytd":
        return f"{today.year}-01-01", None
    m = re.fullmatch(r"(\d+)(d|wk|mo|y)", period)
    if not m:
        raise ValueError(f"unknown period {period!r}")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":  # yfinance: the last n trading days
        return (today - pd.Timedelta(days=2 * n + 7)).date().isoformat(), n
    offset = {"wk": pd.DateOffset(weeks=n), "mo": pd.DateOffset(months=n), "y": pd.DateOffset(years=n)}[unit]
    return (today - offset).date().isoformat(), None


def _close_epoch(day: pd.Timestamp) -> float:
    return pd.Timestamp(day.date()).replace(hour=_CLOSE_HOUR_ET).tz_localize("America/New_York").timestamp()


def _stored(symbols, period: str | None, fields: tuple[str, ...], start: str | None = None) -> dict[str, pd.DataFrame]:
    """Stored daily bars for ``symbols``; queues the ones not stored yet.

    The response is dated by the oldest last bar among the symbols returned,
    and a result missing queued symbols is not cached as fresh.
    """
    from .. import fetcher, store

    syms = list(dict.fromkeys(symbols))
    if fetcher.request_history(syms):
        cache.mark_incomplete()
    last_n = None
    if start is None and period is not None:
        start, last_n = _period_start(period)
    frames = store.frames(syms, fields, start=start)
    if last_n:
        frames = {f: df.tail(last_n) for f, df in frames.items()}
    lead = frames[fields[0]]
    if not lead.empty:
        last = lead.apply(lambda col: col.last_valid_index()).dropna()
        if len(last):
            cache.note_data_time(_close_epoch(min(last)))
    return frames


def get_close_frame(symbols: tuple[str, ...], period: str) -> pd.DataFrame:
    """Adjusted daily closes indexed by date; columns are the requested symbols that have data."""
    if not symbols:
        return pd.DataFrame()
    return _stored(symbols, period, ("adj_close",))["adj_close"].dropna(how="all")


def get_volume_frame(symbols: tuple[str, ...], period: str) -> pd.DataFrame:
    """Daily share volume indexed by date, like :func:`get_close_frame`."""
    if not symbols:
        return pd.DataFrame()
    return _stored(symbols, period, ("volume",))["volume"].dropna(how="all")


def get_daily_bars(ticker: str, start: str) -> pd.DataFrame:
    """One symbol's adjusted Open/High/Low/Close and Volume since ``start``."""
    f = _stored((ticker,), None, ("open", "high", "low", "close", "adj_close", "volume"), start=start)
    if f["close"].empty or ticker not in f["close"]:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    factor = f["adj_close"][ticker] / f["close"][ticker]
    return pd.DataFrame({
        "Open": f["open"][ticker] * factor, "High": f["high"][ticker] * factor,
        "Low": f["low"][ticker] * factor, "Close": f["adj_close"][ticker], "Volume": f["volume"][ticker],
    }).dropna(subset=["Close"])


# Share classes of one issuer. Yahoo reports the WHOLE-company cap at each class's price (live: GOOGL 4.19T and
# GOOG 4.15T), so summing both double-counts the issuer. First symbol = the class kept. Same-share-count pairs
# not listed here (e.g. FOX/FOXA, NWS/NWSA) are caught by the shares rule in _one_per_issuer.
_SHARE_CLASS_GROUPS = (("GOOGL", "GOOG"), ("BRK-B", "BRK-A"), ("FOXA", "FOX"), ("NWSA", "NWS"),
                       ("LEN", "LEN-B"), ("BF-B", "BF-A"), ("HEI", "HEI-A"))
_SAME_CAP_TOLERANCE = 0.25  # classes are one reported company cap only when their caps agree within 25 %


def _one_per_issuer(caps: dict[str, float], shares: dict[str, float]) -> dict[str, float]:
    """Keep one symbol per issuer when Yahoo reports the same company cap for several share classes.

    Issuer = a listed share-class group, or symbols with an identical share count. Classes whose caps differ by
    more than 25 % are genuine per-class caps and are all kept.
    """
    listed = {s: i for i, g in enumerate(_SHARE_CLASS_GROUPS) for s in g}
    groups: dict = {}
    for sym in caps:
        if sym in listed:
            key = ("g", listed[sym])
        elif shares.get(sym):
            key = ("s", shares[sym])
        else:
            key = ("x", sym)
        groups.setdefault(key, []).append(sym)
    drop: set[str] = set()
    for key, members in groups.items():
        if len(members) < 2:
            continue
        if key[0] == "g":
            order = {s: i for i, s in enumerate(_SHARE_CLASS_GROUPS[key[1]])}
            members = sorted(members, key=lambda m: order[m])
        else:
            members = sorted(members, key=lambda m: -caps[m])
        keep = members[0]
        for other in members[1:]:
            if abs(caps[other] - caps[keep]) <= _SAME_CAP_TOLERANCE * caps[keep]:
                drop.add(other)
    return {s: c for s, c in caps.items() if s not in drop}


def get_market_caps(symbols: tuple[str, ...], one_per_issuer: bool = True) -> dict[str, float]:
    """Market cap per symbol from the latest stored snapshot.

    Symbols without a positive cap in the snapshot are omitted. With
    ``one_per_issuer`` (default) a dual-class issuer appears once (see
    :func:`_one_per_issuer`); pass False for per-symbol caps.
    """
    from .. import store

    if not symbols:
        return {}
    quotes = store.quotes(symbols)
    caps = {s: float(q["market_cap"]) for s, q in quotes.items() if q.get("market_cap") and q["market_cap"] > 0}
    shares = {s: float(q["shares"]) for s, q in quotes.items() if q.get("shares") and q["shares"] > 0}
    if caps:
        cache.note_data_time(min(q["ts"] for s, q in quotes.items() if s in caps and q.get("ts")) or None)
    return _one_per_issuer(caps, shares) if one_per_issuer else caps


def _retry_yf(fn, max_retries=2, delay=1.0):
    """Call fn() with retries for transient yfinance errors (401, crumb, etc.)."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            msg = str(e).lower()
            if attempt < max_retries and ("401" in msg or "crumb" in msg or "too many" in msg):
                time.sleep(delay * (attempt + 1))
                continue
            if attempt == max_retries:
                raise
            return None  # non-retryable error, return None
    return None


def get_quote(ticker: str) -> dict:
    """Latest price and change: the 15-minute snapshot, else the last two stored daily bars.

    A symbol not stored yet is queued and returned with ``status: "pending"``.
    """
    from .. import fetcher, store

    row = store.quotes([ticker]).get(ticker)
    with store.connect() as conn:
        sec = conn.execute("SELECT name FROM security WHERE symbol = ?", (ticker,)).fetchone()
    name = (row or {}).get("name") or (sec[0] if sec and sec[0] else ticker)
    if row and row.get("price") is not None:
        if row.get("ts"):
            cache.note_data_time(float(row["ts"]))
        return {"symbol": ticker, "price": float(row["price"]),
                "changePercent": float(row["change_pct"]) if row.get("change_pct") is not None else None,
                "currency": row.get("currency"), "name": name}
    closes = _stored((ticker,), "1mo", ("close",))["close"]
    series = closes[ticker].dropna() if ticker in closes else pd.Series(dtype=float)
    if len(series) >= 1:
        price = float(series.iloc[-1])
        change = (price / float(series.iloc[-2]) - 1) * 100 if len(series) >= 2 and series.iloc[-2] else None
        return {"symbol": ticker, "price": price, "changePercent": change, "currency": None, "name": name}
    fetcher.request_history([ticker])
    return {"symbol": ticker, "price": None, "changePercent": None, "currency": None, "name": name,
            "status": "pending"}


def _info_failed(bundle: dict) -> bool:
    """True when Ticker.info failed or came back without a price.

    Such a bundle still carries statements and a few derived keys, so the
    default empty-result guard would cache it for an hour (and serve it stale
    for a day): JPM then showed no price and every model locked.
    """
    info = bundle.get("info") or {}
    if not (info.get("currentPrice") or info.get("regularMarketPrice")):
        return True
    # Under load Yahoo's profile/financials request can fail while the quote request succeeds:
    # an equity then has a price but no sector, industry, debt, cash or revenue.
    return info.get("quoteType") == "EQUITY" and not any(
        info.get(k) for k in ("sector", "industry", "totalRevenue"))


@cached("yf_info", skip_if=_info_failed)
def get_info(ticker: str) -> dict:
    """Company fundamentals bundle (``info`` + statements) read from the store (Phase 68).

    Built by :func:`fundamentals_store.bundle` from SEC facts, the quote
    snapshot and the stored Yahoo info; no Yahoo call. A symbol with no
    statements or no price yet (a ticker outside the universe) is queued for
    the fetcher and returned with ``status: "pending"`` until it is stored.
    """
    from .. import fetcher, fundamentals_store

    bundle = fundamentals_store.bundle(ticker)
    info = bundle["info"]
    if bundle["_sources"]["origin"] is None or not (info.get("currentPrice") or info.get("regularMarketPrice")):
        pending = fetcher.request_yahoo_info([ticker]) + fetcher.request_history([ticker])
        if pending:
            bundle["status"] = "pending"
    return bundle


# Lightweight keyword sentiment for headlines (no ML dependency).
_POS_WORDS = {
    "beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies",
    "gain", "gains", "jump", "jumps", "upgrade", "upgrades", "record", "growth",
    "profit", "profits", "strong", "rise", "rises", "boost", "outperform", "buy",
    "bullish", "high", "wins", "win", "approval", "approved", "raises", "top",
}
_NEG_WORDS = {
    "miss", "misses", "plunge", "plunges", "fall", "falls", "drop", "drops",
    "slump", "slumps", "downgrade", "downgrades", "loss", "losses", "weak",
    "cut", "cuts", "decline", "declines", "lawsuit", "probe", "warning", "warns",
    "bearish", "low", "fraud", "recall", "sell", "slash", "slashes", "fears",
}


def _score_sentiment(title: str) -> str:
    words = {w.strip(".,!?:;\"'()").lower() for w in title.split()}
    pos = len(words & _POS_WORDS)
    neg = len(words & _NEG_WORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


@cached("yf_news")
def get_news(ticker: str) -> dict:
    """Recent headlines for a ticker with keyword-based sentiment scoring."""
    t = yf.Ticker(ticker)
    items: list[dict] = []
    try:
        raw = t.news or []
    except Exception:
        raw = []

    for n in raw[:12]:
        # yfinance has two shapes: flat (legacy) and nested under "content".
        content = n.get("content") if isinstance(n, dict) else None
        if isinstance(content, dict):
            title = content.get("title") or ""
            pub = (content.get("provider") or {}).get("displayName") or ""
            url = ((content.get("canonicalUrl") or {}).get("url")
                   or (content.get("clickThroughUrl") or {}).get("url") or "")
            ts = content.get("pubDate") or content.get("displayTime") or ""
            published = str(ts)[:10] if ts else None
        else:
            title = n.get("title") or ""
            pub = n.get("publisher") or ""
            url = n.get("link") or ""
            epoch = n.get("providerPublishTime")
            published = (pd.to_datetime(epoch, unit="s").strftime("%Y-%m-%d")
                         if epoch else None)

        if not title:
            continue
        items.append({
            "title": title,
            "publisher": pub,
            "url": url,
            "published": published,
            "sentiment": _score_sentiment(title),
        })

    return {"ticker": ticker, "news": items}


@cached("yf_events")
def get_events(ticker: str) -> dict:
    """Upcoming earnings date, recent dividends, and stock splits for a ticker."""
    t = yf.Ticker(ticker)
    out: dict = {"ticker": ticker, "earnings": None, "dividends": [], "splits": []}

    try:
        cal = t.calendar
        ed = None
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if isinstance(ed, (list, tuple)) and ed:
                ed = ed[0]
        elif cal is not None and hasattr(cal, "loc") and "Earnings Date" in getattr(cal, "index", []):
            ed = cal.loc["Earnings Date"].iloc[0]
        if ed is not None:
            out["earnings"] = pd.to_datetime(str(ed)).strftime("%Y-%m-%d")
    except Exception:
        pass

    try:
        divs = t.dividends
        if divs is not None and len(divs):
            divs = divs.tail(12)
            out["dividends"] = [
                {"date": pd.to_datetime(d).strftime("%Y-%m-%d"), "amount": round(float(v), 4)}
                for d, v in divs.items()
            ]
    except Exception:
        pass

    try:
        splits = t.splits
        if splits is not None and len(splits):
            splits = splits.tail(8)
            out["splits"] = [
                {"date": pd.to_datetime(d).strftime("%Y-%m-%d"), "ratio": round(float(v), 4)}
                for d, v in splits.items()
            ]
    except Exception:
        pass

    return out


def _safe(d, key):
    try:
        return d[key]
    except Exception:
        try:
            return getattr(d, key)
        except Exception:
            return None


def get_ohlc_frame(symbols: tuple[str, ...], period: str, adjust: bool = True) -> dict[str, pd.DataFrame]:
    """Return {symbol: DataFrame[Open,High,Low,Close]} for the requested symbols.

    ``adjust`` scales Open/High/Low/Close by the same split/dividend factor
    (adjusted ÷ raw close) so Garman-Klass high/low/open/close ratios remain
    valid. ``adjust=False`` returns prices as traded (split-adjusted only),
    which is what published breadth counts — advancers, 52-week highs/lows —
    are based on.
    """
    if not symbols:
        return {}
    wide = get_ohlc_wide(symbols, period, adjust)
    result: dict[str, pd.DataFrame] = {}
    for sym in wide["Close"].columns:
        df = pd.DataFrame({c: wide[c][sym] for c in ("Open", "High", "Low", "Close")}).dropna(how="any")
        if len(df):
            result[sym] = df
    return result


def get_ohlc_wide(symbols: tuple[str, ...], period: str, adjust: bool = True) -> dict[str, pd.DataFrame]:
    """Like :func:`get_ohlc_frame` but as ``{"Open"|"High"|"Low"|"Close": date x symbol frame}``,
    for index-wide readers that would otherwise split 500 symbols apart and join them back.
    A bar missing any of the four prices is NaN in all four."""
    f = _stored(symbols, period, ("open", "high", "low", "close", "adj_close"))
    factor = f["adj_close"] / f["close"] if adjust else 1.0
    out = {c.capitalize(): f[c] * factor for c in ("open", "high", "low", "close")}
    valid = out["Open"].notna() & out["High"].notna() & out["Low"].notna() & out["Close"].notna()
    return {c: df.where(valid) for c, df in out.items()}
