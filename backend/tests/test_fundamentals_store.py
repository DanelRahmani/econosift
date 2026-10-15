"""Phase 68 item 4: fundamentals are read from the store (SEC facts + snapshot + stored Yahoo info)."""
from unittest.mock import patch

import pandas as pd
import pytest

from backend import cache, fundamentals_store as fs, store, yahoo_info
from backend.services import yfinance_service as yfs

TABLES = ("fetch_queue", "security", "fundamental", "fundamental_summary", "yahoo_doc", "quote_latest", "price_daily",
          "source_health")


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    cache.clear_all("yf_info")
    with store.connect() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")
    yield
    cache.clear_all("yf_info")
    with store.connect() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")


def _fact(concept, end, value, filed="2026-08-01", source="sec:us-gaap:X", unit="USD", form="10-Q"):
    return dict(symbol="ACME", concept=concept, period_end=end, filed=filed, value=value, unit=unit,
                form=form, source=source)


QUARTERS = ("2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30")


def _store_acme():
    rows = []
    for i, end in enumerate(QUARTERS):
        rows += [_fact("Total Revenue|Q", end, 100.0 + 10 * i), _fact("Net Income|Q", end, 10.0 + i),
                 _fact("Operating Income|Q", end, 20.0), _fact("Operating Cash Flow|Q", end, 15.0),
                 _fact("Capital Expenditure|Q", end, -5.0)]
    rows.append(_fact("Total Revenue|Q", "2025-06-30", 90.0))  # a year before the latest quarter
    for end, rev, ni in (("2025-12-31", 430.0, 44.0), ("2024-12-31", 400.0, 40.0)):
        rows += [_fact("Total Revenue", end, rev, form="10-K"), _fact("Net Income", end, ni, form="10-K"),
                 _fact("Cost Of Revenue", end, rev / 2, form="10-K"),
                 _fact("Total Assets", end, 1000.0, form="10-K"), _fact("Stockholders Equity", end, 500.0, form="10-K")]
    rows += [_fact("Total Assets", "2026-06-30", 1100.0), _fact("Stockholders Equity", "2026-06-30", 550.0),
             _fact("Long Term Debt", "2026-06-30", 200.0), _fact("Current Debt", "2026-06-30", 50.0),
             _fact("Cash And Cash Equivalents", "2026-06-30", 80.0),
             _fact("Current Assets", "2026-06-30", 300.0), _fact("Current Liabilities", "2026-06-30", 150.0),
             _fact("Shares Outstanding", "2026-07-20", 10.0, unit="shares", source="sec:dei:Shares")]
    rows.append(_fact("Total Revenue", "2025-12-31", 420.0, filed="2026-02-01", form="10-K"))  # the original filing
    store.replace_fundamentals(["ACME"], rows, "sec:")
    store.upsert("security", [dict(symbol="ACME", cik="0000000042", sector="Health Care", industry="Pharma",
                                   facts_at="2026-08-02T00:00:00Z")], ("symbol",))
    store.upsert("quote_latest", [dict(symbol="ACME", price=50.0, market_cap=500.0, pe=11.0, div_yield=1.5,
                                       ts=1_760_000_000, name="Acme Corp", currency="USD")], ("symbol",))


def test_info_is_computed_from_sec_facts_and_the_snapshot():
    _store_acme()
    b = fs.bundle("ACME")
    i = b["info"]
    assert i["totalRevenue"] == 100 + 110 + 120 + 130          # last four filed quarters
    assert i["netIncomeToCommon"] == 10 + 11 + 12 + 13
    assert i["freeCashflow"] == 4 * (15.0 - 5.0)
    assert i["profitMargins"] == pytest.approx(46 / 460)
    assert i["revenueGrowth"] == pytest.approx(130 / 90 - 1)   # latest quarter vs a year earlier
    assert i["totalDebt"] == 250.0 and i["totalCash"] == 80.0
    assert i["debtToEquity"] == pytest.approx(250 / 550 * 100)  # Yahoo's percent convention
    assert i["returnOnEquity"] == pytest.approx(46 / 550)
    assert i["currentRatio"] == 2.0
    assert i["sharesOutstanding"] == 10.0 and i["bookValue"] == 55.0
    assert i["currentPrice"] == 50.0 and i["marketCap"] == 500.0 and i["trailingPE"] == 11.0
    assert i["enterpriseValue"] == 500 + 250 - 80
    assert i["sector"] == "Healthcare"                           # GICS name mapped to Yahoo's
    assert i["shortName"] == "Acme Corp" and i["financialCurrency"] == "USD"


