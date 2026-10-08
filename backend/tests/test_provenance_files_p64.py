"""P3-36: data read from downloaded bulk files and bundled JSON is dated by the file.

``provenance.attach`` stamps a ref with the oldest ``@cached`` read, else *now*.
Data served from the IMF / Fama-French bulk parquet files, or from JSON bundled
with the app, must carry ``fetchedAt`` from the file's write time (or, for
bundled data that records its own date, that date), so the Navbar's "Data as
of" is not newer than the data.
"""
from __future__ import annotations

import asyncio
import os

from backend import provenance as pv

# 2026-09-01 12:00:00 UTC as a Unix epoch.
SEP_1_NOON = 1788264000
SEP_1_NOON_ISO = "2026-09-01T12:00:00Z"


def _file(path, when=SEP_1_NOON):
    path.write_bytes(b"x")
    os.utime(path, (when, when))
    return path


def test_epoch_constant_is_2026_09_01_noon_utc():
    assert pv.stamp(SEP_1_NOON) == SEP_1_NOON_ISO


def test_imf_path_is_the_downloaded_file_or_none(tmp_path, monkeypatch):
    from backend.services import bulk_data_service as bulk

    monkeypatch.setattr(bulk, "DATA_DIR", tmp_path)
    assert bulk.imf_path("gdp_growth") is None
    assert bulk.imf_path("no_such_indicator") is None
    f = _file(tmp_path / "imf_gdp_growth.parquet")
    assert bulk.imf_path("gdp_growth") == f


def test_famafrench_path_is_the_downloaded_file_or_none(tmp_path, monkeypatch):
    from backend.services import bulk_data_service as bulk

    monkeypatch.setattr(bulk, "FF_PATH", tmp_path / "ff_factors.parquet")
    assert bulk.famafrench_path() is None
    f = _file(tmp_path / "ff_factors.parquet")
    assert bulk.famafrench_path() == f


def test_macro_imf_series_ref_from_the_bulk_file_is_dated_by_it(tmp_path, monkeypatch):
    from backend.routers import macro
    from backend.services import bulk_data_service as bulk
    from backend.sources import source_imf

    monkeypatch.setattr(bulk, "DATA_DIR", tmp_path)
    entry = {"country": "BR", "data": [{"year": 2024, "value": 3.0, "src": source_imf.SOURCE_LABEL}]}

    assert "fetchedAt" not in macro._macro_series_refs("gdp_growth", entry)[0]   # no file: waterfall used the API

    _file(tmp_path / "imf_gdp_growth.parquet")
    refs = macro._macro_series_refs("gdp_growth", entry)

    assert refs[0]["provider"] == "imf"
    assert refs[0]["fetchedAt"] == SEP_1_NOON_ISO


def test_macro_forecast_from_the_bulk_file_is_dated_by_it(tmp_path, monkeypatch):
    from backend.routers import macro
    from backend.services import bulk_data_service as bulk
    from backend.sources import source_imf

    monkeypatch.setattr(bulk, "DATA_DIR", tmp_path)
    _file(tmp_path / "imf_gdp_growth.parquet")

    async def fake_fetch(indicator, countries, start, end):
        return [{"country": "BR", "countryName": "Brazil", "source_label": source_imf.SOURCE_LABEL,
                 "data": [{"year": 2027, "value": 2.0, "estimate": True}]}]
    monkeypatch.setattr(source_imf, "fetch", fake_fetch)

    out = asyncio.run(macro.forecast(countries="BR", indicator="gdp_growth", end=2030))

    assert out["provenance"]["*"]["fetchedAt"] == SEP_1_NOON_ISO
    assert out["provenance"]["series.BR"]["fetchedAt"] == SEP_1_NOON_ISO


def test_fama_french_from_the_bulk_file_is_dated_by_it(tmp_path, monkeypatch):
    from backend.routers import macro
    from backend.services import bulk_data_service as bulk
    from backend.sources import source_datareader

    monkeypatch.setattr(bulk, "FF_PATH", tmp_path / "ff_factors.parquet")
    monkeypatch.setattr(source_datareader, "fama_french",
                        lambda: [{"year": 2024, "mkt_rf": 1.0, "smb": 0.1, "hml": 0.2, "rf": 0.3}])

    _file(tmp_path / "ff_factors.parquet")

    out = asyncio.run(macro.fama_french())

    assert out["provenance"]["*"]["fetchedAt"] == SEP_1_NOON_ISO


# --- bundled JSON ------------------------------------------------------------

JAN_1_ISO = "2026-01-01T00:00:00Z"


