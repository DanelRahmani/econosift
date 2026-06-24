"""Options & IV Module endpoints — Phase 7."""
from __future__ import annotations

import asyncio
from datetime import date, datetime

import yfinance as yf
from fastapi import APIRouter, Query

from ..services import options_engine as oe
from ..cache import cached

router = APIRouter(prefix="/api/options", tags=["options"])


# ──────────────────────────────────────────────────────────────────────────────
# 🟢 Cached tier — 60-min TTL
# ──────────────────────────────────────────────────────────────────────────────

@cached("options_expiries")
def _expiries_sync(ticker: str) -> list[str]:
    """Return list of available expiry date strings for a ticker."""
    try:
        t = yf.Ticker(ticker.upper())
        return list(t.options)
    except Exception:
        return []


@router.get("/expiries")
async def expiries(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """List all available option expiry dates for a ticker."""
    return await asyncio.to_thread(_expiries_sync, ticker.upper())


@cached("options_ivmetrics")
def _ivmetrics_sync(ticker: str) -> dict:
    return oe.get_iv_metrics(ticker.upper())


@router.get("/ivmetrics")
async def iv_metrics(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Top-level IV KPIs: IV30, IV Rank, IV Percentile, Put/Call OI Ratio, Max Pain, Implied Move."""
    return await asyncio.to_thread(_ivmetrics_sync, ticker.upper())


@cached("options_chain")
def _chain_sync(ticker: str, expiry: str) -> dict:
    return oe.get_chain(ticker.upper(), expiry)


@router.get("/chain")
async def options_chain(
    ticker: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    expiry: str = Query(..., description="Expiry date YYYY-MM-DD"),
):
    """Full options chain (calls + puts) for a ticker and expiry date.

    Note: yfinance options data is delayed ~15 min.
    """
    return await asyncio.to_thread(_chain_sync, ticker.upper(), expiry)


@cached("options_term")
def _term_sync(ticker: str) -> list:
    return oe.get_term_structure(ticker.upper())


@router.get("/termstructure")
async def term_structure(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """IV term structure: ATM IV and straddle cost per expiry, sorted by DTE."""
    return await asyncio.to_thread(_term_sync, ticker.upper())


@cached("options_smile")
def _smile_sync(ticker: str, expiry: str) -> list:
    return oe.get_iv_smile(ticker.upper(), expiry)


@router.get("/smile")
async def iv_smile(
    ticker: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    expiry: str = Query(..., description="Expiry date YYYY-MM-DD"),
):
    """IV smile: call and put IV by moneyness (0.70–1.30) for a given expiry."""
    return await asyncio.to_thread(_smile_sync, ticker.upper(), expiry)


@cached("options_oi")
def _oi_sync(ticker: str, expiry: str) -> dict:
    return oe.get_oi_profile(ticker.upper(), expiry)


@router.get("/oiprofile")
async def oi_profile(
    ticker: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    expiry: str = Query(..., description="Expiry date YYYY-MM-DD"),
):
    """Open-interest profile and max pain for a specific expiry."""
    return await asyncio.to_thread(_oi_sync, ticker.upper(), expiry)


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 User-triggered tier — uncached, POST
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/montecarlo")
async def monte_carlo_options(
    ticker: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    strike: float = Query(..., description="Option strike price"),
    expiry: str = Query(..., description="Expiry date YYYY-MM-DD"),
    opt_type: str = Query(default="call", description="'call' or 'put'"),
    sims: int = Query(default=10_000, description="Number of GBM simulations (max 50,000)"),
):
    """GBM Monte Carlo options pricing (10,000–50,000 paths).

    Fetches spot price and IV from the live chain, then simulates terminal stock
    prices under risk-neutral GBM, discounts payoffs, and returns price
    statistics plus a payoff histogram.
    """
    def _run() -> dict:
        try:
            t = yf.Ticker(ticker.upper())
            fi = t.fast_info
            S = fi.get("lastPrice") or fi.get("last_price")
            if not S or S <= 0:
                return {"error": "Cannot get spot price"}

            try:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                T = max((exp_date - date.today()).days, 1) / 365.0
            except ValueError:
                return {"error": "Invalid expiry date format — expected YYYY-MM-DD"}

            r = oe._risk_free_rate()

            # Fetch the chain to find IV for the requested strike
            chain_data = oe.get_chain(ticker.upper(), expiry)
            if "error" in chain_data:
                return {"error": chain_data["error"]}

            key = "calls" if opt_type.lower() == "call" else "puts"
            rows = chain_data.get(key, [])
            sigma = None
            if rows:
                closest = min(rows, key=lambda row: abs(row.get("strike", 0) - strike), default=None)
                if closest and closest.get("iv"):
                    sigma = closest["iv"] / 100.0

            if not sigma or sigma <= 0:
                sigma = 0.30  # fallback: 30 % vol

            result = oe.mc_option_price(
                float(S),
                float(strike),
                T,
                r,
                sigma,
                opt_type.lower(),
                min(int(sims), 50_000),
            )
            result.update({
                "ticker": ticker.upper(),
                "strike": strike,
                "expiry": expiry,
                "optType": opt_type.lower(),
                "spot": float(S),
                "sigma": round(sigma * 100, 2),  # display as %
            })
            return result
        except Exception as exc:
            return {"error": str(exc)}

    return await asyncio.to_thread(_run)
