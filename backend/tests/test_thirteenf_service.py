"""13F holders from the SEC's quarterly Form 13F data sets (offline).

The synthetic ZIP uses the real data-set layout (tab-separated SUBMISSION,
COVERPAGE and INFOTABLE files, DD-MON-YYYY dates, VALUE in dollars).
"""
from __future__ import annotations

import zipfile
from datetime import date

import pandas as pd
import pytest

from backend.services import thirteenf_service as tf

AAPL = "037833100"
MSFT = "594918104"

SUBMISSION = [
    ("ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"),
    ("A-1", "14-MAY-2026", "13F-HR", "0000000001", "31-MAR-2026"),    # Fund One
    ("A-2", "15-MAY-2026", "13F-HR", "0000000002", "31-MAR-2026"),    # Fund Two, later restated
    ("A-3", "20-MAY-2026", "13F-HR/A", "0000000002", "31-MAR-2026"),  # restatement replaces A-2
    ("A-4", "21-MAY-2026", "13F-HR/A", "0000000001", "31-MAR-2026"),  # new holdings add to A-1
    ("A-5", "10-MAR-2026", "13F-HR", "0000000003", "31-DEC-2025"),    # previous quarter: excluded
    ("A-6", "12-MAY-2026", "13F-NT", "0000000004", "31-MAR-2026"),    # notice, no holdings
    # Seen in the real data: a new-holdings amendment filed as a plain 13F-HR
    ("A-7", "22-MAY-2026", "13F-HR", "0000000001", "31-MAR-2026"),
    # Seen in the real data: a filer still reporting VALUE in thousands
    ("A-8", "13-MAY-2026", "13F-HR", "0000000005", "31-MAR-2026"),
]
COVERPAGE = [
    ("ACCESSION_NUMBER", "REPORTCALENDARORQUARTER", "ISAMENDMENT", "AMENDMENTNO", "AMENDMENTTYPE",
     "FILINGMANAGER_NAME"),
    ("A-1", "31-MAR-2026", "", "", "", "Fund One LP"),
    ("A-2", "31-MAR-2026", "", "", "", "Fund Two LLC"),
    ("A-3", "31-MAR-2026", "Y", "1", "RESTATEMENT", "Fund Two LLC"),
    ("A-4", "31-MAR-2026", "Y", "1", "NEW HOLDINGS", "Fund One LP"),
    ("A-5", "31-DEC-2025", "", "", "", "Fund Three"),
    ("A-6", "31-MAR-2026", "", "", "", "Fund Four"),
    ("A-7", "31-MAR-2026", "Y", "2", "NEW HOLDINGS", "Fund One LP"),
    ("A-8", "31-MAR-2026", "", "", "", "Fund Five"),
]
INFOTABLE = [
    ("ACCESSION_NUMBER", "INFOTABLE_SK", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "FIGI", "VALUE",
     "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL", "INVESTMENTDISCRETION"),
    # Fund One: AAPL split over two rows (summed), plus an AAPL call option (excluded)
    ("A-1", "1", "APPLE INC", "COM", AAPL, "", "2000000", "10000", "SH", "", "SOLE"),
    ("A-1", "2", "APPLE INC", "COM", AAPL, "", "1000000", "5000", "SH", "", "DFND"),
    ("A-1", "3", "APPLE INC", "CALL", AAPL, "", "999999", "99999", "SH", "Call", "SOLE"),
    ("A-1", "4", "MICROSOFT", "COM", MSFT, "", "400000", "1000", "SH", "", "SOLE"),
    # Fund One new-holdings amendment: more AAPL
    ("A-4", "5", "APPLE INC", "COM", AAPL, "", "200000", "1000", "SH", "", "SOLE"),
    # Fund Two original (superseded) and restatement
    ("A-2", "6", "APPLE INC", "COM", AAPL, "", "100", "1", "SH", "", "SOLE"),
    ("A-3", "7", "APPLE INC", "COM", AAPL, "", "4000000", "20000", "SH", "", "SOLE"),
    # Bond principal amount, not shares: excluded
    ("A-3", "8", "APPLE INC", "NOTE", AAPL, "", "500000", "500000", "PRN", "", "SOLE"),
    ("A-7", "10", "MICROSOFT", "COM", MSFT, "", "200000", "500", "SH", "", "SOLE"),
    ("A-8", "11", "APPLE INC", "COM", AAPL, "", "800", "4000", "SH", "", "SOLE"),
    ("A-8", "12", "MICROSOFT", "COM", MSFT, "", "200", "500", "SH", "", "SOLE"),
    # Previous-quarter filer: excluded
    ("A-5", "9", "APPLE INC", "COM", AAPL, "", "9000000", "90000", "SH", "", "SOLE"),
]


