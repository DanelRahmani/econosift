"""Factbook Profiles service — CIA World Factbook country data.

Loads individual country JSON files from factbook/factbook.json repository,
merges with REST Countries data for a comprehensive country profile.

Each country file has ~10 sections: Introduction, Geography, People and Society,
Government, Economy, Energy, Communications, Transportation, Military, Transnational Issues.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to factbook JSON files (flattened from regional folders)
_DATA_DIR = Path("/app/data/bulk/factbook") if Path("/app/data/bulk").exists() else (
    Path(__file__).resolve().parent.parent / "data" / "bulk" / "factbook"
)

# ISO2 → GEC/FIPS code mapping for sovereign countries
# Compiled from factbook/factbook.json README
ISO2_TO_GEC: dict[str, str] = {
    "AF": "af", "AL": "al", "DZ": "ag", "AD": "an", "AO": "ao",
    "AG": "ac", "AR": "ar", "AM": "am", "AU": "as", "AT": "au",
    "AZ": "aj", "BS": "bf", "BH": "ba", "BD": "bg", "BB": "bb",
    "BY": "bo", "BE": "be", "BZ": "bh", "BJ": "bn", "BT": "bt",
    "BO": "bl", "BA": "bk", "BW": "bc", "BR": "br", "BN": "bx",
    "BG": "bu", "BF": "uv", "MM": "bm", "BI": "by", "KH": "cb",
    "CM": "cm", "CA": "ca", "CV": "cv", "CF": "ct", "TD": "cd",
    "CL": "ci", "CN": "ch", "CO": "co", "KM": "cn", "CG": "cf",
    "CR": "cs", "CI": "iv", "HR": "hr", "CU": "cu", "CY": "cy",
    "CZ": "ez", "CD": "cg", "DK": "da", "DJ": "dj", "DM": "do",
    "DO": "dr", "EC": "ec", "EG": "eg", "SV": "es", "GQ": "ek",
    "ER": "er", "EE": "en", "SZ": "wz", "ET": "et", "FJ": "fj",
    "FI": "fi", "FR": "fr", "GA": "gb", "GM": "ga", "GE": "gg",
    "DE": "gm", "GH": "gh", "GR": "gr", "GD": "gj", "GT": "gt",
    "GN": "gv", "GW": "pu", "GY": "gy", "HT": "ha", "HN": "ho",
    "HU": "hu", "IS": "ic", "IN": "in", "ID": "id", "IR": "ir",
    "IQ": "iz", "IE": "ei", "IL": "is", "IT": "it", "JM": "jm",
    "JP": "ja", "JO": "jo", "KZ": "kz", "KE": "ke", "KI": "kr",
    "KP": "kn", "KR": "ks", "XK": "kv", "KW": "ku", "KG": "kg",
    "LA": "la", "LV": "lg", "LB": "le", "LS": "lt", "LR": "li",
    "LY": "ly", "LI": "ls", "LT": "lh", "LU": "lu", "MG": "ma",
    "MW": "mi", "MY": "my", "MV": "mv", "ML": "ml", "MT": "mt",
    "MH": "rm", "MR": "mr", "MU": "mp", "MX": "mx", "FM": "fm",
    "MD": "md", "MC": "mn", "MN": "mg", "ME": "mj", "MA": "mo",
    "MZ": "mz", "NA": "wa", "NR": "nr", "NP": "np", "NL": "nl",
    "NZ": "nz", "NI": "nu", "NE": "ng", "NG": "ni", "NO": "no",
    "MK": "mk", "OM": "mu", "PK": "pk", "PW": "ps", "PA": "pm",
    "PG": "pp", "PY": "pa", "PE": "pe", "PH": "rp", "PL": "pl",
    "PT": "po", "QA": "qa", "RO": "ro", "RU": "rs", "RW": "rw",
    "KN": "sc", "LC": "st", "VC": "vc", "WS": "ws", "SM": "sm",
    "ST": "tp", "SA": "sa", "SN": "sg", "RS": "ri", "SC": "se",
    "SL": "sl", "SG": "sn", "SK": "lo", "SI": "si", "SB": "bp",
    "SO": "so", "ZA": "sf", "SS": "od", "ES": "sp", "LK": "ce",
    "SD": "su", "SR": "ns", "SE": "sw", "CH": "sz", "SY": "sy",
    "TJ": "ti", "TZ": "tz", "TH": "th", "TL": "tt", "TG": "to",
    "TO": "tn", "TT": "td", "TN": "ts", "TR": "tu", "TM": "tx",
    "TV": "tv", "UG": "ug", "UA": "up", "AE": "ae", "GB": "uk",
    "US": "us", "UY": "uy", "UZ": "uz", "VU": "nh", "VA": "vt",
    "VE": "ve", "VN": "vm", "YE": "ym", "ZM": "za", "ZW": "zi",
    # Additional sovereign countries
    "PS": "gz",  # Gaza Strip / Palestine
    "EH": "wi",  # Western Sahara (removed but historical)
    "TW": "tw",  # Taiwan
}

# Region lookup for GEC codes — needed to find the file in the repo ZIP
# Major regions in the factbook repo
_GEC_REGIONS: dict[str, str] = {}
def _build_region_map():
    """Try to determine which region a GEC code is in by checking all folders."""
    if _GEC_REGIONS:
        return
    regions = ["africa", "antarctica", "australia-oceania", "central-america-n-caribbean",
               "central-asia", "east-n-southeast-asia", "europe", "middle-east",
               "north-america", "south-america", "south-asia", "oceans", "world"]
    for region in regions:
        region_dir = _DATA_DIR / region
        if region_dir.exists():
            for f in region_dir.iterdir():
                if f.suffix == ".json":
                    gec = f.stem.lower()
                    _GEC_REGIONS[gec] = region
    # Also check flattened structure (files directly in _DATA_DIR)
    for f in _DATA_DIR.glob("*.json"):
        gec = f.stem.lower()
        if gec not in _GEC_REGIONS:
            _GEC_REGIONS[gec] = ""


def _load_factbook_file(gec_code: str) -> dict | None:
    """Load a single factbook country JSON file by GEC code."""
    _build_region_map()

    # Try region/subfolder first
    region = _GEC_REGIONS.get(gec_code)
    if region:
        path = _DATA_DIR / region / f"{gec_code}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Try flat structure
    path = _DATA_DIR / f"{gec_code}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load factbook file %s: %s", gec_code, exc)

    return None


def _extract_field(value) -> str | None:
    """Extract text from a factbook field value (can be string, dict with 'text', or nested)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text.strip()
        # For multi-year data like GDP, try to get latest
        year_keys = sorted([k for k in value if k.startswith("2")], reverse=True)
        for k in year_keys:
            v = value[k]
            if isinstance(v, dict):
                t = v.get("text", "")
                if t:
                    return t.strip()
            elif isinstance(v, str):
                return v.strip()
        return None
    return None


