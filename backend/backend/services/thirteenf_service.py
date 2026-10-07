"""Institutional holders from the SEC's quarterly Form 13F data sets.

A Form 13F-HR lists the holdings of one institutional manager, so "who holds
AAPL" cannot be read from AAPL's own filings. The SEC publishes every 13F
filed in a three-month window as one ZIP of tab-separated files (SUBMISSION,
COVERPAGE, INFOTABLE, ...), named by filing window, e.g.
``01mar2026-31may2026_form13f.zip``. This module downloads the newest one,
reduces it to the largest holders per CUSIP, and answers lookups from that
reduced file. Ticker → CUSIP uses the mapping bundled with edgartools.

The download (~100 MB) runs in a background thread; until it has finished
once, lookups return an explicit "preparing" envelope, which is not cached.
"""
from __future__ import annotations

import asyncio
import calendar
import csv
import json
import logging
import threading
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from .. import provenance as pv
from .. import cache
from ..cache import async_cached, cached
from . import sec_datasets
from .bulk_data_service import DATA_DIR as _BULK_DIR

log = logging.getLogger(__name__)

_DIR = _BULK_DIR / "13f"
_TOP_N = 25          # holders kept per CUSIP in the reduced file
_SHOW = 10           # holders returned per lookup
_RETRY_AFTER = 3600  # seconds before a failed download is retried
_LAG = "45-day reporting lag"
# Bump when reduce_dataset changes, so stored files built by older code are rebuilt.
_FORMAT = 2

# Filing windows end on the last day of these months (Feb, May, Aug, Nov).
_WINDOW_END_MONTHS = (2, 5, 8, 11)


