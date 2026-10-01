"""EDGAR service: Form 4 insider transactions (13F holders: thirteenf_service)."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta

from .. import provenance as pv
from ..cache import async_cached

log = logging.getLogger(__name__)

_NO_IDENTITY = ("SEC EDGAR identity not configured — set EDGAR_IDENTITY "
                "(\"Your Name you@example.com\") to enable insider and 13F data")


def _edgar_ready() -> bool:
    """Declare the SEC-required User-Agent identity; False if none is set."""
    from ..config import EDGAR_IDENTITY
    if not EDGAR_IDENTITY:
        return False
    from edgar import set_identity  # type: ignore[import]
    set_identity(EDGAR_IDENTITY)
    return True


def _num(v) -> float | None:
    """A float, or None for a missing/NaN/unparseable cell."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN


def _fetch_form4_sync(ticker: str, max_transactions: int | None = 50) -> dict:
    """Open-market Form 4 purchases/sales filed in the last 90 days.

    ``max_transactions`` caps the list for display; the insider aggregate
    passes ``None`` so heavy sellers are not truncated at 50 rows, which
    biased the market-wide buy/sell ratio upward (audit C-31).
    """
    try:
        from edgar import Company  # type: ignore[import]
    except ImportError:
        return {"error": "edgartools not installed", "transactions": [], "ticker": ticker}

    if not _edgar_ready():
        return {"error": _NO_IDENTITY, "transactions": [], "ticker": ticker}
    try:
        company = Company(ticker)
        time.sleep(0.1)
        filings = company.get_filings(form="4")
        if not filings or len(filings) == 0:
            return {"ticker": ticker, "transactions": [], "error": "No Form 4 filings found"}

        cutoff = date.today() - timedelta(days=90)
        transactions: list[dict] = []

        truncated = False
        for filing in filings[:400]:  # newest first; the 90-day cutoff ends the loop
            try:
                fd = filing.filing_date if hasattr(filing, "filing_date") else None
                if fd is None:
                    continue
                if hasattr(fd, "date"):
                    fd = fd.date()
                elif isinstance(fd, str):
                    from datetime import datetime
                    fd = datetime.strptime(fd[:10], "%Y-%m-%d").date()
                if fd < cutoff:
                    break

                time.sleep(0.05)
                obj = filing.obj() if hasattr(filing, "obj") else None
                if obj is None:
                    continue

                insider_name = str(getattr(obj, "insider_name", None) or "Unknown")
                title = getattr(obj, "position", None) or None

                # edgartools 5: open-market trades as a DataFrame (None when
                # the filing has none). Filter the codes here regardless.
                trades = getattr(obj, "market_trades", None)
                if trades is None:
                    continue
                for _, row in trades.iterrows():
                    tx_code = str(row.get("Code", "")).upper()
                    if tx_code not in ("P", "S"):
                        continue
                    shares = _num(row.get("Shares")) or 0.0
                    price = _num(row.get("Price"))
                    total = round(shares * price, 2) if shares and price else None
                    raw_date = row.get("Date")
                    transactions.append({
                        "insiderName": insider_name,
                        "title": title,
                        "transactionType": "Buy" if tx_code == "P" else "Sell",
                        "shares": shares,
                        "pricePerShare": price,
                        "totalValue": total,
                        "date": str(raw_date)[:10] if raw_date else str(fd),
                    })
                    if max_transactions is not None and len(transactions) >= max_transactions:
                        break
            except Exception as exc:
                # Warning, not debug: a parser that fails on every filing
                # (as after an edgartools API change) must show up in the log.
                log.warning("Form4 filing parse error for %s: %s", ticker, exc)
                continue

            if max_transactions is not None and len(transactions) >= max_transactions:
                truncated = True
                break

        return {"ticker": ticker, "transactions": transactions, "truncated": truncated, "error": None}
    except Exception as exc:
        log.warning("get_form4_insiders failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "transactions": [], "error": str(exc)}


def _form4_provenance(ticker: str, result: dict) -> dict:
    dates = [t["date"] for t in result["transactions"] if t.get("date")]
    filings = pv.ref(
        "sec_edgar", ticker, "Form 4 filings, last 90 days, non-derivative table", frequency="event",
        observed=max(dates) if dates else None,
        flags=("partial",) if result.get("truncated") else (),
        note="Open-market purchases (code P) and sales (code S) only; observed is the latest transaction date."
             + (" The list is capped at 50 transactions." if result.get("truncated") else ""))
    return {
        "*": filings,
        "transactions.transactionType": pv.derived("transaction code P = Buy, S = Sell", [filings],
                                                   title="Buy / Sell classification"),
        "transactions.totalValue": pv.derived("shares × price per share (blank if either is missing)", [filings],
                                              title="Transaction value"),
    }


@async_cached("form4")
async def get_form4_insiders(ticker: str) -> dict:
    """Fetch recent Form 4 insider transactions (last 90 days) for a ticker."""
    try:
        result = await asyncio.to_thread(_fetch_form4_sync, ticker)
        if not result.get("error"):
            result = pv.attach(result, _form4_provenance(ticker, result))
        return result
    except Exception as exc:
        log.warning("get_form4_insiders async error for %s: %s", ticker, exc)
        return {"ticker": ticker, "transactions": [], "error": str(exc)}
