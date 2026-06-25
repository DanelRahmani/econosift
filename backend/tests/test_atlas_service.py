"""Tests for atlas_service — fully offline (network monkeypatched)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers: fake data builders
# ---------------------------------------------------------------------------

_FAKE_UNIVERSE = [
    {"iso3": "USA", "name": "United States", "id": "840", "regions": ["G7", "G20"]},
    {"iso3": "CHN", "name": "China",         "id": "156", "regions": ["G20", "EM"]},
    {"iso3": "XKX", "name": "Kosovo",        "id": None,  "regions": []},
]

# WB returns data for USA (2020–2021) and CHN (2021 only)
_FAKE_WB = {
    "USA": {2020: 2.3, 2021: 5.9},
    "CHN": {2021: 8.1},
}

# IMF fills in CHN 2020 and XKX 2021
_FAKE_IMF = {
    "CHN": {2020: 6.0},
    "XKX": {2021: 7.5},
}


def _patch(monkeypatch, indicator="gdp_growth", start=2020, end=2021):
    """Monkeypatch the three I/O helpers in atlas_service."""
    from backend.services import atlas_service
    from backend.cache import _caches

    # Clear relevant caches so each test gets a fresh result
    for key in list(_caches.keys()):
        if "atlas" in key:
            _caches[key].clear()

    monkeypatch.setattr(atlas_service, "_country_universe", lambda: _FAKE_UNIVERSE)

    async def fake_wb(ind, s, e):
        return _FAKE_WB if ind == indicator else {}

    async def fake_imf(ind, s, e):
        return _FAKE_IMF if ind == indicator else {}

    monkeypatch.setattr(atlas_service, "_wb_timeline", fake_wb)
    monkeypatch.setattr(atlas_service, "_imf_timeline", fake_imf)


# ---------------------------------------------------------------------------
# get_timeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeline_all_year_keys_present(monkeypatch):
    """Every year from start..end must appear as a key, even if None."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    result = await atlas_service.get_timeline("gdp_growth", 2020, 2021)
    for c in result["countries"]:
        assert "2020" in c["values"]
        assert "2021" in c["values"]


@pytest.mark.asyncio
async def test_timeline_wb_primary(monkeypatch):
    """WB values take priority over IMF."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    result = await atlas_service.get_timeline("gdp_growth", 2020, 2021)
    usa = next(c for c in result["countries"] if c["iso3"] == "USA")
    assert usa["values"]["2020"] == pytest.approx(2.3)
    assert usa["values"]["2021"] == pytest.approx(5.9)


@pytest.mark.asyncio
async def test_timeline_imf_gap_fill(monkeypatch):
    """IMF fills years where WB is absent."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    result = await atlas_service.get_timeline("gdp_growth", 2020, 2021)
    chn = next(c for c in result["countries"] if c["iso3"] == "CHN")
    # 2020: WB missing → IMF 6.0
    assert chn["values"]["2020"] == pytest.approx(6.0)
    # 2021: WB present (8.1) → WB wins
    assert chn["values"]["2021"] == pytest.approx(8.1)


@pytest.mark.asyncio
async def test_timeline_none_when_both_missing(monkeypatch):
    """Year absent from both WB and IMF → None."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    result = await atlas_service.get_timeline("gdp_growth", 2020, 2021)
    xkx = next(c for c in result["countries"] if c["iso3"] == "XKX")
    # 2020: missing from both
    assert xkx["values"]["2020"] is None
    # 2021: IMF has it
    assert xkx["values"]["2021"] == pytest.approx(7.5)


@pytest.mark.asyncio
async def test_timeline_numeric_id_propagates(monkeypatch):
    """numeric id from the universe propagates to each country entry."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    result = await atlas_service.get_timeline("gdp_growth", 2020, 2021)
    usa = next(c for c in result["countries"] if c["iso3"] == "USA")
    assert usa["id"] == "840"
    xkx = next(c for c in result["countries"] if c["iso3"] == "XKX")
    assert xkx["id"] is None


@pytest.mark.asyncio
async def test_timeline_regions_propagate(monkeypatch):
    """regions list from the universe propagates to each country entry."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    result = await atlas_service.get_timeline("gdp_growth", 2020, 2021)
    usa = next(c for c in result["countries"] if c["iso3"] == "USA")
    assert "G7" in usa["regions"]
    assert "G20" in usa["regions"]


@pytest.mark.asyncio
async def test_timeline_metadata(monkeypatch):
    """Top-level metadata fields are correct."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    result = await atlas_service.get_timeline("gdp_growth", 2020, 2021)
    assert result["indicator"] == "gdp_growth"
    assert result["unit"] == "%"
    assert result["goodDirection"] == "high"
    assert result["start"] == 2020
    assert result["end"] == 2021


@pytest.mark.asyncio
async def test_timeline_invalid_indicator(monkeypatch):
    """Unknown indicator raises ValueError."""
    from backend.services import atlas_service

    with pytest.raises(ValueError, match="Unknown indicator"):
        await atlas_service.get_timeline("nonexistent_indicator", 2020, 2021)


