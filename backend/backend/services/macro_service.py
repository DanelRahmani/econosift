"""Macro orchestration: priority waterfall + merge across 7 sources."""
from __future__ import annotations

import asyncio

from .. import provenance as pv
from ..config import EUROZONE, INDICATOR_UNITS, INDICATORS
from ..models import SeriesResult
from ..sources import (
    source_fred, source_worldbank, source_ecb, source_imf,
    source_dbnomics, source_datareader, source_frankfurter,
)


def _source_order(indicator: str, countries: tuple[str, ...]) -> list:
    """Return ranked list of source modules (highest priority first)."""
    if indicator == "exchange_rates":
        return [source_frankfurter]
    if indicator == "debt_gdp":
        # General-government debt (IMF WEO) for every country first: the World
        # Bank and FRED series are central-government only, and switching
        # definitions mid-series created level breaks (e.g. Korea 47.8 → 52.3).
        return [source_imf, source_worldbank, source_dbnomics]

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
    """Merge per country+year, preferring higher-ranked sources.

    Each point keeps the provider that supplied it; the series label lists
    every provider actually used (previously the first provider's label was
    applied to the whole series even when others filled gaps).
    """
    merged: dict[str, dict] = {}
    for results in ranked_results:  # highest priority first
        for s in results:
            country = s["country"]
            entry = merged.setdefault(country, {
                "country": country,
                "countryName": s["countryName"],
                "_years": {},
            })
            for pt in s["data"]:
                year = pt["year"]
                if year not in entry["_years"]:
                    entry["_years"][year] = {**pt, "src": pt.get("src") or s["source_label"]}

    out: list[SeriesResult] = []
    for country, entry in merged.items():
        years = entry.pop("_years")
        data = [years[y] for y in sorted(years)]
        if not data:
            continue
        labels = list(dict.fromkeys(p["src"] for p in data))
        out.append({
            "country": country,
            "countryName": entry["countryName"],
            "source_label": " + ".join(labels),
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


def _series_id(label: str, indicator: str, iso2: str) -> tuple[str | None, str | None, str | None]:
    """(series id, transform, url) of the provider that ``label`` names, for this indicator and country."""
    annual = "annual mean of the source series (complete years only)"
    yoy = "% change of the annual mean (complete years only)"
    if label in (source_fred.SOURCE_LABEL, source_datareader.SOURCE_LABEL):
        mapping = source_fred.INDICATOR_MAP.get(indicator)
        return (mapping[0], yoy if mapping[1] == "yoy" else annual, None) if mapping else (None, None, None)
    if label == source_worldbank.SOURCE_LABEL:
        return source_worldbank.INDICATOR_MAP.get(indicator), None, None
    if label == source_imf.SOURCE_LABEL:
        return source_imf.INDICATOR_MAP.get(indicator), None, None
    if label.startswith("ECB"):
        key = (f"ICP.M.{source_ecb.ECB_COUNTRY.get(iso2)}.N.000000.4.ANR" if indicator == "inflation"
               else source_ecb.POLICY_RATE_KEY)
        return key, annual, f"https://data.ecb.europa.eu/data/datasets/{key.split('.')[0]}/{key}"
    if label == source_dbnomics.SOURCE_LABEL:
        method = source_dbnomics._METHOD.get(indicator, "mean")
        return source_dbnomics._series_path(indicator, iso2), yoy if method == "yoy" else annual, None
    return None, None, None


def data_provenance(indicator: str, series: list[SeriesResult]) -> dict:
    """Provenance for a ``get_macro_data`` result (a bare list, so the router attaches this).

    ``series.<ISO2>`` lists one ref per provider that actually supplied points for that country (the
    waterfall mixes providers by year); IMF projection years carry the ``estimate`` flag. Points also carry
    their own ``src`` / ``estimate``.
    """
    prov: dict = {"*": pv.derived(
        "annual series merged per country and year from the highest-priority provider that has that year "
        "(FRED, pandas-datareader, ECB, World Bank, IMF WEO, DB.nomics); each point keeps its provider in `src`",
        title=next((i["label"] for i in INDICATORS if i["id"] == indicator), indicator))}
    for s in series:
        refs = []
        for label in dict.fromkeys(p["src"] for p in s["data"] if p.get("src")):
            pts = [p for p in s["data"] if p["src"] == label]
            est = any(p.get("estimate") for p in pts)
            if label == source_frankfurter.SOURCE_LABEL:
                refs.append(pv.ref("frankfurter", None, label, units=get_unit(indicator), observed=pts[-1]["year"]))
                continue
            sid, transform, url = _series_id(label, indicator, s["country"])
            refs.append(pv.label_to_ref(
                label, series=sid, units=get_unit(indicator), frequency="annual", observed=pts[-1]["year"],
                transform=transform, url=url, flags=("estimate",) if est else (),
                note="Includes IMF projection years (points flagged `estimate`)." if est else None))
        if refs:
            prov[f"series.{s['country']}"] = refs
    return prov


# Headline indicators shown on the country comparison snapshot. All are well
# covered by World Bank (fast); avoiding IMF-only series keeps the cards snappy.
SNAPSHOT_INDICATORS = [
    "gdp_growth", "inflation", "unemployment",
    "debt_gdp", "current_account", "gdp_per_capita",
]


async def get_snapshot(countries: list[str], year: int) -> dict:
    """Latest value of each headline indicator per country (for comparison cards).

    Sourced directly from World Bank (fast, broad coverage) rather than the full
    waterfall, so the cards stay responsive — gaps simply render as "—".
    """
    countries_t = tuple(countries)
    tasks = {
        ind: source_worldbank.fetch(ind, countries_t, year - 8, year)
        for ind in SNAPSHOT_INDICATORS
    }
    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)

    # indicator -> { iso2 -> {value, year} }
    by_indicator: dict[str, dict] = {}
    for ind, res in zip(tasks.keys(), gathered):
        values: dict[str, dict] = {}
        if isinstance(res, list):
            for s in res:
                if s["data"]:
                    latest = s["data"][-1]
                    values[s["country"]] = {"value": latest["value"], "year": latest["year"]}
        by_indicator[ind] = values

    labels = {i["id"]: i["label"] for i in INDICATORS}
    prov: dict = {"*": pv.ref("worldbank", None, "World Development Indicators", frequency="annual")}
    for ind in SNAPSHOT_INDICATORS:
        years = [v["year"] for v in by_indicator.get(ind, {}).values()]
        prov[f"indicators.{ind}"] = pv.ref(
            "worldbank", source_worldbank.INDICATOR_MAP.get(ind), labels.get(ind, ind), units=get_unit(ind),
            frequency="annual", observed=max(years) if years else None,
            note="Latest year available per country; each value carries its own `year`.")
    return pv.attach({
        "countries": countries,
        "indicators": [
            {"id": ind, "unit": get_unit(ind), "values": by_indicator.get(ind, {})}
            for ind in SNAPSHOT_INDICATORS
        ],
    }, prov)
