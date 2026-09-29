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

import datetime as _dt
import re as _re
import threading
import time

import requests
import wikitextparser as wtp

# MediaWiki API + the page that carries each index's membership table.
_API = "https://en.wikipedia.org/w/api.php"
# Raw page titles — let requests URL-encode them (don't pre-encode "&" or it
# gets double-escaped into %2526 and the API 404s).
# Wikipedia has moved every one of these onto dedicated "List of ..." articles.
# The parent articles (e.g. "Nasdaq-100") now carry only history and milestone
# tables, so pointing at them silently returned zero members — the screener and
# backtester universes for ndx/dow were empty rather than erroring. The parsing
# itself was fine; only the titles were stale.
_PAGES: dict[str, str] = {
    "sp500": "List of S&P 500 companies",
    "ndx": "List of NASDAQ-100 companies",
    "dow": "List of Dow Jones Industrial Average companies",
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
    headers = {"User-Agent": "EconoSift/1.0 (research dashboard)"}
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


# ---------------------------------------------------------------------------
# Point-in-time membership (Phase 42, task C1)
#
# `get_constituents` returns *today's* members. Any historical study built on
# that silently excludes every company that was delisted, acquired or went
# bankrupt — survivorship bias, worth roughly 1-4% a year on US large caps and
# always in the flattering direction.
#
# Wikipedia keeps an index change log on a separate page. Note the change table
# once lived on "List of S&P 500 companies" and no longer does; it now has its
# own article. Reconstruction walks that log backwards from the current roster.
#
# Coverage is the honest limit here. Measured against the live page, the log
# carries ~20-27 changes/year from 2010 onward, which matches the index's real
# turnover, but under 2/year before 2005 — it is a *selected* history, not a
# complete one. Reconstructions before _COVERAGE_FROM are flagged incomplete
# rather than presented as fact.
# ---------------------------------------------------------------------------

# Only the S&P 500 has a change log in a Date / Added / Removed shape that can
# be walked backwards. The Dow's "Historical components" article exists but is
# laid out as ~64 wide period tables with no date column, and the Nasdaq-100 has
# no change article at all — so neither can be reconstructed by this parser.
# They are deliberately absent rather than listed-but-broken: members_as_of then
# returns today's roster flagged complete=False with an explicit note, instead
# of implying point-in-time support it does not have.
_CHANGES_PAGES: dict[str, str] = {
    "sp500": "Historical components of the S&P 500",
}

# Before this date the change log is too sparse to reconstruct a roster.
_COVERAGE_FROM = _dt.date(2010, 1, 1)

_changes_cache: dict[str, tuple[float, list[dict]]] = {}


def _parse_change_date(raw: str) -> _dt.date | None:
    """Parse the change log's date cell, which is free text like 'August 18, 2026'."""
    text = _re.sub(r"\[\[|\]\]|<[^>]+>", " ", raw or "").strip()
    text = _re.sub(r"\s+", " ", text)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %B %Y", "%B %Y"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Last resort: a bare year-month-day anywhere in the cell.
    m = _re.search(r"(19|20)\d{2}-\d{2}-\d{2}", text)
    if m:
        try:
            return _dt.date.fromisoformat(m.group(0))
        except ValueError:
            return None
    return None


def _parse_changes(wikitext: str) -> list[dict]:
    """Extract [{date, added, removed}] from the change-log table, newest first.

    The table uses a two-row header (Added/Removed each span Ticker+Security),
    so the ticker columns are located by the second header row rather than
    assumed positionally.
    """
    parsed = wtp.parse(wikitext)
    for table in parsed.tables:
        try:
            rows = table.data(strip=True)
        except Exception:
            continue
        if not rows or len(rows) < 3:
            continue

        header = [(_cell(c) or "").lower() for c in rows[0]]
        if not any("date" in h for h in header):
            continue

        # Row 1 disambiguates the spanned Added/Removed columns.
        sub = [(_cell(c) or "").lower() for c in rows[1]]
        ticker_cols = [i for i, c in enumerate(sub) if "ticker" in c or "symbol" in c]
        if len(ticker_cols) < 2:
            continue
        added_i, removed_i = ticker_cols[0], ticker_cols[1]

        out: list[dict] = []
        for row in rows[2:]:
            if not row or removed_i >= len(row):
                continue
            when = _parse_change_date(row[0] or "")
            if when is None:
                continue
            added = _clean_symbol(row[added_i] or "") if added_i < len(row) else ""
            removed = _clean_symbol(row[removed_i] or "")
            if not added and not removed:
                continue
            out.append({"date": when, "added": added or None, "removed": removed or None})

        if out:
            out.sort(key=lambda c: c["date"], reverse=True)
            return out
    return []


def get_membership_changes(index: str) -> list[dict]:
    """Index change log, newest first, cached weekly. Empty when unsupported."""
    key = ALIASES.get(index.strip().lower())
    page = _CHANGES_PAGES.get(key or "")
    if page is None:
        return []

    now = time.time()
    with _lock:
        hit = _changes_cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]

    try:
        changes = _parse_changes(_fetch_wikitext(page))
    except Exception:
        changes = []

    if changes:
        with _lock:
            _changes_cache[key] = (now, changes)
        return changes
    return hit[1] if hit else []


def members_as_of(index: str, as_of: _dt.date) -> dict:
    """Reconstruct index membership on a past date.

    Walks the change log backwards from today's roster: for every change that
    took effect *after* ``as_of``, undo it — drop the added ticker and restore
    the removed one.

    Returns ``{"symbols", "asOf", "complete", "coverageFrom", "changesApplied"}``.
    ``complete`` is False when the request predates reliable coverage or when
    the change log could not be fetched; callers should surface that rather
    than treat the roster as fact.
    """
    current = constituent_symbols(index)
    if not current:
        return {
            "symbols": [], "asOf": as_of.isoformat(), "complete": False,
            "coverageFrom": _COVERAGE_FROM.isoformat(), "changesApplied": 0,
            "note": "current membership unavailable",
        }

    today = _dt.date.today()
    if as_of >= today:
        return {
            "symbols": sorted(current), "asOf": as_of.isoformat(), "complete": True,
            "coverageFrom": _COVERAGE_FROM.isoformat(), "changesApplied": 0,
        }

    changes = get_membership_changes(index)
    if not changes:
        return {
            "symbols": sorted(current), "asOf": as_of.isoformat(), "complete": False,
            "coverageFrom": _COVERAGE_FROM.isoformat(), "changesApplied": 0,
            "note": "change log unavailable — this is today's roster, not a point-in-time one",
        }

    roster = set(current)
    applied = 0
    for ch in changes:                      # newest first
        if ch["date"] <= as_of:
            break
        if ch["added"]:
            roster.discard(ch["added"])     # it had not joined yet
        if ch["removed"]:
            roster.add(ch["removed"])       # it was still a member
        applied += 1

    result = {
        "symbols": sorted(roster),
        "asOf": as_of.isoformat(),
        "complete": as_of >= _COVERAGE_FROM,
        "coverageFrom": _COVERAGE_FROM.isoformat(),
        "changesApplied": applied,
    }
    if not result["complete"]:
        result["note"] = (
            f"the change log is sparse before {_COVERAGE_FROM.isoformat()} "
            "(under ~2 changes/year vs ~20 actual), so this roster is incomplete "
            "and still carries survivorship bias"
        )
    return result
