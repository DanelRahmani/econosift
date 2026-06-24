"""Phase 5 Screener Overhaul — refresh pipeline, preset definitions, and query engine.

Architecture
------------
- ``refresh_universe(index)`` — blocking call that fetches yfinance data for all
  constituents and persists to SQLite via screener_cache.  Guards against
  concurrent refreshes of the same index via per-index locks.
- ``query(...)`` — reads from the SQLite cache, applies presets/filters/sort,
  returns the universe response dict.  If the cache is empty or stale it kicks a
  background refresh and returns stale data immediately (non-blocking).
- ``warm_all()`` — called at startup in a daemon thread; refreshes each index if
  stale, sequentially.

dividendYield normalisation note
---------------------------------
yfinance ``info["dividendYield"]`` returns a decimal fraction (e.g. 0.0156 for
1.56%) in recent versions, matching how ``metrics.compute_ratios`` returns it.
All preset comparisons treat it as a fraction (high_dividend threshold = 0.03 =
3%).  We store and return it as a fraction consistently.
"""
from __future__ import annotations

import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from . import constituents as _constituents
from . import yfinance_service as yfs
from . import screener_cache
from .metrics import altman_z

# ---------------------------------------------------------------------------
# Per-index refresh lock (prevents concurrent double-refresh of same index)
# ---------------------------------------------------------------------------

_refresh_locks: dict[str, threading.Lock] = {
    "dow":   threading.Lock(),
    "ndx":   threading.Lock(),
    "sp500": threading.Lock(),
}


# ---------------------------------------------------------------------------
# PRESETS
# ---------------------------------------------------------------------------

PRESETS: list[dict] = [
    {"id": "top_gainers",          "label": "Top Gainers",         "description": "Highest day % gain",                          "category": "momentum"},
    {"id": "top_losers",           "label": "Top Losers",          "description": "Largest day % loss",                          "category": "momentum"},
    {"id": "high_52w",             "label": "Near 52-Week High",   "description": "Within 5% of 52-week high",                   "category": "momentum"},
    {"id": "low_52w",              "label": "Near 52-Week Low",    "description": "Within 5% of 52-week low (price ≤ low×1.05)", "category": "momentum"},
    {"id": "above_sma200",         "label": "Above 200-Day SMA",   "description": "Price above 200-day moving average",          "category": "technical"},
    {"id": "below_sma200",         "label": "Below 200-Day SMA",   "description": "Price below 200-day moving average",          "category": "technical"},
    {"id": "golden_cross",         "label": "Golden Cross",        "description": "50-day SMA crossed above 200-day recently",   "category": "technical"},
    {"id": "death_cross",          "label": "Death Cross",         "description": "50-day SMA crossed below 200-day recently",   "category": "technical"},
    {"id": "unusual_volume",       "label": "Unusual Volume",      "description": "Volume > 2× 20-day average",                  "category": "volume"},
    {"id": "overbought",           "label": "Overbought (RSI>70)", "description": "14-day RSI above 70",                         "category": "technical"},
    {"id": "oversold",             "label": "Oversold (RSI<30)",   "description": "14-day RSI below 30",                         "category": "technical"},
    {"id": "high_beta",            "label": "High Beta (>1.5)",    "description": "Beta greater than 1.5 vs market",             "category": "risk"},
    {"id": "undervalued",          "label": "Undervalued",         "description": "P/E < 15 and P/B < 1.5",                      "category": "value"},
    {"id": "high_dividend",        "label": "High Dividend Yield", "description": "Dividend yield > 3%",                         "category": "income"},
    {"id": "high_roic",            "label": "High ROIC (>15%)",    "description": "Return on invested capital > 15%",            "category": "quality"},
    {"id": "quality_growth",       "label": "Quality Growth",      "description": "ROE>15%, revenue growth>10%, net margin>10%", "category": "quality"},
    {"id": "deep_value",           "label": "Deep Value",          "description": "P/B < 1 and P/E < 10",                        "category": "value"},
    {"id": "high_short_interest",  "label": "High Short Interest", "description": "Short float > 20%",                           "category": "sentiment"},
]

_PRESET_IDS = {p["id"] for p in PRESETS}


