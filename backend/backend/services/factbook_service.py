"""Country Profiles service — REST Countries data (formerly OpenFactbook).

Loads countries.json (from bulk data or manual placement) and provides
country list and per-country profile with structured sections.

Data source: https://github.com/mledoze/countries (REST Countries format)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .. import provenance as pv
from ..cache import cached

logger = logging.getLogger(__name__)

# ISO 639-2 B/T code mismatches in REST Countries translations
# languages uses T codes (fas, deu) but translations keys use B codes (per, ger)
_LANG_ALT_CODES: dict[str, str] = {
    "fas": "per",  # Persian/Farsi: T=fas, B=per
    "prs": "per",  # Dari (Afghan Persian): no ISO 639-2, map to per
    "deu": "ger",  # German: T=deu, B=ger (defensive, usually both work)
}
_LANG_ALT_CODES_REV: dict[str, str] = {v: k for k, v in _LANG_ALT_CODES.items()}


def _resolve_local_lang(languages: dict, translations: dict) -> str | None:
    """Find the translation key matching the country's primary language.
    
    Tries direct match first, then ISO 639-2 B↔T alternates, then all language codes.
    Returns the matching translation key or None.
    """
    if not languages or not translations:
        return None
    for lang_code in languages:
        if lang_code in translations:
            return lang_code
        alt = _LANG_ALT_CODES.get(lang_code) or _LANG_ALT_CODES_REV.get(lang_code)
        if alt and alt in translations:
            return alt
    return None


def _get_local_name(entry: dict) -> tuple[str, str, str] | None:
    """Get the country's local-language name.
    
    Tries translations first (with B/T code mapping), then falls back
    to name.native. Returns (display_code, common_name, official_name) or None.
    """
    languages = entry.get("languages", {})
    if not isinstance(languages, dict) or not languages:
        return None
    translations = entry.get("translations", {})
    name_data = entry.get("name", {}) if isinstance(entry.get("name"), dict) else {}
    native = name_data.get("native", {}) if isinstance(name_data, dict) else {}

    # Try translations first
    if isinstance(translations, dict):
        code = _resolve_local_lang(languages, translations)
        if code:
            t = translations[code]
            common = t.get("common", "") if isinstance(t, dict) else ""
            official = t.get("official", "") if isinstance(t, dict) else ""
            if common:
                return (code.upper(), common, official)

    # Fall back to name.native (first matching language)
    if isinstance(native, dict):
        for lang_code in languages:
            if lang_code in native:
                n = native[lang_code]
                if isinstance(n, dict):
                    common = n.get("common", "")
                    official = n.get("official", "")
                    if common:
                        return (lang_code.upper(), common, official)

    return None

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

    # ── Introduction (with comms fields merged in) ──
    intro = []
    if name_data.get("official"):
        intro.append({"label": "Official Name", "value": str(name_data["official"])})
    if name_data.get("common"):
        intro.append({"label": "Common Name", "value": str(name_data["common"])})
    intro.append({"label": "Capital", "value": capital_str or "N/A"})
    intro.append({"label": "Region", "value": str(entry.get("region", "") or "N/A")})
    sub = entry.get("subregion", "")
    if sub:
        intro.append({"label": "Subregion", "value": str(sub)})
    # Currency, Calling Code, TLD — merged from old Government section
    currencies = entry.get("currencies", {})
    if isinstance(currencies, dict) and currencies:
        cur_list = [f"{info.get('name', code)} ({info.get('symbol', code)})" if isinstance(info, dict) else str(code)
                    for code, info in currencies.items()]
        intro.append({"label": "Currency", "value": ", ".join(cur_list)})
    idd = entry.get("idd", {})
    if isinstance(idd, dict):
        root = idd.get("root", "")
        if root:
            suffixes = idd.get("suffixes", [])
            intro.append({"label": "Calling Code", "value": f"{root}{' (x'+suffixes[0]+')' if suffixes else ''}"})
    tld = entry.get("tld", [])
    if tld:
        intro.append({"label": "Internet TLD", "value": ", ".join(str(t) for t in tld)})
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

    # ── Translations (local + 5 major languages) ──
    trans = entry.get("translations", {})
    if isinstance(trans, dict):
        trans_fields = []
        common_name = name_data.get("common", entry.get("name", ""))
        # Local language first (primary language of the country)
        local = _get_local_name(entry)
        local_lang_code = None
        if local:
            local_lang_code, local_common, local_official = local
            display_code = local_lang_code
            label = f"{display_code} (Local) — {local_common}"
            trans_fields.append({"label": label, "value": local_official or local_common})
        # English
        trans_fields.append({"label": "ENG — " + str(common_name), "value": str(common_name)})
        for lang in ["fra", "rus", "spa", "zho"]:
            if lang == local_lang_code:
                continue  # already added above
            t = trans.get(lang, {})
            if isinstance(t, dict):
                official = t.get("official", "")
                common = t.get("common", "")
                label = f"{lang.upper()} — {common}" if common else lang.upper()
                trans_fields.append({"label": label, "value": official if official else str(common)})
        if len(trans_fields) > 1:  # always at least English
            sections.append({"title": "Name Translations", "fields": trans_fields})

    return sections


def _provenance(sections: list[dict], rest_titles: set[str], fb_titles: set[str], aircraft: bool) -> dict:
    """Source map for a country profile (see provenance.py). Sections are keyed by title."""
    rest = pv.ref("other", None, "REST Countries dataset (mledoze/countries)",
                  url="https://github.com/mledoze/countries",
                  note="Names, codes, borders, currencies and languages; a static file downloaded by the app.")
    rest["providerName"] = "REST Countries (mledoze/countries)"
    fb = pv.ref("factbook", None, "CIA World Factbook country profile",
                note="From a downloaded snapshot of the factbook/factbook.json GitHub mirror; the snapshot date "
                     "is not recorded, and multi-year fields show their latest year without naming it.")
    prov: dict = {"*": rest}
    for sec in sections:
        title = sec["title"]
        in_fb, in_rest = title in fb_titles, title in rest_titles
        if in_fb and in_rest:
            prov[f"sections.{title}"] = [dict(fb), dict(rest)]
        elif in_fb:
            prov[f"sections.{title}"] = dict(fb)
        elif in_rest:
            ref = dict(rest)
            if aircraft and title == "International Codes":
                ref["note"] = rest["note"] + " The civil aircraft registration prefix comes from the CIA World Factbook."
                prov[f"sections.{title}"] = [ref, dict(fb)]
            else:
                prov[f"sections.{title}"] = ref
    return prov


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
    rest_titles = {s["title"] for s in sections}
    if "People & Society" in rest_titles:
        rest_titles.add("People and Society")  # merged into the factbook section of that name
    fb_titles: set[str] = set()
    aircraft = False

    # Try to merge in CIA Factbook data
    try:
        from .factbook_profiles_service import get_factbook_profile, _load_factbook_file, _extract_field, ISO2_TO_GEC as FB_ISO2
        fb_sections = get_factbook_profile(iso2)
        if fb_sections:
            fb_titles = {s["title"] for s in fb_sections}
            # Merge duplicates: REST Geography → factbook Geography, REST People → factbook People
            fb_by_title = {s["title"]: s for s in fb_sections}
            rest_by_title = {s["title"]: s for s in sections}
            # Merge Introduction
            merged = {}
            intro = {"title": "Introduction", "fields": []}
            if rest_by_title.get("Introduction"):
                intro["fields"].extend(rest_by_title["Introduction"]["fields"])
            if fb_by_title.get("Introduction"):
                intro["fields"].extend(fb_by_title["Introduction"]["fields"])
            merged["Introduction"] = intro
            # Merge Geography
            geo = fb_by_title.pop("Geography", {"title": "Geography", "fields": []})
            if rest_by_title.get("Geography"):
                geo.setdefault("fields", []).extend(rest_by_title["Geography"]["fields"])
            merged["Geography"] = geo
            # Merge People & Society
            people = fb_by_title.pop("People and Society", {"title": "People and Society", "fields": []})
            if rest_by_title.get("People & Society"):
                people.setdefault("fields", []).extend(rest_by_title["People & Society"]["fields"])
            merged["People and Society"] = people

            # Business-first ordering
            order = ["Introduction", "Economy", "Government", "Geography",
                     "People and Society", "Communications", "Energy",
                     "Military and Security", "Transnational Issues",
                     "International Codes", "Name Translations"]
            sections = []
            for key in order:
                if key in merged:
                    sections.append(merged[key])
                elif key in fb_by_title:
                    sections.append(fb_by_title[key])
                elif key in rest_by_title:
                    sections.append(rest_by_title[key])

        # Add civil aircraft registration code to International Codes
        gec = FB_ISO2.get(iso2)
        if gec:
            fb_data = _load_factbook_file(gec)
            if fb_data:
                transport = fb_data.get("Transportation", {})
                ac = _extract_field(transport.get("Civil aircraft registration country code prefix"))
                if ac:
                    for s in sections:
                        if s["title"] == "International Codes":
                            s["fields"].append({"label": "Civil Aircraft Reg", "value": ac})
                            aircraft = True
                            break
    except Exception:
        pass
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

    # Local name (primary language common name)
    local_name = ""
    local = _get_local_name(entry)
    if local:
        local_name = local[1]  # common name

    # French name
    french_name = ""
    translations = entry.get("translations", {})
    if isinstance(translations, dict):
        fra = translations.get("fra", {})
        if isinstance(fra, dict):
            french_name = fra.get("common", "")

    return pv.attach({
        "iso2": iso2,
        "iso3": iso3,
        "name": str(name),
        "localName": str(local_name),
        "frenchName": str(french_name),
        "flag": str(flag),
        "region": str(region),
        "continent": str(region),  # region is the continent in REST Countries
        "borders": border_iso2s,
        "sections": sections,
    }, _provenance(sections, rest_titles, fb_titles, aircraft))
