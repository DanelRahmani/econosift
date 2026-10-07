"""P1-19: AI summaries take numbers from EconoSift data (APP DATA) and news from Google Search.

Offline: Gemini is a fake httpx client; app data is fixture dicts.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from backend.services import ai_context, ai_service


class _Resp:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body
        self.text = json.dumps(body)

    def json(self):
        return self._body


def _ok(text="Headline.\n- point", grounding=None):
    cand = {"content": {"parts": [{"text": text}]}}
    if grounding is not None:
        cand["groundingMetadata"] = grounding
    return _Resp(200, {"candidates": [cand]})


class _FakeClient:
    """Records each request payload and replies from a queue."""
    def __init__(self, replies):
        self.replies, self.payloads = list(replies), []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, params=None, json=None, headers=None):
        self.payloads.append(json)
        return self.replies.pop(0)


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "test-key")

    def install(*replies):
        client = _FakeClient(replies)
        monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda timeout=None: client)
        return client
    return install


_GM = {
    "webSearchQueries": ["Apple earnings October 2026"],
    "groundingChunks": [
        {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a", "title": "reuters.com"}},
        {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a", "title": "reuters.com"}},
        {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/b", "title": "apple.com"}},
    ],
    "searchEntryPoint": {"renderedContent": "<div>chips</div>"},
}


def test_request_carries_app_data_and_the_search_tool(gemini):
    client = gemini(_ok(grounding=_GM))
    facts = {"ticker": "AAPL", "quote": {"price": 330.32, "changePercent": -0.8108}}
    out = asyncio.run(ai_service.generate_summary("Summarise AAPL.", facts))
    payload = client.payloads[0]
    assert payload["tools"] == [{"google_search": {}}]
    prompt = payload["contents"][0]["parts"][0]["text"]
    assert '"price":330.32' in prompt and "must come from APP DATA" in prompt
    assert "Task: Summarise AAPL." in prompt
    # sources come from groundingMetadata, de-duplicated by URI, not from the model's text
    assert out["sources"] == [
        {"title": "reuters.com", "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a"},
        {"title": "apple.com", "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/b"}]
    assert out["searchQueries"] == ["Apple earnings October 2026"]
    assert out["searchEntryPoint"] == "<div>chips</div>"
    assert out["searchUsed"] is True and out["searchNote"] is None


def test_refused_search_falls_back_to_app_data_only_rules(gemini):
    client = gemini(_Resp(400, {"error": {"message": "Search Grounding is not supported."}}), _ok())
    out = asyncio.run(ai_service.generate_summary("Summarise AAPL.", {"ticker": "AAPL"}))
    assert "tools" not in client.payloads[1]
    second_prompt = client.payloads[1]["contents"][0]["parts"][0]["text"]
    assert "You have no news source" in second_prompt
    assert out["searchUsed"] is False and out["sources"] == []
    assert "400" in out["searchNote"] and "EconoSift data only" in out["searchNote"]
    assert not out["text"].startswith("Error:")


def test_both_calls_failing_is_an_error(gemini):
    gemini(_Resp(429, {"error": {"message": "quota"}}), _Resp(429, {"error": {"message": "quota"}}))
    out = asyncio.run(ai_service.generate_summary("t", {}))
    assert out["text"].startswith("Error: Gemini API returned 429")


def test_overloaded_gemini_is_an_error_without_a_second_call(gemini):
    client = gemini(_Resp(503, {"error": {"message": "high demand"}}))
    out = asyncio.run(ai_service.generate_summary("t", {}))
    assert out["text"].startswith("Error: Gemini API returned 503") and len(client.payloads) == 1


def test_no_key_is_an_error(monkeypatch):
    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "")
    out = asyncio.run(ai_service.generate_summary("t", {}))
    assert out["text"].startswith("Error: Gemini API key not configured")


# ── app-data blocks ──

def test_company_block_keeps_headline_figures_and_lock_reasons():
    full = {
        "kpis": {"marketCap": 4820749644490.967, "trailingPE": 41.123456, "dividendYield": 0.31, "beta": None},
        "valuation": {
            "axiomFairValue": {"value": 229.123456, "upsidePct": -0.3065, "verdict": "Overvalued"},
            "models": [{"model": "DCF (Two-Stage)", "value": 168.39711, "locked": False},
                       {"model": "Residual Income (RIM)", "value": None, "locked": True,
                        "reason": "not meaningful: ROE above 100%"}],
            "wacc": {"wacc": 0.1007218, "riskFreeSource": "FRED DGS10", "sensitivity": [[1, 2]]},
        },
        "fundamentals": {"piotroski": {"score": 7, "maxScore": 9}, "beneish": {"mScore": -2.2936,
                                                                                "manipulationLikely": False}},
        "analyst": {"earningsSurprises": [{"date": f"2026-0{i}-01", "surprisePct": 1.0} for i in range(1, 7)]},
    }
    b = ai_context.company_block({"price": 330.32, "changePercent": -0.8107566}, full)
    # 6 significant digits: prices keep their cents, long floats are trimmed
    assert b["quote"] == {"price": 330.32, "changePercent": -0.810757}
    assert b["kpis"] == {"marketCap": 4.82075e12, "trailingPE": 41.1235, "dividendYieldPct": 0.31}  # beta None dropped
    assert b["fairValue"] == {"value": 229.123, "upsidePct": -0.3065, "verdict": "Overvalued"}
    assert b["valuationModels"] == [{"model": "DCF (Two-Stage)", "value": 168.397},
                                    {"model": "Residual Income (RIM)", "reason": "not meaningful: ROE above 100%"}]
    assert b["discountRate"] == {"wacc": 0.100722, "riskFreeSource": "FRED DGS10"}   # no grids
    assert b["healthScores"] == {"piotroski": "7/9", "beneishM": -2.2936, "beneishFlagged": False}
    assert len(b["analysts"]["recentEarningsSurprises"]) == 4


def test_macro_block_regroups_by_country_with_year_and_unit():
    snap = {"indicators": [
        {"id": "gdp_growth", "unit": "%", "values": {"US": {"value": 2.7934, "year": 2025}, "DE": {"value": None}}},
        {"id": "inflation", "unit": "%", "values": {"US": {"value": 2.95, "year": 2025}}}]}
    assert ai_context.macro_block(snap) == {"US": {"gdp_growth": {"value": 2.7934, "year": 2025, "unit": "%"},
                                                   "inflation": {"value": 2.95, "year": 2025, "unit": "%"}}}


def test_dashboard_block_and_missing_sections():
    b = ai_context.dashboard_block(
        {"advancing": 296, "declining": 205, "cumulativeAdLine": [1, 2]},
        {"indices": [{"name": "S&P 500", "price": 7666.45, "change1d": 0.19, "spark": [1, 2]}]},
        None,
        {"gainers": [{"ticker": "ACN", "changePercent": 15.78}] * 8, "losers": []})
    assert b["breadthSP500"] == {"advancing": 296, "declining": 205}
    assert b["indices"] == [{"name": "S&P 500", "price": 7666.45, "change1d": 0.19}]
    assert "fearGreed" not in b and "topLosers" not in b
    assert len(b["topGainers"]) == 5


# ── router: grounding stored and returned; old rows still readable ──

def test_router_returns_and_caches_grounding(gemini, monkeypatch):
    from backend.routers import ai as ai_router
    gemini(_ok(grounding=_GM))
    saved = {}
    monkeypatch.setattr(ai_router, "_save", lambda *a: saved.update(args=a))
    monkeypatch.setattr(ai_router, "_cached_lookup", lambda *a: None)
    from backend.services import macro_service

    async def snap(isos, year):
        return {"indicators": [{"id": "inflation", "unit": "%", "values": {"US": {"value": 2.95, "year": 2025}}}]}
    monkeypatch.setattr(macro_service, "get_snapshot", snap)
    out = asyncio.run(ai_router.ai_macro(ai_router.MacroRequest(countries=["us"])))
    assert out["grounding"]["searchUsed"] is True and len(out["grounding"]["sources"]) == 2
    assert out["appData"]["sections"] == ["macro snapshot"] and out["appData"]["unavailable"] == {}
    record = saved["args"][5]
    assert record["grounding"]["sources"] == out["grounding"]["sources"]

    class Row:  # the cached row read back later
        summary_text, model_used, created_at = "Headline.\n- point", "gemini-2.5-flash", ai_router._utcnow()
        grounding = json.dumps(record)
    monkeypatch.setattr(ai_router, "_cached_lookup", lambda *a: Row)
    again = asyncio.run(ai_router.ai_macro(ai_router.MacroRequest(countries=["US"])))
    assert again["cached"] is True and again["grounding"] == out["grounding"]

    Row.grounding = None  # a summary generated before grounding existed
    old = asyncio.run(ai_router.ai_macro(ai_router.MacroRequest(countries=["US"])))
    assert old["grounding"] is None and "before" in old["provenance"]["*"]["note"]


def test_failed_source_is_reported_not_fatal(gemini, monkeypatch):
    from backend.routers import ai as ai_router
    gemini(_ok())
    monkeypatch.setattr(ai_router, "_save", lambda *a: None)
    monkeypatch.setattr(ai_router, "_cached_lookup", lambda *a: None)
    from backend.services import macro_service

    async def boom(isos, year):
        raise RuntimeError("World Bank down")
    monkeypatch.setattr(macro_service, "get_snapshot", boom)
    out = asyncio.run(ai_router.ai_macro(ai_router.MacroRequest(countries=["US"])))
    assert out["appData"]["sections"] == []
    assert "macro snapshot" in out["appData"]["unavailable"]


def test_migration_adds_grounding_column(tmp_path, monkeypatch):
    import sqlalchemy
    from backend import database
    eng = sqlalchemy.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as c:   # a database created before the column existed
        c.execute(sqlalchemy.text("CREATE TABLE ai_summary (id INTEGER PRIMARY KEY, summary_text TEXT)"))
    monkeypatch.setattr(database, "engine", eng)
    database._add_missing_columns()
    database._add_missing_columns()  # idempotent
    cols = {c["name"] for c in sqlalchemy.inspect(eng).get_columns("ai_summary")}
    assert "grounding" in cols


def test_company_summary_for_several_tickers_fetches_each_one(gemini, monkeypatch):
    # Markets sends the selected pills as "MSFT,aapl". Treated as one symbol,
    # Yahoo resolved the first ticker and the summary described a fictional
    # "combined entity" with AAPL's price. Each ticker gets its own figures.
    from backend.routers import ai as ai_router
    from backend.routers import valuation as valuation_router
    from backend.services import yfinance_service as yfs
    client = gemini(_ok())
    saved = {}
    monkeypatch.setattr(ai_router, "_save", lambda *a: saved.update(args=a))
    monkeypatch.setattr(ai_router, "_cached_lookup", lambda *a: None)
    prices = {"AAPL": 330.32, "MSFT": 517.53}
    asked = []

    def quote(sym):
        asked.append(sym)
        return {"price": prices[sym], "changePercent": 1.0}

    async def full(sym):
        return {}
    monkeypatch.setattr(yfs, "get_quote", quote)
    monkeypatch.setattr(valuation_router, "full", full)

    out = asyncio.run(ai_router.ai_company(ai_router.CompanyRequest(ticker="MSFT, aapl")))
    assert sorted(asked) == ["AAPL", "MSFT"]
    assert out["context_key"] == "AAPL,MSFT" and saved["args"][1] == "AAPL,MSFT"
    sent = json.dumps(client.payloads[0])
    assert "330.32" in sent and "517.53" in sent
    assert "AAPL" in saved["args"][3] and "MSFT" in saved["args"][3] and "each" in saved["args"][3]


def test_old_combined_multi_ticker_summary_is_not_served_from_cache(gemini, monkeypatch):
    from backend.routers import ai as ai_router
    from backend.routers import valuation as valuation_router
    from backend.services import yfinance_service as yfs
    gemini(_ok("Fresh."))
    monkeypatch.setattr(ai_router, "_save", lambda *a: None)

    class Old:  # built before the fix: one "quote" section for the joined string
        summary_text, model_used, created_at = "The combined entity...", "gemini-2.5-flash", ai_router._utcnow()
        grounding = json.dumps({"grounding": {}, "appData": {"asOf": "2026-10-01", "sections": ["quote", "valuation"],
                                                             "unavailable": {}}})
    monkeypatch.setattr(ai_router, "_cached_lookup", lambda *a: Old)
    monkeypatch.setattr(yfs, "get_quote", lambda s: {"price": 1.0})

    async def full(sym):
        return {}
    monkeypatch.setattr(valuation_router, "full", full)
    out = asyncio.run(ai_router.ai_company(ai_router.CompanyRequest(ticker="AAPL,MSFT")))
    assert out["cached"] is False and out["summary_text"] == "Fresh."
