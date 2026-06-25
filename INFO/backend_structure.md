# Axiom Finance — Backend File Structure

Root: `backend/`

```
backend/
├── Dockerfile                  # Python 3.12 image: pip install requirements → uvicorn
├── requirements.txt            # All Python dependencies
├── pytest.ini                  # pytest config (asyncio mode, test paths)
│
├── data/
│   └── cb_meetings.json        # Pre-shipped 2026 central bank meeting dates
│                               # (Fed, ECB, BoE, BoJ) — no API needed
│
├── tests/                      # pytest test suite
│   ├── conftest.py             # Shared fixtures (FastAPI TestClient, mock data)
│   ├── test_smoke.py           # Smoke tests: every router returns HTTP 200
│   ├── test_dcf_engine.py      # Two-stage DCF engine unit tests
│   ├── test_valuation_engine.py     # 8-model valuation + composite scoring
│   ├── test_fundamentals.py    # Piotroski, Beneish, Ohlson, DuPont, ROIC
│   ├── test_analyst_service.py # Analyst ratings + price target parsing
│   ├── test_fama_french.py     # FF3/FF5 factor loading regression
│   ├── test_fx_service.py      # FX rate fetching + base conversion
│   ├── test_regime_service.py  # Macro regime classification rules
│   ├── test_discount_rates.py  # WACC / risk-free rate helpers
│   ├── test_calendar_service.py     # Earnings + macro + IPO event merging
│   ├── test_constituents.py    # Wikipedia MediaWiki API index parsing
│   ├── test_dashboard_services.py   # Breadth, indices, Fear & Greed, movers
│   ├── test_screener_universe.py    # Universe loading + Parquet cache
│   └── test_treemap.py         # Treemap tile generation + drill-down
│
└── backend/                    # Python package (importable as `backend`)
    ├── __init__.py
    ├── main.py                 # FastAPI app factory: mounts all routers, CORS config
    ├── config.py               # Settings loaded from environment (.env)
    ├── models.py               # Pydantic request/response models
    ├── cache.py                # @cached / @async_cached decorators (cachetools TTL)
    │
    ├── data/
    │   ├── damodaran_erp_2026.json  # Damodaran equity risk premia by country/sector
    │   └── sector_multiples.json    # Damodaran sector valuation multiples
    │
    ├── routers/                # FastAPI routers — one file per feature area
    │   ├── __init__.py
    │   ├── admin.py            # /api/admin — cache stats, source health, latency P50/P95
    │   ├── calendar.py         # /api/calendar — earnings, macro, IPO, dividend events
    │   ├── dashboard.py        # /api/dashboard/breadth|indices|fear-greed|movers
    │   ├── macro.py            # /api/macro/* — 10 macro sub-tab endpoints
    │   │                       #   /rates, /inflation, /employment, /housing,
    │   │                       #   /commodities, /fx/heatmap, /fx/ppp,
    │   │                       #   /leading, /financial-conditions, /positioning
    │   ├── market.py           # /api/market/* — price, risk, ratios, news, search
    │   ├── market_data.py      # /api/market/13f, /api/market/form4
    │   ├── options.py          # /api/options/* — expiries, ivmetrics, chain,
    │   │                       #   termstructure, smile, oiprofile, montecarlo
    │   ├── portfolio.py        # /api/portfolio/* — 13 endpoints:
    │   │                       #   analyze, correlation, risk-contribution, capm,
    │   │                       #   rolling, kelly, ff, frontier, montecarlo,
    │   │                       #   blacklitterman, stress
    │   ├── ratios.py           # /api/ratios — 23 fundamental ratios
    │   ├── risk.py             # /api/risk/* — rolling, extended, correlation,
    │   │                       #   garch, hurst, ou, cointegration, montecarlo, stress
    │   ├── screener.py         # /api/screener/universe|presets|status|refresh
    │   ├── search.py           # /api/search — ticker autocomplete
    │   ├── sector.py           # /api/sector/returns|fundamentals|rotation|drill
    │   ├── snowflake.py        # /api/snowflake (single) + /api/snowflake/batch
    │   ├── treemap.py          # /api/treemap?index=&period=
    │   └── valuation.py        # /api/valuation/full|dcf|factors
    │
    ├── services/               # Business logic — called by routers
    │   ├── __init__.py
    │   │
    │   # --- Market data & pricing ---
    │   ├── yfinance_service.py      # Low-level yfinance wrappers (price, info,
    │   │                            #   options, news, market cap fan-out)
    │   ├── fx_service.py            # Frankfurter FX rates + base conversion
    │   ├── indices_service.py       # ~25 global indices (price + return)
    │   ├── movers_service.py        # Top gainers / losers from screener cache
    │   │
    │   # --- Fundamentals & valuation ---
    │   ├── fundamentals.py          # Piotroski F-Score, Beneish M-Score,
    │   │                            #   Ohlson O-Score, DuPont, ROIC, CCC
    │   ├── valuation_engine.py      # 8-model valuation (DCF, DDM, EV/EBITDA,
    │   │                            #   P/E, P/B, P/S, Graham, CAPM) + composite
    │   ├── dcf_engine.py            # Two-stage DCF with terminal value
    │   ├── discount_rates.py        # WACC, CAPM risk-free rate (FRED DGS10), ERP
    │   ├── analyst_service.py       # Analyst ratings + consensus price targets
    │   ├── fama_french.py           # FF3/FF5 factor loading via Ken French CSVs
    │   ├── snowflake_service.py     # 5-axis composite score (0–10 per axis),
    │   │                            #   sector-normalised; full + batch modes
    │   │
    │   # --- Risk ---
    │   ├── metrics.py               # Core risk metrics: Sharpe, Sortino, VaR,
    │   │                            #   Beta, MaxDD, CVaR
    │   ├── advanced_risk.py         # GARCH(1,1), Hurst exponent, Ornstein-Uhlenbeck,
    │   │                            #   Engle-Granger cointegration, Monte Carlo GBM,
    │   │                            #   historical stress scenarios
    │   │
    │   # --- Options ---
    │   ├── options_engine.py        # Black-Scholes pricing + 5 Greeks, IV backsolve
    │   │                            #   (brentq), CRR binomial tree, IV30/Rank/Pct,
    │   │                            #   Max Pain, term structure, smile
    │   │
    │   # --- Portfolio ---
    │   ├── portfolio.py             # 12 portfolio functions: performance, correlation,
    │   │                            #   risk contribution, CAPM, rolling, Kelly,
    │   │                            #   Fama-French, efficient frontier (SLSQP),
    │   │                            #   Monte Carlo, Black-Litterman, stress testing
    │   │
    │   # --- Market structure ---
    │   ├── breadth_service.py       # Advance/decline, new highs/lows, McClellan
    │   ├── feargreed_service.py     # 7-signal Fear & Greed composite index
    │   ├── constituents.py          # Index constituents via Wikipedia MediaWiki API
    │   │                            #   (S&P 500, Nasdaq-100, Dow 30); weekly cache
    │   ├── treemap_service.py       # Treemap tile data: mcap, return, GICS sector/
    │   │                            #   industry; threaded yfinance fan-out
    │   ├── screener_service.py      # High-performance screener: 20+ signal presets,
    │   │                            #   9 result views, reads from Parquet/SQLite cache
    │   ├── screener_cache.py        # Overnight Parquet/SQLite warmer for screener
    │   ├── sector_service.py        # SPDR ETF returns, fundamentals, rotation clock,
    │   │                            #   industry drill-down (top-3 per GICS industry)
    │   │
    │   # --- Macro ---
    │   ├── macro_service.py         # Core macro: GDP, CPI, unemployment waterfall
    │   │                            #   across 7 sources for 20+ countries
    │   ├── macro_expansion_service.py   # Extended macro: housing, employment, leading
    │   │                            #   indicators, financial conditions, IS-LM-PC
    │   ├── rates_service.py         # Yield curve (3M–30Y), TIPS breakevens, real
    │   │                            #   yields, credit spreads, Taylor Rule, ACM term-premium
    │   ├── regime_service.py        # Macro regime classification (expansion /
    │   │                            #   slowdown / stagflation / recession)
    │   ├── cot_service.py           # CFTC COT report — 6 key contracts, net
    │   │                            #   speculator positioning, COT Index
    │   │
    │   # --- Events & filings ---
    │   ├── calendar_service.py      # Unified event schema: macro + earnings +
    │   │                            #   dividends + IPOs; 60-min cache
    │   ├── finnhub_service.py       # Thin Finnhub wrapper (IPOs, economic events,
    │   │                            #   earnings estimates)
    │   ├── edgar_service.py         # SEC EDGAR: Form 4 insider transactions,
    │   │                            #   13F institutional holdings
    │   │
    │   # --- Utilities ---
    │   └── ... (helpers imported by above)
    │
    └── sources/                # Macro data source adapters (waterfall pattern)
        ├── __init__.py
        ├── source_fred.py           # FRED (Federal Reserve) — US series
        ├── source_worldbank.py      # World Bank (wbgapi) — global GDP, CPI
        ├── source_imf.py            # IMF (imfp) — WEO projections
        ├── source_ecb.py            # ECB (ecbdata) — Eurozone series
        ├── source_dbnomics.py       # DB.nomics — multi-source aggregator
        ├── source_datareader.py     # pandas-datareader fallback
        └── source_frankfurter.py    # Frankfurter API — ECB FX rates
```

## Request Flow

```
Browser → Nginx (:80)
           ├── /api/* → backend (uvicorn :8000) → router → service → external API
           └── /*     → frontend (Next.js :3000) → React page
```

## Caching Strategy

All external API calls are wrapped with `@cached(TTLCache(maxsize=..., ttl=3600))` from `cache.py`.
Heavy compute endpoints (GARCH, Monte Carlo, Black-Litterman) are **intentionally uncached** — 
they are triggered by the user via a Calculate / Run button, not on page load.
The screener cache is a separate overnight Parquet/SQLite warmer (`screener_cache.py`) 
that pre-fetches the full universe so screener queries return instantly during the day.
