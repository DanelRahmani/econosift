"""Portfolio builder: aggregate performance & risk for a basket of holdings."""
from __future__ import annotations

import asyncio
from typing import Optional
from datetime import date as date_type

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import provenance as pv
from ..database import get_db
from ..db_models import PortfolioTransaction
from ..services import yfinance_service as yfs
from ..services import portfolio as port
from ..services.discount_rates import risk_free_rate, risk_free_rate_is_fallback

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class Holding(BaseModel):
    ticker: str
    weight: float = Field(default=1.0, ge=0.0)


class PortfolioRequest(BaseModel):
    holdings: list[Holding]
    period: str = "1y"
    risk_free: float = 0.04


class RollingRequest(PortfolioRequest):
    window: int = Field(default=60, ge=10, le=504)


class FFRequest(PortfolioRequest):
    model: str = Field(default="3", pattern="^[35]$")


class BLView(BaseModel):
    ticker: str
    expectedReturn: float


class BLRequest(PortfolioRequest):
    views: list[BLView] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_BENCH_COL = "^GSPC"
_AGG_COL = "AGG"


def _normalise(holdings_raw: list[Holding]) -> list[dict]:
    """Upper-case tickers, drop blanks."""
    return [
        {"ticker": h.ticker.strip().upper(), "weight": h.weight}
        for h in holdings_raw if h.ticker.strip()
    ]


async def _load_frame(holdings: list[dict], period: str,
                      extra: tuple[str, ...] = ()) -> pd.DataFrame | None:
    """Fetch close prices for holdings + any extra symbols."""
    syms = list(dict.fromkeys(h["ticker"] for h in holdings))
    all_syms = tuple(dict.fromkeys(syms + list(extra)))
    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)
    if frame is None or frame.empty:
        return None
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index)
    return frame


def _empty(msg: str = "no data") -> dict:
    return {"error": msg}


def _px_ref(frame, note: str | None = None) -> dict:
    """Yahoo price input for a portfolio computation."""
    return pv.ref("yahoo", None, "Daily adjusted close of the requested tickers",
                  units="price (split/dividend adjusted)", frequency="daily",
                  observed=pv.last_date(frame), note=note)


def _req_rf_ref() -> dict:
    return pv.ref("other", None, "Risk-free rate sent with the request (risk_free)", units="decimal p.a.",
                  note="Supplied by the caller; the API default is 0.04. It is not looked up by the backend.")


def _fred_rf_ref() -> dict:
    if risk_free_rate_is_fallback():
        return pv.fred("DGS10", "10-year Treasury yield used as the risk-free rate", flags=("fallback",),
                       note="FRED was unreachable, so a hard-coded 4% stood in for the risk-free rate.")
    return pv.fred("DGS10", "10-year Treasury yield used as the risk-free rate", units="% p.a.", frequency="daily")