def test_statement_frames_use_the_latest_filing_and_yahoo_labels():
    _store_acme()
    b = fs.bundle("ACME")
    fin = b["financials_df"]
    assert list(fin.columns) == [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]
    assert fin.loc["Total Revenue", pd.Timestamp("2025-12-31")] == 430.0  # restated, not the original 420
    assert b["financials"]["Gross Profit"] == 215.0                      # derived: revenue - cost of revenue
    assert b["balance_sheet"]["Total Assets"] == 1000.0
    assert b["financials_q_df"] is None                                   # annual has two columns


def test_point_in_time_read_sees_only_what_was_filed():
    _store_acme()
    fx, origin = fs.facts("ACME", as_of="2026-03-01")
    assert origin == "sec" and fx["Total Revenue"]["2025-12-31"]["value"] == 420.0
    assert "2026-06-30" not in fx.get("Total Revenue|Q", {})


def test_stored_yahoo_info_fills_what_sec_lacks_but_sec_wins():
    _store_acme()
    yahoo_info.put("info", "ACME", {"forwardEps": 6.0, "targetMeanPrice": 70.0, "sector": "Healthcare",
                                    "totalRevenue": 1.0, "beta": 0.8}, "2026-10-10T00:00:00Z")
    b = fs.bundle("ACME")
    assert b["info"]["forwardEps"] == 6.0 and b["info"]["targetMeanPrice"] == 70.0
    assert b["info"]["totalRevenue"] == 460.0
    ref = fs.field_ref(b, "targetMeanPrice")
    assert ref["provider"] == "yahoo" and "2026-10-10" in ref["note"]
    sec_ref = fs.field_ref(b, "totalRevenue")
    assert sec_ref["provider"] == "sec_edgar" and sec_ref["observed"] == "2026-06-30"
    assert fs.statement_ref(b, "Income statement")["provider"] == "sec_edgar"


def test_get_info_never_calls_yahoo_and_queues_an_unknown_symbol():
    with patch("yfinance.Ticker", side_effect=AssertionError("no Yahoo on the read path")):
        b = yfs.get_info("NOPE")
    assert b["status"] == "pending"
    with store.connect() as conn:
        assert sorted(r[0] for r in conn.execute("SELECT kind FROM fetch_queue WHERE key = 'NOPE'")) == [
            "history", "yahoo_info"]


def test_a_member_with_facts_is_not_queued_for_yahoo_info():
    _store_acme()
    with patch("yfinance.Ticker", side_effect=AssertionError("no Yahoo on the read path")):
        b = yfs.get_info("ACME")
    assert "status" not in b
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM fetch_queue WHERE kind = 'yahoo_info'").fetchone()[0] == 0


def test_screener_refresh_reads_the_store_only():
    from backend.services import constituents, screener_service
    _store_acme()
    members = [{"symbol": "ACME", "name": "Acme", "sector": "Health Care", "industry": "Pharma"}]
    with patch.object(constituents, "get_constituents", return_value=members), \
         patch("yfinance.Ticker", side_effect=AssertionError("no per-ticker .info")), \
         patch("yfinance.download", side_effect=AssertionError("no download")), \
         patch.object(screener_service.screener_cache, "upsert_rows") as rows, \
         patch.object(screener_service.screener_cache, "upsert_shares"), \
         patch.object(screener_service, "prune_non_members", return_value=0):
        assert screener_service.refresh_universe("dow") == 1
    row = rows.call_args.args[0][0]
    assert row["sector"] == "Health Care" and row["netMargin"] == pytest.approx(46 / 460)
    assert row["marketCap"] == 500.0


