"""Axiom Finance FastAPI application entrypoint."""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    market, valuation, ratios, search, macro,
    portfolio, screener, admin, dashboard, treemap, calendar, risk, options,
    market_data, snowflake,
)
from .services import screener_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=screener_service.warm_all, daemon=True).start()
    yield


app = FastAPI(title="Axiom Finance API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