_BENCH_NOTE = ("Benchmark = ^GSPC for US listings (or the regional index for a non-US suffix), chosen from the "
               "first holding only.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze(req: PortfolioRequest):
    """Full portfolio analysis: value series, metrics, drawdown, benchmarks."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"holdings": [], "series": [], "metrics": {}, "missing": []}

    syms = list(dict.fromkeys(h["ticker"] for h in holdings))
    bench = yfs.benchmark_for(syms[0])
    all_syms = tuple(dict.fromkeys(syms + [bench, _BENCH_COL, _AGG_COL]))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, req.period)
    if frame is None or frame.empty:
        return {"holdings": [], "series": [], "metrics": {}, "missing": syms}

    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index)
    bench_series = frame[bench] if bench in frame.columns else None

    result = await asyncio.to_thread(port.analyze, frame, holdings, bench_series, req.risk_free)
    result["benchmark"] = bench

    # Add benchmark comparison series (base-100 ^GSPC / AGG)
    result["benchmarkSeries"] = await asyncio.to_thread(port.benchmark_series, frame, req.period)

    if not result.get("series"):
        return result
    px = _px_ref(frame)
    rf = _req_rf_ref()
    br = f"the benchmark's daily log return ({bench})"
    prov: dict = {
        "*": pv.derived(
            "Weighted portfolio of the holdings' daily adjusted closes; weights are normalised (negatives floored at 0) "
            "and re-spread over holdings that traded that day", [px], title="Portfolio analysis"),
        "series": pv.derived("base-100 compounding of the daily portfolio simple return Σ wᵢ·rᵢ", [px],
                             title="Portfolio value", observed=pv.last_date(frame)),
        "drawdownSeries": pv.derived("cumulative value ÷ running peak − 1, from compounded simple returns", [px],
                                     title="Drawdown"),
        "metrics.totalReturn": pv.derived("final portfolio value ÷ 100 − 1", [px], title="Total return"),
        "metrics.annReturn": pv.derived("mean daily portfolio log return × 252 (a log-return average, not the "
                                        "compounded annual growth)", [px], title="Annualised return"),
        "metrics.annVolatility": pv.derived("sample std of daily portfolio log returns × √252", [px],
                                            title="Annualised volatility"),
        "metrics.sharpe": pv.derived("(annReturn − risk-free rate) ÷ annVolatility", [px, rf], title="Sharpe ratio"),
        "metrics.sortino": pv.derived(
            "(mean daily simple return × 252 − rf) ÷ (√mean(min(r − rf/252, 0)²) × √252)", [px, rf],
            title="Sortino ratio"),
        "metrics.maxDrawdown": pv.derived("worst (portfolio value ÷ running peak − 1)", [px], title="Max drawdown"),
        "metrics.var95": pv.derived("5th percentile of daily portfolio log returns (historical; a return, not a "
                                    "currency amount)", [px], title="Daily VaR 95%"),
        "metrics.beta": pv.derived(
            f"cov(daily portfolio log return, {br}) ÷ var({br}) on shared dates", [px],
            title="Beta", note=_BENCH_NOTE),
        "benchmarkSeries.gspc": pv.ref(
            "yahoo", "^GSPC", "S&P 500 index level rebased to 100", units="index points, price return only",
            frequency="daily", observed=pv.last_date(frame["^GSPC"]) if "^GSPC" in frame.columns else None),
        "benchmarkSeries.agg": pv.ref(
            "yahoo", "AGG", "iShares Core US Aggregate Bond ETF adjusted close, rebased to 100",
            units="price (dividend adjusted)", frequency="daily",
            observed=pv.last_date(frame["AGG"]) if "AGG" in frame.columns else None),
    }
    for h in result.get("holdings", []):
        t = h["ticker"]
        prov[f"holdings.{t}.weight"] = pv.derived("requested weight ÷ sum of requested weights (negatives floored at 0)",
                                                  [], title="Weight")
        prov[f"holdings.{t}.totalReturn"] = pv.derived(
            "last adjusted close ÷ first adjusted close − 1 over the period", [px], title="Holding total return")
        prov[f"holdings.{t}.contribution"] = pv.derived(
            "normalised weight × the holding's total return (a buy-and-hold approximation, not a compounded contribution)",
            [f"holdings.{t}.weight", f"holdings.{t}.totalReturn"], title="Contribution")
    return pv.attach(result, prov)


@router.post("/drawdown")
async def drawdown(req: PortfolioRequest):
    """Underwater drawdown curve for the portfolio."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"drawdownSeries": []}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    present = [h for h in holdings if h["ticker"] in frame.columns]
    if not present:
        return {"drawdownSeries": []}

    total_w = sum(max(h["weight"], 0.0) for h in present) or 1.0
    weights = {h["ticker"]: max(h["weight"], 0.0) / total_w for h in present}
    cols = list(weights.keys())

    px = frame[cols].dropna(how="all").ffill()
    rets = px.pct_change().dropna(how="all").fillna(0.0)
    import numpy as np
    w_vec = np.array([weights[c] for c in cols])
    port_ret = pd.Series(rets[cols].to_numpy() @ w_vec, index=rets.index)

    return pv.attach({"drawdownSeries": port.drawdown_series(port_ret)}, {
        "*": pv.derived(
            "Portfolio simple returns Σ wᵢ·rᵢ (weights normalised over the holdings found, prices forward-filled, "
            "days with no price count as 0%); drawdown = cumulative value ÷ running peak − 1",
            [_px_ref(frame)], title="Portfolio drawdown")})


@router.post("/benchmarks")
async def benchmarks(req: PortfolioRequest):
    """Base-100 cumulative return series for ^GSPC and AGG."""
    holdings = _normalise(req.holdings)
    frame = await _load_frame(holdings, req.period, extra=(_BENCH_COL, _AGG_COL))
    if frame is None:
        return {"gspc": [], "agg": []}
    return pv.attach(port.benchmark_series(frame, req.period), {
        "*": pv.derived("close ÷ first close × 100 for each benchmark", [], title="Benchmark comparison"),
        "gspc": pv.ref("yahoo", "^GSPC", "S&P 500 index level rebased to 100", units="index points, price return only",
                       frequency="daily", observed=pv.last_date(frame["^GSPC"]) if "^GSPC" in frame.columns else None),
        "agg": pv.ref("yahoo", "AGG", "iShares Core US Aggregate Bond ETF adjusted close, rebased to 100",
                      units="price (dividend adjusted)", frequency="daily",
                      observed=pv.last_date(frame["AGG"]) if "AGG" in frame.columns else None),
    })


@router.post("/correlation")
async def correlation(req: PortfolioRequest):
    """Pairwise Pearson correlation matrix for portfolio holdings."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"tickers": [], "matrix": []}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    result = await asyncio.to_thread(port.correlation_matrix, holdings, frame)
    return pv.attach(result, {"*": pv.derived(
        "Pearson correlation of daily log returns (prices forward-filled), rounded to 3 decimals",
        [_px_ref(frame)], title="Correlation matrix")})


@router.post("/risk-contribution")
async def risk_contribution(req: PortfolioRequest):
    """Marginal and percentage risk contribution per holding."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return await asyncio.to_thread(port.risk_contribution, holdings, frame)


@router.post("/capm")
async def capm(req: PortfolioRequest):
    """CAPM attribution: alpha, beta, R², systematic/idiosyncratic variance."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return _empty("no holdings")

    syms = [h["ticker"] for h in holdings]
    bench = yfs.benchmark_for(syms[0])
    frame = await _load_frame(holdings, req.period, extra=(bench,))
    if frame is None:
        return _empty()

    result = await asyncio.to_thread(port.capm_attribution, holdings, frame, bench, req.risk_free)
    if "error" in result:
        return result
    px = _px_ref(frame)
    rf = _req_rf_ref()
    fit = (f"OLS of daily portfolio log return minus rf/252 on the benchmark's ({bench}) daily log return minus "
           "rf/252, with an intercept")
    return pv.attach(result, {
        "*": pv.derived("CAPM regression of the portfolio on its benchmark", [px, rf], title="CAPM attribution",
                        note=_BENCH_NOTE),
        "alpha": pv.derived("intercept of " + fit + " (daily)", [px, rf], title="Alpha (daily)"),
        "annAlpha": pv.derived("daily alpha × 252", ["alpha"], title="Alpha (annualised)"),
        "beta": pv.derived("slope of " + fit, [px, rf], title="Beta"),
        "rSquared": pv.derived("1 − residual sum of squares ÷ total sum of squares of " + fit, [px, rf],
                               title="R²"),
        "systematicVarPct": pv.derived("beta² × var(benchmark log return) ÷ var(portfolio log return)", [px],
                                       title="Systematic variance share"),
        "idiosyncraticVarPct": pv.derived("max(1 − systematicVarPct, 0)", ["systematicVarPct"],
                                          title="Idiosyncratic variance share"),
        "nObs": pv.derived("count of dates shared by portfolio and benchmark returns", [px],
                           title="Observations"),
    })


@router.post("/rolling")
async def rolling(req: RollingRequest):
    """Rolling Sharpe, volatility, and beta (window parameter in body)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"window": req.window, "sharpe": [], "volatility": [], "beta": []}

    syms = [h["ticker"] for h in holdings]
    bench = yfs.benchmark_for(syms[0])
    frame = await _load_frame(holdings, req.period, extra=(bench,))
    if frame is None:
        return _empty()

    result = await asyncio.to_thread(port.rolling_portfolio_metrics, holdings, frame, bench, req.risk_free, req.window)
    px = _px_ref(frame)
    w = req.window
    return pv.attach(result, {
        "*": pv.derived(f"Rolling {w}-day statistics of the portfolio's daily log returns", [px],
                        title="Rolling portfolio metrics"),
        "sharpe": pv.derived(
            f"rolling {w}-day mean of (daily log return − rf/252) × 252 ÷ (rolling std × √252)",
            [px, _req_rf_ref()], title="Rolling Sharpe"),
        "volatility": pv.derived(f"rolling {w}-day sample std of daily log returns × √252", [px],
                                 title="Rolling volatility"),
        "beta": pv.derived(f"rolling {w}-day cov(portfolio, benchmark {bench}) ÷ var(benchmark), daily log returns",
                           [px], title="Rolling beta", note=_BENCH_NOTE),
    })


