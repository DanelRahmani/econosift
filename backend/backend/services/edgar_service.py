"""EDGAR service: 13F institutional holders and Form 4 insider transactions."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta

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


def _fetch_13f_sync(ticker: str) -> dict:
    try:
        from edgar import Company  # type: ignore[import]
    except ImportError:
        return {"error": "edgartools not installed", "holders": [], "ticker": ticker, "asOf": None, "reportingLag": "45-day reporting lag"}

    if not _edgar_ready():
        return {"error": _NO_IDENTITY, "holders": [], "ticker": ticker, "asOf": None, "reportingLag": "45-day reporting lag"}
    try:
        company = Company(ticker)
        time.sleep(0.1)
        filings = company.get_filings(form="13F-HR")
        if not filings or len(filings) == 0:
            return {
                "ticker": ticker,
                "asOf": None,
                "reportingLag": "45-day reporting lag",
                "holders": [],
                "error": "No 13F filings found",
            }

        latest = filings[0]
        filing_date = str(latest.filing_date) if hasattr(latest, "filing_date") else str(date.today())
        time.sleep(0.1)

        holders: list[dict] = []
        try:
            obj = latest.obj() if hasattr(latest, "obj") else None
            if obj is not None and hasattr(obj, "infotable"):
                table = obj.infotable
                if hasattr(table, "iterrows"):
                    for _, row in table.iterrows():
                        name = str(row.get("nameOfIssuer", row.get("name", "Unknown")))
                        shares = int(row.get("sshPrnamt", row.get("shares", 0)) or 0)
                        value = int(row.get("value", 0) or 0) * 1000  # 13F values in thousands
                        holders.append({
                            "name": name,
                            "shares": shares,
                            "value": value,
                            "pctFloat": None,
                            "changeShares": None,
                            "changePct": None,
                        })
            # Sort by value descending, take top 10
            holders.sort(key=lambda x: x["value"], reverse=True)
            holders = holders[:10]
        except Exception as exc:
            log.warning("13F table parse failed for %s: %s", ticker, exc)
            holders = []

        return {
            "ticker": ticker,
            "asOf": filing_date,
            "reportingLag": "45-day reporting lag",
            "holders": holders,
            "error": None,
        }
    except Exception as exc:
        log.warning("get_13f_holders failed for %s: %s", ticker, exc)
        return {
            "ticker": ticker,
            "asOf": None,
            "reportingLag": "45-day reporting lag",
            "holders": [],
            "error": str(exc),
        }


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

                # Extract insider name and title
                insider_name = "Unknown"
                title = None
                if hasattr(obj, "reporting_owner"):
                    ro = obj.reporting_owner
                    if hasattr(ro, "name"):
                        insider_name = str(ro.name)
                    if hasattr(ro, "relationship"):
                        title = str(ro.relationship)

                # Extract transactions from non-derivative table
                if hasattr(obj, "non_derivative_table"):
                    tbl = obj.non_derivative_table
                    if hasattr(tbl, "iterrows"):
                        for _, row in tbl.iterrows():
                            tx_code = str(row.get("transactionCode", "")).upper()
                            if tx_code not in ("P", "S"):
                                continue
                            tx_type = "Buy" if tx_code == "P" else "Sell"
                            shares = None
                            try:
                                shares = float(row.get("transactionShares", 0) or 0)
                            except Exception:
                                shares = 0.0
                            price = None
                            try:
                                price_raw = row.get("transactionPricePerShare")
                                if price_raw is not None:
                                    price = float(price_raw)
                            except Exception:
                                pass
                            total = round(shares * price, 2) if shares and price else None

                            tx_date = str(fd)
                            try:
                                raw_date = row.get("transactionDate")
                                if raw_date:
                                    tx_date = str(raw_date)[:10]
                            except Exception:
                                pass

                            transactions.append({
                                "insiderName": insider_name,
                                "title": title,
                                "transactionType": tx_type,
                                "shares": shares,
                                "pricePerShare": price,
                                "totalValue": total,
                                "date": tx_date,
                            })
                            if max_transactions is not None and len(transactions) >= max_transactions:
                                break
            except Exception as exc:
                log.debug("Form4 filing parse error for %s: %s", ticker, exc)
                continue

            if max_transactions is not None and len(transactions) >= max_transactions:
                truncated = True
                break

        return {"ticker": ticker, "transactions": transactions, "truncated": truncated, "error": None}
    except Exception as exc:
        log.warning("get_form4_insiders failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "transactions": [], "error": str(exc)}


@async_cached("13f")
async def get_13f_holders(ticker: str) -> dict:
    """Fetch top 13F institutional holders for a ticker."""
    try:
        return await asyncio.to_thread(_fetch_13f_sync, ticker)
    except Exception as exc:
        log.warning("get_13f_holders async error for %s: %s", ticker, exc)
        return {
            "ticker": ticker,
            "asOf": None,
            "reportingLag": "45-day reporting lag",
            "holders": [],
            "error": str(exc),
        }


@async_cached("form4")
async def get_form4_insiders(ticker: str) -> dict:
    """Fetch recent Form 4 insider transactions (last 90 days) for a ticker."""
    try:
        return await asyncio.to_thread(_fetch_form4_sync, ticker)
    except Exception as exc:
        log.warning("get_form4_insiders async error for %s: %s", ticker, exc)
        return {"ticker": ticker, "transactions": [], "error": str(exc)}
