"""Offline unit tests for the Fama-French attribution service.

All tests are fully offline:
  - `load_ff_factors` is monkeypatched to return a synthetic DataFrame.
  - yfinance price downloads are monkeypatched via the `yfinance.download` call
    inside `factor_regression`.

The synthetic data is generated as a *known* linear combination of the factor
realizations plus small noise, so the recovered betas should be close to the
true values and R² should be high.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers to build synthetic factor / price data
# ---------------------------------------------------------------------------

_SEED = 42
_N = 504  # ~2 years of daily data


def _make_factor_df(n: int = _N, seed: int = _SEED) -> pd.DataFrame:
    """Return a synthetic daily factor DataFrame with realistic magnitudes."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=date.today(), periods=n, freq="B")
    mkt_rf = rng.normal(0.0004, 0.010, n)
    smb    = rng.normal(0.0001, 0.005, n)
    hml    = rng.normal(0.0001, 0.005, n)
    rmw    = rng.normal(0.0001, 0.004, n)
    cma    = rng.normal(0.0001, 0.004, n)
    rf     = np.full(n, 0.00015)  # ~4% annualised
    return pd.DataFrame(
        {"Mkt-RF": mkt_rf, "SMB": smb, "HML": hml, "RMW": rmw, "CMA": cma, "RF": rf},
        index=idx,
    )


def _make_price_series_from_factors(
    factors: pd.DataFrame,
    true_betas: dict[str, float],
    alpha_daily: float = 0.0002,
    noise_scale: float = 0.002,
    seed: int = _SEED + 1,
) -> pd.Series:
    """Generate a price series whose returns are a linear combo of factors + noise.

    The excess return is:
        r_excess = alpha + beta_MktRF * Mkt-RF + beta_SMB * SMB + ...  + eps

    We then add back RF so the raw return = r_excess + RF, and cumulate to get
    a price series with the same date index as `factors`.
    """
    rng = np.random.default_rng(seed)
    n = len(factors)

    r_excess = np.full(n, alpha_daily, dtype=float)
    for col, beta in true_betas.items():
        if col in factors.columns:
            r_excess += beta * factors[col].values

    eps = rng.normal(0, noise_scale, n)
    r_excess += eps

    raw_ret = r_excess + factors["RF"].values

    # Cumulate to a price series starting at 100.
    prices = np.cumprod(1.0 + raw_ret) * 100.0
    return pd.Series(prices, index=factors.index, name="FAKE")


# ---------------------------------------------------------------------------
# Monkeypatch fixtures
# ---------------------------------------------------------------------------

# True betas used to generate synthetic data (3-factor model).
_TRUE_BETAS_3F = {"Mkt-RF": 1.2, "SMB": 0.4, "HML": -0.3}
_TRUE_BETAS_5F = {"Mkt-RF": 1.1, "SMB": 0.3, "HML": -0.2, "RMW": 0.2, "CMA": -0.1}


@pytest.fixture()
def synthetic_factors_3f():
    return _make_factor_df()


@pytest.fixture()
def synthetic_factors_5f():
    return _make_factor_df()


@pytest.fixture()
def patch_ff3(monkeypatch, synthetic_factors_3f):
    """Patch load_ff_factors in the fama_french module namespace."""
    import backend.services.fama_french as ff_mod

    monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": synthetic_factors_3f)
    return synthetic_factors_3f


@pytest.fixture()
def patch_ff5(monkeypatch, synthetic_factors_5f):
    import backend.services.fama_french as ff_mod

    monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": synthetic_factors_5f)
    return synthetic_factors_5f


def _make_yf_download_patch(factors: pd.DataFrame, true_betas: dict[str, float]):
    """Return a function that fakes yf.download returning a Close-column DataFrame."""
    prices = _make_price_series_from_factors(factors, true_betas)

    def _fake_download(ticker, period=None, interval=None, auto_adjust=None, progress=None, **kw):
        # yfinance returns a DataFrame; factor_regression reads ["Close"] column.
        df = pd.DataFrame({"Close": prices.values}, index=prices.index)
        return df

    return _fake_download


# ---------------------------------------------------------------------------
# Tests: 3-factor regression recovers betas
# ---------------------------------------------------------------------------

