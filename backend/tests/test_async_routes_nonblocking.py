"""Routes must not run blocking sync code on the event loop.

With one uvicorn process, a sync Yahoo call inside an ``async def`` route
froze every other request, /health included. Each case stubs the route's
blocking dependency with a 0.6 s sleep and checks /api/health still answers
while that request is in flight.
"""
import asyncio
import time

import httpx
import pandas as pd
import pytest

from backend.main import app

_SLOW = 0.6


def _sleeper(result):
    def f(*args, **kwargs):
        time.sleep(_SLOW)
        return result
    return f


def _frame():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame({"AAPL": [1.0, 2, 3, 4, 5]}, index=idx)


_HOLD = {"holdings": [{"ticker": "AAPL", "weight": 1.0}]}

CASES = [
    ("get", "/api/technicals?ticker=AAPL", None,
     "backend.services.technicals_service", "get_technicals", {}),
    ("get", "/api/corporate/health?ticker=AAPL", None,
     "backend.services.corporate_health_service", "get_corporate_health", {}),
    ("get", "/api/dividend/analysis?ticker=KO", None,
     "backend.services.dividend_service", "get_dividend_analysis", {}),
    ("get", "/api/snowflake?ticker=AAPL", None,
     "backend.services.snowflake_service", "compute_snowflake", {}),
    ("get", "/api/snowflake/batch?tickers=AAPL", None,
     "backend.services.snowflake_service", "compute_snowflake_batch", {}),
    ("get", "/api/screener/status?index=dow", None,
     "backend.services.constituents", "get_constituents", []),
    ("post", "/api/scenario/historical/stress", _HOLD,
     "backend.services.yfinance_service", "get_close_frame", "frame"),
    ("post", "/api/scenario/custom", {**_HOLD, "shocks": {}},
     "backend.services.yfinance_service", "get_close_frame", "frame"),
    ("post", "/api/research/cross-asset-correlation", None,
     "backend.services.yfinance_service", "get_close_frame", "frame"),
    ("get", "/api/research/fx-macro-link", None,
     "backend.services.yfinance_service", "get_close_frame", "frame"),
]


@pytest.mark.parametrize("method,url,body,mod,attr,result", CASES,
                         ids=[c[1].split("?")[0] for c in CASES])
async def test_route_does_not_block_event_loop(monkeypatch, method, url, body, mod, attr, result):
    import importlib
    module = importlib.import_module(mod)
    monkeypatch.setattr(module, attr, _sleeper(_frame() if result == "frame" else result))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        t0 = time.perf_counter()
        slow = asyncio.create_task(client.request(method, url, json=body))
        await asyncio.sleep(0.05)  # let the slow request reach its dependency
        health = await client.get("/api/health")
        elapsed = time.perf_counter() - t0
        resp = await slow
    assert resp.status_code != 404, url
    assert health.status_code == 200
    # A blocked loop can't even start /health until the 0.6 s sleep ends.
    assert elapsed < _SLOW * 0.75, f"/api/health waited {elapsed:.2f}s behind {url}"
