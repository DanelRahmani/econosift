"""Tests for yield_curve_service — Phase 18A."""
import pytest
from unittest.mock import patch, AsyncMock


def _make_point(date="2024-01-02", value=4.0):
    return {"date": date, "value": value}


MOCK_DATA = {
    "DGS3MO": [_make_point(value=5.30)],
    "DGS2":   [_make_point(value=4.80)],
    "DGS10":  [_make_point(value=4.20)],
    "DGS30":  [_make_point(value=4.40)],
    "DFII10": [_make_point(value=2.10)],
    "T10YIE": [_make_point(value=2.10)],
    "THREEFYTP10":[_make_point(value=0.40)],
    "IRLTLT01DEM156N": [_make_point(value=2.50)],
    "IRLTLT01GBM156N": [_make_point(value=4.10)],
    **{f"DGS{t}": [_make_point(value=4.5)] for t in ["1MO", "6MO", "1", "3", "5", "7", "20"]},
    **{f"DFII{t}": [_make_point(value=2.0)] for t in ["5", "20", "30"]},
    **{f"T{t}YIE": [_make_point(value=2.1)] for t in ["5", "30"]},
    **{f"IRLTLT01{c}M156N": [_make_point(value=3.5)] for c in ["JPM", "FRM", "ITM", "CAM", "AUM", "ESM"]},
}


@pytest.fixture(autouse=True)
def _no_cpi_download():
    """Keep these tests offline: the CPI map (World Bank + BIS zip) is not under test here."""
    with patch("backend.services.yield_curve_service._get_cpi_map", new_callable=AsyncMock, return_value={}):
        yield


@pytest.mark.asyncio
async def test_yield_curves_structure():
    with patch(
        "backend.services.yield_curve_service._fetch_series",
        new_callable=AsyncMock,
        return_value=MOCK_DATA,
    ):
        from backend.services.yield_curve_service import get_yield_curves
        result = await get_yield_curves()
    assert "us_curve" in result
    assert "foreign_10y" in result
    assert "breakevens" in result
    assert "term_premium" in result
    assert result["us_curve"]["spread_2y10y"] == pytest.approx(4.20 - 4.80)
    assert result["us_curve"]["inverted"] is True  # 2Y > 10Y
    assert "Germany" in result["foreign_10y"]


@pytest.mark.asyncio
async def test_yield_curves_spreads_vs_us():
    with patch(
        "backend.services.yield_curve_service._fetch_series",
        new_callable=AsyncMock,
        return_value=MOCK_DATA,
    ):
        from backend.services.yield_curve_service import get_yield_curves
        result = await get_yield_curves()
    us_10y = 4.20
    de_10y = 2.50
    assert result["foreign_10y"]["Germany"]["spread_vs_us"] == pytest.approx(de_10y - us_10y)
