"""Offline tests for econ_lab_service (Phase 15 Econometric Lab).

wb.fetch is monkeypatched with deterministic synthetic SeriesResult data.
All tests are fully offline and reproducible.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any

import numpy as np
import pytest

from backend.models import SeriesResult


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

_COUNTRIES = ["US", "DE", "JP", "GB", "FR", "CN", "IN", "BR", "CA", "AU",
               "KR", "MX", "ES", "IT", "SE"]
_YEARS = list(range(2005, 2025))  # 20 years


def _make_sr(country: str, key: str, values: list[float]) -> SeriesResult:
    """Build a SeriesResult from a list of values aligned to _YEARS."""
    data = [{"year": str(_YEARS[i]), "value": v} for i, v in enumerate(values)]
    return {"country": country, "countryName": country, "data": data, "source_label": "test"}


def _build_panel(seed: int = 42):
    """Return (dep_series, indep1_series, indep2_series) as lists of SeriesResult.

    y = 2 + 3*x1 - 1*x2 + small_noise, across 15 countries × 20 years = 300 obs.
    """
    rng = np.random.default_rng(seed)
    n_c = len(_COUNTRIES)
    n_y = len(_YEARS)

    x1_vals = rng.uniform(1.0, 5.0, size=(n_c, n_y))
    x2_vals = rng.uniform(0.0, 3.0, size=(n_c, n_y))
    noise   = rng.normal(0.0, 0.05, size=(n_c, n_y))
    y_vals  = 2.0 + 3.0 * x1_vals - 1.0 * x2_vals + noise

    dep_series  = [_make_sr(c, "gdp_growth",   list(y_vals[i]))  for i, c in enumerate(_COUNTRIES)]
    indep1      = [_make_sr(c, "inflation",     list(x1_vals[i])) for i, c in enumerate(_COUNTRIES)]
    indep2      = [_make_sr(c, "unemployment",  list(x2_vals[i])) for i, c in enumerate(_COUNTRIES)]
    return dep_series, indep1, indep2


# ---------------------------------------------------------------------------
# Auto-clear caches between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_caches():
    from backend import cache
    cache._caches.clear()
    cache._stats.clear()
    yield
    cache._caches.clear()
    cache._stats.clear()


# ---------------------------------------------------------------------------
# Monkeypatch fixture factory
# ---------------------------------------------------------------------------

def _make_fetch(dep_sr, indep1_sr, indep2_sr, extra: dict | None = None):
    """Return an async wb.fetch replacement that dispatches by indicator key."""
    mapping = {
        "gdp_growth":   dep_sr,
        "inflation":    indep1_sr,
        "unemployment": indep2_sr,
    }
    if extra:
        mapping.update(extra)

    async def _fetch(indicator_key: str, countries: tuple, start: int, end: int):
        return mapping.get(indicator_key, [])

    return _fetch


# ---------------------------------------------------------------------------
# B3-1  Coefficient recovery
# ---------------------------------------------------------------------------

class TestCoefficientRecovery:
    def test_const_recovered(self, monkeypatch):
        """Intercept should be ≈ 2.0."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        assert "error" not in result, result.get("error")
        coefs = {c["name"]: c["coef"] for c in result["coefficients"]}
        assert abs(coefs["const"] - 2.0) < 0.3, f"const={coefs['const']}"

    def test_x1_coef_recovered(self, monkeypatch):
        """Coefficient for inflation (x1) should be ≈ 3.0."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        coefs = {c["name"]: c["coef"] for c in result["coefficients"]}
        assert abs(coefs["inflation"] - 3.0) < 0.3, f"inflation coef={coefs['inflation']}"

    def test_x2_coef_recovered(self, monkeypatch):
        """Coefficient for unemployment (x2) should be ≈ -1.0."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        coefs = {c["name"]: c["coef"] for c in result["coefficients"]}
        assert abs(coefs["unemployment"] - (-1.0)) < 0.3, f"unemployment coef={coefs['unemployment']}"

    def test_r_squared_near_one(self, monkeypatch):
        """R² should be very high given the low noise DGP."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        r2 = result["rSquared"]
        assert r2 is not None and r2 > 0.99, f"rSquared={r2}"

    def test_significant_stars_on_x1(self, monkeypatch):
        """With 300 obs the main regressors should be *** significant."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        stars = {c["name"]: c["stars"] for c in result["coefficients"]}
        assert stars["inflation"] == "***", f"inflation stars={stars['inflation']}"
        assert stars["unemployment"] == "***", f"unemployment stars={stars['unemployment']}"


# ---------------------------------------------------------------------------
# B3-2  Diagnostics (AIC / BIC / adjR²)
# ---------------------------------------------------------------------------

class TestDiagnostics:
    def test_adj_r2_less_than_r2(self, monkeypatch):
        """adjR² ≤ R² always (adding regressors penalises)."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        assert result["adjRSquared"] is not None
        assert result["adjRSquared"] <= result["rSquared"] + 1e-9

    def test_aic_and_bic_present(self, monkeypatch):
        """AIC and BIC should be finite numbers."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        assert result["aic"] is not None and math.isfinite(result["aic"])
        assert result["bic"] is not None and math.isfinite(result["bic"])

    def test_bic_ge_aic(self, monkeypatch):
        """BIC ≥ AIC when n ≥ e² ≈ 7.4 (penalty factor log(n) ≥ 2)."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        # With n=300 log(300)>2 so BIC penalty per param is larger than AIC's 2
        assert result["bic"] >= result["aic"]

    def test_n_obs_matches_expected(self, monkeypatch):
        """nObs should equal n_countries × n_years for complete synthetic data."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        assert result["nObs"] == len(_COUNTRIES) * len(_YEARS)


