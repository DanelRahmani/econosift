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
