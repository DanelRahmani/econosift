"""Offline known-value tests for Markets audit M-02 / M-03 / M-05 (no network)."""
from __future__ import annotations

import pytest

from tests.test_valuation_engine import _make_bundle, patch_network  # noqa: F401  (autouse fixture re-export)


@pytest.fixture(autouse=True)
def static_erp(monkeypatch):
    """Keep these tests offline: load_erp would otherwise try the live Damodaran download."""
    import json
    from backend.services import discount_rates
    path = discount_rates._data_path("damodaran_erp_2026.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(discount_rates, "load_erp", lambda: data)


def _bank_bundle(**kw):
    b = _make_bundle(ticker="JPM", sector="Financial Services", **kw)
    b["info"]["industry"] = "Banks - Diversified"
    return b


# ---------------------------------------------------------------------------
# M-02: DCF lock for banks / FCF <= 0, composite never negative
# ---------------------------------------------------------------------------

class TestDcfLockAndComposite:
    def test_bank_dcf_is_null_with_exact_reason(self):
        from backend.services.valuation_engine import valuation_models
        # JPM-like: negative free cash flow, price ~331.
        r = valuation_models(_bank_bundle(freeCashflow=-147_782_000_000, currentPrice=330.83), beta=1.0)
        dcf = r["models"][0]
        assert dcf["model"] == "DCF (Two-Stage)"
        assert dcf["value"] is None
        assert dcf["locked"] is True
        assert dcf["reason"] == "not meaningful for banks"
        assert dcf["detail"]["dcfResult"]["scenarios"] == []

    def test_negative_fcf_dcf_is_null_with_reason(self):
        from backend.services.valuation_engine import valuation_models
        r = valuation_models(_make_bundle(freeCashflow=-5_000_000_000), beta=1.0)
        dcf = r["models"][0]
        assert dcf["value"] is None
        assert dcf["reason"] == "not meaningful: free cash flow ≤ 0"

    def test_bank_composite_is_never_negative(self):
        from backend.services.valuation_engine import valuation_models
        r = valuation_models(_bank_bundle(freeCashflow=-147_782_000_000, currentPrice=330.83), beta=1.0)
        comp = r["axiomFairValue"]
        assert comp["value"] is None or comp["value"] > 0
        assert "DCF (Two-Stage)" not in comp["weightsUsed"]

    def test_bank_epv_is_locked_and_out_of_composite(self):
        # EPV subtracts net debt; a bank's debt and cash are deposits/reserves, so it is not meaningful.
        from backend.services.valuation_engine import valuation_models
        bundle = _bank_bundle(freeCashflow=-147_782_000_000, currentPrice=330.83)
        bundle["info"]["ebit"] = 60_000_000_000   # EBIT present, so only the bank rule can lock EPV
        r = valuation_models(bundle, beta=1.0)
        by_name = {m["model"]: m for m in r["models"]}
        epv = by_name["EPV (Earnings Power Value)"]
        assert (epv["value"], epv["locked"], epv["reason"]) == (None, True, "not meaningful for banks")
        weights = r["axiomFairValue"]["weightsUsed"]
        assert not {"EPV (Earnings Power Value)", "EV/EBITDA Comps", "DCF (Two-Stage)"} & set(weights)

    def test_composite_excludes_non_positive_values_and_renormalises(self):
        from backend.services.valuation_engine import _composite_fair_value
        models = [
            {"model": "DCF (Two-Stage)", "value": -100.0, "locked": False},     # weight .30, excluded
            {"model": "Graham Formula", "value": 100.0, "locked": False},       # weight .10
            {"model": "Peter Lynch / PEG", "value": 200.0, "locked": False},    # weight .05
            {"model": "EV/EBITDA Comps", "value": 0.0, "locked": False},        # excluded
        ]
        # Only Graham (.10) and Lynch (.05) remain: (100*.10 + 200*.05) / .15 = 20 / .15 = 133.3333
        c = _composite_fair_value(models, 100.0)
        assert c["value"] == pytest.approx(133.333333, rel=1e-6)
        assert set(c["weightsUsed"]) == {"Graham Formula", "Peter Lynch / PEG"}
        assert c["upsidePct"] == pytest.approx(0.333333, rel=1e-4)
        assert c["reason"] is None

    def test_composite_null_with_reason_when_nothing_positive(self):
        from backend.services.valuation_engine import _composite_fair_value
        c = _composite_fair_value([{"model": "DCF (Two-Stage)", "value": -5.0, "locked": False}], 100.0)
        assert c["value"] is None
        assert c["upsidePct"] is None
        assert c["verdict"] == "Insufficient Data"
        assert c["reason"] == "no model produced a positive value"

    def test_composite_null_with_reason_when_no_models(self):
        from backend.services.valuation_engine import _composite_fair_value
        c = _composite_fair_value([], 100.0)
        assert c["value"] is None
        assert c["reason"] == "no model produced a positive value"


# ---------------------------------------------------------------------------
# M-03: DDM growth is sustainable dividend growth, never earnings growth
# ---------------------------------------------------------------------------

class TestDdmSustainableGrowth:
    def _ddm(self, **kw):
        from backend.services.valuation_engine import valuation_models
        growth = kw.pop("growth", 0.10)
        r = valuation_models(_make_bundle(**kw), beta=1.1, growth=growth)
        return r, r["models"][1]

    def test_growth_is_retention_times_roe_when_below_cap(self):
        # payout 0.50, ROE 0.06 -> g = (1 - 0.50) * 0.06 = 0.03 (< rf).  Earnings growth (10%) is ignored.
        r, ddm = self._ddm(dividendRate=2.0, payoutRatio=0.5, returnOnEquity=0.06, growth=0.10)
        ke = r["wacc"]["costOfEquity"]
        assert ddm["detail"]["growthRate"] == pytest.approx(0.03)
        # dividendRate is already the forward dividend (D1): value = 2.0 / (ke - 0.03)
        assert ddm["value"] == pytest.approx(2.0 / (ke - 0.03), rel=1e-9)

    def test_growth_capped_at_risk_free_rate(self):
        # MSFT-like: payout 23%, ROE 33% (normalised to 25%) -> 0.77 * 0.25 = 19.25% -> capped at rf.
        r, ddm = self._ddm(dividendRate=3.92, payoutRatio=0.23, returnOnEquity=0.33, growth=0.10)
        rf, ke = r["wacc"]["riskFree"], r["wacc"]["costOfEquity"]
        assert ddm["detail"]["growthRate"] == pytest.approx(rf)
        assert ddm["value"] == pytest.approx(3.92 / (ke - rf), rel=1e-9)

    def test_earnings_growth_does_not_drive_ddm(self):
        _, low = self._ddm(dividendRate=2.0, payoutRatio=0.5, returnOnEquity=0.06, growth=0.02)
        _, high = self._ddm(dividendRate=2.0, payoutRatio=0.5, returnOnEquity=0.06, growth=0.15)
        assert low["value"] == pytest.approx(high["value"])

    def test_locked_when_roe_missing(self):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(dividendRate=2.0)
        b["info"].pop("returnOnEquity")
        ddm = valuation_models(b, beta=1.1)["models"][1]
        assert ddm["value"] is None and ddm["locked"] is True
        assert ddm["reason"] == "Sustainable dividend growth unavailable (ROE or payout ratio missing)"


# ---------------------------------------------------------------------------
# M-05: RIM with normalised, fading ROE and buyback-aware retention
# ---------------------------------------------------------------------------

class TestRimNormalised:
    def test_rim_value_hand_computed(self):
        from backend.services.valuation_engine import _rim_value
        # bvps 10, ROE0 20%, ke 10%, retention 50%, 5 years; ROE_t = ke + (ROE0 - ke)(1 - t/5):
        #   t=1 ROE .18  RI = .08*10       = .8        PV = .8/1.1       = 0.727273  book1 = 10*(1+.5*.18)    = 10.9
        #   t=2 ROE .16  RI = .06*10.9     = .654      PV = .654/1.21    = 0.540496  book2 = 10.9*1.08        = 11.772
        #   t=3 ROE .14  RI = .04*11.772   = .47088    PV = .47088/1.331 = 0.353777  book3 = 11.772*1.07      = 12.59604
        #   t=4 ROE .12  RI = .02*12.59604 = .2519208  PV = /1.4641      = 0.172062  book4 = 12.59604*1.06    = 13.351802
        #   t=5 ROE .10  RI = 0
        # value = 10 + 0.727273 + 0.540496 + 0.353777 + 0.172062 = 11.793608
        value, pv_ri = _rim_value(10.0, 0.20, 0.10, 0.5, 5)
        assert value == pytest.approx(11.793608, abs=1e-5)
        assert pv_ri == pytest.approx(1.793608, abs=1e-5)

    @staticmethod
    def _aapl_like(roe):
        from backend.services.valuation_engine import valuation_models
        # AAPL: bvps 7.36, dividend payout 12.04%, buybacks 90.711bn / net income 112.01bn = 80.98%.
        b = _make_bundle(ticker="AAPL", bookValue=7.36, returnOnEquity=roe, payoutRatio=0.1204,
                         currentPrice=333.0)
        b["financials"] = {"Net Income": 112_010_000_000.0}
        b["cashflow"] = {"Repurchase Of Capital Stock": -90_711_000_000.0}
        r = valuation_models(b, beta=1.0)
        return next(m for m in r["models"] if m["model"] == "Residual Income (RIM)")

    def test_rim_locked_when_roe_above_100_percent(self):
        rim = self._aapl_like(1.4875101)  # AAPL TTM ROE 148.75%
        assert rim["value"] is None
        assert rim["locked"] is True
        assert rim["reason"] == "not meaningful: ROE above 100% on a buyback-shrunk book"
        assert rim["detail"]["roeRaw"] == pytest.approx(1.4875101)

    def test_rim_not_locked_at_exactly_100_percent(self):
        assert self._aapl_like(1.0)["value"] is not None

    def test_high_roe_is_capped_and_retention_includes_buybacks(self):
        rim = self._aapl_like(0.60)
        d = rim["detail"]
        assert d["roeRaw"] == pytest.approx(0.60)
        assert d["roe"] == pytest.approx(0.25)  # capped
        # retention = 1 - 0.1204 - 90.711/112.01 = 1 - 0.1204 - 0.80983 = 0.06977
        assert d["retentionRate"] == pytest.approx(1 - 0.1204 - 90.711 / 112.01, abs=1e-6)
        # ROE <= 25% on a 7.36 book can add only a few dollars.
        assert rim["value"] is not None and rim["value"] < 15.0

    def test_retention_without_buyback_data_is_one_minus_payout(self):
        from backend.services.valuation_engine import valuation_models
        r = valuation_models(_make_bundle(payoutRatio=0.15, returnOnEquity=0.20), beta=1.0)
        rim = next(m for m in r["models"] if m["model"] == "Residual Income (RIM)")
        assert rim["detail"]["retentionRate"] == pytest.approx(0.85)
        assert rim["detail"]["roe"] == pytest.approx(0.20)  # below the cap: unchanged


# ---------------------------------------------------------------------------
# M-01b: ADR book value per share from converted equity, not mixed-currency priceToBook
# ---------------------------------------------------------------------------

class TestAdrBookValue:
    @staticmethod
    def _adr(**info_over):
        info = {"currency": "USD", "financialCurrency": "TWD", "currentPrice": 400.0, "marketCap": 2.0e12,
                "priceToBook": 93.8,  # Yahoo mixes USD price with TWD book: not usable
                "bookValue": 4.863, "freeCashflow": 1.0e12}
        info.update(info_over)
        return {"ticker": "TSM", "info": info, "financials": {},
                "balance_sheet": {"Stockholders Equity": 6.0e12, "Share Issued": 2.59e10}, "cashflow": {}}

    def test_bvps_from_converted_equity(self, monkeypatch):
        from backend.services import dcf_engine
        monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: 0.03)
        out = dcf_engine.to_price_currency(self._adr())
        # equity USD = 6.0e12 TWD * 0.03 = 1.8e11; ADR-equivalent shares = marketCap / price = 2.0e12 / 400 = 5.0e9
        # bvps = 1.8e11 / 5.0e9 = 36.0   (price / priceToBook would give 400 / 93.8 = 4.26)
        assert out["info"]["bookValue"] == pytest.approx(36.0)

    def test_bvps_none_when_equity_missing(self, monkeypatch):
        from backend.services import dcf_engine
        monkeypatch.setattr(dcf_engine, "_fx_rate", lambda a, b: 0.03)
        b = self._adr()
        b["balance_sheet"] = {}
        assert dcf_engine.to_price_currency(b)["info"]["bookValue"] is None

    def test_same_currency_book_value_untouched(self):
        from backend.services import dcf_engine
        b = self._adr(financialCurrency="USD")
        assert dcf_engine.to_price_currency(b)["info"]["bookValue"] == 4.863


