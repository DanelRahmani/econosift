"""Macro orchestration: priority waterfall + merge across 7 sources."""
from __future__ import annotations

import asyncio

from ..config import EUROZONE, INDICATOR_UNITS
from ..models import SeriesResult
from ..sources import (
    source_fred, source_worldbank, source_ecb, source_imf,
    source_dbnomics, source_datareader, source_frankfurter,
)


def _source_order(indicator: str, countries: tuple[str, ...]) -> list:
    """Return ranked list of source modules (highest priority first)."""
    if indicator == "exchange_rates":
        return [source_frankfurter]

    order: list = []
    has_us = "US" in countries
    has_euro = any(c in EUROZONE for c in countries)

    if has_us:
        order += [source_fred, source_datareader]
    if has_euro and indicator in ("inflation", "interest_rate"):
        order += [source_ecb]
    # Broad fallbacks for all countries.
    order += [source_worldbank, source_imf, source_dbnomics]

    # De-duplicate preserving order.
    seen = set()
    ranked = []
    for s in order:
        if s not in seen:
            ranked.append(s)
            seen.add(s)
    return ranked


def _merge(ranked_results: list[list[SeriesResult]]) -> list[SeriesResult]:
    """Merge per country+year, preferring higher-ranked sources."""
    merged: dict[str, dict] = {}
    for results in ranked_results:  # highest priority first
        for s in results:
            country = s["country"]
            entry = merged.setdefault(country, {
                "country": country,
                "countryName": s["countryName"],
                "source_label": s["source_label"],
                "_years": {},
            })
            for pt in s["data"]:
                year = pt["year"]
                if year not in entry["_years"]:
                    entry["_years"][year] = pt["value"]

    out: list[SeriesResult] = []
    for country, entry in merged.items():
        years = entry.pop("_years")
        data = [{"year": y, "value": v} for y, v in sorted(years.items())]
        if not data:
            continue
        out.append({
            "country": country,
            "countryName": entry["countryName"],
            "source_label": entry["source_label"],
            "data": data,
        })
    return out


async def get_macro_data(indicator: str, countries: list[str],
                         start: int, end: int) -> list[SeriesResult]:
    countries_t = tuple(countries)
    ranked = _source_order(indicator, countries_t)

    results_by_rank: list[list[SeriesResult]] = []
    for src in ranked:
        try:
            res = await src.fetch(indicator, countries_t, start, end)
        except Exception:
            res = []
        results_by_rank.append(res or [])
        # Early exit if every requested country already has data.
        covered = {s["country"] for r in results_by_rank for s in r if s["data"]}
        if all(c in covered for c in countries_t):
            break

    return _merge(results_by_rank)


def get_unit(indicator: str) -> str:
    return INDICATOR_UNITS.get(indicator, "")
