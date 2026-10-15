"""SEC EDGAR JSON APIs (Phase 68): ticker -> CIK map, companyfacts and frames.

Keyless, but SEC's fair-access policy requires a User-Agent that names the
caller with a contact address; it is built from ``EDGAR_IDENTITY``. Without
one every call raises :class:`SecUnavailable` and the fetcher skips SEC work
(Admin shows why). Every request passes ``rate_limit.SEC`` (5/s); a 429
opens its circuit and raises ``YFRateLimitError``, which the fetcher treats
as "wait, don't spend the task's attempts" for any source.
"""
from __future__ import annotations

import requests
from yfinance.exceptions import YFRateLimitError

from .. import rate_limit

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{period}.json"
TIMEOUT = 30


class SecUnavailable(RuntimeError):
    """No EDGAR_IDENTITY configured: SEC refuses anonymous callers."""


def identity() -> str | None:
    from .. import config
    return config.EDGAR_IDENTITY or None


def user_agent() -> str | None:
    ident = identity()
    return f"EconoSift {ident}" if ident else None


def get_json(url: str):
    """GET a SEC JSON document through the SEC guard. None on 404 (no such filer/frame)."""
    ua = user_agent()
    if not ua:
        raise SecUnavailable("EDGAR_IDENTITY is not set; SEC fundamentals are skipped")
    r = rate_limit.SEC.call(requests.get, url, timeout=TIMEOUT,
                            headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"})
    if r.status_code == 429:
        raise YFRateLimitError()  # the guard has opened the SEC circuit
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def cik10(cik) -> str:
    return f"{int(cik):010d}"


def ticker_ciks() -> dict[str, str]:
    """Ticker -> 10-digit CIK from ``company_tickers.json``.

    SEC writes class shares with a dash (``BRK-B``), as the app does; a dot
    form is normalised the same way. The first listing of a ticker wins.
    """
    data = get_json(TICKERS_URL) or {}
    rows = data.values() if isinstance(data, dict) else data
    out: dict[str, str] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper().replace(".", "-")
        cik = row.get("cik_str")
        if ticker and cik is not None:
            out.setdefault(ticker, cik10(cik))
    return out


def companyfacts(cik: str) -> dict | None:
    return get_json(FACTS_URL.format(cik=cik10(cik)))


def frame(taxonomy: str, concept: str, unit: str, period: str) -> dict | None:
    return get_json(FRAMES_URL.format(taxonomy=taxonomy, concept=concept, unit=unit, period=period))
