"""P1-20: a request sent with ``X-Cache-Refresh: 1`` recomputes the cached
entries it reads instead of serving them, unless an entry was fetched in the
last minute (the cooldown that also collapses concurrent refreshes), and keeps
the old value when the source fails."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import cache as cache_mod
from backend.main import REFRESH_HEADER, _start_fetch_log


def _app(fn):
    app = FastAPI(dependencies=[Depends(_start_fetch_log)])

    @app.get("/x")
    def x():
        return fn()

    return TestClient(app)


def _age(cache_name, key, seconds):
    """Pretend the memory entry for ``key`` was fetched ``seconds`` ago."""
    cache_mod._times(cache_name)[key] = time.time() - seconds


def test_refresh_header_recomputes_an_entry_older_than_a_minute():
    calls = {"n": 0}

    @cache_mod.cached("test_refresh_recompute")
    def fn():
        calls["n"] += 1
        return {"n": calls["n"]}

    with patch.object(cache_mod.HybridCache, "_set_in_db"):
        client = _app(fn)
        assert client.get("/x").json() == {"n": 1}
        assert client.get("/x").json() == {"n": 1}          # plain request: cached
        _age("test_refresh_recompute", (), 61)
        r = client.get("/x", headers={REFRESH_HEADER: "1"})
        assert r.json() == {"n": 2}                          # refresh: recomputed
        assert client.get("/x").json() == {"n": 2}           # and the new value is cached
    assert calls["n"] == 2


def test_refresh_within_the_cooldown_serves_the_entry():
    calls = {"n": 0}

    @cache_mod.cached("test_refresh_cooldown")
    def fn():
        calls["n"] += 1
        return {"n": calls["n"]}

    with patch.object(cache_mod.HybridCache, "_set_in_db"):
        client = _app(fn)
        client.get("/x")
        _age("test_refresh_cooldown", (), 30)  # fetched 30 s ago < 60 s cooldown
        assert client.get("/x", headers={REFRESH_HEADER: "1"}).json() == {"n": 1}
    assert calls["n"] == 1


def test_refresh_reaches_nested_cached_inputs():
    calls = {"inner": 0}

    @cache_mod.cached("test_refresh_inner")
    def inner():
        calls["inner"] += 1
        return {"v": calls["inner"]}

    @cache_mod.cached("test_refresh_outer")
    def outer():
        return {"inner": inner()["v"]}

    with patch.object(cache_mod.HybridCache, "_set_in_db"):
        client = _app(outer)
        assert client.get("/x").json() == {"inner": 1}
        _age("test_refresh_inner", (), 120)
        _age("test_refresh_outer", (), 120)
        assert client.get("/x", headers={REFRESH_HEADER: "1"}).json() == {"inner": 2}


def test_failed_refresh_keeps_the_cached_value():
    state = {"fail": False}

    @cache_mod.cached("test_refresh_fail")
    def fn():
        return {} if state["fail"] else {"ok": 1}

    with patch.object(cache_mod.HybridCache, "_set_in_db"):
        client = _app(fn)
        client.get("/x")
        _age("test_refresh_fail", (), 120)
        state["fail"] = True  # the source is down: empty result
        assert client.get("/x", headers={REFRESH_HEADER: "1"}).json() == {"ok": 1}
        assert client.get("/x").json() == {"ok": 1}


def test_header_only_applies_to_its_own_request():
    calls = {"n": 0}

    @cache_mod.cached("test_refresh_scope")
    def fn():
        calls["n"] += 1
        return {"n": calls["n"]}

    with patch.object(cache_mod.HybridCache, "_set_in_db"):
        client = _app(fn)
        client.get("/x")
        _age("test_refresh_scope", (), 120)
        client.get("/x", headers={REFRESH_HEADER: "1"})
        _age("test_refresh_scope", (), 120)
        # No header: the (old-dated, still in TTL) entry is served.
        assert client.get("/x").json() == {"n": 2}


def test_async_refresh_recomputes():
    calls = {"n": 0}

    @cache_mod.async_cached("test_refresh_async")
    async def fn():
        calls["n"] += 1
        return {"n": calls["n"]}

    async def main():
        a = await fn()
        _age("test_refresh_async", (), 120)
        cache_mod.set_refresh(True)
        b = await fn()
        cache_mod.set_refresh(False)
        c = await fn()
        return a, b, c

    with patch.object(cache_mod.HybridCache, "_set_in_db"):
        assert asyncio.run(main()) == ({"n": 1}, {"n": 2}, {"n": 2})
