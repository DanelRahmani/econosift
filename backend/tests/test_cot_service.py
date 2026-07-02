"""Tests for the CFTC COT service source waterfall (P2-22).

All network access is mocked. The waterfall must:
- prefer the Socrata JSON API,
- reject sources that return 200 but parse to nothing (headerless deafut.txt bug),
- fall through to the legacy annual zip,
- never cache a failed/empty envelope (P2-19 residual gap).
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest
import requests

from backend import cache as cache_mod
from backend.services import cot_service


# ---------------------------------------------------------------------------
# Fixtures / fakes
# ---------------------------------------------------------------------------

class FakeResp:
    def __init__(self, *, json_data=None, text="", content=b"", status=200):
        self._json = json_data
        self.text = text
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


def _socrata_records(code: str, weeks: int = 60) -> list[dict]:
    """Well-formed Socrata rows (string values, ISO timestamps) for one code."""
    out = []
    d = date(2026, 6, 23)
    for i in range(weeks):
        out.append({
            "report_date_as_yyyy_mm_dd": f"{d - timedelta(weeks=i)}T00:00:00.000",
            "cftc_contract_market_code": code,
            "noncomm_positions_long_all": str(1000 + 10 * i),
            "noncomm_positions_short_all": str(400 + 5 * i),
            "open_interest_all": str(50000 + i),
        })
    return out


def _legacy_zip_bytes() -> bytes:
    """In-memory annual zip (deacot-style) with legacy column names."""
    rows = ["Report_Date_as_YYYY_MM_DD,CFTC_Contract_Market_Code,"
            "NonComm_Positions_Long_All,NonComm_Positions_Short_All,Open_Interest_All"]
    d = date(2026, 6, 23)
    for contract in cot_service.COT_CONTRACTS:
        code = contract["code"].replace("+", "").strip()
        for i in range(10):
            rows.append(f"{d - timedelta(weeks=i)},{code},{1500 + i},{300 + i},{60000 + i}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("annof.txt", "\n".join(rows))
    return buf.getvalue()


def _make_fake_get(*, socrata=None, zip_bytes=None, socrata_exc=None, zip_exc=None):
    """Route requests.get by URL. `socrata` is records-list or callable(code)."""
    def fake_get(url, params=None, timeout=None, **kwargs):
        if "publicreporting.cftc.gov" in url:
            if socrata_exc is not None:
                raise socrata_exc
            recs = socrata(params) if callable(socrata) else socrata
            return FakeResp(json_data=recs if recs is not None else [])
        if url.endswith(".zip"):
            if zip_exc is not None:
                raise zip_exc
            if zip_bytes is None:
                return FakeResp(status=404)
            return FakeResp(content=zip_bytes)
        return FakeResp(status=404)
    return fake_get


@pytest.fixture(autouse=True)
def _clean_cot_cache():
    """Isolate the module-level 'cot_data' cache and suppress the DB tier."""
    cache_mod._get_cache("cot_data").clear()
    with patch.object(cache_mod.HybridCache, "_set_in_db"), \
         patch.object(cache_mod.HybridCache, "_get_from_db", return_value=None):
        yield
    cache_mod._get_cache("cot_data").clear()


# ---------------------------------------------------------------------------
# _parse_cot — parse validation
# ---------------------------------------------------------------------------

def test_parse_cot_rejects_headerless_frame():
    """deafut.txt has no header row → first data row becomes column names →
    no required column can be identified → parse must yield nothing."""
    headerless = ('"WHEAT-SRW - CHICAGO BOARD OF TRADE",260623,2026-06-23,001602,50000\n'
                  '"GOLD - COMMODITY EXCHANGE INC.",260623,2026-06-23,088691,40000\n')
    df = pd.read_csv(io.StringIO(headerless))
    assert cot_service._parse_cot(df) == []


def test_parse_cot_handles_socrata_columns():
    """Socrata snake_case columns must fuzzy-match the candidate lists."""
    df = pd.DataFrame.from_records(_socrata_records("13874A"))
    contracts = cot_service._parse_cot(df)
    sp = next(c for c in contracts if c["code"] == "13874A")
    assert sp["history"], "S&P contract should have history rows"
    # latest row: long=1000, short=400 → net +600
    assert sp["net_speculator"] == 600
    assert sp["open_interest"] == 50000


# ---------------------------------------------------------------------------
# Source waterfall
# ---------------------------------------------------------------------------

def test_socrata_is_primary_source():
    """When Socrata works, the legacy zips must never be requested."""
    requested = []

    def socrata(params):
        requested.append(params)
        where = (params or {}).get("$where", "")
        for contract in cot_service.COT_CONTRACTS:
            code = contract["code"].replace("+", "").strip()
            if code in where:
                return _socrata_records(code)
        return []

    fake = _make_fake_get(socrata=socrata, zip_exc=AssertionError("zip must not be hit"))
    with patch.object(cot_service.requests, "get", side_effect=fake):
        contracts = cot_service._download_and_parse_sync()

    assert any(c["history"] for c in contracts)
    assert requested, "Socrata endpoint was never queried"


def test_falls_back_to_legacy_zip_when_socrata_fails():
    fake = _make_fake_get(socrata_exc=requests.ConnectionError("down"),
                          zip_bytes=_legacy_zip_bytes())
    with patch.object(cot_service.requests, "get", side_effect=fake):
        contracts = cot_service._download_and_parse_sync()
    assert any(c["history"] for c in contracts)


def test_garbage_200_response_falls_through():
    """A source that returns HTTP 200 but parses to no contracts (the deafut.txt
    headerless bug) must be rejected so the waterfall tries the next source."""
    garbage = [{"col_a": "x", "col_b": "1"}] * 5
    fake = _make_fake_get(socrata=garbage, zip_bytes=_legacy_zip_bytes())
    with patch.object(cot_service.requests, "get", side_effect=fake):
        contracts = cot_service._download_and_parse_sync()
    assert any(c["history"] for c in contracts), "should have fallen through to the zip"


def test_legacy_urls_cover_year_rollover():
    """Annual archive URLs must track the current year (no hardcoded year)."""
    urls = cot_service._legacy_urls()
    year = date.today().year
    assert any(str(year) in u for u in urls)
    assert any(str(year - 1) in u for u in urls)


# ---------------------------------------------------------------------------
# get_cot_data — envelope + cache behavior
# ---------------------------------------------------------------------------

async def test_all_sources_fail_returns_error_envelope():
    fake = _make_fake_get(socrata_exc=requests.ConnectionError("down"),
                          zip_exc=requests.ConnectionError("down"))
    with patch.object(cot_service.requests, "get", side_effect=fake):
        result = await cot_service.get_cot_data()
    assert result["contracts"] == []
    assert result["error"]


async def test_failed_envelope_is_not_cached():
    """P2-19 residual gap: a failure envelope (non-empty dict, empty contracts)
    must NOT be cached — the next call must retry and can succeed."""
    fail = _make_fake_get(socrata_exc=requests.ConnectionError("down"),
                          zip_exc=requests.ConnectionError("down"))
    with patch.object(cot_service.requests, "get", side_effect=fail):
        first = await cot_service.get_cot_data()
    assert first["error"]

    ok = _make_fake_get(socrata_exc=requests.ConnectionError("still down"),
                        zip_bytes=_legacy_zip_bytes())
    with patch.object(cot_service.requests, "get", side_effect=ok):
        second = await cot_service.get_cot_data()
    assert second["error"] is None
    assert any(c["history"] for c in second["contracts"])
