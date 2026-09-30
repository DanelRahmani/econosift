"""Signal adapters for the backtester — Phase 43 (task D2).

Turns the price series the platform already fetches into (dates x tickers)
signal frames that `backtest_engine.run_backtest` can rank.

Every adapter here is **price-derived**. That is deliberate: yfinance
fundamentals are latest-restatement rather than as-reported-then (P3-14), so a
fundamental signal cannot be honestly backtested on free data. The registry
carries an `is_fundamental` flag so the engine can refuse those by default if
any are added later.

Each adapter must satisfy one contract: **the value at date t may only use data
available at t.** Every signal below is built from a trailing window ending at
t, which satisfies it by construction.
"""
from __future__ import annotations

import hashlib
import logging

import numpy as np
import pandas as pd

from . import constituents
from . import yfinance_service as yfs

log = logging.getLogger(__name__)

# Enough history for a 12-month lookback plus a usable backtest window.
_DEFAULT_PERIOD = "10y"


def _momentum(prices: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """Classic 12-1 momentum: trailing return, skipping the most recent month.

    The skip is not decoration — short-horizon reversal contaminates raw 12-month
    momentum, which is why Jegadeesh-Titman and everyone after them omit the
    final month.
    """
    return prices.shift(skip) / prices.shift(lookback) - 1.0


def _short_term_reversal(prices: pd.DataFrame, lookback: int = 21) -> pd.DataFrame:
    """Negative of the last month's return — high signal = biggest loser."""
    return -(prices / prices.shift(lookback) - 1.0)


def _low_volatility(prices: pd.DataFrame, window: int = 126) -> pd.DataFrame:
    """Negative trailing volatility, so the calmest names rank highest."""
    return -prices.pct_change().rolling(window).std()


def _trend(prices: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Distance between fast and slow moving averages, scaled by price."""
    return (prices.rolling(fast).mean() - prices.rolling(slow).mean()) / prices


def _distance_from_high(prices: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """Proximity to the trailing 52-week high (the '52-week high' effect)."""
    return prices / prices.rolling(window).max() - 1.0


def _residual_reversal(prices: pd.DataFrame, window: int = 21) -> pd.DataFrame:
    """Last month's return measured against the cross-sectional mean.

    A crude market-neutral reversal: it strips the common move so the ranking
    reflects relative rather than absolute weakness.
    """
    ret = prices / prices.shift(window) - 1.0
    return -(ret.sub(ret.mean(axis=1), axis=0))


# name -> (builder, label, description, is_fundamental)
SIGNALS: dict[str, tuple] = {
    "momentum_12_1": (
        _momentum, "Momentum (12-1)",
        "Trailing 12-month return skipping the most recent month.", False,
    ),
    "reversal_1m": (
        _short_term_reversal, "Short-term reversal (1m)",
        "Negative of the last month's return — buys the losers.", False,
    ),
    "low_volatility": (
        _low_volatility, "Low volatility (6m)",
        "Negative trailing 126-day volatility — buys the calmest names.", False,
    ),
    "trend_50_200": (
        _trend, "Trend (50/200)",
        "Gap between the 50- and 200-day moving averages, scaled by price.", False,
    ),
    "near_52w_high": (
        _distance_from_high, "Proximity to 52-week high",
        "How close the price sits to its trailing 52-week high.", False,
    ),
    "residual_reversal_1m": (
        _residual_reversal, "Residual reversal (1m)",
        "Last month's return relative to the cross-section.", False,
    ),
}


def available_signals() -> list[dict]:
    """Registry for the UI."""
    return [
        {
            "key": key,
            "label": label,
            "description": desc,
            "isFundamental": is_fund,
        }
        for key, (_fn, label, desc, is_fund) in SIGNALS.items()
    ]


def build_signal(
    signal_key: str,
    universe: str = "sp500",
    period: str = _DEFAULT_PERIOD,
    max_tickers: int = 120,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fetch prices and build the requested signal frame.

    Returns ``(signal, prices, meta)``. The universe is capped because a full
    500-name download is slow and rate-limited; the cap is reported in meta so
    the UI can say so rather than quietly implying full coverage.
    """
    entry = SIGNALS.get(signal_key)
    if entry is None:
        raise ValueError(f"unknown signal '{signal_key}'")
    builder, label, _desc, is_fundamental = entry

    symbols = constituents.constituent_symbols(universe)
    if not symbols:
        raise ValueError(f"no constituents available for universe '{universe}'")

    truncated = len(symbols) > max_tickers
    if truncated:
        # Deterministic subset so repeated runs are comparable — ordered by a
        # hash of the ticker, not alphabetically: the first 120 names A→Z are
        # an arbitrary slice that over-represents a few sectors (audit C-32).
        symbols = sorted(symbols, key=lambda t: hashlib.md5(t.encode()).hexdigest())[:max_tickers]

    prices = yfs.get_close_frame(tuple(symbols), period)
    if prices is None or prices.empty:
        raise ValueError("price download returned no data")

    prices = prices.dropna(axis=1, how="all").ffill()
    signal = builder(prices)

    meta = {
        "signal": signal_key,
        "label": label,
        "universe": universe,
        "period": period,
        "tickersRequested": len(symbols),
        "tickersWithData": int(prices.shape[1]),
        "universeTruncated": truncated,
        "universeSampling": "hash-ordered sample of current constituents" if truncated else "all current constituents",
        "maxTickers": max_tickers,
        "isFundamental": is_fundamental,
    }
    return signal, prices, meta
