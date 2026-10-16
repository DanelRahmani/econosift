"""Strategy plugin backtests (Phase 70, plan §5).

A strategy is a ``.py`` file with a top-level ``generate_weights(ctx)`` that
returns ``{symbol: weight}`` for the rebalance date ``ctx.date``
(``strategy_context.StrategyContext``). Weights are fractions of equity;
negative is short, and whatever is not invested is cash earning nothing.

The engine is the trusted side: it owns the full price panel, asks the
strategy for weights on each rebalance date through a runner (in-process for
the bundled examples and tests, a sandboxed subprocess for uploads), checks the
answer, and values the portfolio daily between rebalances:

- positions are formed at the close of ``t`` and earn from ``t`` to the next
  rebalance, drifting with prices in between (buy and hold);
- costs are ``cost_bps`` on every unit of equity traded (sum of |weight change|),
  taken out of equity at ``t``; turnover is reported one-way (half of that sum);
- a held name whose stored prices end before the next rebalance (an acquisition
  or delisting Yahoo has no exit price for) is carried at its last stored price,
  and the run counts how often that happened instead of inventing a return.

Every result carries the strategy's SHA-256 and the data snapshot it read, so
a run can be reproduced: same hash + same snapshot + same settings = same result.
"""
from __future__ import annotations

import ast
import hashlib
import math
import time

import numpy as np
import pandas as pd

from . import pit
from .strategy_context import Panel, StrategyContext

MAX_SOURCE_BYTES = 200_000
MAX_GROSS = 3.0           # sum of |weights|: 300% gross exposure at most
REBALANCE_RULES = ("W", "M", "Q")


class StrategyError(ValueError):
    """The strategy's code or answer is unusable; the message is for the user."""


def check_source(source: str) -> str:
    """Parse ``source`` without running it; return its SHA-256."""
    raw = source.encode("utf-8")
    if len(raw) > MAX_SOURCE_BYTES:
        raise StrategyError(f"strategy file is over {MAX_SOURCE_BYTES // 1000} kB")
    try:
        tree = ast.parse(source, filename="strategy.py")
    except SyntaxError as exc:
        raise StrategyError(f"syntax error on line {exc.lineno}: {exc.msg}") from exc
    if not any(isinstance(n, ast.FunctionDef) and n.name == "generate_weights" for n in tree.body):
        raise StrategyError("the file must define a top-level function generate_weights(ctx)")
    return hashlib.sha256(raw).hexdigest()


class InProcessRunner:
    """Runs trusted code (the bundled examples, tests) in this process."""

    sandbox = {"mode": "in-process", "note": "trusted code only; uploads always run in the sandbox"}

    def __init__(self, source: str) -> None:
        self.source = source
        self.panel = Panel()
        self._fn = None

    def begin(self, params: dict) -> None:
        ns: dict = {"__name__": "strategy"}
        exec(compile(self.source, "strategy.py", "exec"), ns)  # fresh module state per pass
        self._fn, self._params = ns["generate_weights"], params

    def weights(self, msg: dict, holdings: dict, facts_fn) -> object:
        if "panel" in msg:
            self.panel.apply(msg["panel"])
        return self._fn(StrategyContext(self.panel, msg, self._params, holdings, facts_fn))

    def close(self) -> dict:
        return {}


