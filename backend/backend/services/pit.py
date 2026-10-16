"""Point-in-time data for backtests (Phase 70, plan §5).

``PITData`` loads, once per run, everything a backtest over one index may need:
the index's membership intervals, the stored daily bars of every symbol that
was a member during the run, its splits, and lazily its SEC facts. It is the
trusted side of the harness and may hold data past any rebalance date.

``Feed`` turns it into the messages a ``strategy_context.Panel`` reads, one per
rebalance date ``t``, and is the only thing that decides what a strategy can
see. On ``t`` that is:

- **members**: symbols in the index on ``t`` (added on or before ``t``, removed
  after it). A member with no stored bar in the last ``GAP_DAYS`` is excluded
  and listed with the reason, never filled;
- **prices**: bars up to and including ``t`` (decisions use the close of ``t``;
  the position earns from ``t`` on), only for symbols that had joined the index
  by then. Yahoo's stored levels are adjusted for every split up to today, so
  each view is rescaled to what was quoted on ``t``: a later split or dividend
  changes nothing a strategy sees;
- **fundamentals**: SEC facts filed *before* ``t`` (a filing dated ``t`` may
  have come out after that day's close).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .. import fetcher, fundamentals_store, store
from .strategy_context import FIELDS

GAP_DAYS = 10            # a member with no bar this many days before t is excluded on t
WARMUP_DAYS = 400        # history shown before the first rebalance (a 12-1 momentum needs ~380)
INDEXES = ("sp500", "ndx", "dow")


def _iso(t) -> str:
    return pd.Timestamp(t).date().isoformat()


class PITData:
    def __init__(self, index: str, start, end, warmup_days: int = WARMUP_DAYS) -> None:
        if index not in INDEXES:
            raise ValueError(f"unknown index {index!r}; use one of {INDEXES}")
        self.index = index
        self.start, self.end = pd.Timestamp(start), pd.Timestamp(end)
        if self.end <= self.start:
            raise ValueError("end must be after start")
        self.load_from = self.start - pd.Timedelta(days=warmup_days)
        lo, hi = _iso(self.load_from), _iso(self.end)
        _facts.cache_clear()  # facts may have been stored since the last run

        with store.connect() as conn:
            rows = conn.execute(
                "SELECT symbol, start, end FROM index_membership WHERE index_name = ? "
                "AND start <= ? AND (end IS NULL OR end > ?)", (index, hi, lo)).fetchall()
        self.intervals: dict[str, list[tuple[str, str | None]]] = {}
        for sym, s, e in rows:
            self.intervals.setdefault(sym, []).append((s, e))
        self.membership_rows = len(rows)
        if not self.intervals:
            raise ValueError(f"no stored {index} membership overlaps {lo}..{hi}")

        syms = sorted(self.intervals)
        self.frames = store.frames(syms, FIELDS, lo, hi)
        for f in FIELDS:  # one shared column order; a symbol with no bars has no column
            self.frames[f] = self.frames[f].reindex(columns=self.frames["adj_close"].columns)
        self.stored = set(self.frames["adj_close"].columns)
        self._index = self.frames["adj_close"].index
        close_ff = self.frames["close"].ffill()
        self._close_over_adj = close_ff / self.frames["adj_close"].ffill()

        marks = ", ".join("?" * len(syms))
        with store.connect() as conn:
            self.failed = {r[0] for r in conn.execute(
                f"SELECT key FROM fetch_queue WHERE kind = 'history' AND attempts >= ? AND key IN ({marks})",
                (fetcher.MAX_ATTEMPTS, *syms))}
            splits = conn.execute(
                f"SELECT symbol, date, value FROM corporate_action WHERE type = 'split' AND value > 0 "
                f"AND date > ? AND symbol IN ({marks})", (lo, *syms)).fetchall()
        self.splits: dict[str, list[tuple[pd.Timestamp, float]]] = {}
        for sym, day, ratio in splits:
            self.splits.setdefault(sym, []).append((pd.Timestamp(day), float(ratio)))
        self.split_rows = len(splits)

    # -- membership -------------------------------------------------------
    def first_joined(self, sym: str) -> str:
        return min(s for s, _ in self.intervals[sym])

    def is_member(self, sym: str, t) -> bool:
        day = _iso(t)
        return any(s <= day and (e is None or e > day) for s, e in self.intervals.get(sym, ()))

    def members(self, t) -> tuple[list[str], list[dict]]:
        """(tradable members on ``t``, excluded members with the reason)."""
        t = pd.Timestamp(t)
        recent = self.frames["adj_close"].loc[t - pd.Timedelta(days=GAP_DAYS):t].notna().any()
        tradable, excluded = [], []
        for sym in sorted(self.intervals):
            if not self.is_member(sym, t):
                continue
            if sym in self.stored and bool(recent.get(sym, False)):
                tradable.append(sym)
            elif sym in self.stored:
                excluded.append(dict(symbol=sym, reason=f"no stored bar in the {GAP_DAYS} days before this date"))
            elif sym in self.failed:
                excluded.append(dict(symbol=sym, reason="Yahoo has no history for this symbol"))
            else:
                excluded.append(dict(symbol=sym, reason="history not fetched yet"))
        return tradable, excluded

    # -- price levels as quoted on t ----------------------------------------
    def split_factor(self, t) -> pd.Series:
        """Per symbol, the product of splits after ``t``: stored levels x this = as quoted on ``t``."""
        t = pd.Timestamp(t)
        out = pd.Series(1.0, index=self.frames["adj_close"].columns)
        for sym, events in self.splits.items():
            if sym in out.index:
                out[sym] = float(np.prod([r for d, r in events if d > t])) if events else 1.0
        return out

    def scale(self, t) -> dict[str, pd.Series]:
        """Per field, the factor that rescales stored levels to ``t``'s basis."""
        p = self.split_factor(t)
        pos = self._index.searchsorted(pd.Timestamp(t), side="right") - 1
        c_over_a = self._close_over_adj.iloc[pos] if pos >= 0 else pd.Series(np.nan, index=p.index)
        return {"close": p, "volume": 1.0 / p, "adj_close": c_over_a * p}

    def facts(self, symbol: str, t) -> dict:
        """SEC facts filed before ``t``."""
        return _facts(symbol, _iso(pd.Timestamp(t) - pd.Timedelta(days=1)))

    def snapshot(self) -> dict:
        """What the run read, so a rerun on the same store can be checked against it."""
        with store.connect() as conn:
            price_max = conn.execute("SELECT MAX(date) FROM price_daily").fetchone()[0]
            filed_max = conn.execute("SELECT MAX(filed) FROM fundamental").fetchone()[0]
        return {
            "priceMaxDate": price_max,
            "fundamentalMaxFiled": filed_max,
            "index": self.index,
            "loadedFrom": _iso(self.load_from),
            "loadedTo": _iso(self.end),
            "membershipRows": self.membership_rows,
            "symbols": len(self.intervals),
            "symbolsWithPrices": len(self.stored),
            "priceRows": int(self.frames["adj_close"].notna().sum().sum()),
            "splitRows": self.split_rows,
        }


