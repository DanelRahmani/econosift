"""G10 FX Carry Analytics — Phase 14.

Computes:
  - Carry table: foreign policy rate − USD policy rate, FX vol, vol-adjusted carry
  - Carry backtest: long top-3 / short bottom-3 by carry, base-100 cumulative
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..cache import cached
from . import rates_service
from . import yfinance_service as yfs

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# G10 currency config
# ---------------------------------------------------------------------------

# CCY → list of FRED series ids to try in order (first with recent data wins)
_POLICY_RATE_SERIES: dict[str, list[str]] = {
    "USD": ["FEDFUNDS"],
    "EUR": ["ECBMRRFR", "ECBDFR"],
    "GBP": ["BOERUKM", "INTDSRGBM193N"],
    "CAD": ["INTDSRCAM193N"],
    "AUD": ["INTDSRAUAM193N"],
    "NZD": ["INTDSRNZM193N"],
    "CHF": ["INTDSRCHM193N"],
    "JPY": ["INTDSRJPM193N"],
}

# Non-USD G10 currencies (NOK/SEK omitted — no reliable FRED policy rate series)
_NON_USD_CCYS = ["EUR", "GBP", "CAD", "AUD", "NZD", "CHF", "JPY"]

# Yahoo Finance FX tickers: <CCY>USD=X  (USD per 1 unit foreign)
def _fx_ticker(ccy: str) -> str:
    return f"{ccy}USD=X"

# DXY proxy
_DXY_TICKERS = ("DX-Y.NYB", "UUP")

# Minimum days since last observation for a series to be considered "recent"
_MAX_STALE_DAYS = 120


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(v) -> float | None:
    """Return float or None, never NaN/inf."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _resolve_policy_rates(start: str) -> tuple[dict[str, float], dict[str, str]]:
    """Fetch FRED policy rates for all G10 currencies.

    Returns:
        rates:   CCY -> latest rate (%)
        sources: CCY -> FRED series id that resolved
    """
    all_series: list[str] = []
    for series_list in _POLICY_RATE_SERIES.values():
        all_series.extend(series_list)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_series = [s for s in all_series if not (s in seen or seen.add(s))]

    fred_data = rates_service._fetch_many_fred_sync(unique_series, start)

    rates: dict[str, float] = {}
    sources: dict[str, str] = {}
    cutoff = date.today() - timedelta(days=_MAX_STALE_DAYS)

    for ccy, candidates in _POLICY_RATE_SERIES.items():
        for sid in candidates:
            series = fred_data.get(sid)
            if series is None or series.empty:
                continue
            clean = series.dropna()
            if clean.empty:
                continue
            last_idx = clean.index[-1]
            last_date = last_idx.date() if hasattr(last_idx, "date") else date.fromisoformat(str(last_idx)[:10])
            if last_date < cutoff:
                log.debug("FRED %s for %s last obs %s is stale (>%d days)", sid, ccy, last_date, _MAX_STALE_DAYS)
                continue
            rates[ccy] = round(float(clean.iloc[-1]), 4)
            sources[ccy] = sid
            log.info("Carry: %s resolved via %s (last obs %s, rate %.4f%%)", ccy, sid, last_date, rates[ccy])
            break
        else:
            log.warning("Carry: could not resolve policy rate for %s", ccy)

    return rates, sources


def _compute_fx_vol(close: pd.DataFrame, ticker: str, min_rows: int = 20) -> float | None:
    """Annualised FX vol (%) from daily log returns."""
    if ticker not in close.columns:
        return None
    series = close[ticker].dropna()
    if len(series) < min_rows:
        return None
    log_rets = np.log(series / series.shift(1)).dropna()
    if len(log_rets) < min_rows:
        return None
    vol = float(log_rets.std() * math.sqrt(252) * 100)
    return round(vol, 4) if math.isfinite(vol) else None


