"""What a strategy sees at a rebalance date (Phase 70).

This module is the strategy's side of the backtest harness. It imports only
the standard library, numpy and pandas, so the sandboxed child process can load
it without the rest of the backend (no database, no config, no API keys).

The harness (``pit.Feed``) sends it messages; nothing else fills a ``Panel``.
A message carries only data knowable on its date: bars up to that date, for
symbols that had joined the index by then, rescaled so that levels are what
was quoted then (a later split or dividend never shows). So whatever a
strategy does with this process's memory, it cannot reach a later bar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FIELDS = ("adj_close", "close", "volume")


def _block(b: dict) -> dict[str, pd.DataFrame]:
    idx = pd.DatetimeIndex(pd.to_datetime(b["index"]))
    return {f: pd.DataFrame(np.asarray(b["data"][f], dtype=float).reshape(len(idx), len(b["columns"])),
                            index=idx, columns=list(b["columns"]))
            for f in FIELDS}


class Panel:
    """Every bar shown so far, scaled to the newest date shown (``asof``)."""

    def __init__(self) -> None:
        self.asof: pd.Timestamp | None = None
        self.frames = {f: pd.DataFrame(dtype=float) for f in FIELDS}

    def apply(self, msg: dict) -> None:
        """Advance to ``msg['asof']``: rescale stored bars, append new ones, add newly joined symbols."""
        for f, factors in (msg.get("rescale") or {}).items():
            frame = self.frames[f]
            cols = [c for c in factors if c in frame.columns]
            if cols:
                frame[cols] = frame[cols] * pd.Series({c: factors[c] for c in cols})
        if msg.get("append"):
            new = _block(msg["append"])
            for f in FIELDS:
                self.frames[f] = pd.concat([self.frames[f], new[f]]) if len(self.frames[f].columns) else new[f]
        if msg.get("add"):
            new = _block(msg["add"])
            for f in FIELDS:
                self.frames[f] = new[f] if self.frames[f].empty and not len(self.frames[f].columns) \
                    else self.frames[f].join(new[f], how="outer")
        self.asof = pd.Timestamp(msg["asof"])


class StrategyContext:
    """The argument of ``generate_weights(ctx)``.

    ``date``       the rebalance date (decisions use its close)
    ``universe``   index members on ``date`` with a stored price near it
    ``excluded``   members on ``date`` left out because no price is stored for them
    ``params``     the run's parameters (walk-forward fills these from its grid)
    ``holdings``   current weights, after drifting with prices since the last rebalance
    """

    def __init__(self, panel: Panel, step: dict, params: dict | None = None,
                 holdings: dict | None = None, fundamentals_fn=None) -> None:
        self._panel = panel
        self.date = pd.Timestamp(step["date"])
        if panel.asof is None or self.date > panel.asof:
            raise ValueError("the harness has not shown data up to this date")
        self.universe: list[str] = list(step["universe"])
        self.excluded: list[str] = list(step.get("excluded", []))
        self.params: dict = dict(params or {})
        self.holdings: dict[str, float] = dict(holdings or {})
        self._rel = step.get("rel") or {}
        self._fundamentals_fn = fundamentals_fn

    def prices(self, field: str = "adj_close", lookback: int | None = None,
               symbols=None) -> pd.DataFrame:
        """Daily bars up to and including ``date``: dates x symbols (default: ``universe``).

        ``adj_close`` is total-return adjusted as of ``date``; ``close`` is the
        price quoted then; ``volume`` is shares traded. ``lookback`` keeps the
        last N rows.
        """
        if field not in FIELDS:
            raise ValueError(f"unknown field {field!r}; use one of {FIELDS}")
        frame = self._panel.frames[field]
        cols = [s for s in (self.universe if symbols is None else symbols) if s in frame.columns]
        out = frame.loc[:self.date, cols]
        if lookback is not None:
            out = out.iloc[-int(lookback):]
        rel = self._rel.get(field)
        if rel:  # an earlier date than the panel's newest: undo splits/dividends after it
            out = out * pd.Series({c: rel.get(c, 1.0) for c in cols}, dtype=float)
        return out.copy()

    def fundamentals(self, symbol: str) -> dict:
        """SEC facts filed before ``date``: {concept: {period_end: {value, filed, form}}}."""
        if symbol not in self.universe:
            raise KeyError(f"{symbol} is not an index member on {self.date.date()}")
        if self._fundamentals_fn is None:
            return {}
        return self._fundamentals_fn(symbol)
