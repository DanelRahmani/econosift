"""Portfolio builder: aggregate performance & risk for a basket of holdings."""
from __future__ import annotations

import asyncio
from typing import Optional
from datetime import date as date_type

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..db_models import PortfolioTransaction
from ..services import yfinance_service as yfs
from ..services import portfolio as port
from ..services.discount_rates import risk_free_rate

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

    result = port.analyze(frame, holdings, bench_series, req.risk_free)
    result["benchmark"] = bench

    # Add benchmark comparison series (base-100 ^GSPC / AGG)
    result["benchmarkSeries"] = port.benchmark_series(frame, req.period)

    return result


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

    return {"drawdownSeries": port.drawdown_series(port_ret)}


@router.post("/benchmarks")
async def benchmarks(req: PortfolioRequest):
    """Base-100 cumulative return series for ^GSPC and AGG."""
    holdings = _normalise(req.holdings)
    frame = await _load_frame(holdings, req.period, extra=(_BENCH_COL, _AGG_COL))
    if frame is None:
        return {"gspc": [], "agg": []}
    return port.benchmark_series(frame, req.period)


@router.post("/correlation")
async def correlation(req: PortfolioRequest):
    """Pairwise Pearson correlation matrix for portfolio holdings."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"tickers": [], "matrix": []}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.correlation_matrix(holdings, frame)


@router.post("/risk-contribution")
async def risk_contribution(req: PortfolioRequest):
    """Marginal and percentage risk contribution per holding."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.risk_contribution(holdings, frame)


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

    return port.capm_attribution(holdings, frame, bench, req.risk_free)


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

    return port.rolling_portfolio_metrics(holdings, frame, bench, req.risk_free, req.window)


@router.post("/kelly")
async def kelly(req: PortfolioRequest):
    """Kelly criterion fractions for each holding (on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return []

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.kelly_criterion(holdings, frame)


@router.post("/ff")
async def fama_french(req: FFRequest):
    """Fama-French factor attribution for the portfolio (on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return _empty("no holdings")

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.ff_attribution_portfolio(holdings, frame, req.model, req.risk_free)


@router.post("/frontier")
async def frontier(req: PortfolioRequest):
    """Mean-variance efficient frontier (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"frontier": [], "error": "no holdings"}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.efficient_frontier(holdings, frame)


@router.post("/montecarlo")
async def montecarlo(req: PortfolioRequest):
    """Monte Carlo random weight simulation — risk/return cloud (compute-on-demand)."""
    holdings = _normalise(req.holdings)
    if not holdings:
        return {"points": [], "maxSharpe": {}}

    frame = await _load_frame(holdings, req.period)
    if frame is None:
        return _empty()

    return port.monte_carlo_weights(holdings, frame)


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
    return port.black_litterman(holdings, frame, views, req.risk_free)


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

    return port.stress_test_portfolio(holdings, frame, bench)


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

    return {
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
    }


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

    return PnLResponse(
        items=items,
        total_cost_basis=round(total_cb, 2),
        total_market_value=round(total_mv, 2),
        total_unrealized_pnl=round(total_unreal, 2),
        total_realized_pnl=round(total_real, 2),
        total_return_pct=round(total_ret, 2),
    )
