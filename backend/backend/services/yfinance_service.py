"""Thin, cached wrapper around yfinance."""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from ..cache import cached

# Map common exchange suffixes to a sensible benchmark index.
_BENCHMARK_BY_SUFFIX = {
    "DE": "^GDAXI", "PA": "^FCHI", "AS": "^AEX", "MI": "FTSEMIB.MI",
    "MC": "^IBEX", "L": "^FTSE", "T": "^N225", "HK": "^HSI",
    "SS": "000001.SS", "SZ": "399001.SZ", "KS": "^KS11", "TO": "^GSPTSE",
    "AX": "^AXJO", "SW": "^SSMI", "ST": "^OMX", "BR": "^BVSP",
}
DEFAULT_BENCHMARK = "^GSPC"


def benchmark_for(ticker: str) -> str:
    if "." in ticker:
        suffix = ticker.rsplit(".", 1)[-1].upper()
        return _BENCHMARK_BY_SUFFIX.get(suffix, DEFAULT_BENCHMARK)
    return DEFAULT_BENCHMARK


@cached("yf_close")
def get_close_frame(symbols: tuple[str, ...], period: str) -> pd.DataFrame:
    """Return a DataFrame of adjusted close prices indexed by date.

    Columns are the requested symbols (those that returned data).
    """
    if not symbols:
        return pd.DataFrame()
    raw = yf.download(
        list(symbols),
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if raw is None or len(raw) == 0:
        return pd.DataFrame()

    # Normalise to a flat Close-price frame.
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw["Close"].copy()
        else:
            close = raw.xs("Close", axis=1, level=-1).copy()
    else:
        # Single ticker: pick Close column.
        col = "Close" if "Close" in raw.columns else raw.columns[0]
        close = raw[[col]].copy()
        close.columns = [symbols[0]]

    close = close.dropna(how="all")
    return close


@cached("yf_volume")
def get_volume_frame(symbols: tuple[str, ...], period: str) -> pd.DataFrame:
    """Return a DataFrame of daily share volume indexed by date.

    Mirrors :func:`get_close_frame` but pulls the Volume field — used for
    unusual-volume screening over a large constituent universe.
    """
    if not symbols:
        return pd.DataFrame()
    raw = yf.download(
        list(symbols),
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if raw is None or len(raw) == 0:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        if "Volume" in raw.columns.get_level_values(0):
            vol = raw["Volume"].copy()
        else:
            vol = raw.xs("Volume", axis=1, level=-1).copy()
    else:
        col = "Volume" if "Volume" in raw.columns else raw.columns[-1]
        vol = raw[[col]].copy()
        vol.columns = [symbols[0]]

    return vol.dropna(how="all")


@cached("yf_mcap")
def get_market_caps(symbols: tuple[str, ...]) -> dict[str, float]:
    """Fetch market cap for each symbol via ``fast_info``, in parallel threads.

    This is the first threaded-batch fetch in the service — uses
    ``ThreadPoolExecutor`` (max 10 workers) so the full constituent universe
    (~500 tickers) completes in a few seconds rather than serially.  Any symbol
    that fails or has no positive finite cap is silently omitted.  Never raises.

    Returns ``{symbol: market_cap_float}`` for symbols with a valid cap only.
    """
    import math
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not symbols:
        return {}

    def _fetch_one(sym: str) -> tuple[str, float] | None:
        try:
            fi = yf.Ticker(sym).fast_info
            mcap = None
            try:
                mcap = fi["market_cap"]
            except Exception:
                pass
            if mcap is None:
                try:
                    mcap = fi["marketCap"]
                except Exception:
                    pass
            if mcap is None:
                try:
                    mcap = getattr(fi, "market_cap", None)
                except Exception:
                    pass
            if mcap is not None and not math.isnan(float(mcap)) and float(mcap) > 0:
                return (sym, float(mcap))
        except Exception:
            pass
        return None

    result: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_one, s): s for s in symbols}
        for fut in as_completed(futures):
            try:
                pair = fut.result()
                if pair is not None:
                    result[pair[0]] = pair[1]
            except Exception:
                pass
    return result


@cached("yf_quote")
def get_quote(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.fast_info or {}
    except Exception:
        info = {}
    price = _safe(info, "last_price") or _safe(info, "lastPrice")
    prev = _safe(info, "previous_close") or _safe(info, "previousClose")
    currency = _safe(info, "currency") or "USD"

    name = ticker
    try:
        meta = t.get_info()
    except Exception:
        meta = {}
    if meta:
        name = meta.get("shortName") or meta.get("longName") or ticker
        if price is None:
            price = meta.get("currentPrice") or meta.get("regularMarketPrice")
        if prev is None:
            prev = meta.get("previousClose") or meta.get("regularMarketPreviousClose")
        currency = meta.get("currency") or currency

    change_pct = None
    if price is not None and prev:
        try:
            change_pct = (price - prev) / prev * 100.0
        except Exception:
            change_pct = None

    return {
        "symbol": ticker,
        "price": float(price) if price is not None else None,
        "changePercent": float(change_pct) if change_pct is not None else None,
        "currency": currency,
        "name": name,
    }


@cached("yf_info")
def get_info(ticker: str) -> dict:
    """Full .info dict plus financial statements for ratio analysis."""
    t = yf.Ticker(ticker)
    out: dict = {"ticker": ticker}
    try:
        out["info"] = t.get_info() or {}
    except Exception:
        out["info"] = {}
    out["financials"] = _df_to_dict(_safe_stmt(t, "financials"))
    out["balance_sheet"] = _df_to_dict(_safe_stmt(t, "balance_sheet"))
    out["cashflow"] = _df_to_dict(_safe_stmt(t, "cashflow"))
    return out


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


def _safe_stmt(t, name: str):
    try:
        df = getattr(t, name)
        return df
    except Exception:
        return None


def _df_to_dict(df) -> dict:
    if df is None or not hasattr(df, "empty") or df.empty:
        return {}
    # Most-recent column first; keep row label -> latest value.
    out: dict = {}
    try:
        latest = df.columns[0]
        for idx, val in df[latest].items():
            try:
                out[str(idx)] = None if pd.isna(val) else float(val)
            except Exception:
                continue
    except Exception:
        return {}
    return out


def _safe(d, key):
    try:
        return d[key]
    except Exception:
        try:
            return getattr(d, key)
        except Exception:
            return None