class TestFF3FactorRegression:
    """Offline test: monkeypatched factors + prices; assert beta recovery."""

    def test_returns_dict_with_expected_keys(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))

        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        required_keys = {"ticker", "model", "alpha", "alphaDaily", "betas", "rSquared", "tStats", "nObs", "period", "asOf"}
        assert required_keys.issubset(set(result.keys()))

    def test_ticker_and_model_echoed(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["ticker"] == "FAKE"
        assert result["model"] == "3"
        assert result["period"] == "2y"

    def test_betas_keys_3f(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert set(result["betas"].keys()) == {"MktRF", "SMB", "HML"}

    def test_beta_mktrf_close_to_true(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["betas"]["MktRF"] == pytest.approx(_TRUE_BETAS_3F["Mkt-RF"], abs=0.15), (
            f"MktRF beta {result['betas']['MktRF']:.4f} not close to true {_TRUE_BETAS_3F['Mkt-RF']}"
        )

    def test_beta_smb_close_to_true(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["betas"]["SMB"] == pytest.approx(_TRUE_BETAS_3F["SMB"], abs=0.20)

    def test_beta_hml_close_to_true(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["betas"]["HML"] == pytest.approx(_TRUE_BETAS_3F["HML"], abs=0.20)

    def test_r_squared_high_for_low_noise(self, monkeypatch, patch_ff3):
        """With noise_scale=0.002 vs MktRF std ~0.010 * beta=1.2, R² should be high."""
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["rSquared"] >= 0.70, f"R² {result['rSquared']:.4f} too low"

    def test_r_squared_in_unit_interval(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert 0.0 <= result["rSquared"] <= 1.0

    def test_nobs_reasonable(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["nObs"] >= 200

    def test_tstats_keys_include_alpha_and_betas(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert set(result["tStats"].keys()) == {"alpha", "MktRF", "SMB", "HML"}

    def test_alpha_is_annualised(self, monkeypatch, patch_ff3):
        """alpha = alphaDaily * 252."""
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["alpha"] == pytest.approx(result["alphaDaily"] * 252, rel=1e-6)

    def test_as_of_is_today(self, monkeypatch, patch_ff3):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff3, _TRUE_BETAS_3F))
        result = ff_mod.factor_regression("FAKE", model="3", period="2y")

        assert result["asOf"] == date.today().isoformat()


# ---------------------------------------------------------------------------
# Tests: 5-factor regression
# ---------------------------------------------------------------------------

class TestFF5FactorRegression:

    def test_betas_keys_5f(self, monkeypatch, patch_ff5):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff5, _TRUE_BETAS_5F))
        result = ff_mod.factor_regression("FAKE", model="5", period="2y")

        assert "error" not in result, result.get("error")
        assert set(result["betas"].keys()) == {"MktRF", "SMB", "HML", "RMW", "CMA"}

    def test_beta_mktrf_close_to_true_5f(self, monkeypatch, patch_ff5):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff5, _TRUE_BETAS_5F))
        result = ff_mod.factor_regression("FAKE", model="5", period="2y")

        assert result["betas"]["MktRF"] == pytest.approx(_TRUE_BETAS_5F["Mkt-RF"], abs=0.20)

    def test_r_squared_high_5f(self, monkeypatch, patch_ff5):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff5, _TRUE_BETAS_5F))
        result = ff_mod.factor_regression("FAKE", model="5", period="2y")

        assert result["rSquared"] >= 0.70

    def test_model_echoed_5f(self, monkeypatch, patch_ff5):
        import yfinance as yf
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(yf, "download", _make_yf_download_patch(patch_ff5, _TRUE_BETAS_5F))
        result = ff_mod.factor_regression("FAKE", model="5", period="2y")

        assert result["model"] == "5"


# ---------------------------------------------------------------------------
# Tests: graceful handling when load_ff_factors returns None
# ---------------------------------------------------------------------------

