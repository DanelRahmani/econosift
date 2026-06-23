"""Shared lightweight data shapes."""
from __future__ import annotations

from typing import TypedDict


class DataPoint(TypedDict):
    year: str
    value: float


class SeriesResult(TypedDict):
    country: str
    countryName: str
    data: list[DataPoint]
    source_label: str


def make_series(country: str, country_name: str,
                points: list[tuple[int, float]], source_label: str) -> SeriesResult:
    data: list[DataPoint] = [
        {"year": str(int(y)), "value": float(v)}
        for y, v in points
        if v is not None
    ]
    return {
        "country": country,
        "countryName": country_name,
        "data": data,
        "source_label": source_label,
    }
