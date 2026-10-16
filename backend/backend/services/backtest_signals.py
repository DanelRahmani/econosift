"""Signal adapters for the backtester — Phase 43 (task D2).

Turns stored daily prices into (dates x tickers) signal frames that
`backtest_engine.run_backtest` can rank. Since Phase 70 the prices come from
the store over the point-in-time universe (`pit.PITData`), not a live download
of today's members.

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

import logging

import numpy as np
import pandas as pd

from .. import store
from . import constituents, pit

log = logging.getLogger(__name__)

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


def _period_start(period: str, end: pd.Timestamp) -> pd.Timestamp:
    """'10y' -> ten years before ``end``; 'max' -> the start of the membership log's coverage."""
    if period == "max":
        return pd.Timestamp("2000-01-01")
    if period.endswith("y") and period[:-1].isdigit() and 0 < int(period[:-1]) <= 30:
        return end - pd.DateOffset(years=int(period[:-1]))
    raise ValueError(f"unsupported period {period!r}; use e.g. '10y' or 'max'")


def build_signal(
    signal_key: str,
    universe: str = "sp500",
    period: str = _DEFAULT_PERIOD,
    point_in_time: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, object]:
    """Build the requested signal frame from stored prices (Phase 70: no downloads).

    Returns ``(signal, prices, meta, universe_as_of)``. Prices cover every symbol
    that was an index member during the window, including former members
    where Yahoo still has history. ``universe_as_of(date)`` is the tradable set
    on a rebalance date: the members on that date (or, with ``point_in_time``
    off, today's members, which is survivorship-biased). Members with no stored
    price are excluded and listed in ``meta["excluded"]``, never filled.
    """
    entry = SIGNALS.get(signal_key)
    if entry is None:
        raise ValueError(f"unknown signal '{signal_key}'")
    builder, label, _desc, is_fundamental = entry

    index = constituents.ALIASES.get(universe.lower(), universe.lower())
    with store.connect() as conn:
        last = conn.execute("SELECT MAX(date) FROM price_daily").fetchone()[0]
    if not last:
        raise ValueError("no stored prices yet: the first backfill is still running")
    end = pd.Timestamp(last)
    data = pit.PITData(index, _period_start(period, end), end)

    prices = data.frames["adj_close"].dropna(axis=1, how="all").ffill(limit=pit.GAP_DAYS)
    if prices.empty:
        raise ValueError(f"no stored prices for {universe} members")
    signal = builder(prices)

    excluded: dict[str, str] = {}
    current = {s for s, iv in data.intervals.items() if any(e is None for _, e in iv)}

    def universe_as_of(day):
        tradable, gaps = data.members(day)
        for g in gaps:
            excluded.setdefault(g["symbol"], g["reason"])
        return tradable if point_in_time else [s for s in tradable if s in current]

    meta = {
        "signal": signal_key,
        "label": label,
        "universe": universe,
        "period": period,
        "tickersRequested": len(data.intervals),
        "tickersWithData": int(prices.shape[1]),
        "universeTruncated": False,
        "universeSampling": ("every member on each rebalance date, former members included" if point_in_time
                             else "today's members only (survivorship-biased)"),
        "maxTickers": None,
        "isFundamental": is_fundamental,
        "dataSource": "store",
        "excluded": excluded,  # filled while the engine walks the rebalance dates
        "snapshot": data.snapshot(),
    }
    return signal, prices, meta, universe_as_of