def _tsv(rows):
    return "\n".join("\t".join(r) for r in rows) + "\n"


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / "01mar2026-31may2026_form13f.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("SUBMISSION.tsv", _tsv(SUBMISSION))
        z.writestr("COVERPAGE.tsv", _tsv(COVERPAGE))
        z.writestr("INFOTABLE.tsv", _tsv(INFOTABLE))
    return path


def test_window_names_step_back_by_filing_quarter():
    assert tf.window_names(date(2026, 10, 1))[:4] == [
        "01jun2026-31aug2026", "01mar2026-31may2026", "01dec2025-28feb2026", "01sep2025-30nov2025"]
    assert tf.window_names(date(2028, 4, 2))[0] == "01dec2027-29feb2028"  # leap year


def test_reduce_picks_the_quarter_and_applies_amendments(dataset):
    holders, totals, period = tf.reduce_dataset(dataset, chunksize=3)

    assert period == "2026-03-31"
    aapl = holders[holders["cusip"] == AAPL].sort_values("rank")
    assert list(aapl["manager"]) == ["Fund Two LLC", "Fund One LP", "Fund Five"]
    assert list(aapl["shares"]) == [20000, 16000, 4000]     # restated; 10k + 5k + 1k new holdings
    assert list(aapl["value"]) == [4_000_000, 3_200_000, 800_000]  # dollars, not thousands
    t = totals.set_index("cusip").loc[AAPL]
    assert (t["filers"], t["shares"]) == (3, 40000)
    msft = holders[holders["cusip"] == MSFT]
    assert list(msft["shares"]) == [1500, 500]              # Fund One: 1,000 + 500 from A-7
    # Fund Five's whole filing is in thousands ($0.20/share vs $200): rescaled
    five = holders[holders["manager"] == "Fund Five"].set_index("cusip")["value"]
    assert (five[AAPL], five[MSFT]) == (800_000, 200_000)


