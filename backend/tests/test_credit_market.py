# backend/tests/test_credit_market.py
import pytest
from unittest.mock import patch, AsyncMock

MOCK_SERIES = {
    "BAMLC0A0CM": [{"date": "2024-01-02", "value": 1.05}],
    "BAMLH0A0HYM2": [{"date": "2024-01-02", "value": 3.50}],
    "BAMLC0A4CBBBOAS": [{"date": "2024-01-02", "value": 1.30}],
    "SOFR": [{"date": "2024-01-02", "value": 5.30}],
    "DTB3": [{"date": "2024-01-02", "value": 5.25}],
    "TEDRATE": [{"date": "2023-01-02", "value": 0.15}],
}


def _clear_credit_cache():
    from backend.cache import _caches
    _caches.pop("credit_pulse", None)


@pytest.mark.asyncio
async def test_get_credit_pulse_returns_required_keys():
    _clear_credit_cache()
    with patch(
        "backend.services.credit_market._fetch_series",
        new_callable=AsyncMock,
        return_value=MOCK_SERIES,
    ):
        from backend.services.credit_market import get_credit_pulse
        result = await get_credit_pulse()
    assert "current" in result
    assert "history" in result
    assert "signals" in result
    assert result["current"]["ig_oas"] == pytest.approx(1.05)
    assert result["current"]["hy_oas"] == pytest.approx(3.50)
    assert result["current"]["funding_spread"] == pytest.approx(0.05)  # SOFR - DTB3
    assert result["signals"]["stress"] is False


@pytest.mark.asyncio
async def test_get_credit_pulse_stress_signal_when_hy_wide():
    _clear_credit_cache()
    wide = {**MOCK_SERIES, "BAMLH0A0HYM2": [{"date": "2024-01-02", "value": 9.0}]}
    with patch(
        "backend.services.credit_market._fetch_series",
        new_callable=AsyncMock,
        return_value=wide,
    ):
        from backend.services.credit_market import get_credit_pulse
        result = await get_credit_pulse()
    assert result["signals"]["stress"] is True