# ---------------------------------------------------------------------------
# Generic guard: no unlocked model may show a non-positive per-share value
# ---------------------------------------------------------------------------

NON_POSITIVE = "not meaningful: value ≤ 0 after net debt"


class TestNonPositiveGuard:
    def test_guard_nulls_non_positive_and_keeps_specific_reasons(self):
        from backend.services.valuation_engine import _lock_non_positive
        models = [
            {"model": "EPV (Earnings Power Value)", "value": -12.5, "locked": False, "reason": None, "detail": {"x": 1}},
            {"model": "EV/EBITDA Comps", "value": 0.0, "locked": False, "reason": None, "detail": {}},
            {"model": "Graham Formula", "value": 50.0, "locked": False, "reason": None, "detail": {}},
            {"model": "DDM (Gordon Growth)", "value": None, "locked": True, "reason": "No dividend", "detail": {}},
        ]
        out = _lock_non_positive(models)
        assert out[0]["value"] is None and out[0]["locked"] is True and out[0]["reason"] == NON_POSITIVE
        assert out[0]["detail"] == {"x": 1}  # detail kept for the UI
        assert out[1]["value"] is None and out[1]["reason"] == NON_POSITIVE
        assert out[2]["value"] == 50.0 and out[2]["locked"] is False
        assert out[3]["reason"] == "No dividend"

    def test_epv_negative_after_net_debt_is_locked_in_valuation_models(self):
        from backend.services.valuation_engine import valuation_models
        # EBIT 1bn, tax 21% -> NOPAT 0.79bn; EPV firm = 0.79bn / WACC (WACC >= 5%) <= 15.8bn,
        # net debt = 500bn - 60bn = 440bn -> equity value is deeply negative.
        b = _make_bundle(totalDebt=500_000_000_000)
        b["info"]["ebit"] = 1_000_000_000
        r = valuation_models(b, beta=1.0)
        epv = next(m for m in r["models"] if m["model"] == "EPV (Earnings Power Value)")
        assert epv["value"] is None and epv["locked"] is True and epv["reason"] == NON_POSITIVE
        assert epv["detail"]["impliedEquity"] < 0
        assert "EPV (Earnings Power Value)" not in r["axiomFairValue"]["weightsUsed"]

    def test_no_unlocked_model_is_non_positive(self):
        from backend.services.valuation_engine import valuation_models
        b = _make_bundle(totalDebt=500_000_000_000)
        b["info"]["ebit"] = 1_000_000_000
        r = valuation_models(b, beta=1.0)
        for m in r["models"] + [r["capmImplied"]]:
            assert m["locked"] or m["value"] > 0