def _validate(raw, universe: list[str], day: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise StrategyError(f"{day}: generate_weights must return a dict, got {type(raw).__name__}")
    allowed = set(universe)
    out: dict[str, float] = {}
    for sym, w in raw.items():
        if not isinstance(sym, str):
            raise StrategyError(f"{day}: weight keys must be ticker strings")
        try:
            w = float(w)
        except (TypeError, ValueError):
            raise StrategyError(f"{day}: weight for {sym} is not a number") from None
        if not math.isfinite(w):
            raise StrategyError(f"{day}: weight for {sym} is not finite")
        if w == 0.0:
            continue
        if sym not in allowed:
            raise StrategyError(f"{day}: {sym} is not an index member with a stored price on this date")
        out[sym] = w
    gross = sum(abs(w) for w in out.values())
    if gross > MAX_GROSS + 1e-9:
        raise StrategyError(f"{day}: gross exposure {gross:.2f} is over the {MAX_GROSS:.0f}x limit")
    return out


def _drawdown(equity: pd.Series) -> pd.Series:
    """Below the running peak, counting the starting equity of 1.0 as the first peak."""
    return equity / equity.cummax().clip(lower=1.0) - 1.0


def _metrics(daily: pd.Series, equity: pd.Series, turnovers: list[float], costs: list[float]) -> dict:
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    end_value = float(equity.iloc[-1])
    vol = float(daily.std(ddof=1) * np.sqrt(252)) if len(daily) > 1 else None
    mean = float(daily.mean() * 252) if len(daily) else None
    return {
        "totalReturn": round(end_value - 1.0, 6),
        "cagr": round(end_value ** (1 / years) - 1.0, 6) if end_value > 0 else None,
        "vol": round(vol, 6) if vol is not None else None,
        "sharpe": round(mean / vol, 4) if vol else None,  # daily, risk-free rate 0
        "maxDrawdown": round(float(_drawdown(equity).min()), 6),
        "avgTurnover": round(float(np.mean(turnovers)), 4) if turnovers else None,
        "annualTurnover": round(float(sum(turnovers) / years), 4),
        "totalCost": round(float(sum(costs)), 6),
        "rebalances": len(turnovers),
        "years": round(years, 2),
    }


def run_pass(data: pit.PITData, feed: pit.Feed, runner, start, end, *, rebalance: str = "M",
             cost_bps: float = 10.0, params: dict | None = None) -> dict:
    """One backtest from ``start`` to ``end`` with the strategy behind ``runner``."""
    if rebalance not in REBALANCE_RULES:
        raise ValueError(f"unsupported rebalance {rebalance!r}; use one of {REBALANCE_RULES}")
    px = data.frames["adj_close"]
    dates = pit.rebalance_dates(px.index, start, end, rebalance)
    if len(dates) < 2:
        raise ValueError("the window holds fewer than two rebalance dates")
    last_day = px.index[px.index <= pd.Timestamp(end)][-1]
    held_px = px.ffill()  # a position whose prices end is carried at its last stored price
    runner.begin(dict(params or {}))
    rate = cost_bps / 10_000.0

    equity_parts: list[pd.Series] = []
    level, holdings = 1.0, {}
    turnovers, costs, log, excluded = [], [], [], {}
    stale = 0
    for i, t in enumerate(dates):
        msg, gaps = feed.step(t)
        day = msg["date"]
        for g in gaps:
            excluded.setdefault(g["symbol"], dict(symbol=g["symbol"], firstDate=day, reason=g["reason"]))
        w = _validate(runner.weights(msg, holdings, lambda s, _t=t: data.facts(s, _t)), msg["universe"], day)
        traded = sum(abs(w.get(s, 0.0) - holdings.get(s, 0.0)) for s in set(w) | set(holdings))
        cost = traded * rate
        level *= 1.0 - cost
        turnovers.append(traded / 2.0)
        costs.append(cost)
        log.append(dict(date=day, members=len(msg["universe"]), positions=len(w),
                        turnover=round(traded / 2.0, 4), cost=round(cost, 6)))

        stop = dates[i + 1] if i + 1 < len(dates) else last_day
        window = held_px.loc[t:stop]
        if w:
            syms = list(w)
            growth = window[syms] / window[syms].iloc[0]
            stale += int((px.loc[t:stop, syms].iloc[-1].isna()).sum())
            weights = pd.Series(w)
            value = (1.0 - weights.sum()) + growth.mul(weights, axis=1).sum(axis=1)
            end_value = float(value.iloc[-1])
            holdings = {s: float(weights[s] * growth[s].iloc[-1] / end_value) for s in syms} if end_value > 0 else {}
        else:
            value = pd.Series(1.0, index=window.index)
            holdings = {}
        part = level * value
        equity_parts.append(part if i == 0 else part.iloc[1:])
        level = float(part.iloc[-1])
        if level <= 0:
            raise StrategyError(f"{day}: the portfolio lost all its equity")

    equity = pd.concat(equity_parts)
    daily = equity.pct_change().fillna(equity.iloc[0] - 1.0)  # day one: the first trades' cost
    return {
        "metrics": _metrics(daily, equity, turnovers, costs),
        "equityCurve": [dict(date=d.date().isoformat(), value=round(float(v), 6)) for d, v in equity.items()],
        "drawdown": [dict(date=d.date().isoformat(), value=round(float(v), 6))
                     for d, v in _drawdown(equity).items()],
        "rebalanceLog": log,
        "excluded": sorted(excluded.values(), key=lambda e: e["symbol"]),
        "positionsWithoutExitPrice": stale,
        "start": dates[0].date().isoformat(),
        "end": last_day.date().isoformat(),
    }


def backtest(source: str, name: str = "strategy.py", *, index: str = "sp500", start, end,
             rebalance: str = "M", cost_bps: float = 10.0, params: dict | None = None,
             runner_factory=InProcessRunner) -> dict:
    """Backtest one strategy file over the point-in-time ``index`` universe."""
    digest = check_source(source)
    t0 = time.perf_counter()
    data = pit.PITData(index, start, end)
    runner = runner_factory(source)
    try:
        result = run_pass(data, pit.Feed(data), runner, start, end,
                          rebalance=rebalance, cost_bps=cost_bps, params=params)
    finally:
        sandbox = runner.close()
    result.update(
        available=True,
        strategy={"name": name, "sha256": digest, "bytes": len(source.encode("utf-8"))},
        settings={"index": index, "start": result["start"], "end": result["end"], "rebalance": rebalance,
                  "costBps": cost_bps, "params": dict(params or {})},
        snapshot=data.snapshot(),
        sandbox={**runner.sandbox, **(sandbox or {})},
        seconds=round(time.perf_counter() - t0, 2),
    )
    return result
