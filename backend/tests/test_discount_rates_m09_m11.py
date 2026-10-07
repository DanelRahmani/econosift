"""Offline known-value tests for Markets audit M-09 / M-11 and the short-rate helper (no network)."""
from __future__ import annotations

import io
import sys
import types

import pytest


def _workbook_bytes(sheets: dict[str, list[list]]) -> bytes:
    """Build an in-memory .xlsx: {sheet name: rows (first row = header)}."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Mimics the real ctryprem.xlsx layout (verified against the Jan-2026 release): the first sheet whose
# name contains "country" is the 'Country Lookup' calculator, NOT the data; the data is on
# 'Regional breakdown' (header in row 1, values as decimals, not percent).
_REGIONAL_HEADER = ["Country", "GDP (in millions) in 2024", "Moody's rating", "Sovereign CDS",
                    "Adj. Default Spread", "Equity Risk Premium", "Country Risk Premium",
                    "Corporate Tax Rate", "Region"]


def _fake_ctryprem() -> bytes:
    return _workbook_bytes({
        "Explanation and FAQ": [["Damodaran", "notes"]],
        "Country Lookup": [["To look up the equity risk premium for a country, use this worksheet", None],
                           ["Country", "Turkey"], ["CDS spread", 0.0299]],
        "ERPs by country": [["Country and Equity Risk Premiums"]],
        "Regional breakdown": [
            _REGIONAL_HEADER,
            ["Korea", 1.8e6, "Aa2", 0.0034, 0.004, 0.05, 0.01, 0.25, "Asia"],
            ["Netherlands", 1.2e6, "Aaa", 0.001, 0, 0.0425, 0.0, 0.258, "Western Europe"],
            ["United States", 2.8e7, "Aa1", 0.0044, 0.002, 0.0446, 0.002, 0.25, "North America"],
            ["Nowhere", 1.0, "NA", "NA", "NA", "NA", "NA", "NA", "Asia"],   # unusable row: skipped
        ],
    })


@pytest.fixture
def dr(monkeypatch):
    from backend.services import discount_rates
    return discount_rates


# ---------------------------------------------------------------------------
# M-11: live Damodaran parse + failure path
# ---------------------------------------------------------------------------

class TestLiveDamodaranParse:
    def test_reads_regional_breakdown_sheet_and_converts_to_percent(self, dr, monkeypatch):
        monkeypatch.setattr(dr, "_download_damodaran_xlsx", lambda: _fake_ctryprem())
        data = dr.load_erp()
        assert data["asOf"] == "live"
        # Sheet stores 0.05 -> the module's unit is percent (static JSON: Korea erp 4.869 = 4.869 %).
        assert data["countries"]["Korea"] == {"erp": 5.0, "crp": 1.0, "taxRate": 25.0}
        assert data["countries"]["Netherlands"]["erp"] == 4.25
        assert data["countries"]["Netherlands"]["taxRate"] == 25.8
        assert "Nowhere" not in data["countries"]
        assert data["matureMarketERP"] == 4.46          # the US row's total ERP (0.0446 * 100)
        # and the consumers see decimals: ke inputs
        assert dr.erp_for_country("Korea") == pytest.approx(0.05)

    def test_decoy_country_lookup_sheet_is_not_used(self, dr, monkeypatch):
        # Only a decoy 'Country Lookup' sheet and no 'Regional breakdown' -> unusable -> static file, not garbage.
        blob = _workbook_bytes({"Country Lookup": [["Country", "Turkey"], ["CDS spread", 0.0299]]})
        monkeypatch.setattr(dr, "_download_damodaran_xlsx", lambda: blob)
        data = dr.load_erp()
        assert data["asOf"] == "2026-01-01"             # static JSON
        assert data["countries"]["Korea"]["erp"] == 4.869

    def test_missing_us_row_falls_back_to_static(self, dr, monkeypatch):
        blob = _workbook_bytes({"Regional breakdown": [
            _REGIONAL_HEADER, ["Korea", 1.0, "Aa2", 0.0, 0.0, 0.05, 0.01, 0.25, "Asia"]]})
        monkeypatch.setattr(dr, "_download_damodaran_xlsx", lambda: blob)
        assert dr.load_erp()["asOf"] == "2026-01-01"

    def test_download_failure_serves_static_without_raising(self, dr, monkeypatch):
        def boom():
            raise OSError("network down")
        monkeypatch.setattr(dr, "_download_damodaran_xlsx", boom)
        data = dr.load_erp()                            # used to raise NameError: name 'log' is not defined
        assert data["asOf"] == "2026-01-01"
        assert data["matureMarketERP"] == 4.46
        assert data["countries"]["Korea"]["erp"] == 4.869

    def test_module_has_a_logger(self, dr):
        import logging
        assert isinstance(dr.log, logging.Logger)


# ---------------------------------------------------------------------------
# M-09: South Korea must resolve to Damodaran's "Korea"
# ---------------------------------------------------------------------------

@pytest.fixture
def static_erp(dr, monkeypatch):
    def boom():
        raise OSError("offline")
    monkeypatch.setattr(dr, "_download_damodaran_xlsx", boom)


class TestKoreaMapping:
    def test_exchange_code_ksc_maps_to_korea(self, dr, static_erp):
        assert dr.detect_country({"exchange": "KSC"}) == "Korea"

    def test_full_exchange_name_hint_maps_to_korea(self, dr, static_erp):
        assert dr.detect_country({"fullExchangeName": "Korea Exchange (Stock Market)"}) == "Korea"

    def test_yfinance_country_south_korea_maps_to_korea(self, dr, static_erp):
        assert dr.detect_country({"country": "South Korea"}) == "Korea"

    def test_every_mapped_country_exists_in_damodaran_table(self, dr, static_erp):
        table = dr.load_erp()["countries"]
        targets = set(dr.EXCHANGE_COUNTRY.values()) | {c for _, c in dr._EXCHANGE_NAME_HINTS}
        assert sorted(t for t in targets if t not in table) == []

    def test_samsung_wacc_uses_korean_erp_and_tax(self, dr, static_erp, monkeypatch):
        monkeypatch.setattr(dr, "_risk_free_rate_live", lambda: 0.04)
        bundle = {"info": {"exchange": "KSC", "marketCap": 1_000.0, "totalDebt": 0, "currency": "USD"}}  # currency is no longer assumed (P2-34); USD keeps the stubbed rf
        w = dr.wacc(bundle, beta=1.0)
        # Korea: ERP 4.869 % (the US is 4.46 %), statutory tax 26.4 % (US fallback was 21 %)
        assert w["country"] == "Korea"
        assert w["erp"] == pytest.approx(0.04869)
        assert w["taxRate"] == pytest.approx(0.264)
        # ke = rf + beta * ERP = 0.04 + 1.0 * 0.04869 = 0.08869 ; no debt -> wacc = ke
        assert w["costOfEquity"] == pytest.approx(0.08869)
        assert w["wacc"] == pytest.approx(0.08869)


# ---------------------------------------------------------------------------
# short_risk_free_rate (US 3-month bill, FRED DGS3MO)
# ---------------------------------------------------------------------------

class TestShortRiskFreeRate:
    def test_live_value_is_a_decimal_and_asked_for_dgs3mo(self, dr, monkeypatch):
        asked = []

        def fake(series_id):
            asked.append(series_id)
            return 0.0361 if series_id == "DGS3MO" else 0.0526

        monkeypatch.setattr(dr, "_fetch_fred_latest", fake)
        assert dr.short_risk_free_rate() == pytest.approx(0.0361)
        assert dr.short_risk_free_rate_is_fallback() is False
        assert set(asked) == {"DGS3MO"}                 # never DGS10

    def test_live_value_cached_once(self, dr, monkeypatch):
        calls = []
        monkeypatch.setattr(dr, "_fetch_fred_latest", lambda s: calls.append(s) or 0.0361)
        dr.short_risk_free_rate()
        dr.short_risk_free_rate()
        dr.short_risk_free_rate_is_fallback()
        assert calls == ["DGS3MO"]

    def test_failure_falls_back_and_is_flagged(self, dr, monkeypatch):
        monkeypatch.setattr(dr, "_fetch_fred_latest", lambda s: None)
        assert dr.short_risk_free_rate() == dr.RISK_FREE_FALLBACK == 0.04
        assert dr.short_risk_free_rate_is_fallback() is True

    def test_failure_is_not_cached(self, dr, monkeypatch):
        state = {"value": None}
        monkeypatch.setattr(dr, "_fetch_fred_latest", lambda s: state["value"])
        assert dr.short_risk_free_rate() == 0.04       # FRED down: fallback
        state["value"] = 0.0361                         # FRED back: retried at once, not pinned for an hour
        assert dr.short_risk_free_rate() == pytest.approx(0.0361)
        assert dr.short_risk_free_rate_is_fallback() is False

    def test_ten_year_rate_is_independent_of_short_rate(self, dr, monkeypatch):
        monkeypatch.setattr(dr, "_fetch_fred_latest",
                            lambda s: {"DGS3MO": 0.0361, "DGS10": 0.0526}[s])
        assert dr.short_risk_free_rate() == pytest.approx(0.0361)
        assert dr.risk_free_rate() == pytest.approx(0.0526)


class TestFetchFredLatest:
    def _fake_fredapi(self, monkeypatch, series_values, seen):
        import pandas as pd

        class Fred:
            def __init__(self, api_key):
                pass

            def get_series(self, sid):
                seen.append(sid)
                return pd.Series(series_values)

        mod = types.ModuleType("fredapi")
        mod.Fred = Fred
        monkeypatch.setitem(sys.modules, "fredapi", mod)
        from backend import config
        monkeypatch.setattr(config, "FRED_API_KEY", "test-key")

    def test_returns_last_non_nan_percent_as_decimal(self, dr, monkeypatch):
        seen = []
        self._fake_fredapi(monkeypatch, [3.5, 3.6, float("nan")], seen)
        # last non-NaN observation 3.6 (%) -> 0.036
        assert dr._fetch_fred_latest("DGS3MO") == pytest.approx(0.036)
        assert seen == ["DGS3MO"]

    def test_dgs10_wrapper_still_asks_for_dgs10(self, dr, monkeypatch):
        seen = []
        self._fake_fredapi(monkeypatch, [4.25], seen)
        assert dr._fetch_dgs10() == pytest.approx(0.0425)
        assert seen == ["DGS10"]

    def test_all_sources_failing_returns_none(self, dr, monkeypatch):
        from backend import config
        monkeypatch.setattr(config, "FRED_API_KEY", "")
        dr_mod = types.ModuleType("pandas_datareader.data")

        def boom(*a, **k):
            raise OSError("down")

        dr_mod.DataReader = boom
        pkg = types.ModuleType("pandas_datareader")
        pkg.data = dr_mod
        monkeypatch.setitem(sys.modules, "pandas_datareader", pkg)
        monkeypatch.setitem(sys.modules, "pandas_datareader.data", dr_mod)
        assert dr._fetch_fred_latest("DGS3MO") is None
