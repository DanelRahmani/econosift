"""Tests for country_risk_service — Phase 16."""
from backend.services.country_risk_service import _signal


def test_signal_debt_gdp():
    assert _signal("debt_gdp", 50)  == "green"
    assert _signal("debt_gdp", 75)  == "yellow"
    assert _signal("debt_gdp", 100) == "red"
    assert _signal("debt_gdp", None) is None


def test_signal_inflation():
    assert _signal("inflation", 3)  == "green"
    assert _signal("inflation", 6)  == "yellow"
    assert _signal("inflation", 10) == "red"


def test_signal_fiscal_balance():
    assert _signal("fiscal_balance", -1) == "green"
    assert _signal("fiscal_balance", -4) == "yellow"
    assert _signal("fiscal_balance", -8) == "red"


def test_signal_unemployment():
    assert _signal("unemployment", 4) == "green"
    assert _signal("unemployment", 6) == "yellow"
    assert _signal("unemployment", 9) == "red"


def test_signal_current_account():
    assert _signal("current_account",  0) == "green"
    assert _signal("current_account", -3) == "yellow"
    assert _signal("current_account", -6) == "red"


def test_signal_reserves_growth():
    assert _signal("reserves_growth", 10) == "green"
    assert _signal("reserves_growth",  2) == "yellow"
    assert _signal("reserves_growth", -1) == "red"
