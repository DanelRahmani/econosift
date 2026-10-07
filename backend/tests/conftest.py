"""Shared pytest fixtures for the EconoSift backend test suite.

Math/model tests run fully offline against synthetic data. Network-touching
tests (yfinance, FRED, etc.) should be marked and skipped in CI; we keep the
default suite deterministic and dependency-free.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# P2-36: pin a throwaway SQLite DB before anything imports backend.database.
# _fresh_caches clears both cache tiers before every test, so an inherited
# DATABASE_URL (the live ./data DB inside the container) would be wiped.
_TEST_DB = Path(tempfile.gettempdir()) / "econosift_pytest.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

import pytest
from fastapi.testclient import TestClient

# Ensure `backend` package is importable when running `pytest` from backend/.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture(autouse=True)
def _fresh_caches():
    """Reset both cache tiers before each test.

    The @cached/@async_cached decorators share module-level TTLCaches and a
    persistent SQLite tier; without this reset, values cached by one test leak
    into later ones (empty-data tests receive earlier real results) and even
    across pytest runs via the SQLite volume.
    """
    from backend import cache as cache_mod

    cache_mod.clear_all()
    yield


@pytest.fixture(scope="session")
def client() -> TestClient:
    from backend.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _offline_gnp_price_index(monkeypatch):
    """Ohlson's SIZE scaling reads FRED GDPDEF; pin it so tests stay offline.

    660 ≈ the 2026 GDP deflator rebased to 1968 = 100.
    """
    from backend.services import fundamentals
    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 660.0)


@pytest.fixture(autouse=True)
def _offline_technicals_currency(request, monkeypatch):
    """get_technicals reads the quote currency from Yahoo; the technicals indicator
    tests don't test it, so keep them offline (test_valuation_p64 covers it)."""
    if request.module.__name__.split(".")[-1].startswith("test_technicals"):
        from backend.services import technicals_service
        monkeypatch.setattr(technicals_service, "_quote_currency", lambda ticker: None)
