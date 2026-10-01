"""Insider aggregate from the SEC's quarterly insider transactions data sets.

The synthetic ZIP uses the real data-set layout (tab-separated SUBMISSION,
REPORTINGOWNER and NONDERIV_TRANS files, DD-MON-YYYY dates). The AAPL sale
mirrors a real Form 4: Jennifer Newstead sold 2,399 shares at $340.06.
"""
from __future__ import annotations

import zipfile
from datetime import date

import pytest

from backend.services import insider_aggregator as agg
from backend.services import insider_dataset as ds

SUBMISSION = [
    ("ACCESSION_NUMBER", "FILING_DATE", "PERIOD_OF_REPORT", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERNAME",
     "ISSUERTRADINGSYMBOL"),
    ("A-1", "24-JUN-2026", "22-JUN-2026", "4", "320193", "Apple Inc.", "AAPL"),
    ("A-2", "02-JUN-2026", "30-MAY-2026", "4", "320193", "Apple Inc.", "AAPL"),
    ("A-3", "25-JUN-2026", "22-JUN-2026", "4/A", "320193", "Apple Inc.", "AAPL"),   # amendment: ignored
    ("A-4", "10-JUN-2026", "08-JUN-2026", "4", "1067983", "Berkshire", "BRK.B"),
    ("A-5", "10-JUN-2026", "08-JUN-2026", "4", "46080", "HEICO", "HEI, HEI.A"),
    ("A-6", "15-JUN-2026", "12-JUN-2026", "4", "34088", "Exxon", "XOM"),
    ("A-7", "16-JUN-2026", "12-JUN-2026", "4", "34088", "Exxon", "XOM"),
    ("A-8", "17-JUN-2026", "12-JUN-2026", "4", "34088", "Exxon", "XOM"),
    ("A-9", "17-JUN-2026", "12-JUN-2026", "4", "999", "Tiny Co", "TINY"),           # not in the S&P 500
    ("A-10", "18-JUN-2026", "02-JAN-2026", "4", "34088", "Exxon", "XOM"),           # late filing of an old trade
    ("A-11", "20-MAY-2026", "18-MAY-2026", "3", "34088", "Exxon", "XOM"),           # Form 3: no trades
]
REPORTINGOWNER = [
    ("ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"),
    ("A-1", "1", "Newstead Jennifer", "Officer", "SVP, GC and Government Affairs"),
    ("A-2", "2", "Levinson Arthur D", "Director", ""),
    ("A-3", "1", "Newstead Jennifer", "Officer", "SVP, GC and Government Affairs"),
    ("A-4", "3", "Buffett Warren E", "Director,Officer,TenPercentOwner", "Chairman and CEO"),
    ("A-5", "4", "Mendelson Laurans", "Director,Officer", "CEO"),
    # Joint filing: two reporting owners, one trade — counted once
    ("A-6", "5", "Woods Darren", "Director,Officer", "CEO"),
    ("A-6", "6", "Woods Family Trust", "Other", ""),
    ("A-7", "7", "Mikells Kathryn", "Officer", "CFO"),
    ("A-8", "8", "Burns Ursula", "Director", ""),
    ("A-9", "9", "Someone", "Director", ""),
    ("A-10", "10", "Late Filer", "Director", ""),
]
NONDERIV_TRANS = [
    ("ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
     "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"),
    ("A-1", "1", "22-JUN-2026", "S", "2399.0", "340.06", "D"),
    ("A-1", "2", "22-JUN-2026", "F", "300.0", "340.06", "D"),       # tax withholding: not open market
    ("A-2", "3", "30-MAY-2026", "P", "1000.0", "220.5", "A"),
    ("A-3", "4", "22-JUN-2026", "S", "2399.0", "340.06", "D"),
    ("A-4", "5", "08-JUN-2026", "P", "100.0", "500.0", "A"),
    ("A-5", "6", "08-JUN-2026", "S", "10.0", "", "D"),              # no price reported
    ("A-6", "7", "12-JUN-2026", "P", "100.0", "110.0", "A"),
    ("A-7", "8", "12-JUN-2026", "P", "200.0", "110.0", "A"),
    ("A-8", "9", "12-JUN-2026", "P", "300.0", "110.0", "A"),
    ("A-9", "10", "12-JUN-2026", "P", "5.0", "1.0", "A"),
    ("A-10", "11", "02-JAN-2026", "P", "9999.0", "100.0", "A"),
]
SP500 = [
    {"symbol": "AAPL", "sector": "Information Technology"},
    {"symbol": "BRK-B", "sector": "Financials"},
    {"symbol": "HEI", "sector": "Industrials"},
    {"symbol": "XOM", "sector": "Energy"},
    {"symbol": "MSFT", "sector": "Information Technology"},
]


