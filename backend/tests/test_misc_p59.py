"""Phase 59 (Misc): analyst surprise units, Fama-French asOf, short-interest universe label."""
from __future__ import annotations

import asyncio

import pandas as pd


class _T:
    def __init__(self, ed):
        self.earnings_dates = ed
        self.info = {}

    def get_info(self):
        return {}


class _YF:
    def __init__(self, t):
        self._t = t

    def Ticker(self, s):  # noqa: N802
        return self._t


def _surp(monkeypatch, df):
    import backend.services.analyst_service as svc
    from backend.cache import _caches
    monkeypatch.setattr(svc, "yf", _YF(_T(df)))
    _caches.pop("analyst", None)
    return svc.analyst_data("ZZZ")["earningsSurprises"]


def test_surprise_fallback_is_percent(monkeypatch):
    # actual 1.10, estimate 1.00 -> (1.10 - 1.00) / 1.00 * 100 = 10.0 (no Surprise column)
    df = pd.DataFrame({"EPS Estimate": [1.00], "Reported EPS": [1.10]},
                      index=pd.to_datetime(["2026-07-30"]))
    assert abs(_surp(monkeypatch, df)[0]["surprisePct"] - 10.0) < 1e-6


def test_surprise_primary_path_is_percent_unchanged(monkeypatch):
    df = pd.DataFrame({"EPS Estimate": [1.00], "Reported EPS": [1.10], "Surprise(%)": [10.0]},
                      index=pd.to_datetime(["2026-07-30"]))
    assert abs(_surp(monkeypatch, df)[0]["surprisePct"] - 10.0) < 1e-6


def test_ff_asof_is_last_factor_date(monkeypatch):
    import numpy as np
    import yfinance as yf
    import backend.services.fama_french as ff
    idx = pd.bdate_range("2026-05-01", "2026-08-31")
    rng = np.random.default_rng(1)
    f = pd.DataFrame({c: rng.normal(0, 0.01, len(idx)) for c in ["Mkt-RF", "SMB", "HML"]}, index=idx)
    f["RF"] = 0.0001
    monkeypatch.setattr(ff, "load_ff_factors", lambda model="3": f)
    # prices extend past the factor data (to "today"); asOf must stay at the last aligned factor date
    pidx = pd.bdate_range("2026-05-01", "2026-10-02")
    prices = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, len(pidx))), index=pidx)
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame({"Close": prices.values}, index=prices.index))
    r = ff.factor_regression("FAKE", model="3", period="1y")
    assert "error" not in r
    assert r["asOf"] == "2026-08-31"


def test_short_interest_universe_labelled_honestly(monkeypatch):
    import backend.services.short_interest_service as si
    from backend.cache import _caches
    _caches.pop("short_interest", None)
    monkeypatch.setattr(si, "_fetch_yf_short",
                        lambda t: {"shortPercent": 1.0, "daysToCover": 1.0, "settlementDate": "2026-09-15"})
    r = asyncio.run(si.get_short_interest(universe="sp500"))
    assert r["universeCount"] == len(si._DEFAULT_UNIVERSE) == len(r["items"])
    assert "sample" in r["universe"].lower() and str(r["universeCount"]) in r["universe"]
