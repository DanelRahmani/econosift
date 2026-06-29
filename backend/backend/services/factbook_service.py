"""Country Profiles service — REST Countries data (formerly OpenFactbook).

Loads countries.json (from bulk data or manual placement) and provides
country list and per-country profile with structured sections.

Data source: https://github.com/mledoze/countries (REST Countries format)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..cache import cached

logger = logging.getLogger(__name__)

# Paths: try bulk-download location first, then manual placement
# Bulk data service stores in /app/data/bulk/ — same as other bulk datasets
_DATA_DIR = Path("/app/data") if Path("/app/data").exists() else (Path(__file__).resolve().parent.parent / "data")
_BULK_PATH = _DATA_DIR / "bulk" / "factbook.json"
_MANUAL_PATH = Path(__file__).resolve().parent.parent / "data" / "factbook.json"


def _resolve_path() -> Path | None:
    if _BULK_PATH.exists():
        return _BULK_PATH
    if _MANUAL_PATH.exists():
        return _MANUAL_PATH
    return None


@cached("factbook_data")
def _load_data() -> dict:
    """Load and index the countries JSON. Returns {by_iso2, by_iso3, list}."""
    path = _resolve_path()
    if not path:
        logger.warning("countries.json not found at %s or %s", _BULK_PATH, _MANUAL_PATH)
        return {"by_iso2": {}, "by_iso3": {}, "list": []}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse countries.json: %s", exc)
        return {"by_iso2": {}, "by_iso3": {}, "list": []}

    countries = raw if isinstance(raw, list) else raw.get("countries", [])
    if not isinstance(countries, list):
        countries = []

    by_iso2: dict[str, dict] = {}
    by_iso3: dict[str, dict] = {}
    country_list: list[dict] = []

    for entry in countries:
        if not isinstance(entry, dict):
            continue
        # mledoze/countries format: cca2, cca3, name.common, flag, region
        iso2 = (entry.get("cca2") or entry.get("ISO2") or entry.get("iso2") or "").upper()
        iso3 = (entry.get("cca3") or entry.get("ISO3") or entry.get("iso3") or "").upper()
        name_data = entry.get("name", {})
        if isinstance(name_data, dict):
            name = name_data.get("common") or name_data.get("official") or iso2
        else:
            name = entry.get("name") or entry.get("country") or iso2
        flag = entry.get("flag") or entry.get("Flag") or ""
        region = entry.get("region") or entry.get("continent") or ""

        if not iso2:
            continue

        info = {
            "iso2": iso2,
            "iso3": iso3,
            "name": str(name),
            "flag": str(flag),
            "region": str(region),
        }
        by_iso2[iso2] = entry
        if iso3:
            by_iso3[iso3] = entry
        country_list.append(info)

    country_list.sort(key=lambda c: c["name"])
    logger.info("Countries loaded: %d", len(country_list))
    return {"by_iso2": by_iso2, "by_iso3": by_iso3, "list": country_list}


def _extract_sections(entry: dict) -> list[dict]:
    """Build structured sections from mledoze/countries entry."""
    sections = []

    # Introduction
    name_data = entry.get("name", {})
    intro_fields = []
    if isinstance(name_data, dict):
        if name_data.get("official"):
            intro_fields.append({"label": "Official Name", "value": str(name_data["official"])})
        if name_data.get("common"):
            intro_fields.append({"label": "Common Name", "value": str(name_data["common"])})
    intro_fields.append({"label": "Region", "value": str(entry.get("region", "") or entry.get("subregion", ""))})
    subregion = entry.get("subregion", "")
    if subregion:
        intro_fields.append({"label": "Subregion", "value": str(subregion)})
    capital = entry.get("capital", [])
    if capital and isinstance(capital, list) and capital[0]:
        intro_fields.append({"label": "Capital", "value": str(capital[0])})
    if intro_fields:
        sections.append({"title": "Introduction", "fields": intro_fields})

    # Geography
    geo_fields = []
    area = entry.get("area")
    if area:
        geo_fields.append({"label": "Area", "value": f"{area:,} km²"})
    borders = entry.get("borders", [])
    if borders:
        geo_fields.append({"label": "Borders", "value": ", ".join(borders)})
    landlocked = entry.get("landlocked")
    if landlocked is not None:
        geo_fields.append({"label": "Landlocked", "value": "Yes" if landlocked else "No"})
    latlng = entry.get("latlng", [])
    if latlng and len(latlng) == 2:
        geo_fields.append({"label": "Coordinates", "value": f"{latlng[0]:.2f}, {latlng[1]:.2f}"})
    timezones = entry.get("timezones", [])
    if timezones:
        geo_fields.append({"label": "Timezones", "value": ", ".join(timezones)})
    if geo_fields:
        sections.append({"title": "Geography", "fields": geo_fields})

    # People
    people_fields = []
    pop = entry.get("population")
    if pop:
        people_fields.append({"label": "Population", "value": f"{pop:,}"})
    languages = entry.get("languages", {})
    if languages:
        lang_list = [v for v in languages.values() if v]
        if lang_list:
            people_fields.append({"label": "Languages", "value": ", ".join(lang_list)})
    if people_fields:
        sections.append({"title": "People & Society", "fields": people_fields})

    # Government
    gov_fields = []
    capital_info = entry.get("capitalInfo", {})
    if isinstance(capital_info, dict) and capital_info.get("latlng"):
        gov_fields.append({"label": "Capital", "value": str(capital or [""])[0] if capital else ""})
    currencies = entry.get("currencies", {})
    if currencies:
        cur_list = []
        for code, info in currencies.items():
            if isinstance(info, dict):
                cur_list.append(f"{info.get('name', code)} ({info.get('symbol', code)})")
            else:
                cur_list.append(code)
        if cur_list:
            gov_fields.append({"label": "Currencies", "value": ", ".join(cur_list)})
    tld = entry.get("tld", [])
    if tld:
        gov_fields.append({"label": "TLD", "value": ", ".join(tld)})
    independent = entry.get("independent")
    if independent is not None:
        gov_fields.append({"label": "Independent", "value": "Yes" if independent else "No"})
    unMember = entry.get("unMember")
    if unMember is not None:
        gov_fields.append({"label": "UN Member", "value": "Yes" if unMember else "No"})
    if gov_fields:
        sections.append({"title": "Government", "fields": gov_fields})

    # Economy
    econ_fields = []
    gini = entry.get("gini", {})
    if isinstance(gini, dict):
        for year, val in sorted(gini.items(), reverse=True):
            econ_fields.append({"label": f"Gini ({year})", "value": str(val)})
            break  # just latest
    if not econ_fields:
        # try top-level gini
        pass
    if econ_fields:
        sections.append({"title": "Economy", "fields": econ_fields})

    # Additional: demonyms, car, etc. — skip for brevity

    return sections


def get_country_list() -> list[dict]:
    """Return [{iso2, iso3, name, flag, region}] for all ~260 countries."""
    data = _load_data()
    return data["list"]


def get_country_profile(iso2: str) -> dict | None:
    """Return full profile for a country with structured sections."""
    iso2 = iso2.upper()
    data = _load_data()
    entry = data["by_iso2"].get(iso2)
    if not entry:
        entry = data["by_iso3"].get(iso2)
    if not entry:
        return None

    name_data = entry.get("name", {})
    if isinstance(name_data, dict):
        name = name_data.get("common") or name_data.get("official") or iso2
    else:
        name = entry.get("name") or iso2
    flag = entry.get("flag") or ""
    iso3 = (entry.get("cca3") or entry.get("ISO3") or "").upper()

    sections = _extract_sections(entry)

    return {
        "iso2": iso2,
        "iso3": iso3,
        "name": str(name),
        "flag": str(flag),
        "sections": sections,
    }
