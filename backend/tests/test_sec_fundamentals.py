"""Phase 68 item 2: companyfacts -> `fundamental` (fallback chains, Q4, point-in-time)."""
from unittest.mock import patch

import pytest

from backend import config, fetcher, sec_fundamentals as sf, store


def _fact(start, end, val, filed, form="10-Q", accn=None):
    f = {"end": end, "val": val, "filed": filed, "form": form, "accn": accn or f"acc-{filed}"}
    if start:
        f["start"] = start
    return f


def _doc(us_gaap: dict, dei: dict | None = None) -> dict:
    facts = {"us-gaap": {k: {"units": v} for k, v in us_gaap.items()}}
    if dei:
        facts["dei"] = {k: {"units": v} for k, v in dei.items()}
    return {"cik": 1, "entityName": "Test Co", "facts": facts}


# A June fiscal year (like MSFT): Q1 Jul-Sep, Q2 Oct-Dec, Q3 Jan-Mar, Q4 only inside the 10-K.
FY_REVENUE = [
    _fact("2024-07-01", "2024-09-30", 100.0, "2024-10-30"),
    _fact("2024-10-01", "2024-12-31", 110.0, "2025-01-29"),
    _fact("2024-07-01", "2024-12-31", 210.0, "2025-01-29"),          # 6-month YTD: ignored
    _fact("2025-01-01", "2025-03-31", 120.0, "2025-04-30"),
    _fact("2024-07-01", "2025-03-31", 330.0, "2025-04-30"),          # 9-month YTD
    _fact("2024-07-01", "2025-06-30", 480.0, "2025-07-30", "10-K"),
    _fact("2024-07-01", "2025-06-30", 480.0, "2026-07-29", "10-K"),  # unchanged comparative
]


def _by(rows, concept):
    return sorted((r for r in rows if r["concept"] == concept), key=lambda r: (r["period_end"], r["filed"]))


def test_q4_is_fy_minus_the_three_filed_quarters():
    rows = sf.rows(_doc({"Revenues": {"USD": FY_REVENUE}}), "TST")
    q = _by(rows, "Total Revenue|Q")
    assert [(r["period_end"], r["value"]) for r in q] == [
        ("2024-09-30", 100.0), ("2024-12-31", 110.0), ("2025-03-31", 120.0), ("2025-06-30", 150.0)]
    assert q[-1]["source"] == "sec:derived:Q4 us-gaap:Revenues" and q[-1]["filed"] == "2025-07-30"
    fy = _by(rows, "Total Revenue")
    assert [(r["period_end"], r["value"], r["filed"]) for r in fy] == [("2025-06-30", 480.0, "2025-07-30")]


def test_q4_falls_back_to_the_nine_month_ytd():
    facts = [f for f in FY_REVENUE if f["end"] != "2024-12-31" or f["start"] != "2024-10-01"]
    q = _by(sf.rows(_doc({"Revenues": {"USD": facts}}), "TST"), "Total Revenue|Q")
    assert q[-1]["period_end"] == "2025-06-30" and q[-1]["value"] == 150.0


def test_no_q4_without_the_quarters_and_never_for_eps():
    doc = _doc({"Revenues": {"USD": [_fact("2024-07-01", "2025-06-30", 480.0, "2025-07-30", "10-K")]},
                "EarningsPerShareDiluted": {"USD/shares": [
                    _fact("2024-07-01", "2024-09-30", 1.0, "2024-10-30"),
                    _fact("2024-10-01", "2024-12-31", 1.1, "2025-01-29"),
                    _fact("2025-01-01", "2025-03-31", 1.2, "2025-04-30"),
                    _fact("2024-07-01", "2025-06-30", 4.8, "2025-07-30", "10-K")]}})
    rows = sf.rows(doc, "TST")
    assert _by(rows, "Total Revenue|Q") == []
    assert [r["period_end"] for r in _by(rows, "Diluted EPS|Q")] == ["2024-09-30", "2024-12-31", "2025-03-31"]


def test_revenue_chain_picks_the_first_tag_per_period():
    doc = _doc({"Revenues": {"USD": [_fact("2023-01-01", "2023-12-31", 900.0, "2024-02-01", "10-K")]},
                "RevenueFromContractWithCustomerExcludingAssessedTax": {"USD": [
                    _fact("2023-01-01", "2023-12-31", 850.0, "2024-02-01", "10-K"),
                    _fact("2024-01-01", "2024-12-31", 950.0, "2025-02-01", "10-K")]}})
    fy = _by(sf.rows(doc, "TST"), "Total Revenue")
    assert [(r["period_end"], r["value"], r["source"]) for r in fy] == [
        ("2023-12-31", 900.0, "sec:us-gaap:Revenues"),
        ("2024-12-31", 950.0, "sec:us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax")]


