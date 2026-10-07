"""Options & IV Module endpoints — Phase 7."""
from __future__ import annotations

import asyncio
from datetime import date, datetime

import yfinance as yf
from fastapi import APIRouter, Query

from .. import provenance as pv
from ..services import options_engine as oe
from ..cache import cached

router = APIRouter(prefix="/api/options", tags=["options"])


# ──────────────────────────────────────────────────────────────────────────────
# Provenance helpers
# ──────────────────────────────────────────────────────────────────────────────

def _chain_ref(ticker: str, title: str) -> dict:
    return pv.yahoo(ticker, title, flags=("delayed",))


def _spot_ref(ticker: str) -> dict:
    return pv.yahoo(ticker, "Last price (fast_info lastPrice)", units="price", flags=("delayed",))


def _rf_ref() -> dict:
    return pv.yahoo("^IRX", "13-week T-bill yield, used as the risk-free rate", units="% p.a.", frequency="daily",
                    note="EconoSift uses a hard-coded 5% when this quote is unavailable; the response does not say "
                         "whether it did.")


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
    t = ticker.upper()
    rows = await asyncio.to_thread(_expiries_sync, t)
    return pv.attach({"ticker": t, "expiries": rows},
                     {"*": _chain_ref(t, "Option expiry dates listed for the ticker (Ticker.options)")})


@cached("options_ivmetrics")
def _ivmetrics_sync(ticker: str) -> dict:
    result = oe.get_iv_metrics(ticker.upper())
    if "error" in result:
        return result
    t = result["ticker"]
    chain = _chain_ref(t, "Option chains (calls and puts by expiry)")
    approx = bool(result.get("iv30Approximate"))
    n_hist = result.get("ivHistoryDays")
    history = pv.ref(
        "econosift", "iv30", f"EconoSift's daily record of {t} IV30", units="% annualised", frequency="daily",
        note=(f"{n_hist} sessions recorded; " if n_hist is not None else "")
             + f"IV Rank and Percentile stay empty until {oe._IV_RANK_MIN_HISTORY} sessions exist. "
               "Free sources publish no IV history, so it is recorded each time this endpoint runs.")
    rank_flags = ("partial",) if result.get("ivRankApproximate") else ()
    return pv.attach(result, {
        "*": chain,
        "spot": _spot_ref(t),
        "riskFree": _rf_ref(),
        "iv30": pv.derived(
            "ATM implied volatility (call at the strike nearest spot) of the two expiries bracketing 30 calendar "
            "days, linearly interpolated by days to expiry; Yahoo's impliedVolatility, or back-solved from the call "
            "mid price (Black-Scholes) when Yahoo's is 0.1% or lower",
            [chain, "riskFree"], title="30-day implied volatility", flags=("delayed", "proxy") if approx else ("delayed",),
            note="Fewer than two usable expiries bracket 30 days, so the nearest single expiry stands in."
                 if approx else None),
        "ivRank": pv.derived(
            "(IV30 − lowest recorded IV30) ÷ (highest − lowest) × 100 over up to the last 252 recorded daily IV30 values",
            [history], title="IV Rank", flags=rank_flags),
        "ivPercentile": pv.derived(
            "share of up to the last 252 recorded daily IV30 values that are below today's IV30 × 100",
            [history], title="IV Percentile", flags=rank_flags),
        "pcOIRatio": pv.derived("total put open interest ÷ total call open interest across the nearest 4 expiries",
                                [chain], title="Put/call open-interest ratio", flags=("delayed",)),
        "maxPain": pv.derived(
            "strike that minimises the total intrinsic payout to option holders (Σ call OI × max(strike − s, 0) + "
            "Σ put OI × max(s − strike, 0)) at the first expiry at least 7 days away",
            [chain], title="Max pain", flags=("delayed",)),
        "impliedMove": pv.derived(
            "(ATM call mid + put mid) ÷ spot × 100 at the strike nearest spot, first expiry at least 7 days away; "
            "not tied to a specific earnings date",
            [chain, "spot"], title="Implied move", flags=("delayed",)),
    })