# ---------------------------------------------------------------------------
# B3-3  Missing country-years dropped
# ---------------------------------------------------------------------------

class TestMissingData:
    def test_inner_join_drops_nan_rows(self, monkeypatch):
        """When one indep has NaN for half the rows, nObs should be halved."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, _ = _build_panel()

        # Build i2 with NaN for half the years on all countries
        rng = np.random.default_rng(99)
        half_years = _YEARS[:10]  # only 10 of 20 years
        i2_half = []
        for c in _COUNTRIES:
            vals = list(rng.uniform(0, 3, size=10))
            data = [{"year": str(y), "value": v} for y, v in zip(half_years, vals)]
            i2_half.append({
                "country": c, "countryName": c,
                "data": data, "source_label": "test"
            })

        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2_half))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        assert "error" not in result, result.get("error")
        assert result["nObs"] == len(_COUNTRIES) * 10


# ---------------------------------------------------------------------------
# B3-4  Near-singular design matrix
# ---------------------------------------------------------------------------

class TestNearSingular:
    def test_collinear_sets_warning(self, monkeypatch):
        """Perfectly collinear indep (one = 2×other) sets warning, no exception."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, _ = _build_panel()

        # Build collinear_sr as exactly 2 × i1
        collinear = []
        for sr in i1:
            doubled = [{"year": dp["year"], "value": dp["value"] * 2} for dp in sr["data"]]
            collinear.append({
                "country": sr["country"], "countryName": sr["countryName"],
                "data": doubled, "source_label": "test"
            })

        extra = {"unemployment": collinear}
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, collinear, extra))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], list(_COUNTRIES), 2005, 2024
        ))
        # Should not raise; warning should be set
        assert "error" not in result or result.get("warning") is not None
        # If warning key present it must be a string
        if result.get("warning"):
            assert isinstance(result["warning"], str)


# ---------------------------------------------------------------------------
# B3-5  Insufficient observations
# ---------------------------------------------------------------------------

class TestInsufficientObs:
    def test_tiny_panel_returns_error(self, monkeypatch):
        """n=4 rows (2 countries × 2 years) should return error dict, not raise."""
        from backend.services import econ_lab_service as svc

        tiny_countries = ["US", "DE"]
        tiny_years = [2020, 2021]

        def _tiny_sr(key):
            return [
                {
                    "country": c, "countryName": c,
                    "data": [{"year": str(y), "value": float(j + i)}
                             for j, y in enumerate(tiny_years)],
                    "source_label": "test",
                }
                for i, c in enumerate(tiny_countries)
            ]

        async def _fetch(indicator_key, countries, start, end):
            return _tiny_sr(indicator_key)

        monkeypatch.setattr(svc.wb, "fetch", _fetch)

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "unemployment"], tiny_countries, 2020, 2021
        ))
        assert "error" in result
        assert result["coefficients"] == []
        assert result["nObs"] == 0


# ---------------------------------------------------------------------------
# B3-6  Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def _dummy_fetch(self):
        async def _f(key, countries, start, end):
            return []
        return _f

    def test_invalid_dep(self, monkeypatch):
        from backend.services import econ_lab_service as svc
        monkeypatch.setattr(svc.wb, "fetch", self._dummy_fetch())

        result = asyncio.run(svc.regress(
            "NOT_REAL", ["inflation"], ["US"], 2000, 2024
        ))
        assert "error" in result
        assert result["dep"] == "NOT_REAL"

    def test_invalid_indep(self, monkeypatch):
        from backend.services import econ_lab_service as svc
        monkeypatch.setattr(svc.wb, "fetch", self._dummy_fetch())

        result = asyncio.run(svc.regress(
            "gdp_growth", ["FAKE_VAR"], ["US"], 2000, 2024
        ))
        assert "error" in result

    def test_dep_in_indep(self, monkeypatch):
        from backend.services import econ_lab_service as svc
        monkeypatch.setattr(svc.wb, "fetch", self._dummy_fetch())

        result = asyncio.run(svc.regress(
            "gdp_growth", ["gdp_growth", "inflation"], ["US"], 2000, 2024
        ))
        assert "error" in result

    def test_empty_countries(self, monkeypatch):
        from backend.services import econ_lab_service as svc
        monkeypatch.setattr(svc.wb, "fetch", self._dummy_fetch())

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation"], [], 2000, 2024
        ))
        assert "error" in result
        assert result["countries"] == []

    def test_error_echoes_input_fields(self, monkeypatch):
        """Error dicts must echo dep, indep, countries, start, end."""
        from backend.services import econ_lab_service as svc
        monkeypatch.setattr(svc.wb, "fetch", self._dummy_fetch())

        result = asyncio.run(svc.regress(
            "NOT_REAL", ["inflation"], ["US", "DE"], 2005, 2020
        ))
        assert result["dep"] == "NOT_REAL"
        assert result["indep"] == ["inflation"]
        assert result["countries"] == ["US", "DE"]
        assert result["start"] == 2005
        assert result["end"] == 2020

    def test_dedup_indep(self, monkeypatch):
        """Duplicate indep keys should be silently deduplicated."""
        from backend.services import econ_lab_service as svc
        dep_sr, i1, i2 = _build_panel()
        monkeypatch.setattr(svc.wb, "fetch", _make_fetch(dep_sr, i1, i2))

        result = asyncio.run(svc.regress(
            "gdp_growth", ["inflation", "inflation", "unemployment"],
            list(_COUNTRIES), 2005, 2024
        ))
        # Should succeed and dedup to [inflation, unemployment]
        assert "error" not in result, result.get("error")
        names = [c["name"] for c in result["coefficients"]]
        assert names.count("inflation") == 1
        assert names.count("unemployment") == 1
