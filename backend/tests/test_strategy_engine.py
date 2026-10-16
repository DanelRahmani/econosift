"""Phase 70 item 3: strategy plugins — weights in, equity curve, costs and a reproducible record out."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend import store
from backend.services import strategy_engine as se

TABLES = ("index_membership", "price_daily", "corporate_action", "fetch_queue", "fundamental")
DAYS = pd.bdate_range("2022-01-03", "2024-12-31")
EXAMPLE = (Path(se.__file__).parents[1] / "strategies" / "example_momentum.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _store():
    def wipe():
        with store.connect() as conn:
            for t in TABLES:
                conn.execute(f"DELETE FROM {t}")
    store.init_schema()
    wipe()
    rng = np.random.default_rng(3)
    store.upsert("index_membership", [dict(index_name="sp500", symbol=f"S{i}", start="", end=None) for i in range(6)]
                 + [dict(index_name="sp500", symbol="UP", start="", end=None)], ("index_name", "symbol", "start"))
    bars = []
    for sym in [f"S{i}" for i in range(6)] + ["UP"]:
        # UP rises exactly 0.1% a day; the others are noise around flat.
        px = 100 * (1.001 ** np.arange(len(DAYS)) if sym == "UP"
                    else np.cumprod(1 + rng.normal(0, 0.01, len(DAYS))))
        bars += [dict(symbol=sym, date=d.date().isoformat(), open=p, high=p, low=p, close=p, adj_close=p, volume=1.0)
                 for d, p in zip(DAYS, px)]
    store.upsert("price_daily", bars, ("symbol", "date"))
    yield
    wipe()


def _run(source, **kw):
    return se.backtest(source, start="2023-01-01", end="2024-12-31", **kw)


def test_buy_and_hold_compounds_exactly_and_charges_costs_once():
    res = _run("def generate_weights(ctx):\n    return {'UP': 1.0}\n", cost_bps=50.0)
    eq = pd.Series({p["date"]: p["value"] for p in res["equityCurve"]})
    days = pd.bdate_range("2023-01-31", "2024-12-31")  # first month-end rebalance to the end
    assert eq.iloc[-1] == pytest.approx((1 - 0.005) * 1.001 ** (len(days) - 1), rel=1e-6)
    m = res["metrics"]
    assert m["totalCost"] == pytest.approx(0.005) and m["avgTurnover"] == pytest.approx(0.5 / m["rebalances"], abs=1e-4)
    assert m["maxDrawdown"] == pytest.approx(-0.005, abs=1e-6) and m["sharpe"] > 10
    assert res["drawdown"][-1]["value"] == pytest.approx(0.0)


def test_cash_and_a_short_position_are_valued_correctly():
    res = _run("def generate_weights(ctx):\n    return {'UP': -0.5}\n", cost_bps=0.0)
    final = res["equityCurve"][-1]["value"]
    # Rebalanced monthly back to -50%: each month earns 1.5 - 0.5 * 1.001**n per unit.
    assert final < 1.0 and res["metrics"]["avgTurnover"] > 0


def test_the_example_strategy_runs_and_the_record_makes_it_reproducible():
    a = _run(EXAMPLE, params={"top_n": 2, "lookback": 63})
    b = _run(EXAMPLE, params={"top_n": 2, "lookback": 63})
    assert a["equityCurve"] == b["equityCurve"] and a["strategy"]["sha256"] == b["strategy"]["sha256"]
    assert a["snapshot"]["priceMaxDate"] == "2024-12-31" and a["snapshot"]["priceRows"] > 0
    assert a["settings"]["params"] == {"top_n": 2, "lookback": 63} and a["metrics"]["rebalances"] == 24
    assert all(r["positions"] == 2 for r in a["rebalanceLog"])


@pytest.mark.parametrize("body, message", [
    ("return {'NOPE': 1.0}", "not an index member"),
    ("return {'UP': float('nan')}", "not finite"),
    ("return {'UP': 2.0, 'S1': -2.0}", "gross exposure"),
    ("return [('UP', 1.0)]", "must return a dict"),
])
def test_a_bad_answer_is_rejected_with_the_date(body, message):
    with pytest.raises(se.StrategyError, match=message):
        _run(f"def generate_weights(ctx):\n    {body}\n")


def test_a_file_without_generate_weights_or_with_a_syntax_error_is_refused_before_running():
    with pytest.raises(se.StrategyError, match="generate_weights"):
        se.check_source("def weights(ctx):\n    return {}\n")
    with pytest.raises(se.StrategyError, match="syntax error on line 1"):
        se.check_source("def generate_weights(ctx) return {}\n")


def test_asking_for_a_future_bar_gets_nothing_past_the_date():
    source = (
        "def generate_weights(ctx):\n"
        "    px = ctx.prices()\n"
        "    assert px.index.max() == ctx.date, (px.index.max(), ctx.date)\n"
        "    assert ctx._panel.asof == ctx.date\n"
        "    return {}\n")
    res = _run(source)
    assert res["metrics"]["totalReturn"] == 0.0
