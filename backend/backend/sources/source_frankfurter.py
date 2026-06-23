"""Frankfurter FX source (ECB FX data) via httpx."""
from __future__ import annotations

import httpx
import pandas as pd

from ..cache import async_cached
from ..config import COUNTRY_NAMES
from ..models import SeriesResult, make_series

SOURCE_LABEL = "Frankfurter (ECB FX data)"
BASE_URL = "https://api.frankfurter.dev/v1"

# ISO2 country -> its currency, for the exchange_rates macro indicator.
COUNTRY_CCY = {
    "US": "USD", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR",
    "NL": "EUR", "GB": "GBP", "JP": "JPY", "CN": "CNY", "CA": "CAD",
    "AU": "AUD", "CH": "CHF", "SE": "SEK", "NO": "NOK", "DK": "DKK",
    "PL": "PLN", "KR": "KRW", "IN": "INR", "BR": "BRL", "MX": "MXN",
}


@async_cached("fx_latest")
async def latest(base: str, targets: tuple[str, ...]) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(f"{BASE_URL}/latest",
                            params={"from": base, "to": ",".join(targets)})
            r.raise_for_status()
            data = r.json()
        return {"base": data.get("base", base), "date": data.get("date"),
                "rates": data.get("rates", {})}
    except Exception:
        return {"base": base, "date": None, "rates": {}}


@async_cached("fx_history")
async def history(base: str, targets: tuple[str, ...],
                  start: str, end: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            r = await c.get(f"{BASE_URL}/{start}..{end}",
                            params={"from": base, "to": ",".join(targets)})
            r.raise_for_status()
            data = r.json()
        rates = data.get("rates", {})
        series: dict[str, list[dict]] = {t: [] for t in targets}
        for date in sorted(rates.keys()):
            for ccy, val in rates[date].items():
                if ccy in series:
                    series[ccy].append({"date": date, "rate": float(val)})
        return {
            "base": data.get("base", base),
            "series": [{"currency": k, "data": v} for k, v in series.items()],
        }
    except Exception:
        return {"base": base, "series": []}


@async_cached("frankfurter_fetch")
async def fetch(indicator_key: str, countries: tuple[str, ...],
                start: int, end: int) -> list[SeriesResult]:
    """exchange_rates indicator: annual mean FX vs USD per country currency."""
    if indicator_key != "exchange_rates":
        return []
    targets = []
    ccy_to_country: dict[str, str] = {}
    for c in countries:
        ccy = COUNTRY_CCY.get(c)
        if ccy and ccy != "USD":
            targets.append(ccy)
            ccy_to_country[ccy] = c
    if not targets:
        return []
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(
                f"{BASE_URL}/{start}-01-01..{end}-12-31",
                params={"from": "USD", "to": ",".join(set(targets))})
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []

    rates = data.get("rates", {})
    # Build per-currency annual mean.
    frames: dict[str, list[tuple[int, float]]] = {}
    raw: dict[str, dict[int, list[float]]] = {}
    for date, day in rates.items():
        try:
            year = int(date[:4])
        except (ValueError, TypeError):
            continue
        for ccy, val in day.items():
            raw.setdefault(ccy, {}).setdefault(year, []).append(float(val))
    for ccy, by_year in raw.items():
        frames[ccy] = sorted((y, sum(v) / len(v)) for y, v in by_year.items())

    results: list[SeriesResult] = []
    for ccy, points in frames.items():
        country = ccy_to_country.get(ccy)
        if not country:
            continue
        results.append(make_series(
            country, COUNTRY_NAMES.get(country, country), points, SOURCE_LABEL))
    return results