# ---------------------------------------------------------------------------
# get_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snapshot_slices_correct_year(monkeypatch):
    """get_snapshot returns the correct year's value for each country."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    snap = await atlas_service.get_snapshot("gdp_growth", 2021)
    usa = next(c for c in snap["countries"] if c["iso3"] == "USA")
    assert usa["value"] == pytest.approx(5.9)
    chn = next(c for c in snap["countries"] if c["iso3"] == "CHN")
    assert chn["value"] == pytest.approx(8.1)


@pytest.mark.asyncio
async def test_snapshot_stats_ignore_nulls(monkeypatch):
    """Stats (avg, top, bottom) use only non-null values."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    snap = await atlas_service.get_snapshot("gdp_growth", 2020)
    # 2020: USA=2.3 (WB), CHN=6.0 (IMF gap-fill), XKX=None
    assert snap["stats"]["count_reporting"] == 2
    assert snap["stats"]["avg"] == pytest.approx((2.3 + 6.0) / 2, rel=1e-3)


@pytest.mark.asyncio
async def test_snapshot_top_bottom_order(monkeypatch):
    """top is descending, bottom is ascending."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    snap = await atlas_service.get_snapshot("gdp_growth", 2021)
    # 2021: USA=5.9, CHN=8.1, XKX=7.5 (from IMF)
    top_values = [c["value"] for c in snap["stats"]["top"]]
    assert top_values == sorted(top_values, reverse=True)

    bottom_values = [c["value"] for c in snap["stats"]["bottom"]]
    assert bottom_values == sorted(bottom_values)


@pytest.mark.asyncio
async def test_snapshot_fields(monkeypatch):
    """Snapshot has all required top-level fields."""
    _patch(monkeypatch)
    from backend.services import atlas_service

    snap = await atlas_service.get_snapshot("gdp_growth", 2021)
    assert "indicator" in snap
    assert "unit" in snap
    assert "year" in snap
    assert "countries" in snap
    assert "stats" in snap
    assert "avg" in snap["stats"]
    assert "count_reporting" in snap["stats"]
    assert "top" in snap["stats"]
    assert "bottom" in snap["stats"]


# ---------------------------------------------------------------------------
# get_indicators / get_regions
# ---------------------------------------------------------------------------

def test_get_indicators_returns_six():
    from backend.services import atlas_service

    result = atlas_service.get_indicators()
    assert "indicators" in result
    assert len(result["indicators"]) == 6


def test_get_indicators_valid_good_directions():
    from backend.services import atlas_service

    valid = {"high", "low", "neutral"}
    for ind in atlas_service.get_indicators()["indicators"]:
        assert ind["goodDirection"] in valid, f"{ind['id']} has invalid goodDirection"


def test_get_indicators_ids():
    from backend.services import atlas_service

    ids = {i["id"] for i in atlas_service.get_indicators()["indicators"]}
    expected = {
        "gdp_growth", "inflation", "unemployment",
        "debt_gdp", "current_account", "gdp_per_capita",
    }
    assert ids == expected


def test_get_regions_returns_four():
    from backend.services import atlas_service

    result = atlas_service.get_regions()
    assert "regions" in result
    assert len(result["regions"]) == 4


def test_get_regions_ids():
    from backend.services import atlas_service

    ids = {r["id"] for r in atlas_service.get_regions()["regions"]}
    assert ids == {"G7", "G20", "Eurozone", "EM"}


def test_get_regions_g7_members():
    from backend.services import atlas_service

    regions = {r["id"]: r for r in atlas_service.get_regions()["regions"]}
    g7 = set(regions["G7"]["members"])
    assert {"USA", "CAN", "GBR", "FRA", "DEU", "ITA", "JPN"} == g7


def test_get_regions_eurozone_has_twenty():
    from backend.services import atlas_service

    regions = {r["id"]: r for r in atlas_service.get_regions()["regions"]}
    assert len(regions["Eurozone"]["members"]) == 20


def test_get_regions_em_members():
    from backend.services import atlas_service

    regions = {r["id"]: r for r in atlas_service.get_regions()["regions"]}
    em = set(regions["EM"]["members"])
    # spot-check a few
    assert "CHN" in em
    assert "IND" in em
    assert "BRA" in em


# ---------------------------------------------------------------------------
# Router smoke test (no network)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_with_patches(monkeypatch):
    from backend.services import atlas_service
    from backend.cache import _caches

    for key in list(_caches.keys()):
        if "atlas" in key:
            _caches[key].clear()

    monkeypatch.setattr(atlas_service, "_country_universe", lambda: _FAKE_UNIVERSE)

    async def fake_wb(ind, s, e):
        return _FAKE_WB

    async def fake_imf(ind, s, e):
        return _FAKE_IMF

    monkeypatch.setattr(atlas_service, "_wb_timeline", fake_wb)
    monkeypatch.setattr(atlas_service, "_imf_timeline", fake_imf)

    from backend.main import app
    return TestClient(app)


def test_router_indicators(client_with_patches):
    resp = client_with_patches.get("/api/atlas/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert "indicators" in data
    assert len(data["indicators"]) == 6


def test_router_regions(client_with_patches):
    resp = client_with_patches.get("/api/atlas/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert "regions" in data


def test_router_timeline(client_with_patches):
    resp = client_with_patches.get(
        "/api/atlas/timeline?indicator=gdp_growth&start=2020&end=2021"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "gdp_growth"
    assert len(data["countries"]) == 3


def test_router_snapshot(client_with_patches):
    resp = client_with_patches.get(
        "/api/atlas/snapshot?indicator=gdp_growth&year=2021"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2021
    assert "stats" in data


def test_router_timeline_bad_indicator(client_with_patches):
    resp = client_with_patches.get(
        "/api/atlas/timeline?indicator=bogus&start=2020&end=2021"
    )
    assert resp.status_code == 400


def test_router_snapshot_bad_indicator(client_with_patches):
    resp = client_with_patches.get(
        "/api/atlas/snapshot?indicator=bogus&year=2021"
    )
    assert resp.status_code == 400
