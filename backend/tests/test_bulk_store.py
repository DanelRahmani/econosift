"""Phase 66: World Bank / IMF / Fama-French / BIS downloads live in macro_series."""
import pytest

from backend import store
from backend.services import bulk_data_service as bulk

SERIES = ("wb_gdp_growth", "imf_gdp_growth", "ff_mkt_rf", "ff_smb", "ff_hml", "ff_rf", "zz_test")


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    with store.connect() as conn:
        for s in SERIES:
            conn.execute("DELETE FROM macro_series WHERE series = ?", (s,))
            conn.execute("DELETE FROM source_health WHERE source = ?", (f"series:{s}",))
    yield


def test_replace_series_swaps_the_whole_dataset_and_stamps_it():
    assert store.series_stored_at("zz_test") is None
    store.replace_series("zz_test", [("US", "2020", 1.0), ("US", "2021", 2.0)], "Test")
    store.replace_series("zz_test", [("US", "2021", 2.5)], "Test")
    assert store.read_series("zz_test").values.tolist() == [["US", "2021", 2.5]]
    assert store.series_stored_at("zz_test")


def test_an_empty_download_keeps_the_stored_data():
    store.replace_series("zz_test", [("US", "2020", 1.0)], "Test")
    assert store.replace_series("zz_test", [], "Test") == 0
    assert len(store.read_series("zz_test")) == 1


def test_load_worldbank_reads_the_stored_series_by_country_and_year():
    assert bulk.load_worldbank("gdp_growth", ["BRA"], 2000, 2030) is None  # not downloaded
    store.replace_series("wb_gdp_growth", [("BRA", "2019", 1.2), ("BRA", "2023", 2.9),
                                           ("USA", "2023", 2.5)], "World Bank")
    df = bulk.load_worldbank("gdp_growth", ["BRA"], 2020, 2030)
    assert df.to_dict("records") == [{"iso3": "BRA", "year": 2023, "value": 2.9}]
    assert bulk.worldbank_stored_at("gdp_growth")


def test_load_imf_maps_iso2_to_the_stored_iso3_rows():
    store.replace_series("imf_gdp_growth", [("BRA", "2027", 2.0)], "IMF")
    df = bulk.load_imf("gdp_growth", ["BR"], 2020, 2030)
    assert df.to_dict("records") == [{"iso3": "BRA", "year": 2027, "value": 2.0}]


def test_load_famafrench_rebuilds_the_monthly_factor_table():
    for i, f in enumerate(bulk.FF_FACTORS):
        store.replace_series(f"ff_{f}", [("US", "1999-12", 0.0), ("US", "2024-01", 0.01 * (i + 1))], "FF")
    df = bulk.load_famafrench(2000)
    assert df.to_dict("records") == [{"date": "2024-01-01", "year": 2024, "month": 1,
                                      "mkt_rf": 0.01, "smb": 0.02, "hml": 0.03, "rf": 0.04}]
