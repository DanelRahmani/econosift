"""Snowflake dividend-coverage units (audit C-03) and negative multiples (audit M-02)."""
import pytest
from backend.services.snowflake_service import _axis_value, _fcf_coverage_score


def test_coverage_mixes_percent_yield_with_fraction_fcf_yield():
    # KO-like: dividend yield 2.43 % (percent units), FCF yield 0.014 (fraction)
    # → coverage 0.014 / 0.0243 ≈ 0.58 → band (≥0.7 → 2.0, else 0.5).
    assert _fcf_coverage_score(2.43, 0.014) == 0.5
    # Covered 2.5x: FCF yield 6 % vs dividend 2.4 % → coverage 2.5 → 8.0.
    assert _fcf_coverage_score(2.4, 0.06) == 8.0
    # Covered 3x+ → top score.
    assert _fcf_coverage_score(1.0, 0.035) == 10.0


def _peers():
    return [
        {"pe": 10.0, "ev_ebitda": 5.0, "ev_fcf": -5.0, "fcf_yield": 0.05, "pb": 1.0},
        {"pe": 20.0, "ev_ebitda": 10.0, "ev_fcf": 10.0, "fcf_yield": 0.04, "pb": 2.0},
        {"pe": 30.0, "ev_ebitda": 15.0, "ev_fcf": 20.0, "fcf_yield": 0.03, "pb": 3.0},
        {"pe": 40.0, "ev_ebitda": 20.0, "ev_fcf": 30.0, "fcf_yield": 0.02, "pb": 4.0},
    ]


def _components(row):
    _, comps = _axis_value(row, _peers())
    return {c["label"]: c for c in comps}


def test_negative_ev_fcf_is_not_scored_as_best_value():
    # JPM: EV/FCF = -4.85 used to rank as the cheapest of all (9.2/10 inverted percentile).
    c = _components({"pe": 20.0, "ev_fcf": -4.85, "pb": 2.0})["EV/FCF"]
    assert c["score"] is None
    assert c["value"] == -4.85
    assert c["reason"] == "not meaningful: negative multiple"


def test_negative_multiples_are_excluded_from_the_axis_average():
    # Only P/E (weight .25) can be scored; EV/FCF -4.85 is dropped, not averaged in as a 10.
    # P/E 20 vs peers [10,20,30,40]: 1 peer strictly lower -> pct .25 -> inverted .75 -> 7.5.
    score, _ = _axis_value({"pe": 20.0, "ev_fcf": -4.85}, _peers())
    assert score == 7.5


def test_negative_peer_multiples_do_not_distort_a_positive_rank():
    # EV/FCF 15 vs positive peers [10, 20, 30]: 1 lower -> 1/3 -> inverted 2/3 -> 6.67.
    # (With the -5 peer counted as "lower" it used to be 2/4 -> 5.0.)
    c = _components({"ev_fcf": 15.0})["EV/FCF"]
    assert c["score"] == 6.67
    assert "reason" not in c


def test_negative_pe_and_pb_not_meaningful():
    comps = _components({"pe": -3.0, "pb": -1.2})
    assert comps["P/E"]["score"] is None and comps["P/E"]["reason"] == "not meaningful: negative multiple"
    assert comps["P/B"]["score"] is None and comps["P/B"]["reason"] == "not meaningful: negative multiple"


# ── Audit M-01: Snowflake fallback row (ticker outside the screener cache) ──

def test_fallback_value_inputs_rebuilt_for_adr(monkeypatch):
    """TSM/NVO are not in the screener universe, so their Value axis reads Ticker.info.
    USD-quoted ADR reporting in TWD, 1 TWD = 0.5 USD."""
    from backend.services import dcf_engine
    from backend.services.snowflake_service import _fallback_value_inputs
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: 0.5)
    info = {"currency": "USD", "financialCurrency": "TWD", "marketCap": 10_000.0,
            "ebitda": 600.0, "totalDebt": 1_000.0, "totalCash": 3_000.0,   # TWD
            "totalStockholderEquity": 4_000.0,                                # TWD
            "enterpriseToEbitda": 15.0, "priceToBook": 2.5}                   # Yahoo, mixed
    ev_ebitda, pb = _fallback_value_inputs(info)
    assert ev_ebitda == pytest.approx(30.0)   # EV 10_000 + (1_000 − 3_000)×0.5 = 9_000; / (600×0.5)
    assert pb == pytest.approx(5.0)           # 10_000 / (4_000 × 0.5)


def test_fallback_value_inputs_same_currency_pass_through():
    from backend.services.snowflake_service import _fallback_value_inputs
    info = {"currency": "USD", "financialCurrency": "USD", "enterpriseToEbitda": 15.0, "priceToBook": 2.5}
    assert _fallback_value_inputs(info) == (15.0, 2.5)
