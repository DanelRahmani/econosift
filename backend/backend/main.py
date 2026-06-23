"""Axiom Finance FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    market, valuation, ratios, search, macro,
    portfolio, screener, admin,
)

app = FastAPI(title="Axiom Finance API", version="1.0.0")

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
