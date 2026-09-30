"""Shared sub-annual → annual conversion for the macro source adapters.

Audit D-03 / P2-25: every adapter used ``resample("YE")``, which turns the
current, still-running year into a "full-year" value — a year-to-date mean of
monthly CPI, or the average of the first two quarters of GDP growth, shown as
the annual figure. A year is now emitted only once it is *complete*: the
series has an observation in the final period of that year for its own
frequency (December for monthly data, Q4 for quarterly, the last trading days
for daily/weekly data).

YoY conversions need the year before ``start``; callers fetch from
``start - 1`` so the first requested year is not dropped.
"""
from __future__ import annotations

import pandas as pd


def complete_years(s: pd.Series) -> set[int]:
    """Calendar years for which ``s`` has reached its final period."""
    s = s.dropna()
    if s.empty:
        return set()
    idx = pd.DatetimeIndex(pd.to_datetime(s.index)).sort_values()
    if len(idx) < 2:
        step_days = 365.0
    else:
        step_days = float(pd.Series(idx).diff().dt.days.median())
    # How close to 31 Dec the last observation of a year must be: one period
    # (with slack for month/quarter start dating), never less than a week so
    # daily data survives a year ending on a weekend or holiday.
    tolerance = pd.Timedelta(days=max(step_days * 1.1, 7.0))
    last_per_year = pd.Series(idx, index=idx.year).groupby(level=0).max()
    return {int(y) for y, last in last_per_year.items()
            if last >= pd.Timestamp(int(y), 12, 31) - tolerance}


def to_annual(s: pd.Series, method: str, start: int, end: int) -> list[tuple[int, float]]:
    """Annualise a dated series, keeping only complete years in [start, end].

    ``method``: ``"mean"`` (rates, levels), ``"sum"`` (flows) or ``"yoy"``
    (% change of the annual mean — needs the prior complete year).
    """
    if s is None or len(s) == 0:
        return []
    s = pd.to_numeric(s, errors="coerce").dropna()
    s.index = pd.to_datetime(s.index)
    if s.empty:
        return []
    done = complete_years(s)
    grouped = s[s.index.year.isin(list(done))].groupby(s.index.year)
    annual = grouped.sum() if method == "sum" else grouped.mean()
    if method == "yoy":
        # Only adjacent complete years form a valid YoY pair.
        prev = annual.shift(1)
        adjacent = annual.index.to_series().diff() == 1
        annual = ((annual / prev - 1.0) * 100.0).where(adjacent)
    return sorted((int(y), float(v)) for y, v in annual.dropna().items()
                  if start <= y <= end)