class TestFactorDataUnavailable:

    def test_no_raise_when_factors_none(self, monkeypatch):
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": None)
        result = ff_mod.factor_regression("AAPL", model="3")

        # Must not raise; must return a dict with 'error' key.
        assert isinstance(result, dict)
        assert result.get("error") == "factor data unavailable"

    def test_error_dict_contains_ticker(self, monkeypatch):
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": None)
        result = ff_mod.factor_regression("MSFT", model="3")

        assert result["ticker"] == "MSFT"

    def test_error_dict_contains_model(self, monkeypatch):
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": None)
        result = ff_mod.factor_regression("MSFT", model="5")

        assert result["model"] == "5"

    def test_error_dict_contains_period(self, monkeypatch):
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": None)
        result = ff_mod.factor_regression("MSFT", model="3", period="1y")

        assert result["period"] == "1y"

    def test_error_dict_contains_as_of(self, monkeypatch):
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": None)
        result = ff_mod.factor_regression("MSFT", model="3")

        # no factor data was used, so there is no honest as-of date
        assert "asOf" in result and result["asOf"] is None

    def test_no_raise_when_factors_empty_df(self, monkeypatch):
        import backend.services.fama_french as ff_mod

        monkeypatch.setattr(ff_mod, "load_ff_factors", lambda model="3": pd.DataFrame())
        result = ff_mod.factor_regression("AAPL", model="3")

        assert isinstance(result, dict)
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests: _parse_ff_csv (unit test the CSV parser directly)
# ---------------------------------------------------------------------------

class TestParseFfCsv:
    """Unit test the CSV parsing logic with a hand-crafted mini-CSV."""

    _MINI_3F_CSV = (
        "This file was created by CRSP using SAS\n"
        "Fama/French 3 Factors (Daily)\n"
        "  Daily Factors:\n"
        "  0 : Average Value Weighted Returns -- Daily\n"
        "\n"
        "           , Mkt-RF,  SMB,  HML,   RF\n"
        "19260701,  0.10, -0.24, -0.28,  0.009\n"
        "19260702, -0.09,  0.01,  0.08,  0.009\n"
        "19260706,  0.44,  0.61, -0.53,  0.009\n"
        "Annual Factors:\n"
        "     ,Mkt-RF,SMB,HML,RF\n"
        "1926,29.59,13.18,-3.84,3.28\n"
    )

    def test_parse_returns_dataframe(self):
        from backend.services.fama_french import _parse_ff_csv
        raw = self._MINI_3F_CSV.encode("latin-1")
        df = _parse_ff_csv(raw, ["Mkt-RF", "SMB", "HML", "RF"])
        assert isinstance(df, pd.DataFrame)

    def test_parse_correct_n_rows(self):
        from backend.services.fama_french import _parse_ff_csv
        raw = self._MINI_3F_CSV.encode("latin-1")
        df = _parse_ff_csv(raw, ["Mkt-RF", "SMB", "HML", "RF"])
        # Only 3 daily rows; annual rows should be excluded.
        assert len(df) == 3

    def test_parse_columns_present(self):
        from backend.services.fama_french import _parse_ff_csv
        raw = self._MINI_3F_CSV.encode("latin-1")
        df = _parse_ff_csv(raw, ["Mkt-RF", "SMB", "HML", "RF"])
        assert set(df.columns) == {"Mkt-RF", "SMB", "HML", "RF"}

    def test_parse_values_divided_by_100(self):
        """Values in the CSV are in percent; parser must divide by 100."""
        from backend.services.fama_french import _parse_ff_csv
        raw = self._MINI_3F_CSV.encode("latin-1")
        df = _parse_ff_csv(raw, ["Mkt-RF", "SMB", "HML", "RF"])
        # First row: Mkt-RF = 0.10 / 100 = 0.001
        assert df["Mkt-RF"].iloc[0] == pytest.approx(0.001, abs=1e-8)

    def test_parse_rf_divided_by_100(self):
        from backend.services.fama_french import _parse_ff_csv
        raw = self._MINI_3F_CSV.encode("latin-1")
        df = _parse_ff_csv(raw, ["Mkt-RF", "SMB", "HML", "RF"])
        # RF = 0.009 / 100 = 0.00009
        assert df["RF"].iloc[0] == pytest.approx(0.00009, abs=1e-10)

    def test_parse_index_is_datetime(self):
        from backend.services.fama_french import _parse_ff_csv
        raw = self._MINI_3F_CSV.encode("latin-1")
        df = _parse_ff_csv(raw, ["Mkt-RF", "SMB", "HML", "RF"])
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_parse_first_date(self):
        from backend.services.fama_french import _parse_ff_csv
        raw = self._MINI_3F_CSV.encode("latin-1")
        df = _parse_ff_csv(raw, ["Mkt-RF", "SMB", "HML", "RF"])
        assert df.index[0] == pd.Timestamp("1926-07-01")