def test_a_foreign_listing_reads_yahoo_statements_and_its_last_close():
    store.replace_fundamentals(["ASML.AS"], [
        dict(symbol="ASML.AS", concept="Total Revenue", period_end="2025-12-31", filed="2026-10-01", value=30.0,
             unit="EUR", form="yahoo:financials", source="yahoo"),
        dict(symbol="ASML.AS", concept="Total Assets", period_end="2025-12-31", filed="2026-10-01", value=50.0,
             unit="EUR", form="yahoo:balance_sheet", source="yahoo")], "yahoo")
    store.upsert("price_daily", [dict(symbol="ASML.AS", date="2026-10-14", close=700.0)], ("symbol", "date"))
    yahoo_info.put("info", "ASML.AS", {"sharesOutstanding": 2.0, "marketCap": 1.0, "currency": "EUR"})
    b = fs.bundle("ASML.AS")
    assert b["financials"]["Total Revenue"] == 30.0 and b["balance_sheet"]["Total Assets"] == 50.0
    assert b["info"]["currentPrice"] == 700.0 and b["info"]["marketCap"] == 1400.0
    assert fs.statement_ref(b, "Income statement")["provider"] == "yahoo"


def test_a_line_the_company_stopped_reporting_is_not_current():
    # ABT stopped tagging GrossProfit in 2019 and AOS its cover-page share count in 2015:
    # their last values must not pass for today's.
    _store_acme()
    store.replace_fundamentals(["ACME"], [
        _fact("Gross Profit|Q", e, 999.0, filed="2019-12-01") for e in
        ("2018-12-31", "2019-03-31", "2019-06-30", "2019-09-30")] + [
        _fact("Inventory", "2015-06-30", 5.0, filed="2015-08-01")], "sec:test")
    i = fs.bundle("ACME")["info"]
    assert "grossProfits" not in i                  # and no TTM revenue minus an annual cost either
    assert "quickRatio" not in i                    # 2015 inventory isn't today's


def test_the_snapshot_share_count_wins_when_sec_is_on_another_basis():
    _store_acme()  # SEC: 10 shares; equity 550
    store.upsert("quote_latest", [dict(symbol="ACME", shares=20.0)], ("symbol",))  # a 2-for-1 split since
    i = fs.bundle("ACME")["info"]
    assert i["sharesOutstanding"] == 20.0 and i["bookValue"] == 27.5
    store.upsert("quote_latest", [dict(symbol="ACME", shares=10.5)], ("symbol",))  # within 10 %: SEC's stands
    assert fs.bundle("ACME")["info"]["sharesOutstanding"] == 10.0


def test_stored_summaries_match_the_statements_and_are_read_in_one_query():
    _store_acme()
    assert fs.store_summaries(["ACME", "NONE"]) == 1          # nothing stored for NONE: no row
    frames = fs.annual_frames(["ACME", "NONE"])
    assert set(frames) == {"ACME"}
    fin, full = frames["ACME"]["financials_df"], fs.bundle("ACME")["financials_df"]
    assert list(fin.columns) == list(full.columns[:2])
    assert fin.loc["Total Revenue"].tolist() == full.loc["Total Revenue"].iloc[:2].tolist()
    assert frames["ACME"]["balance_sheet_df"].loc["Total Assets"].iloc[0] == 1000.0


def test_a_company_without_a_stored_summary_is_built_on_read():
    _store_acme()
    frames = fs.annual_frames(["ACME"])                       # no store_summaries call
    assert frames["ACME"]["financials_df"].loc["Net Income"].iloc[0] == 44.0


def test_dupont_and_earnings_quality_read_summaries_not_bundles():
    from backend.services import constituents, corporate_health_service as ch, dupont_service
    _store_acme()
    store.replace_fundamentals(["ACME"], [_fact("Operating Cash Flow", e, v, form="10-K") for e, v in
                                          (("2025-12-31", 50.0), ("2024-12-31", 45.0))], "sec:cf")
    fs.store_summaries(["ACME"])
    members = [{"symbol": "ACME", "name": "Acme", "sector": "Health Care", "industry": "Pharma"}]
    cache.clear_all("sector_dupont")
    cache.clear_all("earnings_quality")
    with patch.object(constituents, "get_constituents", return_value=members), \
         patch.object(yfs, "get_info", side_effect=AssertionError("no full bundle per company")):
        dup = dupont_service.get_sector_dupont()
        eq = ch.get_earnings_quality("dow")
    assert dup["tickerCount"] == 1 and dup["sectors"][0]["netMargin"] == pytest.approx(44 / 430, abs=1e-6)
    assert eq["kpis"]["n"] == 1
    cache.clear_all("sector_dupont")
    cache.clear_all("earnings_quality")
