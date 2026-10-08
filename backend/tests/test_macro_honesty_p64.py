"""P2-34 (A3): macro / stability data-honesty fixes. No network: fetchers are patched."""
import sys
import types

import pandas as pd
import pytest


# --- 2. banking NPL weighting ------------------------------------------------

@pytest.mark.parametrize("npl, flags", [(12.0, 2), (7.0, 1), (4.0, 0)])
def test_banking_npl_flag_weight(npl, flags):
    """Severe NPL (> 10%) counts two flags, so it reaches red with one more flag."""
    from backend.services.banking_stability_service import _banking_signal
    # one extra flag (capital < 6): total 3 -> red only when NPL counts 2
    expected = {2: "red", 1: "yellow", 0: "yellow"}[flags]
    assert _banking_signal(npl, 5.0, None, None) == expected


# --- 3/4. banking field renames ----------------------------------------------

@pytest.mark.asyncio
async def test_banking_rows_use_renamed_keys(monkeypatch):
    from backend.services import banking_stability_service as bs

    async def fake_timeline(indicator, start, end):
        return {"USA": {2023: 1.0}}

    async def fake_gaps(codes):
        return {}

    monkeypatch.setattr(bs.atlas_service, "_wb_timeline", fake_timeline)
    monkeypatch.setattr(bs.source_bis, "get_credit_gaps_bulk", fake_gaps)
    result = await bs.get_banking_stability.__wrapped__()
    row = next(c for c in result["countries"] if c["iso2"] == "US")
    for block in ("kpis", "periods"):
        assert "capitalToAssets" in row[block] and "domesticCreditGdp" in row[block]
        assert "capitalAdequacy" not in row[block]
        assert "domesticCreditGrowth" not in row[block]
    prov = result["provenance"]
    assert "countries.US.kpis.capitalToAssets" in prov
    assert "countries.US.kpis.domesticCreditGdp" in prov
    assert "countries.US.kpis.capitalAdequacy" not in prov
    assert "countries.US.kpis.domesticCreditGrowth" not in prov


# --- 7. ongoing recession ----------------------------------------------------

def _fake_fredapi(monkeypatch, values, start="2025-12-01"):
    idx = pd.date_range(start, periods=len(values), freq="MS")

    class FakeFred:
        def __init__(self, api_key=None):
            pass

        def get_series(self, sid, observation_start=None):
            return pd.Series(values, index=idx)

    mod = types.ModuleType("fredapi")
    mod.Fred = FakeFred
    monkeypatch.setitem(sys.modules, "fredapi", mod)
    from backend.services import macro_expansion_service as mes
    monkeypatch.setattr(mes, "FRED_API_KEY", "test")
    return mes


def test_ongoing_recession_matches_packet_example(monkeypatch):
    mes = _fake_fredapi(monkeypatch, [0, 1, 1], start="2026-01-01")  # ends 2026-03-01
    periods = mes._fetch_recession_dates_sync()
    assert periods == [{"start": "2026-02-01", "end": "2026-03-01", "ongoing": True}]
    assert periods[0]["end"] != str(pd.Timestamp.today().date())


def test_closed_recession_unchanged(monkeypatch):
    mes = _fake_fredapi(monkeypatch, [0, 1, 1, 0], start="2026-01-01")
    periods = mes._fetch_recession_dates_sync()
    assert len(periods) == 1
    assert periods[0]["start"] == "2026-02-01"
    assert periods[0]["end"] == "2026-04-01"  # first month back at 0, as before
    assert not periods[0].get("ongoing")


# --- 6. funding-spread splice date -------------------------------------------

@pytest.mark.asyncio
async def test_funding_spread_splice_date(monkeypatch):
    from backend.services import credit_market as cm
    series = {
        "BAMLC0A0CM": [{"date": "2024-01-02", "value": 1.0}],
        "BAMLH0A0HYM2": [{"date": "2024-01-02", "value": 3.5}],
        "BAMLC0A4CBBB": [{"date": "2024-01-02", "value": 1.3}],
        "TEDRATE": [{"date": "2022-01-20", "value": 0.1}, {"date": "2022-01-21", "value": 0.12}],
        "SOFR": [{"date": "2022-01-21", "value": 0.05}, {"date": "2024-01-02", "value": 5.3}],
        "DTB3": [{"date": "2022-01-21", "value": 0.04}, {"date": "2024-01-02", "value": 5.25}],
    }

    async def fake_fetch():
        return series

    monkeypatch.setattr(cm, "_fetch_series", fake_fetch)
    result = await cm.get_credit_pulse.__wrapped__()
    assert result["fundingSpreadSplice"] == "2022-01-21"
    note = result["provenance"]["history.funding_spread"]["formula"]
    assert "TEDRATE to 2022-01-21, then SOFR − DTB3" in note