def _extract_section(section_data: dict, title: str) -> list[dict]:
    """Convert a factbook section into [{label, value}] fields."""
    fields = []
    if not isinstance(section_data, dict):
        return fields

    for key, value in section_data.items():
        if key in ("keyword",):  # skip metadata
            continue

        label = key.replace("_", " ").replace("  ", " ").strip()
        # Title case the label
        label = " ".join(w[0].upper() + w[1:] if len(w) > 1 else w.upper()
                        for w in label.split())

        text = _extract_field(value)
        if text:
            # Clean up HTML entities
            text = text.replace("\u003cbr\u003e", "\n").replace("\u003cbr/\u003e", "\n")
            text = text.replace("\u003cp\u003e", "").replace("\u003c/p\u003e", "\n")
            text = text.replace("\u003cstrong\u003e", "").replace("\u003c/strong\u003e", "")
            text = text.replace("\u003cem\u003e", "").replace("\u003c/em\u003e", "")
            text = text.replace("&ldquo;", "\"").replace("&rdquo;", "\"")
            text = text.replace("\u0026", "&")  # unescape &
            text = text.strip()
            if text and text != "N/A":
                fields.append({"label": label, "value": text})

    return fields


# Section ordering for display
SECTION_ORDER = [
    "Introduction",
    "Geography",
    "People and Society",
    "Government",
    "Economy",
    "Energy",
    "Communications",
    "Transportation",
    "Military and Security",
    "Transnational Issues",
]


def get_factbook_profile(iso2: str) -> list[dict] | None:
    """Get factbook sections for a country by ISO2 code.

    Returns list of {title, fields: [{label, value}]} sections, or None if not found.
    """
    iso2 = iso2.upper()
    gec = ISO2_TO_GEC.get(iso2)
    if not gec:
        return None

    data = _load_factbook_file(gec)
    if not data:
        return None

    sections = []
    for section_key in SECTION_ORDER:
        section_data = data.get(section_key)
        if section_data and isinstance(section_data, dict):
            fields = _extract_section(section_data, section_key)
            if fields:
                sections.append({
                    "title": section_key,
                    "fields": fields,
                })

    return sections if sections else None
