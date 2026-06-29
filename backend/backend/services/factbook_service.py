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
    """Build comprehensive structured sections from mledoze/countries entry."""
    sections = []
    name_data = entry.get("name", {}) if isinstance(entry.get("name"), dict) else {}
    capital = entry.get("capital", [])
    capital_str = capital[0] if isinstance(capital, list) and capital else ""

    # ── Introduction ──
    intro = []
    if name_data.get("official"):
        intro.append({"label": "Official Name", "value": str(name_data["official"])})
    if name_data.get("common"):
        intro.append({"label": "Common Name", "value": str(name_data["common"])})
    # Native names
    native = name_data.get("native", {})
    if isinstance(native, dict):
        for lang_code, lang_name in native.items():
            if isinstance(lang_name, dict):
                off = lang_name.get("official", "")
                if off and off != name_data.get("official", ""):
                    intro.append({"label": f"Native Name ({lang_code})", "value": str(off)})
    intro.append({"label": "Capital", "value": capital_str or "N/A"})
    intro.append({"label": "Region", "value": str(entry.get("region", "") or "N/A")})
    sub = entry.get("subregion", "")
    if sub:
        intro.append({"label": "Subregion", "value": str(sub)})
    status = entry.get("status", "")
    if status:
        intro.append({"label": "Status", "value": str(status)})
    indep = entry.get("independent")
    if indep is not None:
        intro.append({"label": "Independent", "value": "Yes" if indep else "No"})
    un = entry.get("unMember")
    if un is not None:
        intro.append({"label": "UN Member", "value": "Yes" if un else "No"})
    sections.append({"title": "Introduction", "fields": intro})

    # ── Geography ──
    geo = []
    area = entry.get("area")
    if area:
        geo.append({"label": "Area", "value": f"{area:,} km² ({area * 0.3861:,.0f} sq mi)"})
    borders = entry.get("borders", [])
    if isinstance(borders, list):
        geo.append({"label": "Borders", "value": f"{len(borders)} countries — {', '.join(borders) if borders else 'None (island)'}"})
    landlocked = entry.get("landlocked")
    if landlocked is not None:
        geo.append({"label": "Landlocked", "value": "Yes" if landlocked else "No"})
    latlng = entry.get("latlng", [])
    if isinstance(latlng, list) and len(latlng) == 2:
        geo.append({"label": "Coordinates", "value": f"{latlng[0]:.2f}, {latlng[1]:.2f}"})
    sections.append({"title": "Geography", "fields": geo})

    # ── People & Society ──
    people = []
    languages = entry.get("languages", {})
    if isinstance(languages, dict) and languages:
        lang_list = [f"{name} ({code})" for code, name in languages.items()]
        people.append({"label": "Languages", "value": ", ".join(lang_list)})
    demonyms = entry.get("demonyms", {})
    if isinstance(demonyms, dict):
        for lang, d in demonyms.items():
            if isinstance(d, dict):
                m = d.get("m", "")
                f = d.get("f", "")
                if m or f:
                    people.append({"label": f"Demonym ({lang})", "value": f"♂ {m} / ♀ {f}" if m and f else (m or f)})
    if not people:
        people.append({"label": "Note", "value": "Population data not available in this dataset"})
    sections.append({"title": "People & Society", "fields": people})

    # ── Government ──
    gov = []
    gov.append({"label": "Capital", "value": capital_str or "N/A"})
    currencies = entry.get("currencies", {})
    if isinstance(currencies, dict) and currencies:
        cur_list = [f"{info.get('name', code)} ({info.get('symbol', code)})" if isinstance(info, dict) else str(code)
                    for code, info in currencies.items()]
        gov.append({"label": "Currencies", "value": ", ".join(cur_list)})
    idd = entry.get("idd", {})
    if isinstance(idd, dict):
        root = idd.get("root", "")
        suffixes = idd.get("suffixes", [])
        if root:
            if suffixes:
                gov.append({"label": "Calling Code", "value": f"{root} (x{suffixes[0]}) — {len(suffixes)} area codes"})
            else:
                gov.append({"label": "Calling Code", "value": str(root)})
    tld = entry.get("tld", [])
    if tld:
        gov.append({"label": "Internet TLD", "value": ", ".join(str(t) for t in tld)})
    sections.append({"title": "Government & Communications", "fields": gov})

    # ── International Codes ──
    codes = []
    codes.append({"label": "ISO 3166-1 Alpha-2", "value": str(entry.get("cca2", ""))})
    codes.append({"label": "ISO 3166-1 Alpha-3", "value": str(entry.get("cca3", ""))})
    ccn3 = entry.get("ccn3", "")
    if ccn3:
        codes.append({"label": "ISO 3166-1 Numeric", "value": str(ccn3)})
    cioc = entry.get("cioc", "")
    if cioc:
        codes.append({"label": "IOC Code", "value": str(cioc)})
    alt_spell = entry.get("altSpellings", [])
    if isinstance(alt_spell, list) and alt_spell:
        codes.append({"label": "Alternative Spellings", "value": ", ".join(str(a) for a in alt_spell[:10])})
    sections.append({"title": "International Codes", "fields": codes})

    # ── Translations ──
    trans = entry.get("translations", {})
    if isinstance(trans, dict) and trans:
        trans_fields = []
        # Show a curated set of major languages
        priority = ["fra", "spa", "deu", "ara", "zho", "rus", "jpn", "por", "ita", "nld", "kor", "tur", "pol", "swe", "fin"]
        shown = set()
        for lang in priority + sorted(trans.keys()):
            if lang in shown:
                continue
            t = trans.get(lang, {})
            if isinstance(t, dict):
                official = t.get("official", "")
                common = t.get("common", "")
                label = f"{lang.upper()} — {common}" if common else lang.upper()
                shown.add(lang)
                trans_fields.append({"label": label, "value": official if official else str(common)})
            if len(shown) >= 12:
                break
        if trans_fields:
            sections.append({"title": "Name Translations", "fields": trans_fields})

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
    borders = entry.get("borders", []) if isinstance(entry.get("borders"), list) else []
    # Convert border cca3 codes to cca2 for frontend matching
    border_iso2s = []
    for b in borders:
        border_entry = data["by_iso3"].get(b)
        if border_entry:
            border_iso2s.append(border_entry.get("cca2", b))
        else:
            border_iso2s.append(b)  # keep as-is if not found
    region = entry.get("region", "")

    return {
        "iso2": iso2,
        "iso3": iso3,
        "name": str(name),
        "flag": str(flag),
        "region": str(region),
        "borders": border_iso2s,
        "sections": sections,
    }
