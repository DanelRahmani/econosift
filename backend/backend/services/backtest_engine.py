"""Vectorized cross-sectional backtester — Phase 43 (task D1).

The platform computes a lot of signals — 20+ screener presets, momentum, factor
regime, technicals, the Phase 39 credit and oil indicators — and until now could
only *display* them. Nothing could answer "would this have made money?", and
nothing anywhere modelled transaction costs, so the Kelly and efficient-frontier
outputs on the Portfolio page are gross figures in exactly the place where cost
drag compounds hardest against you.

Design notes, all of them load-bearing:

* **Positions formed at t earn the return from t to t+1.** This is where the
  most common backtest bug lives — pairing a signal with the return already
  realised alongside it. Two sentinels in `test_backtest_engine` pin the
  alignment in both directions: a signal equal to the next period's return must
  score perfectly, and one equal to the last period's must not. Note the
  contract this places on callers: the signal at t must be computable from data
  available at t.
* **Costs are charged on turnover**, reported separately from gross, because the
  gap between the two is the honest headline.
* **The universe can vary through time** via `constituents.members_as_of`, so a
  backtest is not run on today's survivors.
* **Fundamental signals are refused by default.** yfinance fundamentals are
  latest-restatement, not as-reported-then (see P3-14), so a fundamental
  backtest is contaminated in a way free data cannot fix. `allow_lookahead=True`
  overrides it and stamps a warning on the result.
* **Pure compute, no network.** The caller supplies frames, which keeps this
  fully unit-testable — the same shape as `oil_shock_service._decompose`.

This is a *research* tool. Predictability is mostly compensation for risk rather
than alpha, so a positive spread here is not evidence of a free lunch.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

TRADING_DAYS = 252

# Rebalance frequency -> pandas resample rule.
_REBALANCE_RULES = {"W": "W-FRI", "M": "ME", "Q": "QE"}

# Periods per year, for annualising.
_PERIODS_PER_YEAR = {"W": 52.0, "M": 12.0, "Q": 4.0}


class LookaheadError(ValueError):
    """Raised when a signal known to be contaminated is run without opt-in."""


def _rebalance_dates(index: pd.DatetimeIndex, rebalance: str) -> pd.DatetimeIndex:
    """Last available trading date within each rebalance period."""
    rule = _REBALANCE_RULES.get(rebalance)
    if rule is None:
        raise ValueError(f"unsupported rebalance '{rebalance}'; use one of {list(_REBALANCE_RULES)}")
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.resample(rule).last().dropna().values)


def _quantile_weights(row: pd.Series, n_quantiles: int) -> dict[int, pd.Series]:
    """Split one cross-section into equal-weight quantile portfolios.

    Quantile 1 is the lowest signal, `n_quantiles` the highest. Returns only the
    buckets that could be formed; a cross-section too thin to split is skipped
    by the caller.
    """
    valid = row.dropna()
    if len(valid) < n_quantiles:
        return {}

    ranked = valid.rank(method="first")
    # qcut on ranks rather than raw values so ties cannot collapse a bucket.
    buckets = pd.qcut(ranked, n_quantiles, labels=False, duplicates="drop") + 1

    out: dict[int, pd.Series] = {}
    for q in range(1, n_quantiles + 1):
        members = valid.index[buckets == q]
        if len(members) == 0:
            continue
        out[q] = pd.Series(1.0 / len(members), index=members)
    return out


def _turnover(prev: pd.Series | None, curr: pd.Series) -> float:
    """One-way turnover: sum of absolute weight changes, halved."""
    if prev is None:
        return float(curr.abs().sum()) / 2.0
    aligned_prev, aligned_curr = prev.align(curr, fill_value=0.0)
    return float((aligned_curr - aligned_prev).abs().sum()) / 2.0


def _performance(returns: list[float], periods_per_year: float) -> dict:
    """Summary statistics for a sequence of per-period simple returns."""
    if not returns:
        return {
            "totalReturn": None, "cagr": None, "vol": None, "sharpe": None,
            "maxDrawdown": None, "hitRate": None, "periods": 0,
        }

    arr = np.asarray(returns, dtype=float)
    equity = np.cumprod(1.0 + arr)
    total = float(equity[-1] - 1.0)
    years = len(arr) / periods_per_year

    cagr = float(equity[-1] ** (1.0 / years) - 1.0) if years > 0 and equity[-1] > 0 else None
    vol = float(arr.std(ddof=1) * np.sqrt(periods_per_year)) if len(arr) > 1 else None
    sharpe = float(cagr / vol) if cagr is not None and vol not in (None, 0.0) else None

    peak = np.maximum.accumulate(equity)
    max_dd = float((equity / peak - 1.0).min())

    return {
        "totalReturn": round(total, 6),
        "cagr": round(cagr, 6) if cagr is not None else None,
        "vol": round(vol, 6) if vol is not None else None,
        "sharpe": round(sharpe, 4) if sharpe is not None else None,
        "maxDrawdown": round(max_dd, 6),
        "hitRate": round(float((arr > 0).mean()), 4),
        "periods": len(arr),
    }


def _equity_curve(dates: list[str], returns: list[float]) -> list[dict]:
    equity = 1.0
    out = []
    for d, r in zip(dates, returns):
        equity *= 1.0 + r
        out.append({"date": d, "value": round(equity, 6)})
    return out


def run_backtest(
    signal: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    rebalance: str = "M",
    n_quantiles: int = 5,
    long_short: bool = True,
    cost_bps: float = 10.0,
    universe_as_of=None,
    allow_lookahead: bool = False,
    is_fundamental: bool = False,
) -> dict:
    """Backtest a cross-sectional signal.

    Parameters
    ----------
    signal
        dates x tickers. Higher = more attractive. Values may be sparse.
    prices
        dates x tickers of adjusted close.
    rebalance
        'W', 'M' or 'Q'.
    n_quantiles
        Number of ranked buckets.
    long_short
        Also report the top-minus-bottom spread portfolio.
    cost_bps
        One-way cost in basis points, charged on turnover at each rebalance.
    universe_as_of
        Optional ``callable(date) -> list[str]`` restricting the tradable set at
        each rebalance — pass ``constituents.members_as_of`` to remove
        survivorship bias.
    allow_lookahead
        Required to run a fundamental signal; see `is_fundamental`.
    is_fundamental
        Marks the signal as derived from yfinance fundamentals, which are
        latest-restatement rather than point-in-time (P3-14).
    """
    if is_fundamental and not allow_lookahead:
        raise LookaheadError(
            "This signal is derived from fundamentals, which yfinance reports at "
            "their latest restatement rather than as reported at the time. A "
            "backtest of it is contaminated by look-ahead that free data cannot "
            "fix. Pass allow_lookahead=True to run it anyway and read the result "
            "as an upper bound, not an estimate."
        )

    if signal is None or prices is None or signal.empty or prices.empty:
        return {"available": False, "reason": "signal or prices are empty"}

    signal = signal.sort_index()
    prices = prices.sort_index()
    signal.index = pd.to_datetime(signal.index)
    prices.index = pd.to_datetime(prices.index)

    shared = sorted(set(signal.columns) & set(prices.columns))
    if len(shared) < n_quantiles:
        return {
            "available": False,
            "reason": f"only {len(shared)} tickers common to signal and prices; "
                      f"need at least n_quantiles={n_quantiles}",
        }
    signal = signal[shared]
    prices = prices[shared]

    rebal_dates = _rebalance_dates(prices.index, rebalance)
    if len(rebal_dates) < 3:
        return {"available": False, "reason": "not enough rebalance periods"}

    periods_per_year = _PERIODS_PER_YEAR[rebalance]
    cost_rate = cost_bps / 10_000.0

    # Alignment — the thing that decides whether any of this means anything.
    #
    # Positions are formed from the signal as it stands at rebalance date t, and
    # earn the return from t to t+1. `forward_returns` is shifted -1 precisely
    # so that the return sits at the date the decision was made, never before
    # it. There is no additional lag on the signal: adding one would model a
    # trader who waits a full extra period after seeing their own signal, which
    # understates every strategy rather than protecting against look-ahead.
    #
    # The contract this places on callers: the signal at t must be computable
    # from data available at t. A signal built from future data will produce a
    # spectacular and meaningless result — test_backtest_engine has a sentinel
    # pair that pins this alignment in both directions.
    signal_at_rebal = signal.reindex(rebal_dates, method="ffill")

    px_at_rebal = prices.reindex(rebal_dates, method="ffill")
    forward_returns = px_at_rebal.pct_change().shift(-1)  # return earned over the NEXT period

    quantile_returns: dict[int, list[float]] = {q: [] for q in range(1, n_quantiles + 1)}
    quantile_costs: dict[int, list[float]] = {q: [] for q in range(1, n_quantiles + 1)}
    prev_weights: dict[int, pd.Series | None] = {q: None for q in range(1, n_quantiles + 1)}
    used_dates: list[str] = []
    turnovers: list[float] = []
    skipped = 0

    for i, dt in enumerate(rebal_dates[:-1]):
        row = signal_at_rebal.loc[dt]

        if universe_as_of is not None:
            try:
                allowed = set(universe_as_of(dt.date()))
                row = row[[c for c in row.index if c in allowed]]
            except Exception as exc:      # never let universe lookup kill a run
                log.warning("universe_as_of failed at %s: %s", dt.date(), exc)

        buckets = _quantile_weights(row, n_quantiles)
        if len(buckets) < n_quantiles:
            skipped += 1
            continue

        fwd = forward_returns.loc[dt]
        period_turnover = 0.0
        for q, weights in buckets.items():
            realised = fwd.reindex(weights.index)
            # A name that stops trading is dropped and the bucket renormalised,
            # rather than silently counted as a zero return.
            realised = realised.dropna()
            if realised.empty:
                quantile_returns[q].append(0.0)
                quantile_costs[q].append(0.0)
                continue
            w = weights.reindex(realised.index)
            w = w / w.sum()

            gross = float((w * realised).sum())
            turn = _turnover(prev_weights[q], w)
            quantile_returns[q].append(gross)
            quantile_costs[q].append(turn * cost_rate)
            prev_weights[q] = w
            period_turnover += turn

        turnovers.append(period_turnover / max(len(buckets), 1))
        used_dates.append(dt.strftime("%Y-%m-%d"))

    if not used_dates:
        return {"available": False, "reason": "no rebalance period had a complete cross-section"}

    quantiles_out = {}
    for q in range(1, n_quantiles + 1):
        gross = quantile_returns[q]
        costs = quantile_costs[q]
        net = [g - c for g, c in zip(gross, costs)]
        quantiles_out[str(q)] = {
            "gross": _performance(gross, periods_per_year),
            "net": _performance(net, periods_per_year),
            "equityCurve": _equity_curve(used_dates, net),
            "totalCostDrag": round(float(sum(costs)), 6),
        }

    result: dict = {
        "available": True,
        "quantiles": quantiles_out,
        "periods": len(used_dates),
        "skippedPeriods": skipped,
        "start": used_dates[0],
        "end": used_dates[-1],
        "avgTurnover": round(float(np.mean(turnovers)), 4) if turnovers else None,
        "settings": {
            "rebalance": rebalance,
            "nQuantiles": n_quantiles,
            "costBps": cost_bps,
            "longShort": long_short,
            "universePointInTime": universe_as_of is not None,
        },
    }

    if long_short:
        top = quantile_returns[n_quantiles]
        bottom = quantile_returns[1]
        top_c = quantile_costs[n_quantiles]
        bot_c = quantile_costs[1]
        spread_gross = [t - b for t, b in zip(top, bottom)]
        spread_net = [
            (t - tc) - (b - bc) for t, tc, b, bc in zip(top, top_c, bottom, bot_c)
        ]
        result["longShort"] = {
            "gross": _performance(spread_gross, periods_per_year),
            "net": _performance(spread_net, periods_per_year),
            "equityCurve": _equity_curve(used_dates, spread_net),
            "totalCostDrag": round(float(sum(top_c) + sum(bot_c)), 6),
        }

    if allow_lookahead and is_fundamental:
        result["warning"] = (
            "Run with allow_lookahead=True on a fundamental signal. yfinance "
            "reports fundamentals at their latest restatement, so these figures "
            "use numbers that were not knowable at the decision date. Treat the "
            "result as an upper bound, not an estimate."
        )

    result["caveat"] = (
        "Cross-sectional predictability is mostly compensation for risk rather "
        "than alpha: a positive spread typically means the top bucket carries "
        "risk the bottom does not. Costs are modelled as cost_bps x turnover "
        "and exclude market impact, borrow cost on the short leg, and taxes."
    )
    return result
