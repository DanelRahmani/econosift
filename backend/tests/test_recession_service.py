"""Tests for recession_service (12-month-ahead yield-curve probit) — Phase 38c."""
import pandas as pd

from backend.services.recession_service import _compute_recession, _fit_probit


def test_fit_probit_negative_beta_on_separable_data():
    # Lower spread -> recession (y=1); higher spread -> no recession (y=0),
    # with two overlap points near the boundary so the data is not perfectly
    # separable (avoids quasi-complete-separation non-convergence).
    xs = [round(-5.0 + 0.4 * i, 2) for i in range(26)]  # -5.0 .. 5.0
    ys = [1 if x < -0.2 else 0 for x in xs]
    ys[xs.index(-0.6)] = 0
    ys[xs.index(0.2)] = 1

    alpha, beta = _fit_probit(xs, ys)

    assert alpha is not None and beta is not None
    assert beta < 0

    from scipy.stats import norm
    p_low = norm.cdf(alpha + beta * -5.0)
    p_high = norm.cdf(alpha + beta * 5.0)
    assert p_low > p_high


def test_fit_probit_returns_none_on_too_few_obs():
    assert _fit_probit([1.0, -1.0], [0, 1]) == (None, None)


def test_fit_probit_returns_none_on_all_zero_y():
    xs = [float(i) for i in range(30)]
    ys = [0] * 30
    assert _fit_probit(xs, ys) == (None, None)


def _dates(n: int) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range("2015-01-01", periods=n, freq="MS")]


def _month_strs(n: int) -> list[str]:
    return [d.strftime("%Y-%m") for d in pd.date_range("2015-01-01", periods=n, freq="MS")]


def _synthetic_data(usrec_values: list[int]) -> dict:
    """60 months: spread +1.5 for months 0-39, -1.5 for months 40-59."""
    n = 60
    dates = _dates(n)
    spread = [1.5 if i < 40 else -1.5 for i in range(n)]
    return {
        "T10Y3M": [{"date": dates[i], "value": spread[i]} for i in range(n)],
        "USREC": [{"date": dates[i], "value": usrec_values[i]} for i in range(n)],
        "RECPROUSM156N": [{"date": dates[i], "value": 5.0} for i in range(n)],
        "SAHMREALTIME": [{"date": dates[i], "value": 0.1} for i in range(n)],
    }


def test_compute_recession_synthetic():
    n = 60
    # Recession (y=1 target) at months 51-57 (0-based); with a 12-month lead
    # this is driven mostly by the deeply negative spread at months 39-45.
    # Month 39 (still in the positive-spread era) is included so neither
    # spread level has a 0%/100% empirical recession rate (avoids
    # quasi-complete separation in the probit fit).
    usrec = [1 if 51 <= i <= 57 else 0 for i in range(n)]
    data = _synthetic_data(usrec)

    out = _compute_recession(data)

    assert set(out.keys()) == {"asOf", "kpis", "history", "recessions", "model"}
    assert 0.0 <= out["kpis"]["prob12m"] <= 100.0
    assert out["kpis"]["monthsInverted"] == 20
    assert out["kpis"]["sahm"] == 0.1
    assert out["kpis"]["smoothedProb"] == 5.0
    assert out["kpis"]["spreadPct"] == -1.5

    # 48 training months (t=0..47) have a defined target (t+12 <= 59)
    assert out["model"]["nObs"] == 48
    assert out["model"]["alpha"] is not None
    assert out["model"]["beta"] < 0

    months = _month_strs(n)
    assert out["recessions"] == [{"start": months[51], "end": months[57]}]
    assert len(out["history"]["probability"]) == 60
    assert len(out["history"]["spread"]) == 60


def test_compute_recession_ongoing_episode_at_tail():
    n = 60
    usrec = [1 if i >= 55 else 0 for i in range(n)]
    data = _synthetic_data(usrec)

    out = _compute_recession(data)

    months = _month_strs(n)
    assert out["recessions"] == [{"start": months[55], "end": months[59]}]


def test_compute_recession_empty_dict_returns_empty():
    assert _compute_recession({}) == {}


def test_compute_recession_missing_spread_returns_empty():
    data = {"T10Y3M": [], "USREC": [{"date": "2020-01-01", "value": 1}]}
    assert _compute_recession(data) == {}


def test_compute_recession_all_zero_usrec_model_none_but_history_present():
    n = 60
    data = _synthetic_data([0] * n)

    out = _compute_recession(data)

    assert out != {}
    assert out["model"]["alpha"] is None
    assert out["model"]["beta"] is None
    assert out["model"]["nObs"] == 48
    assert out["kpis"]["prob12m"] is None
    assert out["history"]["probability"] == []
    assert len(out["history"]["spread"]) == 60
    assert out["recessions"] == []