@router.post("/kelly")
async def kelly(req: PortfolioRequest):
    """Kelly criterion fractions for each holding (on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return await asyncio.to_thread(port.kelly_criterion, holdings, frame, req.risk_free)


@router.post("/ff")
async def fama_french(req: FFRequest):
    """Fama-French factor attribution for the portfolio (on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return _empty("no holdings")

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return await asyncio.to_thread(port.ff_attribution_portfolio, holdings, frame, req.model, req.risk_free)


@router.post("/frontier")
async def frontier(req: PortfolioRequest):
    """Mean-variance efficient frontier (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"frontier": [], "error": "no holdings"}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    result = await asyncio.to_thread(port.efficient_frontier, holdings, frame)
    if "error" in result:
        return result
    px = _px_ref(frame)
    rf = _fred_rf_ref()
    est = ("μ = mean daily log return × 252 and Σ = sample covariance of daily log returns × 252 (prices "
           "forward-filled); long-only, fully invested")
    return pv.attach(result, {
        "*": pv.derived("Mean-variance optimisation: " + est, [px, rf], title="Efficient frontier"),
        "frontier": pv.derived(
            "minimum-variance long-only portfolio (SLSQP) for each of 50 target returns between the lowest- and "
            "highest-return long-only portfolios; sharpe = (ret − rf) ÷ vol. " + est, [px, rf],
            title="Efficient frontier points"),
        "maxSharpe": pv.derived(
            "long-only weights maximising (μᵀw − rf) ÷ √(wᵀΣw) (SLSQP). " + est, [px, rf],
            title="Maximum-Sharpe portfolio"),
        "currentPortfolio": pv.derived("the request's weights (normalised): ret = μᵀw, vol = √(wᵀΣw), "
                                       "sharpe = (ret − rf) ÷ vol. " + est, [px, rf], title="Current portfolio"),
    })


@router.post("/montecarlo")
async def montecarlo(req: PortfolioRequest):
    """Monte Carlo random weight simulation — risk/return cloud (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"points": [], "maxSharpe": {}}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    result = await asyncio.to_thread(port.monte_carlo_weights, holdings, frame)
    if "error" in result:
        return result
    px = _px_ref(frame)
    rf = _fred_rf_ref()
    return pv.attach(result, {
        "*": pv.derived(
            "10,000 random long-only weight vectors drawn from Dirichlet(1, …, 1) (seed 42); ret = μᵀw, "
            "vol = √(wᵀΣw), sharpe = (ret − rf) ÷ vol, with μ and Σ the annualised mean and covariance of daily "
            "log returns; at most 5,000 points are returned", [px, rf], title="Random-portfolio cloud"),
        "maxSharpe": pv.derived("the sampled portfolio with the highest Sharpe ratio (not an optimiser result)",
                                ["*"], title="Best sampled portfolio"),
    })


@router.post("/blacklitterman")
async def black_litterman(req: BLRequest):
    """Black-Litterman posterior + optimal weights (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return _empty("no holdings")

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    views = [{"ticker": v.ticker.strip().upper(), "expectedReturn": v.expectedReturn}
             for v in req.views]
    caps = await asyncio.to_thread(
        yfs.get_market_caps, tuple(h["ticker"] for h in holdings))
    result = await asyncio.to_thread(port.black_litterman, holdings, frame, views, req.risk_free, caps)
    if "error" in result:
        return result
    px = _px_ref(frame)
    rf = _req_rf_ref()
    mcap = pv.ref("yahoo", None, "Market capitalisation (fast_info market_cap) of each holding",
                  note="Current market caps, used as the equilibrium weights only when every holding has one.")
    assume = "δ = 2.5 (risk aversion) and τ = 0.05 are fixed assumptions, not estimates"
    prov: dict = {
        "*": pv.derived("Black-Litterman: equilibrium returns π = δΣw_mkt, blended with the request's absolute views. "
                        + assume, [px, mcap, rf], title="Black-Litterman"),
        "priorWeights": pv.derived(
            "'marketCap' when every holding has a Yahoo market cap (w_mkt = cap ÷ Σ caps), otherwise 'portfolio' "
            "(the request's own weights)", [mcap], title="Prior weights basis"),
        "currentWeights": pv.derived("request weights ÷ sum of weights (negatives floored at 0)", [],
                                     title="Current weights"),
        "optimalWeights": pv.derived(
            "w* = (δΣ)⁻¹·μ_BL floored at 0 and renormalised to 1 (long-only); with no views, the prior weights "
            "are returned unchanged. " + assume, ["*"], title="Optimal weights"),
    }
    for row in result.get("blReturns", []):
        t = row["ticker"]
        prov[f"blReturns.{t}.equilibriumReturn"] = pv.derived(
            "π + rf, where π = δ·Σ·w_mkt is the implied excess return (Σ = annualised covariance of daily log "
            "returns)", ["*"], title="Equilibrium return")
        prov[f"blReturns.{t}.blReturn"] = pv.derived(
            "μ_BL + rf, where μ_BL = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹[(τΣ)⁻¹π + PᵀΩ⁻¹(q − rf)], Ω = τPΣPᵀ; equals the "
            "equilibrium return when no views are given", ["*"], title="Black-Litterman return")
    return pv.attach(result, prov)


@router.post("/stress")
async def stress(req: PortfolioRequest):
    """Historical stress test across GFC / COVID / rate-shock / dot-com (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    syms = [h["ticker"] for h in holdings]
    bench = yfs.benchmark_for(syms[0])
    # Stress periods go back to 2000, so override period to max
    frame = await _load_frame(holdings, "max", extra=(bench,))
    if frame is None:
        return _empty()

    return await asyncio.to_thread(port.stress_test_portfolio, holdings, frame, bench)


# ---------------------------------------------------------------------------
# Transaction log models
# ---------------------------------------------------------------------------

class TransactionIn(BaseModel):
    id: Optional[int] = None  # None for new, set for updates
    ticker: str
    date: date_type
    type: str  # "buy" | "sell"
    quantity: float = Field(gt=0.0)
    price: float = Field(gt=0.0)
    fees: float = Field(default=0.0, ge=0.0)


class TransactionSyncRequest(BaseModel):
    transactions: list[TransactionIn]


class PnLRequest(BaseModel):
    transactions: list[TransactionIn]
    current_prices: dict[str, float] = Field(default_factory=dict)  # ticker → price


class PnLItem(BaseModel):
    ticker: str
    quantity: float
    cost_basis: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_return_pct: float


class PnLResponse(BaseModel):
    items: list[PnLItem]
    total_cost_basis: float
    total_market_value: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_return_pct: float
    provenance: dict | None = None


# ---------------------------------------------------------------------------
# Transaction endpoints
# ---------------------------------------------------------------------------

@router.post("/transactions/sync")
def sync_transactions(req: TransactionSyncRequest, db: Session = Depends(get_db)):
    """Save transactions to SQLite (upsert by id)."""
    saved = 0
    for t in req.transactions:
        existing = None
        if t.id is not None:
            existing = db.query(PortfolioTransaction).filter(
                PortfolioTransaction.id == t.id
            ).first()

        if existing:
            existing.ticker = t.ticker.strip().upper()
            existing.date = t.date
            existing.type = t.type.lower()
            existing.quantity = t.quantity
            existing.price = t.price
            existing.fees = t.fees
        else:
            row = PortfolioTransaction(
                ticker=t.ticker.strip().upper(),
                date=t.date,
                type=t.type.lower(),
                quantity=t.quantity,
                price=t.price,
                fees=t.fees,
            )
            db.add(row)
        saved += 1

    db.commit()
    return {"saved": saved}


@router.get("/transactions")
def get_transactions(db: Session = Depends(get_db)):
    """Return all saved transactions from SQLite."""
    rows = db.query(PortfolioTransaction).order_by(
        PortfolioTransaction.date.desc(),
        PortfolioTransaction.created_at.desc(),
    ).all()

    return pv.attach({
        "transactions": [
            {
                "id": r.id,
                "ticker": r.ticker,
                "date": r.date.isoformat() if r.date else None,
                "type": r.type,
                "quantity": r.quantity,
                "price": r.price,
                "fees": r.fees,
            }
            for r in rows
        ]
    }, {"*": pv.ref("econosift", None, "Transactions you entered (stored in this app's database)")})


@router.post("/transactions/pnl", response_model=PnLResponse)
def compute_pnl(req: PnLRequest):
    """Compute realized & unrealized P&L from transaction log + current prices."""
    if not req.transactions:
        return PnLResponse(
            items=[], total_cost_basis=0, total_market_value=0,
            total_unrealized_pnl=0, total_realized_pnl=0, total_return_pct=0
        )

    import numpy as np

    # Sort by date ascending for FIFO lot matching
    sorted_tx = sorted(req.transactions, key=lambda t: t.date)

    # Separate buys and sells per ticker
    buys: dict[str, list[dict]] = {}
    sells: dict[str, list[dict]] = {}
    for t in sorted_tx:
        ticker = t.ticker.strip().upper()
        entry = {"date": t.date, "quantity": t.quantity, "price": t.price, "fees": t.fees}
        if t.type.lower() == "buy":
            buys.setdefault(ticker, []).append(entry)
        else:
            sells.setdefault(ticker, []).append(entry)

    realized_pnl_by_ticker: dict[str, float] = {}
    remaining_qty: dict[str, float] = {}
    cost_basis_remaining: dict[str, float] = {}

    for ticker, buy_list in buys.items():
        # FIFO lot matching
        lots = [{"qty": b["quantity"], "price": b["price"]} for b in buy_list]
        total_cost = 0.0
        total_qty = 0.0

        for b in buy_list:
            total_cost += b["quantity"] * b["price"] + b["fees"]
            total_qty += b["quantity"]

        realized = 0.0
        remaining_lots = list(lots)  # shallow copy

        for sell in sells.get(ticker, []):
            qty_to_match = sell["quantity"]
            sell_price = sell["price"]

            while qty_to_match > 0 and remaining_lots:
                lot = remaining_lots[0]
                match_qty = min(qty_to_match, lot["qty"])
                realized += match_qty * (sell_price - lot["price"]) - sell["fees"] * (match_qty / sell["quantity"]) if sell["quantity"] > 0 else 0
                lot["qty"] -= match_qty
                qty_to_match -= match_qty
                if lot["qty"] <= 0:
                    remaining_lots.pop(0)

        # Remaining position
        rem_qty = sum(l["qty"] for l in remaining_lots)
        rem_cost = sum(l["qty"] * l["price"] for l in remaining_lots)
        remaining_qty[ticker] = rem_qty
        cost_basis_remaining[ticker] = rem_cost
        realized_pnl_by_ticker[ticker] = realized

    # Build response
    items: list[PnLItem] = []
    for ticker in set(list(buys.keys()) + list(req.current_prices.keys())):
        qty = remaining_qty.get(ticker, 0)
        cb = cost_basis_remaining.get(ticker, 0)
        avg_cost = cb / qty if qty > 0 else 0
        price = req.current_prices.get(ticker, 0)
        mv = qty * price
        unrealized = mv - cb
        realized = realized_pnl_by_ticker.get(ticker, 0)
        total_ret = (unrealized + realized) / cb if cb > 0 else 0

        items.append(PnLItem(
            ticker=ticker,
            quantity=round(qty, 6),
            cost_basis=round(cb, 2),
            avg_cost=round(avg_cost, 2),
            market_value=round(mv, 2),
            unrealized_pnl=round(unrealized, 2),
            realized_pnl=round(realized, 2),
            total_return_pct=round(total_ret * 100, 2),
        ))

    total_cb = sum(i.cost_basis for i in items)
    total_mv = sum(i.market_value for i in items)
    total_unreal = sum(i.unrealized_pnl for i in items)
    total_real = sum(i.realized_pnl for i in items)
    total_ret = ((total_mv + total_real - total_cb) / total_cb * 100) if total_cb > 0 else 0

    txns = pv.ref("other", None, "Transactions entered by the user (buys and sells, with fees)",
                  note="User-entered records, not provider data.")
    prices = pv.ref("other", None, "Current prices sent with the request (current_prices)",
                    note="Supplied by the caller; the backend does not fetch quotes here. A ticker with no price "
                         "is valued at 0.")
    prov: dict = {
        "*": pv.derived("First-in-first-out lot matching over the user's transactions, valued at the supplied prices",
                        [txns, prices], title="Transaction P&L"),
        "total_cost_basis": pv.derived("sum of the items' cost_basis", ["*"], title="Total cost basis"),
        "total_market_value": pv.derived("sum of the items' market_value", ["*"], title="Total market value"),
        "total_unrealized_pnl": pv.derived("sum of the items' unrealized_pnl", ["*"], title="Total unrealised P&L"),
        "total_realized_pnl": pv.derived("sum of the items' realized_pnl", ["*"], title="Total realised P&L"),
        "total_return_pct": pv.derived("(total_market_value + total_realized_pnl − total_cost_basis) ÷ "
                                       "total_cost_basis × 100", ["*"], title="Total return"),
    }
    for it in items:
        t = it.ticker
        prov[f"items.{t}.quantity"] = pv.derived(
            "bought quantity − sold quantity, matched first-in-first-out (a ticker with sells but no buys is ignored)",
            [txns], title="Quantity held")
        prov[f"items.{t}.cost_basis"] = pv.derived(
            "Σ remaining lot quantity × buy price after FIFO matching; buy fees are not included", [txns],
            title="Cost basis")
        prov[f"items.{t}.avg_cost"] = pv.derived("cost_basis ÷ quantity", [f"items.{t}.cost_basis"], title="Average cost")
        prov[f"items.{t}.market_value"] = pv.derived("quantity × the price supplied in current_prices", [prices],
                                                     title="Market value")
        prov[f"items.{t}.unrealized_pnl"] = pv.derived("market_value − cost_basis", [f"items.{t}.market_value"],
                                                       title="Unrealised P&L")
        prov[f"items.{t}.realized_pnl"] = pv.derived(
            "Σ over matched lots of matched quantity × (sell price − lot buy price) − the sell's fees pro-rated by "
            "matched quantity", [txns], title="Realised P&L")
        prov[f"items.{t}.total_return_pct"] = pv.derived(
            "(unrealized_pnl + realized_pnl) ÷ remaining cost_basis × 100 (0 when nothing is left)",
            [f"items.{t}.unrealized_pnl", f"items.{t}.realized_pnl"], title="Total return")

    return PnLResponse(
        items=items,
        total_cost_basis=round(total_cb, 2),
        total_market_value=round(total_mv, 2),
        total_unrealized_pnl=round(total_unreal, 2),
        total_realized_pnl=round(total_real, 2),
        total_return_pct=round(total_ret, 2),
        provenance=pv.attach({}, prov)["provenance"],
    )
