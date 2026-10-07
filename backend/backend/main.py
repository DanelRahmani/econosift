"""EconoSift FastAPI application entrypoint."""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from . import cache

STALE_HEADER = "X-Data-Stale"
# Sent by a page's Refresh button (P1-20): this GET recomputes the cached data
# it reads instead of serving it (see cache.set_refresh).
REFRESH_HEADER = "X-Cache-Refresh"

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
    from .services import errorlog
    # Capture source failures in memory so the Admin page can surface them;
    # every service degrades quietly by design, which otherwise makes a broken
    # provider indistinguishable from a genuinely empty result.
    errorlog.install()
    init_db()
    threading.Thread(target=screener_service.warm_all, daemon=True).start()
    scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


async def _start_fetch_log(request: Request, response: Response) -> None:
    # Must be async: it runs in the request's own task, so the log it opens is
    # the one the endpoint and its threads report cache reads to.
    def on_stale(fetched_at: float) -> None:
        # Data past its TTL was served while it refreshes in the background;
        # the header carries the oldest such fetch time for the UI's badge.
        stamp = datetime.fromtimestamp(fetched_at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prev = response.headers.get(STALE_HEADER)
        if prev is None or stamp < prev:
            response.headers[STALE_HEADER] = stamp

    cache.start_fetch_log(on_stale)
    cache.set_refresh(request.method == "GET" and request.headers.get(REFRESH_HEADER) == "1")


app = FastAPI(title="EconoSift API", version="1.0.0", lifespan=lifespan,
              dependencies=[Depends(_start_fetch_log)])

# EconoSift has no authentication by design — it is a single-user, self-hosted app.
# That makes the CORS policy load-bearing: with allow_origins=["*"] any page you
# happened to visit could preflight and PUT /api/admin/config, which writes API
# keys to .env. Binding nginx to loopback does not help there, because a browser
# on this machine can reach loopback. So the origin list is explicit.
#
# The Tauri desktop build serves a static export, so its page origin is
# tauri://localhost (macOS/Linux) or http://tauri.localhost (Windows) while it
# calls the backend on 127.0.0.1:8000 — both must stay allowed or the desktop
# app breaks. ECONOSIFT_CORS_ORIGINS (legacy AXIOM_CORS_ORIGINS also works)
# extends the list for anyone
# tunnelling in from another host.
_DEFAULT_ORIGINS = [
    "http://localhost",
    "http://localhost:80",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "tauri://localhost",
    "http://tauri.localhost",
]
_extra_origins = [
    o.strip()
    for o in (
        os.getenv("ECONOSIFT_CORS_ORIGINS")
        or os.getenv("AXIOM_CORS_ORIGINS", "")
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _extra_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # The desktop build calls the backend cross-origin; without this the
    # browser hides the header from fetch().
    expose_headers=[STALE_HEADER],
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