def _erp(as_of="2026-01-01"):
    return {"asOf": as_of, "sourceUrl": "https://example.test/ctryprem.xlsx", "matureMarketERP": 4.46,
            "countries": {"United States": {"erp": 4.46, "taxRate": 21.0}}}


def test_bundled_as_of_stamps_a_date_and_ignores_live_or_malformed():
    from backend.services import discount_rates as dr

    assert dr.bundled_as_of({"asOf": "2026-01-05"}) == "2026-01-05T00:00:00Z"
    assert dr.bundled_as_of({"asOf": "live"}) is None
    assert dr.bundled_as_of({}) is None
    assert dr.bundled_as_of({"asOf": "2026-13-45"}) is None


def test_damodaran_erp_ref_is_dated_by_the_bundled_as_of_not_the_request(monkeypatch):
    from backend.services import valuation_engine as ve

    monkeypatch.setattr(ve, "load_erp", lambda: _erp())
    monkeypatch.setattr(ve, "load_sector_multiples", lambda: {"asOf": "2026-01-05", "sectorMultiples": {}})
    result = {"ticker": "AAPL", "wacc": {"country": "United States"}, "currency": "USD"}

    prov = ve.provenance({"info": {"sector": "Technology"}}, result, 1.0)

    assert prov["valuation.wacc.erp"]["fetchedAt"] == JAN_1_ISO
    assert prov["valuation.wacc.taxRate"]["fetchedAt"] == JAN_1_ISO
    assert prov["valuation.models.EV/EBITDA Comps.detail.sectorMultiple"]["fetchedAt"] == "2026-01-05T00:00:00Z"


def test_damodaran_live_download_keeps_the_cache_date(monkeypatch):
    from backend.services import valuation_engine as ve

    monkeypatch.setattr(ve, "load_erp", lambda: _erp("live"))
    monkeypatch.setattr(ve, "load_sector_multiples", lambda: {"asOf": "2026-01-05"})
    prov = ve.provenance({"info": {}}, {"ticker": "AAPL", "wacc": {"country": "United States"}}, 1.0)

    assert "fetchedAt" not in prov["valuation.wacc.erp"]


def test_risk_free_rates_erp_ref_is_dated_by_the_bundled_as_of(monkeypatch):
    from backend.routers import valuation as vr
    from backend.services import discount_rates as dr

    monkeypatch.setattr(dr, "load_erp", lambda: _erp())

    prov = vr._risk_free_provenance([{"name": "United States", "basis": "fallback"}])

    assert prov["rates.United States.erp"]["fetchedAt"] == JAN_1_ISO


def test_cb_meetings_retrieved_time_is_the_oldest_retrieved_date():
    from backend.services import cb_meetings

    rows = [{"retrieved": "2026-10-02"}, {"retrieved": "2026-03-04"}, {}, {"retrieved": "2026-08-01"}]
    assert cb_meetings.retrieved_time(rows) == "2026-03-04T00:00:00Z"
    assert cb_meetings.retrieved_time([{}]) is None                       # a live iCal row has none
    assert cb_meetings.retrieved_time([]) is None


def test_calendar_cb_ref_uses_the_oldest_retrieved_row():
    from backend.services import calendar_service as cal

    rows = [{"date": "2026-11-05", "retrieved": "2026-10-02"}, {"date": "2026-12-16", "retrieved": "2026-09-15"}]

    prov = cal._provenance(rows)

    assert prov["macro"][0]["fetchedAt"] == "2026-09-15T00:00:00Z"


def test_central_bank_next_meeting_ref_uses_its_rows_retrieved_date():
    from backend.services import centralbanks_service as cbs

    meetings = [{"bank": "Fed", "date": "2026-12-09", "source": "https://fed.example", "retrieved": "2026-09-15"}]
    current = {"Fed": {"rate": None, "series": "FEDFUNDS", "next_meeting": "2026-12-09"}}

    prov = cbs._provenance(current, [], meetings)

    assert prov["current.Fed.next_meeting"]["fetchedAt"] == "2026-09-15T00:00:00Z"


def test_doing_business_ref_is_dated_by_the_bundled_file(tmp_path, monkeypatch):
    from backend.services import business_service as bs

    f = _file(tmp_path / "doing_business.json")
    monkeypatch.setattr(bs, "_DOING_BUSINESS_PATH", f)

    prov = bs._provenance([])

    ref = prov["kpis.doingBusinessScore"]
    assert ref["fetchedAt"] == SEP_1_NOON_ISO
    assert "bundled with the app" in ref["note"]
