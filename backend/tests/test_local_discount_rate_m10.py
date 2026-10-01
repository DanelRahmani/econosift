"""Offline known-value tests for Markets audit M-10 (owner decision: option B + Blume interim).

Non-US listings priced in a non-USD currency are discounted in that currency: the local 10-year
government yield (FRED/OECD IRLTLT01xxM156N, monthly), a beta against the local index,
Blume-adjusted (0.67*b + 0.33), and the Damodaran country ERP. USD-priced listings keep the US
10-year (DGS10) and the raw beta. When no local rate exists the rate is None with a reason; the US
rate is never substituted.
"""
from __future__ import annotations

import pytest

# Live ASML.AS before the fix (audit M-10): rf 5.26 % (US DGS10), beta 2.235 vs ^AEX, ERP 4.23 % (NL)
# -> ke = 0.0526 + 2.235 * 0.0423 = 0.147141 (14.72 %).
US_10Y = 0.0526
NL_10Y = 0.03285          # IRLTLT01NLM156N, 2026-08-01 observation (3.285 %)
NL_ERP = 4.23             # percent, Damodaran
US_ERP = 4.33
ASML_BETA = 2.235

_ERP_TABLE = {
    "asOf": "2026-01-05",
    "matureMarketERP": US_ERP,
    "countries": {
        "Netherlands": {"erp": NL_ERP, "taxRate": 25.8},
        "United States": {"erp": US_ERP, "taxRate": 25.0},
        "United Kingdom": {"erp": 5.0, "taxRate": 25.0},
        "Hong Kong": {"erp": 5.0, "taxRate": 16.5},
        "Norway": {"erp": 4.33, "taxRate": 22.0},
        "Switzerland": {"erp": 4.33, "taxRate": 19.6},
    },
}


@pytest.fixture
def dr(monkeypatch):
    from backend.services import discount_rates
    monkeypatch.setattr(discount_rates, "load_erp", lambda: _ERP_TABLE)
    monkeypatch.setattr(discount_rates, "_risk_free_rate_live", lambda: US_10Y)
    local = {"IRLTLT01NLM156N": {"value": NL_10Y, "asOf": "2026-08-01"},
             "IRLTLT01GBM156N": {"value": 0.049886, "asOf": "2026-08-01"},
             "IRLTLT01NOM156N": {"value": 0.0428635, "asOf": "2026-08-01"}}
    monkeypatch.setattr(discount_rates, "_local_risk_free_live", lambda sid: local.get(sid))
    return discount_rates


def _bundle(ticker: str, currency: str, exchange: str, country: str | None = None) -> dict:
    # No debt, so WACC = ke and the test isolates the cost of equity.
    info = {"currency": currency, "exchange": exchange, "marketCap": 1.0e11, "totalDebt": 0,
            "effectiveTaxRate": 0.2}
    if country:
        info["country"] = country
    return {"ticker": ticker, "info": info, "financials": {}, "balance_sheet": {}}


def test_blume_adjustment_known_value(dr):
    # 0.67 * 2.235 + 0.33 = 1.49745 + 0.33 = 1.82745
    assert dr.blume_adjust(ASML_BETA) == pytest.approx(1.82745, abs=1e-9)
    assert dr.blume_adjust(None) is None


def test_asml_uses_local_rf_blume_beta_and_country_erp(dr):
    w = dr.wacc(_bundle("ASML.AS", "EUR", "AMS"), ASML_BETA)
    # ke = 0.03285 + 1.82745 * 0.0423 = 0.03285 + 0.077301135 = 0.110151135 (was 0.147141)
    assert w["country"] == "Netherlands"
    assert w["riskFree"] == pytest.approx(NL_10Y)
    assert w["riskFreeSource"] == "FRED IRLTLT01NLM156N"
    assert w["riskFreeAsOf"] == "2026-08-01"
    assert w["rawBeta"] == pytest.approx(ASML_BETA)
    assert w["beta"] == pytest.approx(1.82745)
    assert w["betaAdjustment"] == "Blume"
    assert w["erp"] == pytest.approx(0.0423)
    assert w["costOfEquity"] == pytest.approx(0.110151135, abs=1e-9)
    assert w["wacc"] == pytest.approx(0.110151135, abs=1e-9)