@router.get("/ivmetrics")
async def iv_metrics(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Top-level IV KPIs: IV30, IV Rank, IV Percentile, Put/Call OI Ratio, Max Pain, Implied Move."""
    return await asyncio.to_thread(_ivmetrics_sync, ticker.upper())


@cached("options_chain")
def _chain_sync(ticker: str, expiry: str) -> dict:
    result = oe.get_chain(ticker.upper(), expiry)
    if "error" in result:
        return result
    t = result["ticker"]
    prov: dict = {
        "*": _chain_ref(t, f"Option chain for expiry {expiry}"),
        "spot": _spot_ref(t),
        "riskFree": _rf_ref(),
        "dividendYield": pv.yahoo(t, "Dividend yield (dividendYield in Yahoo info ÷ 100)", units="% p.a."),
        "dte": pv.derived("expiry date − today, in calendar days", [], title="Days to expiry"),
    }
    # Chain rows are keyed by column: calls.<column> / puts.<column> (rows are strikes, not stable ids).
    for side in ("calls", "puts"):
        prov[f"{side}.mid"] = pv.derived("(bid + ask) ÷ 2, or the last price when bid and ask are both 0",
                                         ["*"], title="Mid price", flags=("delayed",))
        prov[f"{side}.iv"] = pv.derived(
            "Yahoo impliedVolatility × 100; back-solved from the mid price (Black-Scholes-Merton, Brent root-find) "
            "when Yahoo's value is 0.1% or lower; blank above 500%",
            ["*", "riskFree", "dividendYield"], title="Implied volatility", flags=("delayed",))
        prov[f"{side}.delta"] = pv.derived(
            "Black-Scholes-Merton delta at the row's implied volatility, spot, T = max(days, 1) ÷ 365, the risk-free "
            "rate and the dividend yield", [f"{side}.iv", "spot", "riskFree", "dividendYield"], title="Delta")
        prov[f"{side}.bsPrice"] = pv.derived(
            "Black-Scholes-Merton theoretical price at the row's implied volatility (same inputs as delta)",
            [f"{side}.iv", "spot", "riskFree", "dividendYield"], title="Theoretical price")
    return pv.attach(result, prov)


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
    t = ticker.upper()
    rows = await asyncio.to_thread(_term_sync, t)
    chain = _chain_ref(t, "Option chains (calls and puts) for every listed expiry")
    return pv.attach({"ticker": t, "points": rows}, {
        "*": chain,
        "points.dte": pv.derived("expiry date − today, in calendar days", [], title="Days to expiry"),
        "points.atmIV": pv.derived(
            "Yahoo impliedVolatility × 100 of the call at the strike nearest spot; back-solved from the call mid "
            "price (Black-Scholes, Brent root-find, no dividend yield) when Yahoo's is 0.1% or lower; blank above "
            "500%", [chain, _spot_ref(t), _rf_ref()], title="At-the-money implied volatility", flags=("delayed",)),
        "points.straddle": pv.derived(
            "ATM call mid + put mid at the strike nearest spot, mid = (bid + ask) ÷ 2", [chain, _spot_ref(t)],
            title="Straddle cost", flags=("delayed",)),
    })


@cached("options_smile")
def _smile_sync(ticker: str, expiry: str) -> list:
    return oe.get_iv_smile(ticker.upper(), expiry)


@router.get("/smile")
async def iv_smile(
    ticker: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    expiry: str = Query(..., description="Expiry date YYYY-MM-DD"),
):
    """IV smile: call and put IV by moneyness (0.70–1.30) for a given expiry."""
    t = ticker.upper()
    rows = await asyncio.to_thread(_smile_sync, t, expiry)
    chain = _chain_ref(t, f"Option chain for expiry {expiry}")
    iv = ("Yahoo impliedVolatility × 100; back-solved from the mid price (Black-Scholes, Brent root-find, no "
          "dividend yield) when Yahoo's is 0.1% or lower; blank above 500%")
    return pv.attach({"ticker": t, "expiry": expiry, "points": rows}, {
        "*": chain,
        "points.moneyness": pv.derived("strike ÷ spot, kept between 0.70 and 1.30", [chain, _spot_ref(t)],
                                       title="Moneyness"),
        "points.callIV": pv.derived(iv, [chain, _spot_ref(t), _rf_ref()], title="Call implied volatility",
                                    flags=("delayed",)),
        "points.putIV": pv.derived(iv, [chain, _spot_ref(t), _rf_ref()], title="Put implied volatility",
                                   flags=("delayed",)),
    })


@cached("options_oi")
def _oi_sync(ticker: str, expiry: str) -> dict:
    result = oe.get_oi_profile(ticker.upper(), expiry)
    if "error" in result:
        return result
    t = result["ticker"]
    chain = _chain_ref(t, f"Open interest by strike for expiry {expiry}")
    return pv.attach(result, {
        "*": chain,
        "spot": _spot_ref(t),
        "maxPain": pv.derived(
            "strike that minimises the total intrinsic payout to option holders (Σ call OI × max(strike − s, 0) + "
            "Σ put OI × max(s − strike, 0)) for this expiry", [chain], title="Max pain", flags=("delayed",)),
    })


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
    seed: int | None = Query(default=None, description="Optional RNG seed for a reproducible run"),
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

            sigma_fallback = not sigma or sigma <= 0
            if sigma_fallback:
                sigma = 0.30  # fallback: 30 % vol

            result = oe.mc_option_price(
                float(S),
                float(strike),
                T,
                r,
                sigma,
                opt_type.lower(),
                min(int(sims), 50_000),
                seed,
            )
            result.update({
                "ticker": ticker.upper(),
                "strike": strike,
                "expiry": expiry,
                "optType": opt_type.lower(),
                "spot": float(S),
                "sigma": round(sigma * 100, 2),  # display as %
            })
            if "error" in result:
                return result
            t = ticker.upper()
            spot_ref = _spot_ref(t)
            chain = _chain_ref(t, f"Option chain for expiry {expiry}")
            if sigma_fallback:
                sigma_prov = pv.derived(
                    "hard-coded 30% volatility: no implied volatility was available at the closest listed strike",
                    [], title="Volatility assumption", flags=("fallback",))
            else:
                sigma_prov = pv.derived(
                    "implied volatility of the listed option (same type and expiry) whose strike is closest to the "
                    "requested strike, as a percent", [chain], title="Implied volatility", flags=("delayed",))
            return pv.attach(result, {
                "*": pv.derived(
                    "Risk-neutral GBM Monte Carlo: S_T = spot × exp((r − σ²/2)T + σ√T·Z) with Z ~ N(0,1), "
                    "T = max(days to expiry, 1) ÷ 365, unseeded draws; price = mean of e^(−rT) × payoff",
                    [spot_ref, "sigma", "riskFree"], title="Monte Carlo option price"),
                "spot": spot_ref,
                "sigma": sigma_prov,
                "riskFree": _rf_ref(),
                "std": pv.derived("standard deviation of the simulated discounted payoffs", ["*"], title="Payoff std"),
                "var95": pv.derived("5th percentile of the simulated discounted payoffs (a payoff, not a loss)",
                                    ["*"], title="5th percentile payoff"),
                "var99": pv.derived("1st percentile of the simulated discounted payoffs (a payoff, not a loss)",
                                    ["*"], title="1st percentile payoff"),
                "distribution": pv.derived("50-bin histogram of the non-zero simulated discounted payoffs",
                                           ["*"], title="Payoff distribution"),
                "bsPrice": pv.derived(
                    "Black-Scholes price with the same spot, strike, T, r and σ; no dividend yield (unlike the chain)",
                    [spot_ref, "sigma", "riskFree"], title="Black-Scholes price"),
            })
        except Exception as exc:
            return {"error": str(exc)}

    return await asyncio.to_thread(_run)