def _tsv(rows):
    return "\n".join("\t".join(r) for r in rows) + "\n"


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / "2026q2_form345.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("SUBMISSION.tsv", _tsv(SUBMISSION))
        z.writestr("REPORTINGOWNER.tsv", _tsv(REPORTINGOWNER))
        z.writestr("NONDERIV_TRANS.tsv", _tsv(NONDERIV_TRANS))
    return path


def test_quarter_names_newest_ended_first():
    assert ds.quarter_names(date(2026, 10, 1)) == ["2026q3", "2026q2", "2026q1", "2025q4"]
    assert ds.quarter_names(date(2027, 1, 5), count=2) == ["2026q4", "2026q3"]
    assert ds.quarter_end("2026q2") == date(2026, 6, 30)


def test_reduce_keeps_open_market_trades_from_original_form4s(dataset):
    trades = ds.reduce_dataset(dataset)
    assert len(trades) == 9  # 11 rows − tax withholding − the 4/A
    sale = trades[trades["accession"] == "A-1"].iloc[0]
    assert (sale["insiderName"], sale["title"], sale["code"]) == (
        "Newstead Jennifer", "SVP, GC and Government Affairs", "S")
    assert (sale["shares"], sale["price"], sale["date"]) == (2399.0, 340.06, "2026-06-22")
    joint = trades[trades["accession"] == "A-6"]
    assert list(joint["insiderName"]) == ["Woods Darren"]
    assert trades.loc[trades["accession"] == "A-2", "title"].iloc[0] == "Director"


def test_aggregate_known_values(dataset):
    out = agg.aggregate(ds.reduce_dataset(dataset), SP500, "2026q2")

    assert out["period"] == {"start": "2026-04-01", "end": "2026-06-30"}
    assert out["asOf"] == "2026-06-30"
    assert out["tickersChecked"] == 5
    assert out["tickersWithData"] == 4                    # AAPL, BRK-B, HEI, XOM
    assert (out["buyCount"], out["sellCount"]) == (5, 2)  # TINY and the January trade excluded
    assert out["totalSellValue"] == round(2399 * 340.06)  # HEICO sale has no price: value 0
    assert out["totalBuyValue"] == 220500 + 50000 + 11000 + 22000 + 33000
    assert out["buySellRatio"] == 2.5

    assert out["clusterBuys"] == [{"ticker": "XOM", "insiderCount": 3, "transactionCount": 3,
                                   "totalValue": 66000.0, "dateRange": "2026-06-12 to 2026-06-12"}]
    top = out["topTrades"][0]
    assert (top["ticker"], top["insiderName"], top["transactionType"], top["totalValue"]) == (
        "AAPL", "Newstead Jennifer", "Sell", round(2399 * 340.06, 2))
    sectors = {s["sector"]: s for s in out["sectorSentiment"]}
    assert (sectors["Information Technology"]["buys"], sectors["Information Technology"]["sells"]) == (1, 1)
    assert sectors["Energy"]["netBuyRatio"] == 1.0
    assert {t["ticker"] for t in out["topTrades"]} == {"AAPL", "BRK-B", "HEI", "XOM"}


def test_load_latest_uses_newest_published_quarter(dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "_DIR", tmp_path / "form345")
    published = {"insider-transactions-data-sets/2026q2_form345.zip": "https://sec.example/2026q2_form345.zip"}
    probes = []

    def find(path, ua):
        probes.append(path)
        return published.get(path)

    monkeypatch.setattr(ds.sec_datasets, "find", find)
    monkeypatch.setattr(ds.sec_datasets, "download", lambda url, dest, ua: dest.write_bytes(dataset.read_bytes()))
    monkeypatch.setattr(ds, "_user_agent", lambda: "Test Person test@example.com")
    monkeypatch.setattr(ds, "date", type("D", (), {"today": staticmethod(lambda: date(2026, 10, 1))}))

    quarter, trades, url = ds.load_latest()
    assert (quarter, len(trades), url) == ("2026q2", 9, "https://sec.example/2026q2_form345.zip")
    assert probes == ["insider-transactions-data-sets/2026q3_form345.zip",
                      "insider-transactions-data-sets/2026q2_form345.zip"]

    # Second call: the stored quarter is reused, only the newer one is probed again.
    probes.clear()
    assert ds.load_latest()[0] == "2026q2"
    assert probes == ["insider-transactions-data-sets/2026q3_form345.zip"]