def window_names(today: date, count: int = 4) -> list[str]:
    """Names of the most recent ``count`` filing windows that have ended,
    newest first, in the SEC's file naming (``01mar2026-31may2026``)."""
    out: list[str] = []
    y, m = today.year, today.month
    while len(out) < count:
        if m in _WINDOW_END_MONTHS:
            end = date(y, m, calendar.monthrange(y, m)[1])
            if end < today:
                sy, sm = (y, m - 2) if m > 2 else (y - 1, m + 10)
                out.append(f"01{_mon(sm)}{sy}-{end.day:02d}{_mon(m)}{y}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out


def previous_window(window: str) -> str:
    """The filing window one quarter before ``window``."""
    return window_names(_window_end(window) + timedelta(days=1), count=2)[1]


def _mon(m: int) -> str:
    return calendar.month_abbr[m].lower()


def _window_end(name: str) -> date:
    return datetime.strptime(name.split("-")[1], "%d%b%Y").date()


# ---------------------------------------------------------------------------
# Reduce one data set to holders per CUSIP
# ---------------------------------------------------------------------------

def _read(z: zipfile.ZipFile, name: str, usecols: list[str], **kw):
    return pd.read_csv(z.open(name), sep="\t", dtype=str, usecols=usecols, quoting=csv.QUOTE_NONE,
                       encoding="utf-8", encoding_errors="replace", **kw)


def reduce_dataset(path: Path, chunksize: int = 500_000) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Return ``(holders, totals, period)`` for the quarter most 13F-HRs in the
    data set report on.

    * ``holders``: cusip, cik, manager, shares, value (USD), rank — the top
      ``_TOP_N`` managers per CUSIP by shares.
    * ``totals``: cusip, filers, shares, value across all managers.

    Per manager the latest original-or-restatement report for the quarter
    counts, plus any later "new holdings" amendments. Only share positions
    count: options (PUTCALL) and principal amounts (PRN) are excluded.
    """
    with zipfile.ZipFile(path) as z:
        sub = _read(z, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK",
                                          "PERIODOFREPORT"])
        cov = _read(z, "COVERPAGE.tsv", ["ACCESSION_NUMBER", "AMENDMENTTYPE", "FILINGMANAGER_NAME"])
        sub = sub[sub["SUBMISSIONTYPE"].isin(["13F-HR", "13F-HR/A"])].merge(cov, on="ACCESSION_NUMBER", how="left")
        sub["period"] = pd.to_datetime(sub["PERIODOFREPORT"], format="%d-%b-%Y", errors="coerce")
        sub["filed"] = pd.to_datetime(sub["FILING_DATE"], format="%d-%b-%Y", errors="coerce")

        period = sub.loc[sub["SUBMISSIONTYPE"] == "13F-HR", "period"].mode().max()
        sub = sub[sub["period"] == period]
        amend = sub["AMENDMENTTYPE"].fillna("").str.upper()
        # The cover page decides, not the form type: a new-holdings amendment
        # is occasionally filed as a plain 13F-HR.
        is_add = amend == "NEW HOLDINGS"
        base = (sub[((sub["SUBMISSIONTYPE"] == "13F-HR") & ~is_add) | (amend == "RESTATEMENT")]
                .sort_values(["filed", "ACCESSION_NUMBER"]).groupby("CIK").tail(1))
        adds = sub[is_add].merge(base[["CIK", "filed"]], on="CIK", suffixes=("", "_base"))
        adds = adds[adds["filed"] >= adds["filed_base"]]
        acc_cik = pd.concat([base, adds]).set_index("ACCESSION_NUMBER")["CIK"]
        managers = base.set_index("CIK")["FILINGMANAGER_NAME"]

        parts = []
        for chunk in _read(z, "INFOTABLE.tsv", ["ACCESSION_NUMBER", "CUSIP", "VALUE", "SSHPRNAMT",
                                                "SSHPRNAMTTYPE", "PUTCALL"], chunksize=chunksize):
            chunk = chunk[chunk["ACCESSION_NUMBER"].isin(acc_cik.index)
                          & (chunk["SSHPRNAMTTYPE"] == "SH") & chunk["PUTCALL"].isna()]
            if chunk.empty:
                continue
            chunk = chunk.assign(
                cusip=chunk["CUSIP"].str.strip().str.upper(),
                shares=pd.to_numeric(chunk["SSHPRNAMT"], errors="coerce").fillna(0).astype("int64"),
                value=pd.to_numeric(chunk["VALUE"], errors="coerce").fillna(0).astype("int64"))
            parts.append(chunk.groupby(["ACCESSION_NUMBER", "cusip"])[["shares", "value"]].sum().reset_index())

    pos = pd.concat(parts) if parts else pd.DataFrame(columns=["ACCESSION_NUMBER", "cusip", "shares", "value"])
    pos = _fix_thousands(pos)
    pos["cik"] = pos["ACCESSION_NUMBER"].map(acc_cik)
    pos = pos.groupby(["cik", "cusip"])[["shares", "value"]].sum().reset_index()
    pos = pos[pos["shares"] > 0]
    pos["manager"] = pos["cik"].map(managers).fillna("Unknown manager")

    totals = (pos.groupby("cusip").agg(filers=("cik", "nunique"), shares=("shares", "sum"), value=("value", "sum"))
              .reset_index())
    pos = pos.sort_values(["cusip", "shares"], ascending=[True, False])
    pos["rank"] = pos.groupby("cusip").cumcount() + 1
    holders = pos[pos["rank"] <= _TOP_N][["cusip", "cik", "manager", "shares", "value", "rank"]]
    return holders.reset_index(drop=True), totals, period.date().isoformat()


def _fix_thousands(pos: pd.DataFrame) -> pd.DataFrame:
    """Rescale filings that still report VALUE in thousands of dollars.

    VALUE has been in dollars since 2023, but some managers still file in
    thousands. Such a filing's implied prices (value / shares) sit at ~1/1000
    of the median price other filers imply for the same CUSIP across its
    positions, so the whole filing is multiplied by 1,000. The test is per
    filing, never per row, so one odd position cannot trigger it.
    """
    if pos.empty:
        return pos
    held = pos[pos["shares"] > 0]
    price = held["value"] / held["shares"]
    ratio = price / price.groupby(held["cusip"]).transform("median")
    per_filing = ratio.groupby(held["ACCESSION_NUMBER"]).median()
    thousands = per_filing[(per_filing > 0.0005) & (per_filing < 0.002)].index
    if len(thousands):
        log.info("13F: %d filings report VALUE in thousands; rescaled", len(thousands))
        pos = pos.copy()
        mask = pos["ACCESSION_NUMBER"].isin(thousands)
        pos.loc[mask, "value"] = pos.loc[mask, "value"] * 1000
    return pos


def write_reduced(window: str, holders: pd.DataFrame, totals: pd.DataFrame, period: str, url: str = "") -> None:
    """Store a reduced data set and keep only the two newest: the newest serves lookups,
    the one before it gives the quarter-on-quarter change (P2-37)."""
    _DIR.mkdir(parents=True, exist_ok=True)
    holders.to_parquet(_DIR / f"holders_{window}.parquet", index=False)
    totals.to_parquet(_DIR / f"totals_{window}.parquet", index=False)
    meta = {"window": window, "period": period, "format": _FORMAT, "url": url,
            "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    # Meta last: its presence marks the data set as complete.
    (_DIR / f"meta_{window}.json").write_text(json.dumps(meta))
    keep = sorted((p.stem[len("meta_"):] for p in _DIR.glob("meta_*.json")), key=_window_end)[-2:]
    for p in _DIR.iterdir():
        if not any(w in p.name for w in keep):
            p.unlink(missing_ok=True)


def _meta(window: str) -> dict | None:
    """Meta of the stored data set of ``window``, or None if absent or built by older code."""
    path = _DIR / f"meta_{window}.json"
    meta = json.loads(path.read_text()) if path.exists() else None
    return meta if meta and meta.get("format") == _FORMAT else None


def _latest_meta() -> dict | None:
    if not _DIR.exists():
        return None
    metas = sorted(_DIR.glob("meta_*.json"), key=lambda p: _window_end(p.stem[len("meta_"):]))
    meta = json.loads(metas[-1].read_text()) if metas else None
    return meta if meta and meta.get("format") == _FORMAT else None


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def _ticker_keys(ticker: str) -> set[str]:
    """Spellings to look up: the bundled map writes share classes without a
    separator ("BRKB"), Yahoo with a dash ("BRK-B")."""
    return {ticker, ticker.replace("-", "").replace(".", "")}


def _cusips_for(ticker: str) -> list[str]:
    from edgar.reference.tickers import cusip_ticker_mapping  # type: ignore[import]
    df = cusip_ticker_mapping().reset_index()
    return [str(c).upper() for c in df.loc[df["Ticker"].isin(_ticker_keys(ticker)), "Cusip"]]


def _change_state(window: str) -> tuple[dict, dict | None]:
    """``(change, previous meta)``: whether the previous quarter is stored for the QoQ change."""
    name = previous_window(window)
    prev = _meta(name)
    loading = _build_state["window"] == name
    return {"available": prev is not None, "previousAsOf": prev["period"] if prev else None,
            "previousDataset": name,
            "reason": None if prev else (f"The previous quarter's 13F data set ({name}, a ~100 MB download) "
                                         "has not been loaded."),
            "canLoad": prev is None and not loading, "loading": loading}, prev


def _changes(holders: pd.DataFrame, cusip: str, prev: dict) -> dict:
    """cik -> (change in shares, change %) against the previous quarter's data set.

    A manager absent from a complete previous list (all filers stored) opened a
    new position: the change is its whole holding, with no %. One absent from a
    list cut at the top ``_TOP_N`` may simply have ranked lower: no change.
    """
    w = prev["window"]
    totals = pd.read_parquet(_DIR / f"totals_{w}.parquet", filters=[("cusip", "==", cusip)])
    before = pd.read_parquet(_DIR / f"holders_{w}.parquet", filters=[("cusip", "==", cusip)])
    complete = totals.empty or int(totals["filers"].iloc[0]) <= _TOP_N
    had = dict(zip(before["cik"], before["shares"]))
    out = {}
    for r in holders.itertuples():
        if r.cik in had:
            diff = int(r.shares) - int(had[r.cik])
            out[r.cik] = (diff, round(diff / had[r.cik] * 100, 2) if had[r.cik] else None)
        elif complete:
            out[r.cik] = (int(r.shares), None)
        else:
            out[r.cik] = (None, None)
    return out


def lookup(ticker: str, shares_outstanding: float | None = None) -> dict | None:
    """Top holders of ``ticker`` from the newest reduced data set, or None if
    none has been built yet. ``shares_outstanding`` gives each holder's % of
    shares; the previous quarter's data set, when stored, its QoQ change."""
    meta = _latest_meta()
    if meta is None:
        return None
    window = meta["window"]
    change, prev = _change_state(window)
    out = {"ticker": ticker, "asOf": meta["period"], "reportingLag": _LAG, "holders": [],
           "filers": None, "totalShares": None, "cusip": None, "dataset": window, "error": None,
           "change": change}
    cusips = _cusips_for(ticker)
    totals = pd.read_parquet(_DIR / f"totals_{window}.parquet", filters=[("cusip", "in", cusips)]) if cusips else None
    if totals is None or totals.empty:
        out["error"] = f"No 13F holdings of {ticker} were reported for the quarter ending {meta['period']}."
        return out
    # A ticker can map to several CUSIPs (old issues); use the one most held.
    top = totals.sort_values("filers", ascending=False).iloc[0]
    holders = pd.read_parquet(_DIR / f"holders_{window}.parquet", filters=[("cusip", "==", top["cusip"])])
    holders = holders.sort_values("rank").head(_SHOW)
    changes = _changes(holders, top["cusip"], prev) if prev else {}
    out.update(cusip=top["cusip"], filers=int(top["filers"]), totalShares=int(top["shares"]), holders=[
        {"name": r.manager, "shares": int(r.shares), "value": int(r.value),
         "pctFloat": round(int(r.shares) / shares_outstanding * 100, 2) if shares_outstanding else None,
         "changeShares": changes.get(r.cik, (None, None))[0], "changePct": changes.get(r.cik, (None, None))[1]}
        for r in holders.itertuples()])
    return out


def load_previous() -> dict:
    """Start building the previous quarter's data set (a ~100 MB download), on request
    only, so lookups can show the quarter-on-quarter change."""
    meta = _latest_meta()
    if meta is None:
        return {"started": False, "window": None, "error": "No 13F data set has been built yet."}
    name = previous_window(meta["window"])
    if _meta(name):
        return {"started": False, "window": name, "error": None}  # already stored
    ua = _user_agent()
    if not ua:
        return {"started": False, "window": name,
                "error": "SEC EDGAR identity not configured — set EDGAR_IDENTITY to enable 13F data"}
    try:
        url = sec_datasets.find(f"form-13f-data-sets/{name}_form13f.zip", ua)
    except requests.RequestException as exc:
        return {"started": False, "window": name, "error": f"SEC data set probe failed: {exc}"}
    if not url:
        return {"started": False, "window": name, "error": f"The SEC data set {name} was not found."}
    _start_build(name, url)
    if _build_state["window"] != name:  # _start_build did nothing: say why
        if _build_state["window"]:
            return {"started": False, "window": name,
                    "error": "Another 13F download is already running; try again in a minute or two."}
        return {"started": False, "window": name,
                "error": f"The last 13F download failed ({_build_state['error']}); it can be retried after an hour."}
    cache.clear_all("13f")  # so the next lookup reports the download in progress
    return {"started": True, "window": name, "error": None}


# ---------------------------------------------------------------------------
# Download / build in the background
# ---------------------------------------------------------------------------

_build_lock = threading.Lock()
_build_state: dict = {"window": None, "error": None, "failed_at": 0.0}


def _user_agent() -> str | None:
    from ..config import EDGAR_IDENTITY
    return EDGAR_IDENTITY or None


@cached("13f_window")
def _latest_window() -> dict | None:
    """The newest published data set: ``{"window": ..., "url": ...}``."""
    ua = _user_agent()
    if not ua:
        return None
    for name in window_names(date.today()):
        try:
            url = sec_datasets.find(f"form-13f-data-sets/{name}_form13f.zip", ua)
        except requests.RequestException as exc:
            log.warning("13F data set probe failed: %s", exc)
            return None
        if url:
            return {"window": name, "url": url}
    return None


def _build(window: str, url: str) -> None:
    zpath = _DIR / f"{window}.zip.part"
    try:
        _DIR.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        sec_datasets.download(url, zpath, _user_agent())
        write_reduced(window, *reduce_dataset(zpath), url=url)
        log.info("13F data set %s built in %.0f s", window, time.time() - t0)
        _build_state.update(error=None)
    except Exception as exc:
        log.warning("13F data set %s failed: %s", window, exc)
        _build_state.update(error=str(exc), failed_at=time.time())
    finally:
        zpath.unlink(missing_ok=True)
        _build_state["window"] = None
        _build_lock.release()
        cache.clear_all("13f")  # cached lookups said "preparing" or lacked this quarter


def _start_build(window: str, url: str) -> None:
    if _build_state["error"] and time.time() - _build_state["failed_at"] < _RETRY_AFTER:
        return
    if not _build_lock.acquire(blocking=False):
        return  # already running
    _build_state["window"] = window
    threading.Thread(target=_build, args=(window, url), daemon=True, name="13f-build").start()


def _holders_sync(ticker: str) -> dict:
    empty = {"ticker": ticker, "asOf": None, "reportingLag": _LAG, "holders": [], "status": "unavailable"}
    latest = _latest_window()
    have = _latest_meta()
    if latest and (have is None or _window_end(latest["window"]) > _window_end(have["window"])):
        _start_build(latest["window"], latest["url"])
    if have is None:
        if not _user_agent():
            return {**empty, "error": "SEC EDGAR identity not configured — set EDGAR_IDENTITY "
                                      "(\"Your Name you@example.com\") to enable 13F data"}
        if _build_state["window"]:
            return {**empty, "error": "Preparing the SEC 13F data set (a ~100 MB download) — "
                                      "institutional holders appear in a minute or two."}
        return {**empty, "error": "Could not load the SEC 13F data set"
                                  + (f": {_build_state['error']}" if _build_state["error"] else ".")}
    shares_out = _shares_outstanding(ticker)
    out = lookup(ticker, shares_out)
    if out["error"]:
        return out
    ref = pv.ref(
        "sec_edgar", None, f"Form 13F data set, filings {have['window']}", url=have["url"],
        units="shares; value in USD", frequency="quarterly", observed=have["period"],
        note=f"Positions reported on Form 13F-HR by institutional managers for the quarter ending "
             f"{have['period']}, filed up to 45 days later. Share positions only (options and principal "
             f"amounts excluded); a restated report replaces the original and new-holdings amendments are "
             f"added. Filings whose values imply ~1/1000 of other filers' prices are read as reported in "
             f"thousands and multiplied by 1,000. Top {_SHOW} of {out['filers']} filers by shares (CUSIP {out['cusip']}).")
    # A stored data set: fetched when it was built, not at request time (P3-35).
    ref["fetchedAt"] = have["builtAt"]
    prov: dict = {"*": ref}
    yahoo = pv.yahoo(ticker, "sharesOutstanding (Ticker.info)", units="shares")
    prov["pctFloat"] = pv.derived(
        "13F shares held ÷ shares outstanding × 100", [ref, yahoo], title="% of shares outstanding",
        note="Shares outstanding is Yahoo's current count, not the quarter-end one, and covers the listed "
             "class only; for ADRs Yahoo may count ordinary shares rather than ADSs. Float is not used.")
    prev = _meta(out["change"]["previousDataset"])
    if prev:
        before = pv.ref("sec_edgar", None, f"Form 13F data set, filings {prev['window']}", url=prev["url"],
                        units="shares", frequency="quarterly", observed=prev["period"])
        before["fetchedAt"] = prev["builtAt"]
        prov["change"] = pv.derived(
            "shares this quarter − shares the same manager (CIK) reported for the previous quarter; "
            "% = change ÷ previous shares × 100", [ref, before], title="Quarter-on-quarter change",
            note=f"A manager absent from the previous quarter's list is a new position (no %) when that list "
                 f"holds every filer; when it was cut at the top {_TOP_N}, no change is shown.")
    return pv.attach(out, prov)


def _shares_outstanding(ticker: str) -> float | None:
    """``sharesOutstanding`` from the cached Yahoo info, or None."""
    try:
        from . import yfinance_service as yfs
        value = (yfs.get_info(ticker).get("info") or {}).get("sharesOutstanding")
        return float(value) if value else None
    except Exception as exc:
        log.warning("13F: shares outstanding unavailable for %s: %s", ticker, exc)
        return None


@async_cached("13f")
async def get_13f_holders(ticker: str) -> dict:
    """Top 13F institutional holders of ``ticker``."""
    try:
        return await asyncio.to_thread(_holders_sync, ticker)
    except Exception as exc:
        log.warning("get_13f_holders failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "asOf": None, "reportingLag": _LAG, "holders": [], "error": str(exc)}
