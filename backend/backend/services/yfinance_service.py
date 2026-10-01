"""Thin, cached wrapper around yfinance."""
from __future__ import annotations

import logging
import time
import numpy as np
import pandas as pd
import yfinance as yf

from ..cache import cached

log = logging.getLogger(__name__)

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
        def _call():
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
                return float(mcap)
            return None
        try:
            val = _retry_yf(_call, max_retries=1, delay=1.5)
            if val is not None:
                return (sym, val)
        except Exception:
            pass
        return None

    import time as _time
    result: dict[str, float] = {}
    BATCH_SIZE = 10
    syms_list = list(symbols)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i in range(0, len(syms_list), BATCH_SIZE):
            batch = syms_list[i:i + BATCH_SIZE]
            # Progressive backoff: 0.3s base, up to 2s for later batches
            delay = min(0.3 + (i / BATCH_SIZE) * 0.05, 2.0)
            if i > 0:
                _time.sleep(delay)
            futures = {ex.submit(_fetch_one, s): s for s in batch}
            for fut in as_completed(futures):
                try:
                    pair = fut.result()
                    if pair is not None:
                        result[pair[0]] = pair[1]
                except Exception:
                    pass
    return result


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


@cached("yf_quote")
def get_quote(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = {}
    try:
        info = _retry_yf(lambda: t.fast_info or {})
    except Exception:
        info = {}
    price = _safe(info, "last_price") or _safe(info, "lastPrice")
    prev = _safe(info, "previous_close") or _safe(info, "previousClose")
    currency = _safe(info, "currency") or "USD"

    name = ticker
    try:
        meta = _retry_yf(lambda: t.get_info())
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
    """Full .info dict plus financial statements for ratio analysis."""
    t = yf.Ticker(ticker)
    out: dict = {"ticker": ticker, "info": {}}
    for _ in range(2):  # one retry: Yahoo intermittently fails info calls under load
        try:
            out["info"] = t.get_info() or {}
        except Exception:
            log.warning("Ticker.info failed for %s", ticker, exc_info=True)
            out["info"] = {}
        if not _info_failed(out):
            break
    info = out["info"]

    # ── Store raw DataFrames for multi-period consumers (Piotroski, Beneish) ──
    fin_df = _safe_stmt(t, "financials")
    bs_df = _safe_stmt(t, "balance_sheet")
    cf_df = _safe_stmt(t, "cashflow")
    out["financials"] = _df_to_dict(fin_df)
    out["balance_sheet"] = _df_to_dict(bs_df)
    out["cashflow"] = _df_to_dict(cf_df)
    out["financials_df"] = fin_df if fin_df is not None and not fin_df.empty else None
    out["balance_sheet_df"] = bs_df if bs_df is not None and not bs_df.empty else None
    out["cashflow_df"] = cf_df if cf_df is not None and not cf_df.empty else None

    # ── Fix 1: Inject missing keys from alternative yfinance accessors ──
    price = info.get("currentPrice") or info.get("regularMarketPrice")

    # trailingEps: compute from trailingPE and price
    if "trailingEps" not in info or info["trailingEps"] is None:
        pe = info.get("trailingPE")
        if pe and price and pe > 0:
            info["trailingEps"] = price / pe

    # forwardEps: try earnings_estimate DataFrame, fallback to price/forwardPE
    if "forwardEps" not in info or info["forwardEps"] is None:
        try:
            ee = t.earnings_estimate
            if ee is not None and not ee.empty and "0y" in ee.index:
                row = ee.loc["0y"]
                if "avg" in ee.columns:
                    info["forwardEps"] = float(row["avg"])
        except Exception:
            pass
        if "forwardEps" not in info or info["forwardEps"] is None:
            fpe = info.get("forwardPE")
            if fpe and price and fpe > 0:
                info["forwardEps"] = price / fpe

    # freeCashflow: from cashflow statement dict
    cf_dict = out.get("cashflow", {})
    if "freeCashflow" not in info or info["freeCashflow"] is None:
        fcf = cf_dict.get("Free Cash Flow")
        if fcf is not None:
            info["freeCashflow"] = fcf

    # operatingCashflow: from cashflow statement dict
    if "operatingCashflow" not in info or info["operatingCashflow"] is None:
        ocf = cf_dict.get("Operating Cash Flow") or cf_dict.get("Total Cash From Operating Activities")
        if ocf is not None:
            info["operatingCashflow"] = ocf

    # sector / industry: yfinance populates sectorKey/industryKey alternate keys
    if "sector" not in info or info["sector"] is None:
        sector = info.get("sectorKey") or info.get("sectorDisp")
        if sector:
            info["sector"] = sector
    if "industry" not in info or info["industry"] is None:
        industry = info.get("industryKey") or info.get("industryDisp")
        if industry:
            info["industry"] = industry

    # beta: try fast_info first, fallback to 2Y daily returns vs benchmark
    if "beta" not in info or info["beta"] is None:
        try:
            fi_beta = t.fast_info.get("beta") if hasattr(t, "fast_info") else None
            if fi_beta:
                info["beta"] = float(fi_beta)
        except Exception:
            pass
        if "beta" not in info or info["beta"] is None:
            try:
                bench = benchmark_for(ticker)
                frame = yf.download(
                    [ticker, bench], period="2y", auto_adjust=True,
                    progress=False, threads=False,
                )
                if frame is not None and not frame.empty:
                    if isinstance(frame.columns, pd.MultiIndex):
                        close = frame["Close"]
                    else:
                        close = frame
                    if ticker in close.columns and bench in close.columns:
                        r = np.log(close[ticker] / close[ticker].shift(1)).dropna()
                        br = np.log(close[bench] / close[bench].shift(1)).dropna()
                        joined = pd.concat([r, br], axis=1, join="inner").dropna()
                        if len(joined) > 2:
                            var_b = joined.iloc[:, 1].var(ddof=1)
                            if var_b and var_b > 0:
                                info["beta"] = joined.iloc[:, 0].cov(joined.iloc[:, 1]) / var_b
            except Exception:
                pass

    # ── Fix 6: Shares precision guard for large-cap tickers ──
    shares_raw = info.get("sharesOutstanding")
    if shares_raw is not None:
        try:
            shares_val = float(shares_raw)
        except (TypeError, ValueError):
            shares_val = None
        mcap = info.get("marketCap")
        if shares_val is not None and mcap is not None and shares_val < 1_000_000_000 and mcap > 100_000_000_000:
            # Shares look too low for a large-cap — try fast_info fallback
            try:
                fi_shares = t.fast_info.get("shares_outstanding")
                if fi_shares and float(fi_shares) > 1_000_000_000:
                    info["sharesOutstanding"] = float(fi_shares)
            except Exception:
                pass

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


@cached("yf_ohlc")
def get_ohlc_frame(symbols: tuple[str, ...], period: str, adjust: bool = True) -> dict[str, pd.DataFrame]:
    """Return {symbol: DataFrame[Open,High,Low,Close]} for the requested symbols.

    auto_adjust scales Open/High/Low/Close by the same split/dividend factor so
    Garman-Klass high/low/open/close ratios remain valid after adjustment.
    ``adjust=False`` returns prices as traded (split-adjusted only), which is
    what published breadth counts — advancers, 52-week highs/lows — are based on.
    """
    if not symbols:
        return {}
    raw = yf.download(
        list(symbols),
        period=period,
        interval="1d",
        auto_adjust=adjust,
        progress=False,
        threads=True,
    )
    if raw is None or len(raw) == 0:
        return {}

    _OHLC_FIELDS = {"Open", "High", "Low", "Close"}

    if isinstance(raw.columns, pd.MultiIndex):
        # Detect which level holds the OHLC field names (auto_adjust can flip order).
        field_level = 0 if _OHLC_FIELDS & set(raw.columns.get_level_values(0)) else 1
        tick_level = 1 - field_level
        result: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            try:
                df = raw.xs(sym, axis=1, level=tick_level)[["Open", "High", "Low", "Close"]].dropna(how="any")
                if len(df) > 0:
                    result[sym] = df
            except (KeyError, Exception):
                pass
        return result
    else:
        # Single-ticker: flat frame with OHLC columns.
        try:
            df = raw[["Open", "High", "Low", "Close"]].dropna(how="any")
            if len(df) > 0:
                return {symbols[0]: df}
        except (KeyError, Exception):
            pass
        return {}
