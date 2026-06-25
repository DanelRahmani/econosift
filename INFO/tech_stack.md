# Axiom Finance — Tech Stack

## Overview

Axiom Finance is a self-hosted financial analytics dashboard. The system is split into a Python backend API and a Next.js frontend, connected through an Nginx reverse proxy, all orchestrated with Docker Compose.

---

## Backend

| Layer | Technology | Details |
|---|---|---|
| Language | Python 3.12 | |
| Web framework | FastAPI | Async-capable, auto-generates OpenAPI docs |
| ASGI server | Uvicorn (standard) | Runs inside the backend Docker container |
| Data — market | yfinance ≥ 0.2.40 | Price history, fundamentals, options chains, earnings |
| Data — macro (US) | fredapi | FRED economic time series (GDP, CPI, unemployment, yields, etc.) |
| Data — macro (global) | wbgapi, imfp, ecbdata, dbnomics, eurostat, pandas-datareader | 7-source waterfall covering World Bank, IMF, ECB, DB.nomics, Eurostat |
| Data — FX rates | frankfurter (HTTP) | Free ECB-sourced currency rates |
| Data — filings | edgartools | EDGAR Form 4 (insider activity) and 13F (institutional holders) |
| Data — universe | financedatabase, wikitextparser | FinanceDatabase small-cap universe; MediaWiki API for index constituents |
| Data — events | finnhub-python | IPO calendar, economic events, earnings estimates |
| Numerical / stats | numpy, scipy, arch | Array math, optimization (SLSQP), GARCH(1,1) volatility |
| Data wrangling | pandas, pyarrow, openpyxl | DataFrames, Parquet screener cache, Excel reading |
| Caching | cachetools | In-process TTL cache (60 min default) via `@cached` / `@async_cached` |
| HTTP client | httpx | Async external HTTP calls |
| Config | python-dotenv | Loads `.env` (FRED_API_KEY, FINNHUB_API_KEY, etc.) |
| Testing | pytest, pytest-asyncio | Unit + async endpoint tests |

---

## Frontend

| Layer | Technology | Details |
|---|---|---|
| Language | TypeScript 5.5 | Strict mode |
| Framework | Next.js 14.2 (App Router) | File-based routing under `app/` |
| UI library | React 18.3 | |
| Styling | Tailwind CSS 3.4 | Utility-first; dark/light theme via `ThemeProvider` |
| Charts — financial | Recharts 2.12 | Line, area, bar, scatter, radar (all SVG-based) |
| Charts — treemap | d3-hierarchy 3, d3-scale 4, d3-shape 3 | Squarified treemap rendered to `<canvas>` |
| Build tooling | PostCSS, Autoprefixer | Tailwind processing pipeline |
| E2E testing | Playwright 1.61 | Browser automation tests |

---

## Infrastructure

| Component | Technology | Details |
|---|---|---|
| Containerisation | Docker Compose | Three services: `backend`, `frontend`, `nginx` |
| Reverse proxy | Nginx (Alpine image) | Routes `/api/*` → backend:8000, everything else → frontend:3000 |
| Backend image | Python 3.12 (Dockerfile in `backend/`) | |
| Frontend image | Node (Dockerfile in `frontend/`) | Runs `next build` then `next start` |

---

## External Data Sources (no paid APIs required)

| Source | What it provides | Key? |
|---|---|---|
| Yahoo Finance (yfinance) | Prices, fundamentals, options, news | No |
| FRED (Federal Reserve) | US macro series (GDP, CPI, yields…) | Optional free key |
| World Bank (wbgapi) | Global GDP, inflation, unemployment | No |
| IMF (imfp) | WEO projections, Article IV data | No |
| ECB (ecbdata) | Eurozone rates, HICP | No |
| DB.nomics | Multi-source macro aggregator | No |
| Eurostat | EU statistical data | No |
| Frankfurter | FX rates (ECB-sourced) | No |
| EDGAR (edgartools) | SEC filings (13F, Form 4) | No |
| Finnhub | IPOs, earnings, economic calendar | Optional free key |
| Ken French Data Library | Fama-French factor returns (CSV) | No |
| CFTC | COT positioning data (CSV) | No |
