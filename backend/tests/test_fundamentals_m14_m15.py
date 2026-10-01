"""Audit M-14 (Beneish from the statement history), M-15 (Ohlson SIZE in USD), M-23 (Piotroski bands, bank CCC)."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.services import dcf_engine, fundamentals


def _df(rows: dict) -> pd.DataFrame:
    """rows: {line item: (this year, prior year)}; columns newest first like yfinance."""
    cols = [pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")]
    return pd.DataFrame({c: [v[i] for v in rows.values()] for i, c in enumerate(cols)}, index=list(rows))


def _beneish_bundle(ni=200.0, ocf=200.0, industry="Software - Application"):
    # Both years identical -> every index DSRI/GMI/AQI/SGI/DEPI/SGAI/LVGI = 1.
    fin = _df({"Total Revenue": (1000, 1000), "Cost Of Revenue": (600, 600), "Net Income": (ni, ni),
               "Selling General And Administration": (100, 100)})
    bs = _df({"Accounts Receivable": (100, 100), "Current Assets": (400, 400), "Net PPE": (300, 300),
              "Total Assets": (1000, 1000), "Current Liabilities": (200, 200),
              "Total Liabilities Net Minority Interest": (500, 500)})
    cf = _df({"Operating Cash Flow": (ocf, ocf), "Depreciation And Amortization": (50, 50)})
    return {"ticker": "T", "info": {"industry": industry}, "financials_df": fin,
            "balance_sheet_df": bs, "cashflow_df": cf}


def test_beneish_known_value_neutral_indexes():
    # TATA = (200 - 200) / 1000 = 0, all other indexes 1:
    # M = -4.84 + .920 + .528 + .404 + .892 + .115 - .172 + 4.679*0 - .327 = -2.48
    r = fundamentals.beneish_m(_beneish_bundle())
    assert r["mScore"] == pytest.approx(-2.48, abs=1e-4)
    assert r["manipulationLikely"] is False and "note" not in r


def test_beneish_with_accruals_flags_manipulation():
    # TATA = (200 - 100) / 1000 = 0.1 -> M = -2.48 + 4.679 * 0.1 = -2.0121 > -2.22
    r = fundamentals.beneish_m(_beneish_bundle(ocf=100.0))
    assert r["mScore"] == pytest.approx(-2.0121, abs=1e-4)
    assert r["manipulationLikely"] is True


def test_beneish_without_history_is_null_with_note():
    b = {"info": {}, "financials": {"Total Revenue": 1.0}}   # no *_df statements
    r = fundamentals.beneish_m(b)
    assert r["mScore"] is None and len(r["note"]) > 10


def test_beneish_not_computed_for_banks():
    r = fundamentals.beneish_m(_beneish_bundle(industry="Banks - Diversified"))
    assert r["mScore"] is None and "bank" in r["note"].lower()


# ── M-15 Ohlson SIZE in USD ──

def _ohlson_bundle(ccy: str) -> dict:
    return {"info": {"currency": ccy, "financialCurrency": ccy},
            "financials": {"Net Income": 0.0},
            "balance_sheet": {"Total Assets": 66_000_000_000.0 * 100, "Total Liabilities Net Minority Interest": 0.0},
            "cashflow": {}}


def test_ohlson_size_converts_statement_currency_to_usd(monkeypatch):
    # index 660 -> SIZE = ln(TA_usd[$mn] / 6.6). JPY assets 6.6e12 at 0.01 USD/JPY = $66bn
    # -> ln(66_000 / 6.6) = ln(10_000); same assets read as USD would give ln(10_000 * 100).
    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 660.0)
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: 0.01 if (a, b) == ("JPY", "USD") else None)
    jpy = fundamentals.ohlson_o(_ohlson_bundle("JPY"))
    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 660.0)
    usd = fundamentals.ohlson_o(_ohlson_bundle("USD"))
    # identical ratios, only SIZE differs: ln(10_000 * 100) - ln(10_000) = ln(100)
    assert jpy["oScore"] - usd["oScore"] == pytest.approx(0.407 * math.log(100), abs=1e-6)


def test_ohlson_without_fx_rate_is_null_with_reason(monkeypatch):
    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 660.0)
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: None)
    r = fundamentals.ohlson_o(_ohlson_bundle("JPY"))
    assert r["oScore"] is None and r["probDefault"] is None and "JPY" in r["reason"]


# ── M-23 ──

def _pio(score, max_score):
    crit = {f"c{i}": (i < score) for i in range(max_score)}
    return crit


def test_piotroski_interpretation_scales_to_max_score(monkeypatch):
    base = {"info": {}, "financials": {"Net Income": 1.0}, "balance_sheet": {}, "cashflow": {}}
    # 7 evaluated tests: 6/7 = .857 >= 7/9 Strong; 5/7 = .714 Average; 3/7 = .429 < 4/9 Weak.
    assert fundamentals._piotroski_band(6, 7) == "Strong"
    assert fundamentals._piotroski_band(5, 7) == "Average"
    assert fundamentals._piotroski_band(3, 7) == "Weak"
    assert fundamentals._piotroski_band(0, 0) == "Insufficient data"
    assert "interpretation" in fundamentals.piotroski_f(base)


def test_bank_cash_conversion_cycle_is_null_with_reason():
    bundle = {"info": {"industry": "Banks - Diversified"}, "financials": {"Total Revenue": 1000.0},
              "balance_sheet": {"Accounts Receivable": 600.0}, "cashflow": {}}
    r = fundamentals.cash_conversion_cycle(bundle)
    assert r["dso"] is None and r["ccc"] is None
    assert "bank" in r["unavailable"]["dso"].lower() and "bank" in r["unavailable"]["ccc"].lower()


def test_non_bank_cash_conversion_cycle_has_no_unavailable():
    bundle = {"info": {"industry": "Software - Application"}, "financials": {"Total Revenue": 1000.0},
              "balance_sheet": {"Accounts Receivable": 100.0}, "cashflow": {}}
    r = fundamentals.cash_conversion_cycle(bundle)
    assert r["dso"] == pytest.approx(36.5) and "unavailable" not in r


# ── verifier follow-ups ──

def test_beneish_uses_quarterly_prior_year_when_one_annual_column():
    # One annual column (2024) only; the prior year comes from the quarterly frames dated a year
    # earlier, as on /corporate/health. Identical years -> every index 1 -> same M as the 2-year case.
    two_year = fundamentals.beneish_m(_beneish_bundle())
    b = _beneish_bundle()
    q_cols = [pd.Timestamp("2024-12-31"), pd.Timestamp("2024-09-30"), pd.Timestamp("2024-06-30"),
              pd.Timestamp("2024-03-31"), pd.Timestamp("2023-12-31"), pd.Timestamp("2023-09-30"),
              pd.Timestamp("2023-06-30"), pd.Timestamp("2023-03-31")]
    for key in ("financials_df", "balance_sheet_df", "cashflow_df"):
        annual = b[key]
        flow = key != "balance_sheet_df"
        # flows: four quarters sum to the annual figure; stocks: the quarter-end balance.
        q = pd.DataFrame({c: annual.iloc[:, 0] / (4 if flow else 1) for c in q_cols})
        b[key.replace("_df", "_q_df")] = q
        b[key] = annual.iloc[:, :1]
    assert fundamentals.beneish_m(b)["mScore"] == pytest.approx(two_year["mScore"], abs=1e-9)


def test_ohlson_converted_bundle_with_failed_fx_keeps_source_currency(monkeypatch):
    # to_price_currency could not find a JPY->USD rate: _fx = {from: JPY, to: USD, rate: None} and the
    # statements are still JPY. They must not be read as USD (SIZE 100x too large): null + reason.
    monkeypatch.setattr(fundamentals, "_gnp_price_index", lambda: 660.0)
    monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: None)
    b = _ohlson_bundle("JPY")
    b["info"]["currency"] = "USD"
    b["_fx"] = {"from": "JPY", "to": "USD", "rate": None}
    r = fundamentals.ohlson_o(b)
    assert r["oScore"] is None and "JPY" in r["reason"]
