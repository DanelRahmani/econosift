# Axiom Finance — Tech Stack (Phases 0–19)

## Overview

Axiom Finance is a self-hosted financial analytics dashboard. The system is split into a Python backend API and a Next.js frontend, connected through an Nginx reverse proxy, all orchestrated with Docker Compose.

---

## Backend

| Layer | Technology | Details |
|---|---|---|
| Language | Python 3.12 | |
| Web framework | FastAPI | Async-capable, auto-generates OpenAPI docs |
| ASGI server | Uvicorn (standard) | Runs inside the backend Docker container |
| Data — market | yfinance ≥ 0.2.40 | Price history, fundamentals, options chains, earnings, news, calendar |
| Data — macro (US) | fredapi | FRED economic time series (GDP, CPI, unemployment, yields, DGS10, etc.) |
| Data — macro (global) | wbgapi, imfp, ecbdata, dbnomics, eurostat, pandas-datareader | 7-source waterfall covering World Bank, IMF, ECB, DB.nomics, Eurostat |
| Data — FX rates | frankfurter (HTTP) | Free ECB-sourced currency rates |
| Data — filings | edgartools | EDGAR Form 4 (insider activity) and 13F (institutional holders) |
| Data — universe | financedatabase, wikitextparser | FinanceDatabase small-cap universe; MediaWiki API for index constituents |
| Data — events | finnhub-python | IPO calendar, economic events, earnings estimates |
| Numerical / stats | numpy, scipy, arch | Array math, optimization (SLSQP), GARCH(1,1) volatility, stats distributions |
| Data wrangling | pandas, pyarrow, openpyxl | DataFrames, Parquet screener cache, Excel reading |
| ORM | SQLAlchemy 2.0 | ORM models (DailyPrice, DailyQuote, DailyMacro, DailyFX, CacheEntry, JobExecution) |
| Database | SQLite (WAL mode) | Persistent storage: OHLCV backfill, cached fundamentals, macro data |
| Scheduling | APScheduler | Background jobs: daily price/quote/FX refresh, screener warm, backfill checks |
| Caching (in-memory) | cachetools | In-process TTL cache (60 min, 2048 maxsize) via `@cached` / `@async_cached` |
| Two-tier cache | HybridCache (memory → SQLite) | Composite endpoint: checks memory first, then SQLite, then yfinance |
| HTTP client | httpx, requests | Async external HTTP calls + sync fallbacks |
| Config | python-dotenv | Loads `.env` (FRED_API_KEY, FINNHUB_API_KEY, DATABASE_URL, etc.) |
| Testing | pytest, pytest-asyncio, httpx | 508+ unit + async endpoint tests with mock yfinance bundles |

---

## Frontend

| Layer | Technology | Details |
|---|---|---|
| Language | TypeScript 5.5 | Strict mode |
| Framework | Next.js 14.2 (App Router) | File-based routing under `app/` |
| UI library | React 18.3 | |
| Styling | Tailwind CSS 3.4 | Utility-first; dark/light theme via ThemeProvider + CSS custom properties |
| Charts — general | Recharts 2.12 | Line, area, bar, scatter, radar (all SVG-based) |
| Charts — treemap | d3-hierarchy 3, d3-scale 4, d3-shape 3 | Squarified treemap rendered to `<canvas>` |
| Charts — atlas | react-simple-maps | Choropleth world map with react-geo-tools |
| State / data fetching | @tanstack/react-query 5 | Client-side caching, stale-while-revalidate, query invalidation |
| Build tooling | PostCSS, Autoprefixer | Tailwind processing pipeline |
| E2E testing | Playwright 1.61 | Browser automation tests |

---

## Infrastructure

| Component | Technology | Details |
|---|---|---|
| Containerisation | Docker Compose | Three services: `backend`, `frontend`, `nginx` |
| Reverse proxy | Nginx (Alpine image) | Routes `/api/*` → backend:8000, everything else → frontend:3000; gzip enabled |
| Backend image | Python 3.12 (Dockerfile in `backend/`) | |
| Frontend image | Node 20 (Dockerfile in `frontend/`) | Runs `next build` then `next start` |
| Storage | Docker volumes | SQLite database persisted at `./data/axiomfinance.db`; Parquet cache at `./data/screener_cache/` |