def test_us_listing_unchanged(dr):
    w = dr.wacc(_bundle("AAPL", "USD", "NMS"), 1.2)
    # ke = 0.0526 + 1.2 * 0.0433 = 0.10456; raw beta, US 10-year
    assert w["riskFree"] == pytest.approx(US_10Y)
    assert w["riskFreeSource"] == "FRED DGS10"
    assert w["beta"] == pytest.approx(1.2) and w["betaAdjustment"] is None
    assert w["costOfEquity"] == pytest.approx(0.10456, abs=1e-9)


def test_usd_priced_foreign_listing_keeps_us_rate(dr):
    # A USD-priced OTC line of a Swiss company: the rate follows the price currency (USD).
    w = dr.wacc(_bundle("NSRGY", "USD", "PNK", country="Switzerland"), 0.8)
    assert w["riskFree"] == pytest.approx(US_10Y) and w["riskFreeSource"] == "FRED DGS10"
    assert w["beta"] == pytest.approx(0.8)


def test_no_local_series_is_null_with_reason_never_us(dr):
    # Hong Kong has no 10-year yield on FRED: no rate, no cost of equity, no WACC.
    w = dr.wacc(_bundle("0700.HK", "HKD", "HKG"), 1.1)
    assert w["riskFree"] is None
    assert w["costOfEquity"] is None and w["wacc"] is None
    assert "Hong Kong" in w["unavailable"]["riskFree"]
    assert "US" in w["unavailable"]["riskFree"]          # says the US rate is not substituted


def test_fred_unreachable_is_null_with_reason(dr, monkeypatch):
    monkeypatch.setattr(dr, "_local_risk_free_live", lambda sid: None)
    w = dr.wacc(_bundle("ASML.AS", "EUR", "AMS"), ASML_BETA)
    assert w["riskFree"] is None and w["wacc"] is None
    assert "IRLTLT01NLM156N" in w["unavailable"]["riskFree"]


def test_currency_not_the_countrys_is_null(dr):
    # A EUR-priced line on the London exchange: GBP gilts would discount EUR cash flows.
    w = dr.wacc(_bundle("XYZ.L", "EUR", "LSE"), 1.0)
    assert w["riskFree"] is None
    assert "EUR" in w["unavailable"]["riskFree"] and "GBP" in w["unavailable"]["riskFree"]


def test_pence_quote_matches_gbp(dr):
    w = dr.wacc(_bundle("SHEL.L", "GBp", "LSE"), 1.0)
    assert w["riskFree"] == pytest.approx(0.049886)
    assert w["riskFreeSource"] == "FRED IRLTLT01GBM156N"


def test_no_local_index_drops_the_sp500_beta(dr):
    # Oslo (.OL) has no mapped local index, so the 2-year beta was measured against the S&P 500:
    # it is not used; beta = 1 is assumed and said so. ke = 0.0428635 + 1 * 0.0433 = 0.0861635
    w = dr.wacc(_bundle("EQNR.OL", "NOK", "OSL", country="Norway"), 1.6)
    assert w["rawBeta"] is None and w["beta"] is None
    assert "local index" in w["unavailable"]["beta"]
    assert w["costOfEquity"] == pytest.approx(0.0861635, abs=1e-9)


def test_benchmark_suffixes():
    from backend.services.yfinance_service import benchmark_for
    assert benchmark_for("UCB.BR") == "^BFX"     # Brussels, not Brazil
    assert benchmark_for("PETR4.SA") == "^BVSP"  # Sao Paulo
    assert benchmark_for("ASML.AS") == "^AEX"


def test_valuation_models_lock_with_the_rate_reason(dr):
    from backend.services.valuation_engine import valuation_models
    b = _bundle("0700.HK", "HKD", "HKG")
    b["info"].update({"currentPrice": 500.0, "trailingEps": 20.0, "forwardEps": 22.0,
                      "sharesOutstanding": 2.0e8})
    out = valuation_models(b, 1.1)
    dcf = next(m for m in out["models"] if m["model"].startswith("DCF"))
    assert dcf["locked"] and "Hong Kong" in dcf["reason"]
