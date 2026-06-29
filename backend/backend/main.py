"""Axiom Finance FastAPI application entrypoint."""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import DeduplicationMiddleware
from .routers import (
    market, valuation, ratios, search, macro,
    portfolio, screener, admin, dashboard, treemap, calendar, risk, options,
    market_data, snowflake, sector, technicals, atlas, research, credit,
    yield_curve, policy, sovereign, scenario, wiki, corporate, dividend, insider,
    mergers, factbook, crossborder, stability, ai,
)
from .services import screener_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .database import init_db
    from .services.jobs import start_scheduler
    init_db()
    threading.Thread(target=screener_service.warm_all, daemon=True).start()
    scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Axiom Finance API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(DeduplicationMiddleware)


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok"}


app.include_router(market.router)
app.include_router(valuation.router)
app.include_router(ratios.router)
app.include_router(search.router)
app.include_router(macro.router)
app.include_router(portfolio.router)
app.include_router(screener.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(treemap.router)
app.include_router(calendar.router)
app.include_router(risk.router)
app.include_router(options.router)
app.include_router(market_data.router)
app.include_router(snowflake.router)
app.include_router(sector.router)
app.include_router(technicals.router)
app.include_router(atlas.router)
app.include_router(research.router)
app.include_router(credit.router)
app.include_router(yield_curve.router)
app.include_router(policy.router)
app.include_router(sovereign.router)
app.include_router(scenario.router)
app.include_router(wiki.router)
app.include_router(corporate.router)
app.include_router(dividend.router)
app.include_router(insider.router)
app.include_router(mergers.router)
app.include_router(factbook.router)
app.include_router(crossborder.router)
app.include_router(stability.router)
app.include_router(ai.router)