@pytest.mark.asyncio
async def test_funding_spread_splice_none_without_tedrate(monkeypatch):
    from backend.services import credit_market as cm

    async def fake_fetch():
        return {"SOFR": [{"date": "2024-01-02", "value": 5.3}],
                "DTB3": [{"date": "2024-01-02", "value": 5.25}]}

    monkeypatch.setattr(cm, "_fetch_series", fake_fetch)
    result = await cm.get_credit_pulse.__wrapped__()
    assert result["fundingSpreadSplice"] is None


# --- 9. sector rotation confidence -------------------------------------------

def test_phase_confidence_is_winners_share_of_positive_scores():
    from backend.services.sector_service import _phase_confidence
    scores = {"Early": 3.0, "Mid": 1.0, "Late": 0.0, "Recession": 0.0}
    assert _phase_confidence(scores, "Early") == 75


def test_phase_confidence_none_when_all_zero():
    from backend.services.sector_service import _phase_confidence
    assert _phase_confidence({"Early": 0.0, "Mid": 0.0, "Late": 0.0, "Recession": 0.0}, "Early") is None


# --- 1. real yield CPI basis -------------------------------------------------

def _yield_data():
    pt = lambda v: [{"date": "2026-08-01", "value": v}]  # noqa: E731
    return {"DGS10": [{"date": "2026-08-01", "value": 4.0}], "IRLTLT01DEM156N": pt(3.0)}


@pytest.mark.asyncio
async def test_real_yield_uses_annual_cpi_and_labels_basis(monkeypatch):
    from backend.services import yield_curve_service as ycs

    async def fake_series():
        return _yield_data()

    async def fake_wb(indicator, start, end):
        return {"DEU": {2024: 2.0, 2025: 2.4}}

    async def no_monthly():
        return {}

    monkeypatch.setattr(ycs, "_fetch_series", fake_series)
    monkeypatch.setattr(ycs, "_fetch_monthly_cpi", no_monthly)
    monkeypatch.setattr(ycs.atlas_service, "_wb_timeline", fake_wb)
    result = await ycs.get_yield_curves.__wrapped__()
    de = next(r for r in result["global_yields"] if r["iso2"] == "DE")
    assert de["cpiBasis"] == "annual 2025"
    assert de["inflation"] == pytest.approx(2.4)
    assert de["real_yield"] == pytest.approx(3.0 - 2.4)
    assert "annual 2025" in result["provenance"]["global_yields.DE.inflation"]["note"]


@pytest.mark.asyncio
async def test_real_yield_prefers_monthly_cpi_when_available(monkeypatch):
    from backend.services import yield_curve_service as ycs

    async def fake_series():
        return _yield_data()

    async def fake_wb(indicator, start, end):
        return {"DEU": {2025: 2.4}}

    async def monthly():
        return {"DE": ("2026-08", 1.8)}

    monkeypatch.setattr(ycs, "_fetch_series", fake_series)
    monkeypatch.setattr(ycs, "_fetch_monthly_cpi", monthly)
    monkeypatch.setattr(ycs.atlas_service, "_wb_timeline", fake_wb)
    result = await ycs.get_yield_curves.__wrapped__()
    de = next(r for r in result["global_yields"] if r["iso2"] == "DE")
    assert de["cpiBasis"] == "monthly 2026-08"
    assert de["real_yield"] == pytest.approx(3.0 - 1.8)


@pytest.mark.asyncio
async def test_real_yield_falls_back_to_annual_when_monthly_older(monkeypatch):
    from backend.services import yield_curve_service as ycs

    async def fake_wb(indicator, start, end):
        return {"DEU": {2025: 2.4}}

    async def monthly():
        return {"DE": ("2023-06", 9.9)}

    monkeypatch.setattr(ycs, "_fetch_monthly_cpi", monthly)
    monkeypatch.setattr(ycs.atlas_service, "_wb_timeline", fake_wb)
    cpi = await ycs._get_cpi_map()
    assert cpi["DE"] == {"value": 2.4, "basis": "annual 2025"}
