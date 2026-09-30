"""Shared lightweight data shapes."""
from __future__ import annotations

from typing import NotRequired, TypedDict


class DataPoint(TypedDict):
    year: str
    value: float
    # Provider that supplied this point (the macro waterfall mixes providers
    # within one series, so a single series-level label is not enough).
    src: NotRequired[str]
    # True for projections (e.g. IMF WEO years that have not happened yet).
    estimate: NotRequired[bool]


class SeriesResult(TypedDict):
    country: str
    countryName: str
    data: list[DataPoint]
    source_label: str


def make_series(country: str, country_name: str,
                points: list[tuple[int, float]], source_label: str,
                estimate_from: int | None = None) -> SeriesResult:
    """Build a series; points from ``estimate_from`` onward are projections."""
    data: list[DataPoint] = []
    for y, v in points:
        if v is None:
            continue
        pt: DataPoint = {"year": str(int(y)), "value": float(v), "src": source_label}
        if estimate_from is not None and int(y) >= estimate_from:
            pt["estimate"] = True
        data.append(pt)
    return {
        "country": country,
        "countryName": country_name,
        "data": data,
        "source_label": source_label,
    }
