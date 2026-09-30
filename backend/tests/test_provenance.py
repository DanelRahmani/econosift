"""Provenance refs, the attach() helper, and cache fetch-time tracking."""
from __future__ import annotations

import asyncio
import contextvars
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import cache as cache_mod
from backend import provenance as pv


# ---------------------------------------------------------------------------
# refs
# ---------------------------------------------------------------------------

def test_ref_builds_series_link_from_provider_template():
    r = pv.fred("DGS10", "10-Year Treasury", units="%", frequency="daily", observed="2026-09-28")
    assert r["provider"] == "fred"
    assert r["providerName"].startswith("FRED")
    assert r["url"] == "https://fred.stlouisfed.org/series/DGS10"
    assert (r["series"], r["units"], r["frequency"], r["observed"]) == ("DGS10", "%", "daily", "2026-09-28")
    assert "fetchedAt" not in r  # stamped by attach(), not at construction


def test_ref_without_series_links_to_provider_home():
    assert pv.ref("bis")["url"] == "https://data.bis.org"


def test_unknown_provider_and_flag_are_rejected():
    with pytest.raises(ValueError):
        pv.ref("bloomberg")
    with pytest.raises(ValueError):
        pv.ref("fred", "DGS10", flags=("made_up",))
    with pytest.raises(ValueError):
        pv.derived("a / b", flags=("made_up",))


def test_derived_records_formula_and_inputs():
    d = pv.derived("price / eps", ["price", pv.yahoo("AAPL", "trailingEps")], title="P/E")
    assert d["provider"] == "derived" and d["formula"] == "price / eps"
    assert d["inputs"][0] == "price" and d["inputs"][1]["provider"] == "yahoo"


def test_unrecognised_label_keeps_adapter_wording():
    r = pv.label_to_ref("Some Statistics Office")
    assert r["provider"] == "other" and r["providerName"] == "Some Statistics Office"
    assert pv.label_to_ref("World Bank (WDI)", series="NY.GDP.MKTP.KD.ZG")["provider"] == "worldbank"


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------

def test_attach_adds_map_without_mutating_the_result():
    result = {"value": 1}
    out = pv.attach(result, {"*": pv.yahoo("AAPL")})
    assert "provenance" not in result
    assert out["value"] == 1 and out["provenance"]["*"]["provider"] == "yahoo"
    assert out["provenance"]["*"]["fetchedAt"].endswith("Z")


def test_attach_keeps_keys_the_result_already_carries():
    inner = pv.attach({"v": 1}, {"v": pv.fred("DGS10")})
    out = pv.attach(inner, {"v": pv.yahoo("^TNX"), "*": pv.yahoo("AAPL")})
    assert out["provenance"]["v"]["provider"] == "fred"
    assert out["provenance"]["*"]["provider"] == "yahoo"


def test_attach_stamps_every_ref_in_a_list_and_passes_non_dicts_through():
    out = pv.attach({}, {"*": [pv.ref("worldbank"), pv.ref("imf")]})
    assert all("fetchedAt" in r for r in out["provenance"]["*"])
    assert pv.attach([1, 2], {"*": pv.ref("bis")}) == [1, 2]


# ---------------------------------------------------------------------------
# fetch times
# ---------------------------------------------------------------------------

def test_cache_hit_reports_when_the_entry_was_fetched():
    @cache_mod.cached("prov_test_hit")
    def fetch():
        return {"v": 1}

    cache_mod.start_fetch_log()
    before = time.time()
    fetch()
    first = cache_mod.oldest_fetch()
    assert before <= first <= time.time()

    time.sleep(0.05)
    cache_mod.start_fetch_log()
    fetch()  # hit
    assert cache_mod.oldest_fetch() == first  # not the time of this read


def test_entry_built_from_older_cached_input_is_dated_by_that_input():
    @cache_mod.cached("prov_test_inner")
    def inner():
        return {"v": 1}

    @cache_mod.cached("prov_test_outer")
    def outer():
        return {"w": inner()["v"] + 1}

    cache_mod.start_fetch_log()
    inner()
    inner_time = cache_mod.oldest_fetch()
    time.sleep(0.05)

    cache_mod.start_fetch_log()
    outer()  # computed now, from the older inner entry
    assert cache_mod.oldest_fetch() == inner_time
    cache_mod.start_fetch_log()
    outer()  # hit
    assert cache_mod.oldest_fetch() == inner_time


def test_no_log_started_means_no_fetch_time():
    @cache_mod.cached("prov_test_nolog")
    def fetch():
        return {"v": 1}

    def read():
        fetch()
        return cache_mod.oldest_fetch()

    # A context in which no log was started (e.g. a scheduler job).
    assert contextvars.Context().run(read) is None


def test_request_reports_original_fetch_time_through_threads():
    """End to end: the app-level dependency opens the log, the endpoint reads a
    cached value in a worker thread, and attach() stamps the original time."""
    @cache_mod.cached("prov_test_endpoint")
    def fetch():
        return {"v": 1}

    async def start():
        cache_mod.start_fetch_log()

    app = FastAPI(dependencies=[Depends(start)])

    @app.get("/threaded")
    async def threaded():
        data = await asyncio.to_thread(fetch)
        return pv.attach(data, {"*": pv.yahoo("AAPL")})

    @app.get("/sync")
    def sync():
        return pv.attach(fetch(), {"*": pv.yahoo("AAPL")})

    client = TestClient(app)
    first = client.get("/threaded").json()["provenance"]["*"]["fetchedAt"]
    time.sleep(1.1)  # fetchedAt has one-second resolution
    assert client.get("/threaded").json()["provenance"]["*"]["fetchedAt"] == first
    assert client.get("/sync").json()["provenance"]["*"]["fetchedAt"] == first
