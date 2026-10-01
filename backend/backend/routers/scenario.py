from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import provenance as pv
from ..services import scenario_lab, yfinance_service, portfolio

router = APIRouter(prefix="/api/scenario", tags=["Scenario Lab"])

class PortfolioRequest(BaseModel):
    holdings: list[dict] # {"ticker": "AAPL", "weight": 0.5}

class CustomShockRequest(PortfolioRequest):
    shocks: dict[str, float] # {"equities": -0.10, "rates": 50, "credit": 100}

@router.get("/historical")
async def get_historical_episodes():
    """Return predefined historical episodes and shocks."""
    return scenario_lab.get_historical_episodes()

@router.post("/historical/stress")
async def stress_historical(req: PortfolioRequest):
    """Stress test a portfolio using predefined historical periods."""
    tickers = [h["ticker"] for h in req.holdings]
    if not tickers:
        raise HTTPException(400, "No valid holdings")
        
    try:
        frame = yfinance_service.get_close_frame(tuple(tickers), period="max")
        results = portfolio.stress_test_portfolio(req.holdings, frame, "^GSPC")
        if not results:
            return {"episodes": results}
        px = pv.ref("yahoo", None, "Daily adjusted close of the holdings, full available history",
                    units="price (split/dividend adjusted)", frequency="daily", observed=pv.last_date(frame))
        prov: dict = {"*": pv.derived(
            "Historical stress replay: the portfolio's weighted daily simple returns inside fixed calendar windows",
            [px], title="Historical stress test")}
        for ep in results:
            if "error" in ep:
                continue
            prov[f"episodes.{ep['scenario']}"] = pv.derived(
                f"totalReturn = compounded weighted daily returns from {ep['start']} to {ep['end']}; maxDrawdown = "
                "worst (value ÷ running peak − 1) inside the window; weights normalised over holdings that traded",
                [px], title=ep.get("label"), observed=ep["end"],
                note=None if "^GSPC" in frame.columns else
                "The benchmark series is empty: the price frame holds only the portfolio's tickers, not ^GSPC.")
        return pv.attach({"episodes": results}, prov)
    except Exception as e:
        raise HTTPException(500, f"Stress test failed: {str(e)}")

@router.post("/custom")
async def simulate_custom(req: CustomShockRequest):
    """Simulate a custom shock using beta exposure."""
    tickers = [h["ticker"] for h in req.holdings] + ["^GSPC", "TLT", "HYG"]
    tickers = list(set(tickers))
    
    try:
        frame = yfinance_service.get_close_frame(tuple(tickers), period="5y")
        result = scenario_lab.simulate_custom_shock(req.holdings, frame, req.shocks)
        return result
    except Exception as e:
        raise HTTPException(500, f"Custom shock failed: {str(e)}")