def test_holders_lookup_maps_ticker_to_cusip(dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(tf, "_DIR", tmp_path)
    tf.write_reduced("01mar2026-31may2026", *tf.reduce_dataset(dataset))
    monkeypatch.setattr(tf, "_cusips_for", lambda ticker: [AAPL, "000000000"] if ticker == "AAPL" else [])

    out = tf.lookup("AAPL")

    assert out["asOf"] == "2026-03-31"
    assert out["filers"] == 3 and out["totalShares"] == 40000
    assert [h["name"] for h in out["holders"]] == ["Fund Two LLC", "Fund One LP", "Fund Five"]
    assert out["holders"][0] == {"name": "Fund Two LLC", "shares": 20000, "value": 4_000_000,
                                 "pctFloat": None, "changeShares": None, "changePct": None}
    assert tf.lookup("ZZZZ")["holders"] == []


def test_share_class_tickers_match_the_mapping_spelling():
    # The bundled CUSIP map spells Berkshire class B "BRKB"; Yahoo uses "BRK-B".
    assert tf._ticker_keys("BRK-B") == {"BRK-B", "BRKB"}
    assert tf._ticker_keys("BF.B") == {"BF.B", "BFB"}
    assert tf._ticker_keys("AAPL") == {"AAPL"}


def test_files_built_by_older_code_are_ignored(dataset, tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(tf, "_DIR", tmp_path)
    tf.write_reduced("01mar2026-31may2026", *tf.reduce_dataset(dataset))
    meta = tmp_path / "meta_01mar2026-31may2026.json"
    m = json.loads(meta.read_text())
    assert tf._latest_meta()["format"] == tf._FORMAT
    meta.write_text(json.dumps({**m, "format": tf._FORMAT - 1}))
    assert tf._latest_meta() is None  # triggers a rebuild


def test_latest_window_finds_files_at_the_new_sec_location(monkeypatch):
    # Jun-Aug 2026 was published only under /files/datastandardsinnovation/.
    seen = []

    def find(path, ua):
        seen.append(path)
        return "https://new.example/" + path if path.startswith("form-13f-data-sets/01jun2026") else None

    monkeypatch.setattr(tf.sec_datasets, "find", find)
    monkeypatch.setattr(tf, "_user_agent", lambda: "Test Person test@example.com")
    class Oct1(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 1)

    monkeypatch.setattr(tf, "date", Oct1)
    out = tf._latest_window.__wrapped__()
    assert out == {"window": "01jun2026-31aug2026",
                   "url": "https://new.example/form-13f-data-sets/01jun2026-31aug2026_form13f.zip"}
    assert seen == ["form-13f-data-sets/01jun2026-31aug2026_form13f.zip"]


# ---------------------------------------------------------------------------
# P2-37: quarter-on-quarter change and % of shares outstanding
# ---------------------------------------------------------------------------

CUR = "01mar2026-31may2026"   # quarter ending 2026-03-31 (the `dataset` fixture)
PREV = "01dec2025-28feb2026"  # quarter ending 2025-12-31

# Previous quarter: Fund One held 12,000 AAPL, Fund Two 25,000; Fund Five held none.
PREV_SUBMISSION = [
    SUBMISSION[0],
    ("B-1", "10-FEB-2026", "13F-HR", "0000000001", "31-DEC-2025"),
    ("B-2", "11-FEB-2026", "13F-HR", "0000000002", "31-DEC-2025"),
]
PREV_COVERPAGE = [
    COVERPAGE[0],
    ("B-1", "31-DEC-2025", "", "", "", "Fund One LP"),
    ("B-2", "31-DEC-2025", "", "", "", "Fund Two LLC"),
]
PREV_INFOTABLE = [
    INFOTABLE[0],
    ("B-1", "1", "APPLE INC", "COM", AAPL, "", "2400000", "12000", "SH", "", "SOLE"),
    ("B-2", "2", "APPLE INC", "COM", AAPL, "", "5000000", "25000", "SH", "", "SOLE"),
]


@pytest.fixture
def prev_dataset(tmp_path):
    path = tmp_path / f"{PREV}_form13f.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("SUBMISSION.tsv", _tsv(PREV_SUBMISSION))
        z.writestr("COVERPAGE.tsv", _tsv(PREV_COVERPAGE))
        z.writestr("INFOTABLE.tsv", _tsv(PREV_INFOTABLE))
    return path


def test_previous_window_steps_back_one_filing_quarter():
    assert tf.previous_window(CUR) == PREV
    assert tf.previous_window("01dec2027-29feb2028") == "01sep2027-30nov2027"


def test_the_two_newest_data_sets_are_kept(dataset, prev_dataset, tmp_path, monkeypatch):
    store = tmp_path / "13f"
    monkeypatch.setattr(tf, "_DIR", store)
    tf.write_reduced(CUR, *tf.reduce_dataset(dataset))
    tf.write_reduced(PREV, *tf.reduce_dataset(prev_dataset))   # older, built on request: keeps CUR
    assert {p.name for p in store.glob("meta_*.json")} == {f"meta_{CUR}.json", f"meta_{PREV}.json"}
    assert tf._latest_meta()["window"] == CUR

    tf.write_reduced("01jun2026-31aug2026", *tf.reduce_dataset(dataset))  # a newer quarter: PREV drops out
    assert {p.name for p in store.glob("meta_*.json")} == {
        f"meta_{CUR}.json", "meta_01jun2026-31aug2026.json"}


def test_lookup_computes_qoq_change_and_pct_of_shares_outstanding(dataset, prev_dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(tf, "_DIR", tmp_path / "13f")
    tf.write_reduced(PREV, *tf.reduce_dataset(prev_dataset))
    tf.write_reduced(CUR, *tf.reduce_dataset(dataset))
    monkeypatch.setattr(tf, "_cusips_for", lambda ticker: [AAPL])

    out = tf.lookup("AAPL", shares_outstanding=1_000_000)

    rows = {h["name"]: h for h in out["holders"]}
    # Fund Two: 20,000 now vs 25,000 → −5,000, −5,000 / 25,000 = −20 %; 20,000 / 1,000,000 = 2 % of shares
    assert (rows["Fund Two LLC"]["changeShares"], rows["Fund Two LLC"]["changePct"]) == (-5000, -20.0)
    assert rows["Fund Two LLC"]["pctFloat"] == 2.0
    # Fund One: 16,000 vs 12,000 → +4,000, +33.33 %; 1.6 % of shares
    assert (rows["Fund One LP"]["changeShares"], rows["Fund One LP"]["changePct"]) == (4000, 33.33)
    assert rows["Fund One LP"]["pctFloat"] == 1.6
    # Fund Five: absent from a complete previous list (2 filers ≤ top 25) → a new position
    assert (rows["Fund Five"]["changeShares"], rows["Fund Five"]["changePct"]) == (4000, None)
    assert out["change"] == {"available": True, "previousAsOf": "2025-12-31", "previousDataset": PREV,
                             "reason": None, "canLoad": False, "loading": False}


def test_lookup_without_the_previous_quarter_offers_to_load_it(dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(tf, "_DIR", tmp_path / "13f")
    tf.write_reduced(CUR, *tf.reduce_dataset(dataset))
    monkeypatch.setattr(tf, "_cusips_for", lambda ticker: [AAPL])

    out = tf.lookup("AAPL", shares_outstanding=None)

    assert all(h["changeShares"] is None and h["pctFloat"] is None for h in out["holders"])
    assert out["change"]["available"] is False and out["change"]["canLoad"] is True
    assert out["change"]["previousDataset"] == PREV
    assert "previous quarter" in out["change"]["reason"]


def test_holder_outside_a_truncated_previous_list_has_no_change(dataset, prev_dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(tf, "_DIR", tmp_path / "13f")
    holders, totals, period = tf.reduce_dataset(prev_dataset)
    totals.loc[totals["cusip"] == AAPL, "filers"] = 40   # the stored previous list is the top 25 of 40
    tf.write_reduced(PREV, holders, totals, period)
    tf.write_reduced(CUR, *tf.reduce_dataset(dataset))
    monkeypatch.setattr(tf, "_cusips_for", lambda ticker: [AAPL])

    rows = {h["name"]: h for h in tf.lookup("AAPL")["holders"]}

    assert (rows["Fund Five"]["changeShares"], rows["Fund Five"]["changePct"]) == (None, None)
    assert rows["Fund Two LLC"]["changeShares"] == -5000


def test_loading_the_previous_quarter_starts_its_build(dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(tf, "_DIR", tmp_path / "13f")
    tf.write_reduced(CUR, *tf.reduce_dataset(dataset))
    monkeypatch.setattr(tf, "_user_agent", lambda: "Test Person test@example.com")
    monkeypatch.setattr(tf.sec_datasets, "find", lambda path, ua: "https://sec.example/" + path)
    started = []

    def fake_start(window, url):
        started.append((window, url))
        tf._build_state["window"] = window  # as the real _start_build does

    monkeypatch.setattr(tf, "_start_build", fake_start)
    monkeypatch.setitem(tf._build_state, "window", None)
    monkeypatch.setitem(tf._build_state, "error", None)

    out = tf.load_previous()

    assert started == [(PREV, f"https://sec.example/form-13f-data-sets/{PREV}_form13f.zip")]
    assert out == {"started": True, "window": PREV, "error": None}


def _previous_ready(dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(tf, "_DIR", tmp_path / "13f")
    tf.write_reduced(CUR, *tf.reduce_dataset(dataset))
    monkeypatch.setattr(tf, "_user_agent", lambda: "Test Person test@example.com")
    monkeypatch.setattr(tf.sec_datasets, "find", lambda path, ua: "https://sec.example/" + path)
    monkeypatch.setattr(tf.cache, "clear_all", lambda *a, **k: None)


def test_loading_previous_while_another_build_runs_reports_not_started(dataset, tmp_path, monkeypatch):
    _previous_ready(dataset, tmp_path, monkeypatch)
    monkeypatch.setitem(tf._build_state, "window", "01jun2026-31aug2026")
    monkeypatch.setitem(tf._build_state, "error", None)
    monkeypatch.setattr(tf, "_start_build", lambda window, url: None)  # lock is held: does nothing

    out = tf.load_previous()

    assert out["started"] is False and out["window"] == PREV
    assert "already running" in out["error"]


def test_loading_previous_while_it_is_already_building_is_started(dataset, tmp_path, monkeypatch):
    _previous_ready(dataset, tmp_path, monkeypatch)
    monkeypatch.setitem(tf._build_state, "window", PREV)
    monkeypatch.setitem(tf._build_state, "error", None)
    monkeypatch.setattr(tf, "_start_build", lambda window, url: None)

    assert tf.load_previous() == {"started": True, "window": PREV, "error": None}


def test_loading_previous_after_a_recent_failure_reports_the_backoff(dataset, tmp_path, monkeypatch):
    _previous_ready(dataset, tmp_path, monkeypatch)
    monkeypatch.setitem(tf._build_state, "window", None)
    monkeypatch.setitem(tf._build_state, "error", "connection reset")
    monkeypatch.setitem(tf._build_state, "failed_at", tf.time.time())
    monkeypatch.setattr(tf.threading, "Thread", lambda *a, **k: pytest.fail("must not start a download"))

    out = tf.load_previous()

    assert out["started"] is False and out["window"] == PREV
    assert "connection reset" in out["error"] and "an hour" in out["error"]


def test_holders_response_sources_the_new_columns(dataset, prev_dataset, tmp_path, monkeypatch, client):
    monkeypatch.setattr(tf, "_DIR", tmp_path / "13f")
    tf.write_reduced(PREV, *tf.reduce_dataset(prev_dataset))
    tf.write_reduced(CUR, *tf.reduce_dataset(dataset))
    monkeypatch.setattr(tf, "_cusips_for", lambda ticker: [AAPL])
    monkeypatch.setattr(tf, "_latest_window", lambda: None)
    monkeypatch.setattr(tf, "_shares_outstanding", lambda t: 1_000_000)

    out = client.get("/api/market/13f?ticker=AAPL").json()

    assert out["holders"][0]["pctFloat"] == 2.0            # Fund Two: 20,000 / 1,000,000
    prov = out["provenance"]
    assert {r["provider"] for r in prov["pctFloat"]["inputs"]} == {"sec_edgar", "yahoo"}
    assert prov["change"]["inputs"][1]["observed"] == "2025-12-31"


def test_previous_quarter_route_starts_the_download(monkeypatch, client):
    monkeypatch.setattr(tf, "load_previous", lambda: {"started": True, "window": PREV, "error": None})
    assert client.post("/api/market/13f/previous").json() == {"started": True, "window": PREV, "error": None}