def test_liabilities_are_derived_and_labelled_when_missing():
    doc = _doc({"LiabilitiesAndStockholdersEquity": {"USD": [_fact(None, "2025-12-31", 1000.0, "2026-02-01", "10-K")]},
                "StockholdersEquity": {"USD": [_fact(None, "2025-12-31", 300.0, "2026-02-01", "10-K")]}})
    (row,) = _by(sf.rows(doc, "TST"), "Total Liabilities Net Minority Interest")
    assert row["value"] == 700.0
    assert row["source"] == "sec:derived:us-gaap:LiabilitiesAndStockholdersEquity - us-gaap:StockholdersEquity"


def test_restatement_adds_a_version_and_outflows_take_yahoos_sign():
    doc = _doc({"PaymentsToAcquirePropertyPlantAndEquipment": {"USD": [
        _fact("2024-01-01", "2024-12-31", 50.0, "2025-02-01", "10-K"),
        _fact("2024-01-01", "2024-12-31", 50.0, "2025-05-01"),            # comparative, same value
        _fact("2024-01-01", "2024-12-31", 55.0, "2026-02-01", "10-K")]}})  # restated
    capex = _by(sf.rows(doc, "TST"), "Capital Expenditure")
    assert [(r["filed"], r["value"]) for r in capex] == [("2025-02-01", -50.0), ("2026-02-01", -55.0)]


def test_shares_prefer_dei_and_skip_ambiguous_multi_class_cover_pages():
    dei = {"EntityCommonStockSharesOutstanding": {"shares": [
        _fact(None, "2026-01-20", 10.0, "2026-02-01", "10-K"),
        _fact(None, "2026-04-20", 6.0, "2026-05-01", "10-Q"),   # two classes, one filing:
        _fact(None, "2026-04-20", 4.0, "2026-05-01", "10-Q")]}}  # ambiguous, dropped
    gaap = {"CommonStockSharesOutstanding": {"shares": [_fact(None, "2025-12-31", 9.0, "2026-02-01", "10-K")]}}
    rows = _by(sf.rows(_doc(gaap, dei), "TST"), "Shares Outstanding")
    assert [(r["period_end"], r["value"], r["source"]) for r in rows] == [
        ("2025-12-31", 9.0, "sec:us-gaap:CommonStockSharesOutstanding"),
        ("2026-01-20", 10.0, "sec:dei:EntityCommonStockSharesOutstanding")]


def test_non_periodic_forms_are_ignored():
    doc = _doc({"NetIncomeLoss": {"USD": [_fact("2025-01-01", "2025-12-31", 10.0, "2026-02-01", "10-K"),
                                          _fact("2025-01-01", "2025-12-31", 9.9, "2026-04-01", "DEF 14A")]}})
    assert [r["value"] for r in _by(sf.rows(doc, "TST"), "Net Income")] == [10.0]
    assert set(sf.filings(doc)) == {"acc-2026-02-01", "acc-2026-04-01"}  # every filing is known


# --- the fetcher task -------------------------------------------------------

TABLES = ("fetch_queue", "security", "source_health", "fundamental", "sec_filing")


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(config, "EDGAR_IDENTITY", "Jane Doe jane@example.com")
    store.init_schema()
    with store.connect() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")
    yield
    with store.connect() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")


def test_run_facts_stores_every_symbol_of_the_cik_and_is_resumable(db):
    store.upsert("security", [dict(symbol="GOOG", cik="0001652044"), dict(symbol="GOOGL", cik="0001652044"),
                              dict(symbol="AAPL", cik="0000320193")], ("symbol",))
    fetcher.queue_facts_backfill()
    with store.connect() as conn:
        assert sorted(r[0] for r in conn.execute("SELECT key FROM fetch_queue WHERE kind='facts'")) == [
            "0000320193", "0001652044"]
    doc = _doc({"Revenues": {"USD": FY_REVENUE}})
    with patch("backend.sources.source_sec.companyfacts", return_value=doc):
        n = fetcher.run_facts("0001652044")
    assert n == 2 * len(sf.rows(doc, "X"))
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(DISTINCT symbol) FROM fundamental").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM sec_filing").fetchone()[0] == len(sf.filings(doc))
        conn.execute("DELETE FROM fetch_queue")
    fetcher.queue_facts_backfill()  # resumes with only what is left
    with store.connect() as conn:
        assert [r[0] for r in conn.execute("SELECT key FROM fetch_queue")] == ["0000320193"]
    status = fetcher.sec_status()["facts"]
    assert status["total"] == 2 and status["done"] == 1


def test_run_facts_with_nothing_usable_stores_nothing(db):
    store.upsert("security", [dict(symbol="ASML", cik="0000937966")], ("symbol",))
    with patch("backend.sources.source_sec.companyfacts", return_value=None), pytest.raises(RuntimeError):
        fetcher.run_facts("0000937966")
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM fundamental").fetchone()[0] == 0
        assert conn.execute("SELECT facts_at FROM security").fetchone()[0] is None
