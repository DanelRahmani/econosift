"""Index constituent lists (S&P 500 / Nasdaq-100 / Dow 30).

Source of truth is Wikipedia via the MediaWiki ``action=parse`` API (raw
wikitext, parsed with ``wikitextparser``) — never HTML scraping. Results are
cached for a week because membership changes only a few times a year.

This module is foundational: Phase 2 breadth / movers and Phase 3 treemap /
Phase 5 screener all draw their universes from here. Keep the return shape
stable: ``[{"symbol", "name", "sector", "industry"}]`` with yfinance-ready
symbols. ``industry`` is the GICS Sub-Industry (or ``None`` for indices whose
Wikipedia table lacks that column, e.g. Nasdaq-100 / Dow 30).
"""
from __future__ import annotations

import threading
import time

import requests
import wikitextparser as wtp

# MediaWiki API + the page that carries each index's membership table.
_API = "https://en.wikipedia.org/w/api.php"
# Raw page titles — let requests URL-encode them (don't pre-encode "&" or it
# gets double-escaped into %2526 and the API 404s).
_PAGES: dict[str, str] = {
    "sp500": "List of S&P 500 companies",
    "ndx": "Nasdaq-100",
    "dow": "Dow Jones Industrial Average",
}
ALIASES = {
    "sp500": "sp500", "spx": "sp500", "^gspc": "sp500", "s&p500": "sp500",
    "sp": "sp500", "s&p 500": "sp500",
    "ndx": "ndx", "nasdaq100": "ndx", "nasdaq-100": "ndx", "^ndx": "ndx",
    "dow": "dow", "djia": "dow", "dow30": "dow", "^dji": "dow",
}

# Weekly TTL — membership is near-static; refresh weekly to catch rebalances.
_TTL = 7 * 24 * 60 * 60
_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = threading.Lock()


def _fetch_wikitext(page: str) -> str:
    params = {
        "action": "parse", "page": page, "prop": "wikitext",
        "format": "json", "formatversion": "2", "redirects": "1",
    }
    headers = {"User-Agent": "AxiomFinance/1.0 (research dashboard)"}
    resp = requests.get(_API, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()["parse"]["wikitext"]


def _clean_symbol(raw: str) -> str:
    """Normalise a wikitext cell to a yfinance ticker.

    Strips wiki links / refs / formatting and converts class-share dots to the
    dash form yfinance expects (BRK.B -> BRK-B).
    """
    # wikitextparser gives plain text but cells can still carry links/refs.
    parsed = wtp.parse(raw)
    text = parsed.plain_text().strip()
    # Tickers are often wrapped in symbol templates ({{NyseSymbol|MMM}},
    # {{NASDAQ link|AMGN}}, …) whose contents plain_text() drops — pull the
    # ticker from the last positional template argument instead.
    if not text and parsed.templates:
        positional = [a.value.strip() for a in parsed.templates[0].arguments
                      if a.positional]
        if positional:
            text = positional[-1]
    # Drop any trailing reference markers or footnotes.
    text = text.split("[")[0].split("\n")[0].strip()
    # A symbol cell sometimes renders as "NYSE: ABC" — keep the last token.
    if ":" in text:
        text = text.split(":")[-1].strip()
    text = text.upper().replace(".", "-")
    return text


def _header_index(rows: list[list[str]], *names: str) -> int | None:
    if not rows:
        return None
    header = [(_cell(h) or "").strip().lower() for h in rows[0]]
    for i, h in enumerate(header):
        for n in names:
            if n in h:
                return i
    return None


def _cell(v) -> str:
    if v is None:
        return ""
    return wtp.parse(str(v)).plain_text().strip()


def _sector_header_index(rows: list[list[str]]) -> int | None:
    """Find the GICS *Sector* column, explicitly excluding sub-industry columns.

    We can't reuse :func:`_header_index` with "sector" because the header
    "GICS Sub-Industry" also contains the word "sector" via sibling matches —
    this helper only returns the index when "sector" appears in the cell but
    "sub" does not, so it resolves to the pure sector column.
    """
    if not rows:
        return None
    header = [(_cell(h) or "").strip().lower() for h in rows[0]]
    for i, h in enumerate(header):
        if "sector" in h and "sub" not in h:
            return i
    # Fallback: accept "industry" only if no sector column at all (Dow table
    # uses "Sector" but some tables only have "Industry").
    for i, h in enumerate(header):
        if "industry" in h and "sub" not in h:
            return i
    return None


def _subindustry_header_index(rows: list[list[str]]) -> int | None:
    """Find the GICS Sub-Industry column (contains both 'sub' and 'industry')."""
    if not rows:
        return None
    header = [(_cell(h) or "").strip().lower() for h in rows[0]]
    for i, h in enumerate(header):
        if "sub" in h and "industry" in h:
            return i
    return None


def _parse_constituents(wikitext: str, index: str) -> list[dict]:
    """Find the membership table and pull symbol / name / sector / industry columns."""
    parsed = wtp.parse(wikitext)
    out: list[dict] = []
    seen: set[str] = set()

    for table in parsed.tables:
        try:
            rows = table.data(strip=True)
        except Exception:
            continue
        if not rows or len(rows) < 2:
            continue
        sym_i = _header_index(rows, "symbol", "ticker")
        if sym_i is None:
            continue
        name_i = _header_index(rows, "company", "security", "name")
        sector_i = _sector_header_index(rows)
        subind_i = _subindustry_header_index(rows)

        for row in rows[1:]:
            if sym_i >= len(row):
                continue
            symbol = _clean_symbol(row[sym_i] or "")
            if not symbol or len(symbol) > 8 or symbol in seen:
                continue
            # Guard against junk rows (must look like a ticker).
            if not all(c.isalnum() or c == "-" for c in symbol):
                continue
            seen.add(symbol)
            out.append({
                "symbol": symbol,
                "name": _cell(row[name_i]) if name_i is not None and name_i < len(row) else symbol,
                "sector": (_cell(row[sector_i])
                           if sector_i is not None and sector_i < len(row) else None) or None,
                "industry": (_cell(row[subind_i])
                             if subind_i is not None and subind_i < len(row) else None) or None,
            })
        if out:
            break  # first table with a Symbol header is the membership table

    return out


def get_constituents(index: str) -> list[dict]:
    """Return ``[{"symbol", "name", "sector", "industry"}]`` for an index, cached weekly.

    ``industry`` is the GICS Sub-Industry where available (S&P 500), else ``None``.
    On any fetch/parse failure we serve the last good cached value (even if
    stale) and otherwise return an empty list — we never fabricate members.
    """
    key = ALIASES.get(index.strip().lower())
    if key is None:
        return []

    now = time.time()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]

    try:
        wikitext = _fetch_wikitext(_PAGES[key])
        members = _parse_constituents(wikitext, key)
    except Exception:
        members = []

    if members:
        with _lock:
            _cache[key] = (now, members)
        return members

    # Fetch/parse failed — fall back to stale cache if we have one.
    return hit[1] if hit else []


def constituent_symbols(index: str) -> list[str]:
    """Convenience: just the yfinance-ready ticker symbols for an index."""
    return [c["symbol"] for c in get_constituents(index)]