---

## External Data Sources (no paid APIs required)

| Source | What it provides | Key? |
|---|---|---|
| Yahoo Finance (yfinance) | Prices, fundamentals, options, news, calendar, earnings | No |
| FRED (Federal Reserve) | US macro series (GDP, CPI, yields, DGS10, TIPS, breakevens…) | Optional free key ✅ SET |
| World Bank (wbgapi) | Global GDP, inflation, unemployment, country risk KPIs | No |
| IMF (imfp) | WEO projections, Article IV data | No |
| ECB (ecbdata) | Eurozone rates, HICP | No |
| DB.nomics | Multi-source macro aggregator | No |
| Eurostat | EU statistical data | No |
| Frankfurter | FX rates (ECB-sourced) | No |
| EDGAR (edgartools) | SEC filings (13F, Form 4) | No |
| Finnhub | IPOs, earnings, economic calendar | Optional free key ✅ SET |
| Ken French Data Library | Fama-French factor returns (CSV) | No |
| CFTC | COT positioning data (CSV) | No |
| OECD | Immediate central-bank rates, 3-month interbank rates (IRSTCI01*, IR3TIB01*) | No |
| Wikipedia MediaWiki API | S&P 500 / Nasdaq-100 / Dow 30 constituents | No |

---

## 11 Core Pages (full investment research stack)

| Page | Route | Content |
|------|-------|---------|
| **Dashboard** | `/dashboard` | Market breadth, global indices, Fear & Greed, top movers |
| **Markets** | `/markets` | Price charts, technicals (MACD/BB/Ichimoku/Fib/Pivots), valuation (8 models + DCF + Snowflake), ratios, risk (VaR/Sharpe/Beta/GARCH), options & IV, news, 13F/Form 4 |
| **Screener** | `/screener` | S&P 500 / Nasdaq 100 / Dow 30 universe, 20+ preset signals, 9 result tabs, overnight cache |
| **Portfolio** | `/portfolio` | Efficient frontier, Black-Litterman, Monte Carlo, Fama-French attribution, stress testing |
| **Risk** | `/risk` | Rolling metrics, GARCH, Hurst, cointegration, historical stress scenarios |
| **Options** | `/options` | IV analytics (IV30/Rank/Percentile), Greeks, term structure, OI profile, binomial pricing |
| **Sectors** | `/sectors` | SPDR ETF returns, rotation clock, industry drill-down |
| **Treemap** | `/treemap` | S&P 500 / Nasdaq / Dow squarified treemap |
| **Calendar** | `/calendar` | Earnings, dividends, macro releases, IPOs, CB meetings |
| **Macro** | `/macro` | 12-tab hub: rates, inflation, growth, housing, commodities, FX, leading indicators, financial conditions, COT, Econometric Lab, Country Risk, Central Banks |
| **Atlas** | `/atlas` | Choropleth world map: 6 macro indicators, ~200 countries, 2000–2024, year slider, regional blocs |

## 4 Additional Pages (Phase 18A — Macro-Financial Intelligence)

| Page | Route | Content |
|------|-------|---------|
| **Research** | `/research` | Risk Parity, FX Carry, Cross-Sectional Momentum, Realized Moments |
| **Yield Curve** | `/yield` | US spot curve, TIPS real yields, breakevens, ACM term premium |
| **Policy Tracker** | `/policy` | CB divergence, G10 carry differentials, policy surprises |
| **Sovereign Risk** | `/sovereign` | 6-KPI traffic-light rankings, ~200 countries |

## 1 Deferred Page (Phase 18B)

| Page | Route | Content |
|------|-------|---------|
| **Scenario Lab** | `/scenario` | Stress scenario designer (basic stub, deferred) |
