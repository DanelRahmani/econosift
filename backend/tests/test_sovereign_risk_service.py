import pytest
from unittest.mock import patch, AsyncMock

MOCK_YIELD = {
    "us_curve": {"points": [], "spread_2y10y": -0.6, "spread_3m10y": -1.0, "inverted": True},
    "foreign_10y": {
        "Germany": {"yield_10y": 2.5, "spread_vs_us": -1.7},
        "Italy":   {"yield_10y": 4.0, "spread_vs_us": -0.2},
    },
    "real_yields": [], "breakevens": {}, "term_premium": {"current": 0.4, "history": []},
}
MOCK_RISK = {
    "countries": [
        {
            "iso3": "DEU", "name": "Germany", "year": 2023,
            "indicators": {"debt_gdp": 65.0, "current_account": 7.0, "inflation": 2.0,
                           "fiscal_balance": -2.5, "reserves_growth": 3.0, "unemployment": 3.5},
            "signals": {"debt_gdp": "yellow", "current_account": "green", "inflation": "green",
                        "fiscal_balance": "green", "reserves_growth": "green", "unemployment": "green"},
        },
        {
            "iso3": "ITA", "name": "Italy", "year": 2023,
            "indicators": {"debt_gdp": 140.0, "current_account": 0.0, "inflation": 3.5,
                           "fiscal_balance": -5.0, "reserves_growth": -2.0, "unemployment": 7.0},
            "signals": {"debt_gdp": "red", "current_account": "green", "inflation": "yellow",
                        "fiscal_balance": "red", "reserves_growth": "yellow", "unemployment": "yellow"},
        },
    ],
    "thresholds": {},
}

@pytest.mark.asyncio
async def test_sovereign_risk_structure():
    with patch("backend.services.sovereign_risk_service.get_yield_curves",
               new_callable=AsyncMock, return_value=MOCK_YIELD), \
         patch("backend.services.sovereign_risk_service.get_country_risk",
               new_callable=AsyncMock, return_value=MOCK_RISK):
        from backend.services.sovereign_risk_service import get_sovereign_risk
        result = await get_sovereign_risk()
    assert "countries" in result
    assert "top_risk" in result
    deu = next((c for c in result["countries"] if c["iso3"] == "DEU"), None)
    ita = next((c for c in result["countries"] if c["iso3"] == "ITA"), None)
    assert deu is not None
    assert ita["composite_score"] > deu["composite_score"]  # Italy riskier