def _passes_preset(row: dict, preset_id: str) -> bool:
    """Return True if the row satisfies the given preset predicate.

    Rows missing required fields (None values) are excluded (return False).
    """
    def _v(key: str) -> float | None:
        return row.get(key)

    p = preset_id

    if p == "top_gainers":
        v = _v("changePercent"); return v is not None and v > 0
    if p == "top_losers":
        v = _v("changePercent"); return v is not None and v < 0
    if p == "high_52w":
        # within 5% of 52w high: price >= high52 * 0.95
        price, high = _v("price"), _v("high52")
        return price is not None and high is not None and high > 0 and price >= high * 0.95
    if p == "low_52w":
        # near 52w low: price <= low52 * 1.05
        price, low = _v("price"), _v("low52")
        return price is not None and low is not None and low > 0 and price <= low * 1.05
    if p == "above_sma200":
        v = _v("aboveSma200"); return v is True
    if p == "below_sma200":
        v = _v("aboveSma200"); return v is False
    if p == "golden_cross":
        v = _v("goldenCross"); return v is True
    if p == "death_cross":
        v = _v("goldenCross"); return v is False
    if p == "unusual_volume":
        v = _v("volumeRatio"); return v is not None and v > 2.0
    if p == "overbought":
        v = _v("rsi14"); return v is not None and v > 70.0
    if p == "oversold":
        v = _v("rsi14"); return v is not None and v < 30.0
    if p == "high_beta":
        v = _v("beta"); return v is not None and v > 1.5
    if p == "undervalued":
        pe, pb = _v("pe"), _v("pb")
        return pe is not None and pb is not None and pe < 15 and pb < 1.5
    if p == "high_dividend":
        # dividendYield stored as fraction; 0.03 = 3%
        v = _v("dividendYield"); return v is not None and v > 0.03
    if p == "high_roic":
        v = _v("roic"); return v is not None and v > 0.15
    if p == "quality_growth":
        roe, rg, nm = _v("roe"), _v("revenueGrowth"), _v("netMargin")
        return (roe is not None and rg is not None and nm is not None
                and roe > 0.15 and rg > 0.10 and nm > 0.10)
    if p == "deep_value":
        pb, pe = _v("pb"), _v("pe")
        return pb is not None and pe is not None and pb < 1.0 and pe < 10.0
    if p == "high_short_interest":
        v = _v("shortFloat"); return v is not None and v > 0.20

    return False


def apply_presets(rows: list[dict], preset_ids: list[str]) -> list[dict]:
    """Filter rows to those that pass ALL of the given presets (AND logic)."""
    if not preset_ids:
        return rows
    return [r for r in rows if all(_passes_preset(r, pid) for pid in preset_ids)]


def apply_filters(rows: list[dict], filters: list[dict]) -> list[dict]:
    """Filter rows by a list of {"field", "op", "value"} dicts.

    Supported ops: "lt", "gt", "eq".  Rows where the field is None are excluded.
    """
    if not filters:
        return rows

    def _passes(row: dict) -> bool:
        for f in filters:
            field, op, target = f["field"], f["op"], f["value"]
            v = row.get(field)
            if v is None:
                return False
            try:
                v = float(v)
                target = float(target)
            except (TypeError, ValueError):
                return False
            if op == "lt" and not (v < target):
                return False
            if op == "gt" and not (v > target):
                return False
            if op == "eq" and not (v == target):
                return False
        return True

    return [r for r in rows if _passes(r)]


def sort_rows(rows: list[dict], sort_key: str, direction: str) -> list[dict]:
    """Sort rows by sort_key; nulls always last regardless of direction."""
    reverse = direction != "asc"

    def _key(row: dict):
        v = row.get(sort_key)
        if v is None:
            # Nulls last: large sentinel for desc, small for asc
            return (1, 0)
        return (0, -v if reverse else v)

    return sorted(rows, key=_key)


# ---------------------------------------------------------------------------
# Refresh pipeline — per-ticker fetch
# ---------------------------------------------------------------------------

