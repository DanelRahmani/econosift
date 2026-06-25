"""Tests for Phase 17.D API Optimization Layer."""
from __future__ import annotations

# Uses the shared `client` fixture from conftest.py (session-scoped TestClient).


def test_composite_endpoint_exists(client):
    """GET /api/market/composite returns 200 or 422/500 (not 404)."""
    resp = client.get("/api/market/composite?tickers=AAPL&period=1y")
    assert resp.status_code in (200, 422, 500), (
        f"Expected 200/422/500, got {resp.status_code}: {resp.text}"
    )


def test_composite_endpoint_no_tickers(client):
    """GET /api/market/composite without tickers returns 422."""
    resp = client.get("/api/market/composite")
    assert resp.status_code == 422


def test_composite_endpoint_empty_tickers(client):
    """GET /api/market/composite with blank tickers value returns 422."""
    resp = client.get("/api/market/composite?tickers=")
    assert resp.status_code == 422


def test_admin_performance_endpoint(client):
    """GET /api/admin/performance returns 200 with expected top-level keys."""
    resp = client.get("/api/admin/performance")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "cache" in data
    assert "jobs_last_24h" in data
    assert "database" in data


def test_admin_performance_jobs_is_list(client):
    """jobs_last_24h must be a list (possibly empty or containing an error entry)."""
    data = client.get("/api/admin/performance").json()
    assert isinstance(data["jobs_last_24h"], list)


def test_middleware_does_not_break_health(client):
    """DeduplicationMiddleware must not break the /api/health endpoint."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_middleware_does_not_break_existing_market_endpoints(client):
    """Existing /api/market/13f endpoint still works (422 = missing param, not broken)."""
    resp = client.get("/api/market/13f")
    assert resp.status_code == 422  # missing required 'ticker' param