def _metrics_from_series(cum: pd.Series) -> dict:
    """Compute CAGR, vol, Sharpe, maxDrawdown from a base-100 cumulative series."""
    if cum.empty or len(cum) < 2:
        return {"cagr": None, "vol": None, "sharpe": None, "maxDrawdown": None}
    log_rets = np.log(cum / cum.shift(1)).dropna()
    n = len(log_rets)
    years = n / 252
    total_return = float(cum.iloc[-1] / cum.iloc[0]) - 1.0
    cagr = round(((1 + total_return) ** (1 / years) - 1) * 100, 4) if years > 0 else None
    ann_vol = round(float(log_rets.std() * math.sqrt(252) * 100), 4) if n > 1 else None
    sharpe = round(cagr / ann_vol, 4) if (cagr is not None and ann_vol and ann_vol > 0) else None
    rolling_max = cum.cummax()
    dd = (cum - rolling_max) / rolling_max
    max_dd = round(float(dd.min() * 100), 4)
    return {
        "cagr": _clean(cagr),
        "vol": _clean(ann_vol),
        "sharpe": _clean(sharpe),
        "maxDrawdown": _clean(max_dd),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("carry_table")
def get_carry_table(period: str = "3y") -> dict:
    """Build G10 FX carry table sorted by carry (desc).

    Returns:
    {
      "asOf": "YYYY-MM-DD",
      "usdRate": float,
      "rows": [
        {
          "ccy": "AUD",
          "pair": "AUD/USD",
          "spot": float,
          "foreignRate": float,
          "carry": float,
          "fxVol": float | None,
          "volAdjCarry": float | None,
          "rateSource": "INTDSRAUAM193N"
        },
        ...
      ]  # sorted by carry desc
    }
    """
    try:
        # 5-year start to ensure we have recent observations
        start = (date.today() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
        rates, sources = _resolve_policy_rates(start)

        usd_rate = rates.get("USD")
        if usd_rate is None:
            log.warning("Carry: could not resolve USD policy rate (FEDFUNDS)")
            return {"error": "USD policy rate unavailable", "asOf": str(date.today()), "usdRate": None, "rows": []}

        # Fetch FX spot data
        fx_tickers = tuple(_fx_ticker(ccy) for ccy in _NON_USD_CCYS)
        close = yfs.get_close_frame(fx_tickers, period)

        rows = []
        for ccy in _NON_USD_CCYS:
            if ccy not in rates:
                continue
            ticker = _fx_ticker(ccy)
            foreign_rate = rates[ccy]
            carry = round(foreign_rate - usd_rate, 4)

            # Spot price
            spot: float | None = None
            if ticker in close.columns:
                last_valid = close[ticker].dropna()
                if not last_valid.empty:
                    spot = round(float(last_valid.iloc[-1]), 6)

            fx_vol = _compute_fx_vol(close, ticker)
            vol_adj_carry: float | None = None
            if fx_vol is not None and fx_vol > 0:
                vol_adj_carry = round(carry / fx_vol, 4)

            rows.append({
                "ccy": ccy,
                "pair": f"{ccy}/USD",
                "spot": _clean(spot),
                "foreignRate": _clean(foreign_rate),
                "carry": _clean(carry),
                "fxVol": _clean(fx_vol),
                "volAdjCarry": _clean(vol_adj_carry),
                "rateSource": sources.get(ccy, "unknown"),
            })

        rows.sort(key=lambda r: r["carry"] if r["carry"] is not None else -999, reverse=True)

        # Determine asOf date from FX data
        as_of = str(date.today())
        if not close.empty:
            last_idx = close.dropna(how="all").index
            if len(last_idx):
                d = last_idx[-1]
                as_of = str(d.date()) if hasattr(d, "date") else str(d)[:10]

        return {
            "asOf": as_of,
            "usdRate": _clean(usd_rate),
            "rows": rows,
        }
    except Exception as exc:
        log.exception("get_carry_table failed: %s", exc)
        return {"error": str(exc), "asOf": str(date.today()), "usdRate": None, "rows": []}


@cached("carry_backtest")
def get_carry_backtest(period: str = "3y") -> dict:
    """Long top-3 / short bottom-3 carry strategy backtest.

    Returns:
    {
      "series": [{"date": "YYYY-MM-DD", "strategy": float, "benchmark": float}, ...],
      "legs": {"long": ["AUD", "NZD", "GBP"], "short": ["JPY", "CHF", "EUR"]},
      "metrics": {"cagr": float, "vol": float, "sharpe": float, "maxDrawdown": float}
    }
    """
    _EMPTY = {
        "series": [],
        "legs": {"long": [], "short": []},
        "metrics": {"cagr": None, "vol": None, "sharpe": None, "maxDrawdown": None},
    }
    try:
        table = get_carry_table(period)
        rows = table.get("rows", [])
        if not rows:
            return {**_EMPTY, "error": table.get("error", "no carry data")}

        # Rank by carry — rows already sorted desc
        ranked = [r for r in rows if r["carry"] is not None]
        if len(ranked) < 6:
            return {**_EMPTY, "error": f"not enough currencies with carry data (need 6, got {len(ranked)})"}

        long_ccys = [r["ccy"] for r in ranked[:3]]
        short_ccys = [r["ccy"] for r in ranked[-3:]]

        # Fetch FX price histories
        all_ccys = long_ccys + short_ccys
        fx_tickers = tuple(_fx_ticker(ccy) for ccy in all_ccys)
        close = yfs.get_close_frame(fx_tickers, period)

        # Fetch DXY benchmark
        dxy_close: pd.Series | None = None
        for dxy_sym in _DXY_TICKERS:
            dxy_frame = yfs.get_close_frame((dxy_sym,), period)
            if dxy_sym in dxy_frame.columns and not dxy_frame[dxy_sym].dropna().empty:
                dxy_close = dxy_frame[dxy_sym].dropna()
                break

        if close.empty:
            return {**_EMPTY, "error": "no FX price data"}

        # Daily returns for each leg
        rets = close.pct_change().dropna(how="all")

        # Strategy return = Σ weight_i * daily_return
        # long: +1/3 each, short: -1/3 each
        weight = 1.0 / 3.0
        strategy_rets = pd.Series(0.0, index=rets.index)
        for ccy in long_ccys:
            tk = _fx_ticker(ccy)
            if tk in rets.columns:
                strategy_rets = strategy_rets.add(rets[tk].fillna(0) * weight)
        for ccy in short_ccys:
            tk = _fx_ticker(ccy)
            if tk in rets.columns:
                strategy_rets = strategy_rets.add(rets[tk].fillna(0) * (-weight))

        strategy_rets = strategy_rets.dropna()
        if strategy_rets.empty:
            return {**_EMPTY, "error": "strategy returns are empty"}

        cum_strategy = (1 + strategy_rets).cumprod() * 100

        # Benchmark base-100
        bench_series: pd.Series | None = None
        if dxy_close is not None and not dxy_close.empty:
            dxy_rets = dxy_close.pct_change().dropna()
            bench_series = (1 + dxy_rets).cumprod() * 100
        else:
            bench_series = pd.Series(100.0, index=cum_strategy.index)

        # Align on common index
        common_idx = cum_strategy.index.intersection(bench_series.index)
        if common_idx.empty:
            # Reindex benchmark to strategy
            bench_aligned = bench_series.reindex(cum_strategy.index, method="ffill").fillna(100.0)
        else:
            cum_strategy = cum_strategy.reindex(common_idx)
            bench_aligned = bench_series.reindex(common_idx)

        # Build series output
        series_records = []
        for dt, strat_val in cum_strategy.items():
            bench_val = bench_aligned.get(dt, None) if hasattr(bench_aligned, "get") else bench_aligned.loc[dt] if dt in bench_aligned.index else None
            series_records.append({
                "date": str(dt.date()) if hasattr(dt, "date") else str(dt)[:10],
                "strategy": _clean(strat_val),
                "benchmark": _clean(bench_val),
            })

        metrics = _metrics_from_series(cum_strategy)

        return {
            "series": series_records,
            "legs": {"long": long_ccys, "short": short_ccys},
            "metrics": metrics,
        }
    except Exception as exc:
        log.exception("get_carry_backtest failed: %s", exc)
        return {**_EMPTY, "error": str(exc)}