def _clean(v: Any) -> float | None:
    """Convert to float, returning None for NaN/Inf/None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _fetch_ticker_fundamentals(sym: str) -> dict:
    """Fetch full info bundle for one ticker and return a partial screener row.

    Never raises.  Missing fields default to None.
    """
    try:
        bundle = yfs.get_info(sym)
        info = bundle.get("info", {}) or {}
        bs = bundle.get("balance_sheet", {}) or {}
        fin = bundle.get("financials", {}) or {}
        cf = bundle.get("cashflow", {}) or {}

        def _i(key: str) -> float | None:
            return _clean(info.get(key))

        def _g(d: dict, *keys: str) -> float | None:
            for k in keys:
                v = d.get(k)
                if v is not None:
                    return _clean(v)
            return None

        mcap = _i("marketCap")
        enterprise_value = _i("enterpriseValue")
        fcf = _i("freeCashflow") or _g(cf, "Free Cash Flow")
        shares = _i("sharesOutstanding")

        # ROIC = NOPAT / Invested Capital  (best-effort from statements)
        # NOPAT ≈ EBIT * (1 - tax_rate); Invested Capital ≈ Total Equity + Total Debt
        roic: float | None = None
        try:
            ebit = _g(fin, "EBIT", "Operating Income")
            tax_prov = _g(fin, "Tax Provision")
            pretax_inc = _g(fin, "Pretax Income")
            equity = _g(bs, "Stockholders Equity", "Common Stock Equity") or _i("totalStockholderEquity")
            total_debt = _g(bs, "Total Debt") or _i("totalDebt")
            if ebit and equity and total_debt is not None:
                tax_rate = (tax_prov / pretax_inc) if (tax_prov and pretax_inc and pretax_inc != 0) else 0.21
                nopat = ebit * (1 - tax_rate)
                inv_cap = equity + total_debt
                if inv_cap and inv_cap != 0:
                    roic = _clean(nopat / inv_cap)
        except Exception:
            roic = None

        # evFcf
        ev_fcf: float | None = None
        if enterprise_value and fcf and fcf != 0:
            ev_fcf = _clean(enterprise_value / fcf)

        # fcfYield
        fcf_yield: float | None = None
        if fcf and mcap and mcap > 0:
            fcf_yield = _clean(fcf / mcap)

        # Altman Z
        az = altman_z(info, bs, fin)

        return {
            "symbol": sym,
            "name": info.get("shortName") or info.get("longName") or sym,
            "sector": info.get("sector") or None,
            "industry": info.get("industry") or None,
            # valuation
            "pe":             _i("trailingPE"),
            "forwardPE":      _i("forwardPE"),
            "eps":            _i("trailingEps"),
            # dividendYield: yfinance returns as a decimal fraction (e.g. 0.015)
            "dividendYield":  _i("dividendYield"),
            "beta":           _i("beta"),
            "pb":             _i("priceToBook"),
            "evEbitda":       _i("enterpriseToEbitda"),
            "evFcf":          ev_fcf,
            "fcfYield":       fcf_yield,
            "roic":           roic,
            "psRatio":        _i("priceToSalesTrailing12Months"),
            # short interest
            "shortFloat":     _i("shortPercentOfFloat"),
            "shortRatio":     _i("shortRatio"),
            # profitability (from statements via metrics-style extraction)
            "grossMargin":    _g(fin, "Gross Profit") and _g(fin, "Total Revenue") and
                              _clean((_g(fin, "Gross Profit") or 0) / (_g(fin, "Total Revenue") or 1)),
            "operatingMargin": _i("operatingMargins"),
            "netMargin":      _i("profitMargins"),
            "roe":            _i("returnOnEquity"),
            "roa":            _i("returnOnAssets"),
            "debtToEquity":   _i("debtToEquity"),
            "currentRatio":   _i("currentRatio"),
            "revenueGrowth":  _i("revenueGrowth"),
            "epsGrowth":      _i("earningsGrowth"),
            # market cap and shares (for mcap fallback in treemap)
            "marketCap":      mcap,
            "_sharesOutstanding": shares,
            # fields computed from price/volume frames later
            "price": None, "changePercent": None, "volume": None,
            "avgVolume20d": None, "volumeRatio": None,
            "sma50": None, "sma200": None, "aboveSma200": None,
            "goldenCross": None, "rsi14": None,
            "high52": None, "low52": None, "pctFromHigh": None,
            "spark": None,
            # not cheaply derivable — leave None
            "piotroski": None, "esg": None, "earningsRev30d": None,
            "altmanZ": az,
        }
    except Exception:
        return {
            "symbol": sym,
            "name": sym,
            "sector": None, "industry": None,
            "_sharesOutstanding": None,
        }


def _fix_gross_margin(row: dict, bundle: dict) -> None:
    """Fix the grossMargin value which had a logic error in the lambda above."""
    # The original lambda assignment was wrong — fix it here
    fin = bundle.get("financials", {}) or {}
    gp = None
    rev = None
    for k in ("Gross Profit",):
        v = fin.get(k)
        if v is not None:
            gp = float(v)
            break
    for k in ("Total Revenue",):
        v = fin.get(k)
        if v is not None:
            rev = float(v)
            break
    if gp is not None and rev is not None and rev != 0:
        try:
            val = gp / rev
            if not math.isnan(val) and not math.isinf(val):
                row["grossMargin"] = val
                return
        except Exception:
            pass
    row["grossMargin"] = None


# ---------------------------------------------------------------------------
# Technicals — vectorised from price/volume frames
# ---------------------------------------------------------------------------

def _rsi(series: pd.Series, period: int = 14) -> float | None:
    """Compute the most-recent RSI value for a price series."""
    s = series.dropna()
    if len(s) < period + 1:
        return None
    delta = s.diff().dropna()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean().iloc[-1]
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return _clean(100.0 - (100.0 / (1.0 + rs)))


def _compute_technicals(
    sym: str,
    close_frame: pd.DataFrame,
    vol_frame: pd.DataFrame,
) -> dict:
    """Compute all price/volume-derived technical fields for one symbol.

    Returns a dict of the technical fields (None for those that can't be computed).
    """
    out: dict = {
        "price": None, "changePercent": None, "volume": None,
        "avgVolume20d": None, "volumeRatio": None,
        "sma50": None, "sma200": None, "aboveSma200": None,
        "goldenCross": None, "rsi14": None,
        "high52": None, "low52": None, "pctFromHigh": None,
        "spark": [],
    }

    if close_frame is None or close_frame.empty or sym not in close_frame.columns:
        return out

    col = close_frame[sym].dropna()
    if col.empty:
        return out

    # Last price and 1-day return
    price = _clean(col.iloc[-1])
    out["price"] = price
    if len(col) >= 2:
        prev = col.iloc[-2]
        if prev and prev != 0:
            out["changePercent"] = _clean((col.iloc[-1] / prev - 1.0) * 100.0)

    # SMAs (use full available history for accuracy)
    if len(col) >= 50:
        out["sma50"] = _clean(col.tail(50).mean())
    if len(col) >= 200:
        out["sma200"] = _clean(col.tail(200).mean())

    sma50 = out["sma50"]
    sma200 = out["sma200"]
    if price is not None and sma200 is not None:
        out["aboveSma200"] = price > sma200
    if sma50 is not None and sma200 is not None:
        # goldenCross: sma50 > sma200 with a crossover in the last ~10 sessions
        currently_above = sma50 > sma200
        # Check for crossover: look at rolling sma50/sma200 for last 10 sessions
        if len(col) >= 200:
            recent = col.tail(210)  # a bit extra for rolling
            sma50_series = recent.rolling(50, min_periods=50).mean().dropna()
            sma200_series = recent.rolling(200, min_periods=200).mean().dropna()
            aligned = pd.concat([sma50_series, sma200_series], axis=1).dropna()
            aligned.columns = ["s50", "s200"]
            if len(aligned) >= 2:
                last10 = aligned.tail(10)
                # golden cross: was below, now above in last 10 sessions
                was_below = (last10["s50"] < last10["s200"]).any()
                is_above_now = currently_above
                out["goldenCross"] = bool(is_above_now and was_below) if was_below else bool(currently_above)
            else:
                out["goldenCross"] = currently_above
        else:
            out["goldenCross"] = currently_above

    # RSI-14
    out["rsi14"] = _rsi(col)

    # 52-week high/low (use last 252 trading days available)
    tail252 = col.tail(252)
    if not tail252.empty:
        h52 = _clean(tail252.max())
        l52 = _clean(tail252.min())
        out["high52"] = h52
        out["low52"] = l52
        if price is not None and h52 is not None and h52 > 0:
            out["pctFromHigh"] = _clean((price / h52 - 1.0) * 100.0)

    # Spark: ~63 most-recent daily closes (3 months ≈ 63 trading days)
    spark_col = col.tail(63)
    out["spark"] = [_clean(v) for v in spark_col.tolist() if _clean(v) is not None]

    # Volume
    if vol_frame is not None and not vol_frame.empty and sym in vol_frame.columns:
        vcol = vol_frame[sym].dropna()
        if not vcol.empty:
            out["volume"] = _clean(vcol.iloc[-1])
            avg20 = _clean(vcol.tail(20).mean()) if len(vcol) >= 5 else None
            out["avgVolume20d"] = avg20
            if avg20 and avg20 > 0 and out["volume"] is not None:
                out["volumeRatio"] = _clean(out["volume"] / avg20)

    return out


# ---------------------------------------------------------------------------
# Public refresh pipeline
# ---------------------------------------------------------------------------

def refresh_universe(index: str) -> int:
    """Fetch and cache fundamentals + technicals for all constituents of index.

    Returns the number of rows written.  If a refresh is already running for
    this index, returns 0 immediately (no double-refresh).

    This is a blocking call — run it in a daemon thread from the caller.
    """
    lock = _refresh_locks.get(index)
    if lock is None:
        return 0

    acquired = lock.acquire(blocking=False)
    if not acquired:
        return 0  # already refreshing

    try:
        members = _constituents.get_constituents(index)
        if not members:
            return 0

        syms = tuple(c["symbol"] for c in members)
        meta = {c["symbol"]: c for c in members}

        # --- Batch price/volume frames ---
        close_frame = yfs.get_close_frame(syms, "1y")
        vol_frame = yfs.get_volume_frame(syms, "3mo")

        # --- Per-ticker fundamentals fan-out ---
        info_rows: dict[str, dict] = {}
        bundles: dict[str, dict] = {}

        def _fetch(sym: str) -> tuple[str, dict, dict]:
            try:
                bundle = yfs.get_info(sym)
            except Exception:
                bundle = {"info": {}, "financials": {}, "balance_sheet": {}, "cashflow": {}}
            info = bundle.get("info", {}) or {}
            bs = bundle.get("balance_sheet", {}) or {}
            fin = bundle.get("financials", {}) or {}
            cf_data = bundle.get("cashflow", {}) or {}

            def _i(key: str) -> float | None:
                return _clean(info.get(key))

            def _g(d: dict, *keys: str) -> float | None:
                for k in keys:
                    v = d.get(k)
                    if v is not None:
                        return _clean(v)
                return None

            mcap = _i("marketCap")
            enterprise_value = _i("enterpriseValue")
            fcf = _i("freeCashflow") or _g(cf_data, "Free Cash Flow")
            shares = _i("sharesOutstanding")

            # ROIC
            roic: float | None = None
            try:
                ebit = _g(fin, "EBIT", "Operating Income")
                tax_prov = _g(fin, "Tax Provision")
                pretax_inc = _g(fin, "Pretax Income")
                equity = (_g(bs, "Stockholders Equity", "Common Stock Equity")
                          or _i("totalStockholderEquity"))
                total_debt = _g(bs, "Total Debt") or _i("totalDebt")
                if ebit is not None and equity is not None and total_debt is not None:
                    tax_rate = (tax_prov / pretax_inc
                                if (tax_prov and pretax_inc and pretax_inc != 0)
                                else 0.21)
                    nopat = ebit * (1 - tax_rate)
                    inv_cap = equity + total_debt
                    if inv_cap and inv_cap != 0:
                        roic = _clean(nopat / inv_cap)
            except Exception:
                roic = None

            ev_fcf: float | None = None
            if enterprise_value and fcf and fcf != 0:
                ev_fcf = _clean(enterprise_value / fcf)

            fcf_yield: float | None = None
            if fcf is not None and mcap and mcap > 0:
                fcf_yield = _clean(fcf / mcap)

            # grossMargin
            gp = _g(fin, "Gross Profit")
            rev = _g(fin, "Total Revenue")
            gross_margin: float | None = None
            if gp is not None and rev is not None and rev != 0:
                gross_margin = _clean(gp / rev)

            az = altman_z(info, bs, fin)

            row = {
                "symbol": sym,
                "name": info.get("shortName") or info.get("longName") or sym,
                "sector": meta.get(sym, {}).get("sector") or info.get("sector") or None,
                "industry": meta.get(sym, {}).get("industry") or info.get("industry") or None,
                "pe":             _i("trailingPE"),
                "forwardPE":      _i("forwardPE"),
                "eps":            _i("trailingEps"),
                "dividendYield":  _i("dividendYield"),
                "beta":           _i("beta"),
                "pb":             _i("priceToBook"),
                "evEbitda":       _i("enterpriseToEbitda"),
                "evFcf":          ev_fcf,
                "fcfYield":       fcf_yield,
                "roic":           roic,
                "psRatio":        _i("priceToSalesTrailing12Months"),
                "shortFloat":     _i("shortPercentOfFloat"),
                "shortRatio":     _i("shortRatio"),
                "grossMargin":    gross_margin,
                "operatingMargin": _i("operatingMargins"),
                "netMargin":      _i("profitMargins"),
                "roe":            _i("returnOnEquity"),
                "roa":            _i("returnOnAssets"),
                "debtToEquity":   _i("debtToEquity"),
                "currentRatio":   _i("currentRatio"),
                "revenueGrowth":  _i("revenueGrowth"),
                "epsGrowth":      _i("earningsGrowth"),
                "marketCap":      mcap,
                "_sharesOutstanding": shares,
                "altmanZ":        az,
                "piotroski":      None,
                "esg":            None,
                "earningsRev30d": None,
            }
            return sym, row, bundle

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_fetch, sym): sym for sym in syms}
            for fut in as_completed(futures):
                sym = futures[fut]
                try:
                    s, row, bundle = fut.result()
                    info_rows[s] = row
                except Exception:
                    info_rows[sym] = {"symbol": sym, "name": sym,
                                      "sector": None, "industry": None,
                                      "_sharesOutstanding": None}

        # --- Assemble final rows (merge technicals) ---
        rows_to_upsert: list[dict] = []
        shares_to_upsert: dict[str, float] = {}

        for sym in syms:
            base = info_rows.get(sym, {"symbol": sym, "name": sym})
            technicals = _compute_technicals(sym, close_frame, vol_frame)
            row = {**base, **technicals}

            # marketCap fallback: price × sharesOutstanding
            if (row.get("marketCap") is None or row.get("marketCap", 0) == 0):
                shares = base.get("_sharesOutstanding")
                price = technicals.get("price")
                if shares and price:
                    row["marketCap"] = _clean(float(shares) * float(price))

            # Track shares for treemap fix
            shares_outstanding = base.get("_sharesOutstanding")
            if shares_outstanding:
                shares_to_upsert[sym] = float(shares_outstanding)

            # Remove private field before upsert
            row.pop("_sharesOutstanding", None)
            rows_to_upsert.append(row)

        screener_cache.upsert_rows(rows_to_upsert)
        screener_cache.upsert_shares(shares_to_upsert)
        return len(rows_to_upsert)

    except Exception:
        return 0
    finally:
        lock.release()


# ---------------------------------------------------------------------------
# Query engine
# ---------------------------------------------------------------------------

def query(
    index: str,
    preset_ids: list[str],
    filters: list[dict],
    sort_key: str,
    direction: str,
    limit: int,
) -> dict:
    """Read from cache, filter, sort, and return the universe response dict.

    If the cache is stale/empty, kicks a background refresh and returns stale
    data immediately with stale=True.
    """
    members = _constituents.get_constituents(index)
    symbols = [m["symbol"] for m in members]

    stale = screener_cache.is_stale(symbols)
    as_of: str | None = screener_cache.last_refresh(symbols)
    count = screener_cache.row_count(symbols)

    if stale or count == 0:
        # Kick background refresh (daemon=True so it doesn't block shutdown)
        t = threading.Thread(target=refresh_universe, args=(index,), daemon=True)
        t.start()

    rows = screener_cache.get_rows(symbols)

    # Apply presets
    filtered = apply_presets(rows, preset_ids)
    # Apply ad-hoc filters
    filtered = apply_filters(filtered, filters)
    # Sort
    filtered = sort_rows(filtered, sort_key, direction)
    # Limit
    if limit and limit > 0:
        filtered = filtered[:limit]

    return {
        "index": index,
        "asOf": as_of,
        "count": len(filtered),
        "screened": len(rows),
        "stale": stale,
        "presets": preset_ids,
        "results": filtered,
    }


# ---------------------------------------------------------------------------
# Startup warm
# ---------------------------------------------------------------------------

def warm_all() -> None:
    """Warm all three index caches sequentially (called at container start).

    Runs in a daemon thread — must never raise, even if yfinance is unreachable.
    """
    for index in ("dow", "ndx", "sp500"):
        try:
            members = _constituents.get_constituents(index)
            symbols = [m["symbol"] for m in members]
            if screener_cache.is_stale(symbols):
                refresh_universe(index)
        except Exception:
            pass
