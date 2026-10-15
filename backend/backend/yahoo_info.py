"""Yahoo-only company fields SEC doesn't have (Phase 68 item 5, plan §3).

Forward EPS and estimates, analyst targets and ratings, beta, Yahoo's sector
and industry names, short interest, the business summary, ETF total assets:
``Ticker.info`` is the only free source. The fetcher refreshes it on a weekly
rotation (~75 symbols a day, oldest first) plus on demand for a symbol a page
asks about, and stores the dict as Yahoo returned it. Pages read only the
stored copy, dated by ``fetched_at``.

A symbol with no SEC facts (a foreign filer, an IFRS 20-F filer) also gets
Yahoo's annual and quarterly statements stored in `fundamental` (source
``yahoo``, ``filed`` = the fetch date: what was knowable then).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd

from . import store

logger = logging.getLogger(__name__)

PER_DAY = 75            # ~520 symbols -> each one refreshed about weekly
RETRY_DELAYS = (0.0, 0.0, 3.0)  # quote-only answers come in bursts: retry at once, then after a pause
# Yahoo statement -> (attribute, quarterly attribute, flows?). Balance-sheet rows are
# instants, stored once per date like SEC's; flows get the '|Q' suffix for quarters.
STATEMENTS = {"financials": ("financials", "quarterly_financials", True),
              "balance_sheet": ("balance_sheet", "quarterly_balance_sheet", False),
              "cashflow": ("cashflow", "quarterly_cashflow", True)}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _jsonable(info: dict) -> dict:
    out = {}
    for k, v in info.items():
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            continue
        out[k] = v
    return out


def statement_rows(symbol: str, t, currency: str | None, filed: str) -> list[dict]:
    """`fundamental` rows from Yahoo's statements (annual + quarterly)."""
    rows: list[dict] = []
    for name, (annual, quarterly, flows) in STATEMENTS.items():
        seen: set[tuple[str, str]] = set()
        for attr, is_q in ((annual, False), (quarterly, True)):
            try:
                df = getattr(t, attr)
            except Exception:
                logger.warning("yahoo_info: %s.%s failed", symbol, attr, exc_info=True)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            for col in df.columns:
                end = pd.Timestamp(col).date().isoformat()
                for label, val in df[col].items():
                    if val is None or pd.isna(val):
                        continue
                    concept = f"{label}|Q" if is_q and flows else str(label)
                    if (concept, end) in seen:
                        continue  # an instant in both the annual and the quarterly sheet
                    seen.add((concept, end))
                    rows.append(dict(symbol=symbol, concept=concept, period_end=end, filed=filed,
                                     value=float(val), unit=currency, form=f"yahoo:{name}", source="yahoo"))
    return rows


def has_sec_facts(symbol: str) -> bool:
    with store.connect() as conn:
        return conn.execute("SELECT 1 FROM security WHERE symbol = ? AND facts_at IS NOT NULL",
                            (symbol,)).fetchone() is not None


def fetch(symbol: str) -> int:
    """Fetch and store one symbol's Ticker.info (and statements if SEC has none)."""
    import yfinance as yf
    from .services.yfinance_service import _info_failed

    t = yf.Ticker(symbol)
    info: dict = {}
    for delay in RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            info = t.get_info() or {}
        except Exception:
            logger.warning("yahoo_info: Ticker.info failed for %s", symbol, exc_info=True)
            info = {}
        if not _info_failed({"info": info}):
            break
    if _info_failed({"info": info}):
        raise RuntimeError(f"Ticker.info for {symbol} came back without a price or profile")

    # forwardEps is struck on next fiscal year (+1y), the year forwardPE uses.
    if info.get("forwardEps") is None and info.get("quoteType") == "EQUITY":
        try:
            ee = t.earnings_estimate
            if ee is not None and not ee.empty and "+1y" in ee.index and "avg" in ee.columns:
                info["forwardEps"] = float(ee.loc["+1y"]["avg"])
        except Exception:
            pass

    now = _now()
    rows = 0
    if info.get("quoteType") == "EQUITY" and not has_sec_facts(symbol):
        stmt = statement_rows(symbol, t, info.get("financialCurrency") or info.get("currency"), now[:10])
        rows = store.replace_fundamentals([symbol], stmt, "yahoo")
    put("info", symbol, _jsonable(info), now)
    return rows + 1


def put(kind: str, symbol: str, doc: dict, fetched_at: str | None = None) -> None:
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO yahoo_doc (kind, symbol, doc, fetched_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (kind, symbol) DO UPDATE SET doc = excluded.doc, fetched_at = excluded.fetched_at",
            (kind, symbol, json.dumps(doc), fetched_at or _now()))


def stored(symbols, kind: str = "info") -> dict[str, tuple[dict, str]]:
    """symbol -> (doc, fetched_at) for the symbols that have a stored ``kind`` document."""
    syms = list(dict.fromkeys(symbols))
    if not syms:
        return {}
    with store.connect() as conn:
        rows = conn.execute(f"SELECT symbol, doc, fetched_at FROM yahoo_doc WHERE kind = ? "
                            f"AND symbol IN ({', '.join('?' * len(syms))})", (kind, *syms)).fetchall()
    return {s: (json.loads(d), at) for s, d, at in rows}


def rotation(extra: tuple[str, ...] = (), n: int = PER_DAY) -> list[str]:
    """Today's batch: the ``n`` equities (plus ``extra``, e.g. sector ETFs) stored longest ago."""
    with store.connect() as conn:
        syms = [r[0] for r in conn.execute("SELECT symbol FROM security WHERE symbol NOT LIKE '^%'")]
        have = dict(conn.execute("SELECT symbol, fetched_at FROM yahoo_doc WHERE kind = 'info'"))
    syms = list(dict.fromkeys([*syms, *extra]))
    syms.sort(key=lambda s: (s in have, have.get(s) or "", s))  # never fetched first, then oldest
    return syms[:n]
