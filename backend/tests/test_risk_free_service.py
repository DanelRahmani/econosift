"""Per-country risk-free rates state what they are (audit D-32)."""
import asyncio
from datetime import date, timedelta

from backend.services import macro_expansion_service, risk_free_service as rfs


def _rates(monkeypatch, fred: dict) -> dict[str, dict]:
    monkeypatch.setattr(macro_expansion_service, "_fetch_fred_series_sync", lambda ids, start: fred)
    monkeypatch.setattr(rfs, "_get_country_erp", lambda c: 0.05)
    rows = asyncio.run(rfs.get_risk_free_rates.__wrapped__())
    return {r["name"]: r for r in rows}


def test_developed_markets_use_ten_year_government_yields():
    for country in ("United Kingdom", "Germany", "Japan", "Canada"):
        sid, tenor = rfs._COUNTRY_SERIES[country]
        assert sid.startswith("IRLTLT01") and tenor == "10Y government bond"


def test_observed_rate_carries_series_and_date(monkeypatch):
    recent = (date.today() - timedelta(days=40)).isoformat()
    rows = _rates(monkeypatch, {"IRLTLT01DEM156N": [{"date": recent, "value": 2.75}]})
    de = rows["Germany"]
    assert de["riskFreeRate"] == 0.0275
    assert (de["basis"], de["series"], de["asOf"], de["stale"]) == ("observed", "IRLTLT01DEM156N", recent, False)


def test_missing_series_is_flagged_as_fallback_not_passed_off_as_data(monkeypatch):
    rows = _rates(monkeypatch, {})
    assert rows["Germany"]["basis"] == "fallback" and rows["Germany"]["series"] is None


def test_old_observation_is_stale(monkeypatch):
    old = (date.today() - timedelta(days=400)).isoformat()
    rows = _rates(monkeypatch, {"IRSTCI01RUM156N": [{"date": old, "value": 16.0}]})
    assert rows["Russia"]["stale"] is True