@lru_cache(maxsize=4096)
def _facts(symbol: str, as_of: str) -> dict:
    fx, _origin = fundamentals_store.facts(symbol, as_of=as_of)
    return {concept: {end: dict(value=v["value"], filed=v["filed"], form=v["form"]) for end, v in ends.items()}
            for concept, ends in fx.items()}


def _block(frames: dict[str, pd.DataFrame], rows, cols: list[str], scale: dict[str, pd.Series]) -> dict | None:
    if not cols or not rows.any():
        return None
    idx = frames["adj_close"].index[rows]
    return {"index": [d.date().isoformat() for d in idx], "columns": cols,
            "data": {f: (frames[f].loc[rows, cols] * scale[f][cols]).to_numpy().tolist() for f in FIELDS}}


class Feed:
    """Messages for a strategy's ``Panel``: what is visible on each rebalance date.

    Dates may repeat or go back (walk-forward reruns a window), but the panel only
    ever advances: a date before the newest one shown is served from bars already
    shown, rescaled to that date (``rel``).
    """

    def __init__(self, data: PITData) -> None:
        self.data = data
        self.asof: pd.Timestamp | None = None
        self.shown: list[str] = []
        self._scale: dict[str, pd.Series] | None = None

    def step(self, t) -> tuple[dict, list[dict]]:
        """(message for the strategy's process, excluded members with reasons)."""
        t = pd.Timestamp(t)
        universe, excluded = self.data.members(t)
        msg: dict = {"date": _iso(t), "universe": universe, "excluded": [e["symbol"] for e in excluded]}
        if self.asof is None or t > self.asof:
            msg["panel"] = self._advance(t)
        if t < self.asof:
            msg["rel"] = self._ratio(self.data.scale(t), self._scale, self.shown)
        return msg, excluded

    def _advance(self, t: pd.Timestamp) -> dict:
        d = self.data
        new_scale = d.scale(t)
        idx = d.frames["adj_close"].index
        joined = [s for s in d.frames["adj_close"].columns
                  if s not in self.shown and self.data.first_joined(s) <= _iso(t)]
        msg: dict = {"asof": _iso(t)}
        if self.asof is not None:
            msg["rescale"] = self._ratio(new_scale, self._scale, self.shown)
            msg["append"] = _block(d.frames, (idx > self.asof) & (idx <= t), self.shown, new_scale)
        msg["add"] = _block(d.frames, idx <= t, joined, new_scale)
        self.shown = self.shown + joined
        self.asof, self._scale = t, new_scale
        return msg

    @staticmethod
    def _ratio(num: dict[str, pd.Series], den: dict[str, pd.Series], cols: list[str]) -> dict:
        out = {}
        for f in FIELDS:
            r = (num[f][cols] / den[f][cols]).replace([np.inf, -np.inf], np.nan)
            r = r[r.notna() & ((r - 1.0).abs() > 1e-12)]
            if len(r):
                out[f] = {k: float(v) for k, v in r.items()}
        return out


def rebalance_dates(index: pd.DatetimeIndex, start, end, rule: str) -> list[pd.Timestamp]:
    """The last trading date of each period between ``start`` and ``end``."""
    rules = {"W": "W-FRI", "M": "ME", "Q": "QE"}
    if rule not in rules:
        raise ValueError(f"unsupported rebalance {rule!r}; use one of {list(rules)}")
    days = index[(index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))]
    s = pd.Series(days, index=days)
    return [pd.Timestamp(x) for x in s.resample(rules[rule]).last().dropna()]
