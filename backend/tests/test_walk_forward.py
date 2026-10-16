"""Phase 70 item 5: walk-forward picks parameters in-sample and reports out-of-sample only."""
import pandas as pd
import pytest

from backend.services import strategy_engine as se
from tests.test_strategy_engine import _store  # noqa: F401  (the stored universe fixture)

PICK = "def generate_weights(ctx):\n    return {ctx.params['pick']: 1.0}\n"
STRICT = ("def generate_weights(ctx):\n"
          "    px = ctx.prices()\n"
          "    assert px.index.max() == ctx.date, (px.index.max(), ctx.date)\n"
          "    return {ctx.params['pick']: 1.0}\n")


def _wf(source=PICK, **kw):
    kw.setdefault("grid", {"pick": ["S1", "UP", "S2"]})
    return se.walk_forward(source, start="2022-01-01", end="2024-12-31", train_years=1, test_years=1, **kw)


def test_only_test_windows_are_reported_and_they_join_without_gaps():
    res = _wf()
    assert res["outOfSampleOnly"] and [f["testStart"][:4] for f in res["folds"]] == ["2023", "2024"]
    dates = pd.DatetimeIndex([p["date"] for p in res["equityCurve"]])
    assert dates.min() >= pd.Timestamp("2023-01-01") and dates.is_monotonic_increasing and dates.is_unique
    expected = pd.bdate_range(dates.min(), "2024-12-31")
    assert len(dates) == len(expected)  # the 2023 fold holds its December positions into 2024's first rebalance
    assert all("trainMetrics" not in f for f in res["folds"])


def test_the_in_sample_winner_is_chosen_and_carried_out_of_sample():
    res = _wf()
    assert [f["params"] for f in res["folds"]] == [{"pick": "UP"}, {"pick": "UP"}]
    # UP compounds 0.1% a day: the stitched curve is that, less one entry cost per fold.
    n = len(res["equityCurve"])
    assert res["equityCurve"][-1]["value"] == pytest.approx((1 - 0.001) ** 2 * 1.001 ** (n - 1), rel=1e-6)


def test_rewound_train_windows_still_see_nothing_past_their_date():
    res = _wf(STRICT)
    assert res["available"]


def test_the_grid_is_capped():
    with pytest.raises(ValueError, match="at most"):
        _wf(grid={"a": list(range(6)), "b": list(range(6))})


def test_the_endpoint_runs_the_example_grid_in_the_sandbox(client):
    r = client.post("/api/research/strategies/walkforward", json={
        "strategyId": "example:example_momentum", "start": "2022-01-01", "end": "2024-12-31",
        "trainYears": 1, "testYears": 1, "params": {}, "grid": {"top_n": [1, 2], "lookback": [21, 63]}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sandbox"]["mode"] == "subprocess" and len(body["folds"]) == 2
    assert body["settings"]["combinations"] == 4 and body["externalRequestsDuringRun"] == 0
