"""Open-market insider trades from the SEC's quarterly insider transactions
data sets (Forms 3, 4 and 5 filed in one calendar quarter, ~11 MB per ZIP of
tab-separated files, e.g. ``2026q2_form345.zip``).

One file replaces the per-company Form 4 requests the aggregate used to make
(one per filing across ~500 companies, 1-2 hours). The data set appears a few
days after each quarter ends, so the newest trades are up to a quarter old.
"""
from __future__ import annotations

import calendar
import csv
import logging
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from .. import store
from . import sec_datasets
from .bulk_data_service import DATA_DIR as _BULK_DIR

log = logging.getLogger(__name__)

_DIR = _BULK_DIR / "form345"  # download scratch only; the reduced trades live in insider_trade
_COLS = ["accession", "sk", "symbols", "insiderName", "title", "code", "shares", "price", "date"]
_DB_COLS = ["accession", "sk", "symbols", "insider_name", "title", "code", "shares", "price", "date"]
_CODES = {"P", "S"}  # open-market purchase / sale


def quarter_names(today: date, count: int = 4) -> list[str]:
    """The ``count`` most recent calendar quarters that have ended, newest
    first, in the SEC's naming (``2026q2``)."""
    y, q = today.year, (today.month - 1) // 3
    out: list[str] = []
    while len(out) < count:
        if q == 0:
            y, q = y - 1, 4
        out.append(f"{y}q{q}")
        q -= 1
    return out


def quarter_start(name: str) -> date:
    return date(int(name[:4]), 3 * int(name[-1]) - 2, 1)


def quarter_end(name: str) -> date:
    y, m = int(name[:4]), 3 * int(name[-1])
    return date(y, m, calendar.monthrange(y, m)[1])


def _read(z: zipfile.ZipFile, name: str, usecols: list[str]) -> pd.DataFrame:
    return pd.read_csv(z.open(name), sep="\t", dtype=str, usecols=usecols, quoting=csv.QUOTE_NONE,
                       encoding="utf-8", encoding_errors="replace", keep_default_na=False)


def reduce_dataset(path: Path) -> pd.DataFrame:
    """Open-market purchases and sales from original Form 4s.

    Columns: accession, sk, symbols (the issuer's trading symbol(s) as filed),
    insiderName, title, code (P/S), shares, price, date (ISO). Amendments
    (4/A) are left out so a corrected trade is not counted twice; a joint
    filing counts once, under its first reporting owner.
    """
    with zipfile.ZipFile(path) as z:
        sub = _read(z, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "DOCUMENT_TYPE", "ISSUERTRADINGSYMBOL"])
        own = _read(z, "REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP",
                                              "RPTOWNER_TITLE"])
        tr = _read(z, "NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "TRANS_DATE", "TRANS_CODE",
                                             "TRANS_SHARES", "TRANS_PRICEPERSHARE"])
    sub = sub[sub["DOCUMENT_TYPE"] == "4"]
    own = own.drop_duplicates("ACCESSION_NUMBER")
    tr = tr[tr["TRANS_CODE"].isin(_CODES)]
    df = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    title = df["RPTOWNER_TITLE"].fillna("").str.strip()
    return pd.DataFrame({
        "accession": df["ACCESSION_NUMBER"],
        "sk": df["NONDERIV_TRANS_SK"],
        "symbols": df["ISSUERTRADINGSYMBOL"],
        "insiderName": df["RPTOWNERNAME"].fillna("Unknown"),
        "title": title.where(title != "", df["RPTOWNER_RELATIONSHIP"].fillna("")),
        "code": df["TRANS_CODE"],
        "shares": pd.to_numeric(df["TRANS_SHARES"], errors="coerce").fillna(0.0),
        "price": pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce").fillna(0.0),
        "date": pd.to_datetime(df["TRANS_DATE"], format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d"),
    }).reset_index(drop=True)


def _user_agent() -> str | None:
    from ..config import EDGAR_IDENTITY
    return EDGAR_IDENTITY or None


def _meta(quarter: str) -> tuple[str, str] | None:
    """``(url, built_at)`` of the stored data set of ``quarter``, or None."""
    with store.connect() as conn:
        return conn.execute("SELECT url, built_at FROM sec_dataset WHERE name = 'form345' AND period_key = ?",
                            (quarter,)).fetchone()


def _stored(quarter: str) -> tuple[pd.DataFrame, str] | None:
    meta = _meta(quarter)
    if meta is None:
        return None
    with store.connect() as conn:
        rows = conn.execute(f"SELECT {', '.join(_DB_COLS)} FROM insider_trade WHERE quarter = ?",
                            (quarter,)).fetchall()
    return pd.DataFrame(rows, columns=_COLS), meta[0]


def _write(quarter: str, trades: pd.DataFrame, url: str) -> None:
    """Store one quarter's trades and drop older ones, in one transaction (the
    meta row marks it complete, so a reader never sees a half-written quarter)."""
    from datetime import datetime, timezone
    built = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with store.connect() as conn:
        conn.execute("DELETE FROM insider_trade")
        conn.execute("DELETE FROM sec_dataset WHERE name = 'form345'")
        conn.executemany(
            f"INSERT OR REPLACE INTO insider_trade (quarter, {', '.join(_DB_COLS)}) "
            f"VALUES ({', '.join('?' * (len(_DB_COLS) + 1))})",
            [(quarter, *r) for r in store.records(trades, _COLS)])
        conn.execute("INSERT INTO sec_dataset (name, period_key, url, built_at) VALUES ('form345', ?, ?, ?)",
                     (quarter, url, built))


def built_at(quarter: str) -> str | None:
    """When the stored data set of ``quarter`` was built."""
    meta = _meta(quarter)
    return meta[1] if meta else None


def load_latest() -> tuple[str, pd.DataFrame, str] | None:
    """``(quarter, trades, url)`` for the newest published quarter, downloading
    and reducing it once. Quarters newer than the stored one are probed on
    every call; None if no data set is available."""
    ua = _user_agent()
    if not ua:
        return None
    for quarter in quarter_names(date.today()):
        have = _stored(quarter)
        if have:
            return quarter, have[0], have[1]
        path = f"insider-transactions-data-sets/{quarter}_form345.zip"
        try:
            url = sec_datasets.find(path, ua)
        except requests.RequestException as exc:
            log.warning("Insider data set probe failed for %s: %s", quarter, exc)
            continue
        if not url:
            continue
        _DIR.mkdir(parents=True, exist_ok=True)
        part = _DIR / f"{quarter}.zip.part"
        try:
            sec_datasets.download(url, part, ua)
            trades = reduce_dataset(part)
        finally:
            part.unlink(missing_ok=True)
        _write(quarter, trades, url)
        log.info("Insider data set %s: %d open-market trades", quarter, len(trades))
        return quarter, trades, url
    return None
