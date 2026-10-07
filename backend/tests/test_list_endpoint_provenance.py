"""P2-32: endpoints that returned a bare list (or a ticker-keyed dict) are wrapped
in an object so they can carry the top-level ``provenance`` map.

Offline: the service functions and the price-frame loader are monkeypatched.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.routers import options as options_router
from backend.routers import portfolio as portfolio_router
from backend.routers import sector as sector_router
from backend.routers import snowflake as snowflake_router
from backend.services import portfolio as port
from backend.services import screener_cache
from backend.services import sector_service
from backend.services import snowflake_service

HOLDINGS = {"holdings": [{"ticker": "AAA", "weight": 0.6}, {"ticker": "BBB", "weight": 0.4}]}


def _prov(body: dict) -> dict:
    assert "provenance" in body
    prov = body["provenance"]
    assert "*" in prov
    return prov


def _star(body: dict) -> dict:
    star = _prov(body)["*"]
    return star[0] if isinstance(star, list) else star


# --------------------------------------------------------------------- options

def test_expiries_wrapped(client, monkeypatch):
    monkeypatch.setattr(options_router, "_expiries_sync", lambda t: ["2026-11-20", "2026-12-18"])
    body = client.get("/api/options/expiries", params={"ticker": "aapl"}).json()
    assert body["ticker"] == "AAPL"
    assert body["expiries"] == ["2026-11-20", "2026-12-18"]
    star = _star(body)
    assert star["provider"] == "yahoo"
    assert "delayed" in star["flags"]


def test_termstructure_wrapped(client, monkeypatch):
    rows = [{"expiry": "2026-11-20", "dte": 48, "atmIV": 31.2, "straddle": 9.5},
            {"expiry": "2026-12-18", "dte": 76, "atmIV": 29.9, "straddle": 12.1}]
    monkeypatch.setattr(options_router.oe, "get_term_structure", lambda t: rows)
    body = client.get("/api/options/termstructure", params={"ticker": "aapl"}).json()
    assert body["ticker"] == "AAPL"
    assert body["points"] == rows
    assert _star(body)["provider"] == "yahoo"
    assert "delayed" in _star(body)["flags"]


def test_smile_wrapped(client, monkeypatch):
    rows = [{"strike": 90.0, "moneyness": 0.9, "callIV": 35.0, "putIV": 36.5},
            {"strike": 100.0, "moneyness": 1.0, "callIV": 30.0, "putIV": 30.4}]
    monkeypatch.setattr(options_router.oe, "get_iv_smile", lambda t, e: rows)
    body = client.get("/api/options/smile", params={"ticker": "aapl", "expiry": "2026-11-20"}).json()
    assert body["ticker"] == "AAPL"
    assert body["expiry"] == "2026-11-20"
    assert body["points"] == rows
    assert _star(body)["provider"] == "yahoo"
    assert "delayed" in _star(body)["flags"]


# ---------------------------------------------------------------------- sector

def test_sector_fundamentals_wrapped(client, monkeypatch):
    rows = [{"ticker": "XLK", "sector": "Technology", "price": 200.0, "beta": 1.1},
            {"ticker": "XLF", "sector": "Financials", "price": 45.0, "beta": 0.9}]
    monkeypatch.setattr(sector_service, "get_sector_fundamentals", lambda: rows)
    body = client.get("/api/sector/fundamentals").json()
    assert body["sectors"] == rows
    assert _star(body)["provider"] == "yahoo"


def test_sector_drill_wrapped(client, monkeypatch):
    rows = [{"industry": "Software", "stocks": [{"symbol": "MSFT", "name": "Microsoft", "change1d": 1.2}]}]
    monkeypatch.setattr(sector_service, "get_sector_industry_drill", lambda s: rows)
    monkeypatch.setattr(sector_router, "_snapshot_time", lambda s: "2026-10-02T06:00:00Z")
    body = client.get("/api/sector/drill", params={"sector": "Technology"}).json()
    assert body["sector"] == "Technology"
    assert body["industries"] == rows
    star = _star(body)
    assert star["provider"] == "derived"
    assert star["fetchedAt"] == "2026-10-02T06:00:00Z"


# ------------------------------------------------------------------- portfolio

@pytest.fixture
def frame(monkeypatch):
    idx = pd.date_range("2026-01-01", periods=30, freq="B")
    df = pd.DataFrame({"AAA": range(100, 130), "BBB": range(50, 80), "^GSPC": range(10, 40)}, index=idx,
                      dtype=float)

    async def fake_load(holdings, period, extra=()):
        return df

    monkeypatch.setattr(portfolio_router, "_load_frame", fake_load)
    return df


def test_risk_contribution_wrapped(client, frame, monkeypatch):
    rows = [{"ticker": "AAA", "weight": 0.6, "marginalContrib": 0.1, "pctContrib": 0.7},
            {"ticker": "BBB", "weight": 0.4, "marginalContrib": 0.04, "pctContrib": 0.3}]
    monkeypatch.setattr(port, "risk_contribution", lambda h, f: rows)
    body = client.post("/api/portfolio/risk-contribution", json=HOLDINGS).json()
    assert body["holdings"] == rows
    assert _star(body)["provider"] == "derived"
    assert "holdings.AAA.pctContrib" in body["provenance"]


def test_kelly_wrapped(client, frame, monkeypatch):
    rows = [{"ticker": "AAA", "kellyFraction": 0.5, "annReturn": 0.2, "annVolatility": 0.15}]
    monkeypatch.setattr(port, "kelly_criterion", lambda h, f, rf: rows)
    body = client.post("/api/portfolio/kelly", json=HOLDINGS).json()
    assert body["holdings"] == rows
    assert _star(body)["provider"] == "derived"
    assert "holdings.AAA.kellyFraction" in body["provenance"]


def test_stress_wrapped(client, frame, monkeypatch):
    rows = [{"scenario": "gfc", "label": "GFC", "start": "2007-10-09", "end": "2009-03-09",
             "totalReturn": -0.4, "maxDrawdown": -0.5, "returnsTimeSeries": [], "benchmark": []}]
    monkeypatch.setattr(port, "stress_test_portfolio", lambda h, f, b: rows)
    body = client.post("/api/portfolio/stress", json=HOLDINGS).json()
    assert body["scenarios"] == rows
    assert _star(body)["provider"] == "derived"
    assert "scenarios.gfc.totalReturn" in body["provenance"]


def test_empty_holdings_returns():
    import asyncio

    req = portfolio_router.PortfolioRequest(holdings=[])
    assert asyncio.run(portfolio_router.risk_contribution(req)) == {"holdings": []}
    assert asyncio.run(portfolio_router.kelly(req)) == {"holdings": []}
    assert asyncio.run(portfolio_router.stress(req)) == {"scenarios": []}


# ------------------------------------------------------------------- snowflake

def test_snowflake_batch_wrapped(client, monkeypatch):
    scores = {"AAPL": {"overallScore": 6.1, "scores": {"value": 5.0, "growth": 7.0, "performance": 8.0,
                                                        "health": 6.0, "dividend": 4.5}}}
    monkeypatch.setattr(snowflake_service, "compute_snowflake_batch", lambda k: scores)
    monkeypatch.setattr(snowflake_router, "_oldest_row_time", lambda syms: "2026-10-02T06:00:00Z")
    body = client.get("/api/snowflake/batch", params={"tickers": "aapl"}).json()
    assert body["scores"] == scores
    star = _star(body)
    assert star["provider"] == "derived"
    assert star["fetchedAt"] == "2026-10-02T06:00:00Z"
    assert "scores.AAPL.overallScore" in body["provenance"]


def test_snowflake_batch_is_dated_by_its_oldest_row(client, monkeypatch, tmp_path):
    scores = {"AAPL": {"overallScore": 6.1, "scores": {}}, "MSFT": {"overallScore": 7.0, "scores": {}}}
    monkeypatch.setattr(snowflake_service, "compute_snowflake_batch", lambda k: scores)
    monkeypatch.setenv("SCREENER_DB_PATH", str(tmp_path / "sc.db"))
    screener_cache.reset_connection()
    try:
        conn = screener_cache._get_conn()
        conn.executemany("INSERT INTO fundamentals (symbol, updated_at) VALUES (?, ?)",
                         [("AAPL", "2026-10-01T00:00:00+00:00"), ("MSFT", "2026-06-26T20:49:48+00:00")])
        conn.commit()
        body = client.get("/api/snowflake/batch", params={"tickers": "aapl,msft"}).json()
    finally:
        screener_cache.reset_connection()
    assert _star(body)["fetchedAt"] == "2026-06-26T20:49:48Z"
