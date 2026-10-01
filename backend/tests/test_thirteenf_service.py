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
