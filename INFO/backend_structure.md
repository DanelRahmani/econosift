# Axiom Finance — Backend File Structure (Phases 0–19)

Root: `backend/`

```
backend/
├── Dockerfile                  # Python 3.12 image: pip install requirements → uvicorn
├── requirements.txt            # All Python dependencies (yfinance, fastapi, numpy, scipy, SQLAlchemy, APScheduler, etc.)
├── pytest.ini                  # pytest config (asyncio mode, test paths)
│
├── data/
│   ├── cb_meetings.json        # Pre-shipped 52 central bank meeting dates (Fed, ECB, BoE, BoJ, BoC, RBA, SNB)
│   └── .gitkeep                # SQLite DB lives here at runtime: data/axiomfinance.db
│
├── backend/                    # Python package (importable as `backend`)
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory: mounts 25 routers, CORS config, lifespan (DB init, scheduler)
│   ├── config.py               # Settings loaded from environment (FRED_API_KEY, FINNHUB_API_KEY, DATABASE_URL)
│   ├── models.py               # Pydantic request/response models
│   ├── cache.py                # @cached / @async_cached decorators (cachetools TTL, 60-min default, 2048 maxsize)
│   ├── database.py             # SQLAlchemy engine + SessionLocal + init_db (SQLite WAL mode, auto-creates tables)
│   ├── db_models.py            # 8 ORM tables: DailyPrice, DailyQuote, DailyMacro, DailyFX, CacheEntry, JobExecution, etc.
│   ├── middleware.py           # DeduplicationMiddleware stub (future: duplicate request guard)
│   │
│   ├── data/
│   │   ├── damodaran_erp_2026.json  # Damodaran equity risk premia by country/sector
│   │   └── sector_multiples.json    # Damodaran sector valuation multiples
│   │
│   ├── routers/                # 25 FastAPI routers — one file per feature area
│   │   ├── __init__.py
│   │   ├── admin.py            # /api/admin — cache stats, source health, latency P50/P95, performance metrics
│   │   ├── atlas.py            # /api/atlas/timeline|snapshot — choropleth world map (6 macro indicators, ~200 countries)
│   │   ├── calendar.py         # /api/calendar — earnings, macro, IPO, dividend, CB meeting events
│   │   ├── credit.py           # /api/credit/pulse — credit market pulse (spreads, yields, debt metrics)
│   │   ├── dashboard.py        # /api/dashboard/breadth|indices|fear-greed|movers
│   │   ├── macro.py            # /api/macro/* — 12 macro sub-tab endpoints: rates, inflation, employment,
│   │   │                       #   housing, commodities, fx/heatmap, fx/ppp, leading, financial-conditions,
│   │   │                       #   positioning, country-risk, central-banks, lab (econometric)
│   │   ├── market.py           # /api/market/* — prices, quote, risk, sectors, events, news
│   │   ├── market_data.py      # /api/market/13f, /api/market/form4 — EDGAR filings
│   │   ├── options.py          # /api/options/* — expiries, ivmetrics, chain, termstructure, smile, oiprofile, montecarlo
│   │   ├── policy.py           # /api/policy/tracker — central bank divergence, G10 carry differentials, policy surprises
│   │   ├── portfolio.py        # /api/portfolio/* — 13 endpoints: analyze, correlation, risk-contribution,
│   │   │                       #   capm, rolling, kelly, ff, frontier, montecarlo, blacklitterman, stress
│   │   ├── ratios.py           # /api/ratios — 23 fundamental ratios + Z-score, beta, Sharpe, Sortino
│   │   ├── research.py         # /api/research/* — risk-parity, carry, momentum, realized-moments, cross-section
│   │   ├── risk.py             # /api/risk/* — rolling, extended, correlation, garch, hurst, ou, cointegration,
│   │   │                       #   montecarlo, stress
│   │   ├── scenario.py         # /api/scenario/run — stress scenario designer/lab (Phase 18B deferred, stub)
│   │   ├── screener.py         # /api/screener/universe|presets|status|refresh — cached multi-index screener
│   │   ├── search.py           # /api/search — ticker autocomplete (yfinance + local cache)
│   │   ├── sector.py           # /api/sector/returns|fundamentals|rotation|drill
│   │   ├── snowflake.py        # /api/snowflake (single) + /api/snowflake/batch — 5-axis composite score
│   │   ├── sovereign.py        # /api/sovereign/risk — sovereign risk rankings (6 KPI traffic-light, ~200 countries)
│   │   ├── technicals.py       # /api/technicals — SMA, EMA, MACD, RSI, BB, Ichimoku, Fibonacci, Pivot Points
│   │   ├── treemap.py          # /api/treemap?index=&period= — S&P 500 / NDX / Dow squarified treemap
│   │   ├── valuation.py        # /api/valuation/full|dcf|factors — 8-model valuation + CAPM + Axiom Fair Value
│   │   └── yield_curve.py      # /api/yield/curve — US spot curve, TIPS real yields, breakevens, ACM term premium
│   │
│   ├── services/               # Business logic — called by routers (45+ services)
│   │   ├── __init__.py
│   │   │
│   │   # --- Market data & pricing ---
│   │   ├── yfinance_service.py      # Low-level yfinance wrappers: close/volume frames, info+statements bundle,
│   │   │                            #   quotes (fast_info), market caps (threaded), news, events, retry logic
│   │   ├── fx_service.py            # Frankfurter FX rates + base conversion
│   │   ├── indices_service.py       # ~25 global indices (price + return) via yfinance
│   │   ├── movers_service.py        # Top gainers / losers from screener cache
│   │   │
│   │   # --- Fundamentals & valuation ---
│   │   ├── fundamentals.py          # Piotroski F-Score (4/9 — needs multi-period to unlock 9/9),
│   │   │                            #   Beneish M-Score (always null — needs t-1 data),
│   │   │                            #   Ohlson O-Score, DuPont (3-factor + 5-factor), ROIC, CCC
│   │   ├── valuation_engine.py      # 8-model valuation (DCF Two-Stage, DDM Gordon Growth, Graham Formula,
│   │   │                            #   Graham Number, Peter Lynch/PEG, EV/EBITDA, RIM, EPV) + Axiom composite
│   │   ├── dcf_engine.py            # Two-stage DCF with terminal value, 3 scenarios, 7×7 sensitivity heatmap
│   │   ├── discount_rates.py        # WACC, CAPM cost of equity, risk-free rate (FRED DGS10 via fredapi/pandas-datareader),
│   │   │                            #   ERP (Damodaran country-by-country), tax rates, country detection
│   │   ├── analyst_service.py       # Analyst ratings + consensus price targets, earnings surprises,
│   │   │                            #   forward estimates (earnings/revenue) via yfinance DataFrames
│   │   ├── fama_french.py           # FF3/FF5 factor loading via Ken French CSVs (pandas-datareader)
│   │   ├── snowflake_service.py     # 5-axis composite score (Value/Growth/Performance/Health/Dividend),
│   │   │                            #   0–10 per axis, sector-normalised via percentile ranking; full + batch modes
│   │   │
│   │   # --- Risk ---
│   │   ├── metrics.py               # Core risk metrics: log_returns, Sharpe, Sortino, VaR/CVaR, Beta, CAPM,
│   │   │                            #   DCF single-stage, Altman Z-Score, 23 financial ratios compute_ratios()
│   │   ├── advanced_risk.py         # GARCH(1,1) via arch, Hurst exponent, Ornstein-Uhlenbeck mean-reversion,
│   │   │                            #   Engle-Granger cointegration, Monte Carlo GBM, historical stress scenarios
│   │   │
│   │   # --- Options ---
│   │   ├── options_engine.py        # Black-Scholes pricing + 5 Greeks (delta/gamma/theta/vega/rho), IV backsolve
│   │   │                            #   (brentq), CRR binomial tree (American), IV30/Rank/Percentile, Max Pain,
│   │   │                            #   term structure, IV smile, OI profile, Monte Carlo options pricing
│   │   │                            #   ⚠️ KNOWN BUG: IV30 returns ~0.001% (see FACT_CHECK.md)
│   │   │
│   │   # --- Portfolio ---
│   │   ├── portfolio.py             # 12 portfolio functions: performance, correlation, risk contribution,
│   │   │                            #   CAPM attribution, rolling metrics, Kelly criterion, Fama-French attribution,
│   │   │                            #   efficient frontier (SLSQP), Monte Carlo, Black-Litterman, stress testing
│   │   │
│   │   # --- Market structure ---
│   │   ├── breadth_service.py       # Advance/decline, new highs/lows, McClellan oscillator
│   │   ├── feargreed_service.py     # 7-signal Fear & Greed composite index
│   │   ├── constituents.py          # Index constituents via Wikipedia MediaWiki API + wikitextparser
│   │   │                            #   (S&P 500, Nasdaq-100, Dow 30); weekly cache via @cached
│   │   ├── treemap_service.py       # Treemap tile data: mcap, return%, GICS sector/industry;
│   │   │                            #   threaded yfinance fan-out, period mapping
│   │   ├── screener_service.py      # High-performance screener: 20+ signal presets (Chapter 7, 50/200 DMA,
│   │   │                            #   unusual volume, low float, etc.), 9 result views, cached universe
│   │   ├── screener_cache.py        # Overnight Parquet/SQLite warmer for screener universe;
│   │   │                            #   SQLite with upsert + fetch_ticker_fundamentals() per ticker
│   │   ├── sector_service.py        # SPDR ETF returns, fundamentals (P/E, P/B, yield, beta, vol),
│   │   │                            #   rotation clock (Stovall 4-phase), industry drill-down (top-3 per GICS)
│   │   │
│   │   # --- Technical Analysis ---
│   │   ├── technicals_service.py    # SMA, EMA, MACD, RSI, Bollinger Bands, Ichimoku Cloud,
│   │   │                            #   Fibonacci retracements, Pivot Points (Standard/Camarilla/Fib)
│   │   │
│   │   # --- Research (Quant Tools) ---
│   │   ├── risk_parity_service.py   # Risk parity: inverse-vol + ERC via SLSQP, monthly-rebalanced backtest vs 60/40
│   │   ├── carry_service.py         # G10 FX carry: carry table + long-top3/short-bottom3 backtest vs DXY
│   │   ├── momentum_service.py      # Cross-sectional momentum: 1M/3M/6M/12M-1M deciles, Dow/NDX/S&P
│   │   ├── realized_moments_service.py  # Garman-Klass realized variance + rolling skew/kurtosis + cross-section
│   │   ├── econ_lab_service.py      # Pooled OLS regression on World Bank panel data (numpy+scipy, no statsmodels)
│   │   ├── scenario_lab.py          # Stress scenario designer (Phase 18B deferred, basic stub)
│   │   │
│   │   # --- Macro ---
│   │   ├── macro_service.py         # Core macro: GDP, CPI, unemployment — 7-source waterfall for 20+ countries
│   │   ├── macro_expansion_service.py   # Extended macro: housing, employment, leading indicators,
│   │   │                            #   financial conditions, IS-LM-PC panels, FRED batch fetcher
│   │   ├── macro_regime_service.py  # Macro regime overlay: growth/inflation quadrant for Atlas/Macro
│   │   ├── rates_service.py         # US Treasury yield curve (3M–30Y), TIPS real yields, breakevens,
│   │   │                            #   credit spreads, Taylor Rule, ACM term premium
│   │   ├── regime_service.py        # Macro regime classification: 2×2 Goldilocks (expansion/slowdown/
│   │   │                            #   stagflation/recession) via GDP growth vs CPI inflation
│   │   ├── cot_service.py           # CFTC COT report — 6 key contracts, net speculator positioning, COT Index
│   │   │
│   │   # --- Macro-Financial Intelligence (Phase 18A) ---
│   │   ├── credit_market.py         # Credit market pulse: IG/HY spreads, CDX, SOFR, repo
│   │   ├── yield_curve_service.py   # Full US spot curve construction, interpolation, TIPS/breakevens
│   │   ├── policy_service.py        # Central bank divergence score, G10 carry differentials, policy surprises
│   │   ├── sovereign_risk_service.py # Sovereign risk: 6-KPI traffic-light rankings, ~200 countries
│   │   │
│   │   # --- Atlas ---
│   │   ├── atlas_service.py         # World choropleth data: 6 macro indicators (GDP, CPI, etc.)
│   │   │                            #   across ~200 countries, 2000–2024, via World Bank + IMF
│   │   │
│   │   # --- Events & filings ---
│   │   ├── calendar_service.py      # Unified event schema: macro releases + earnings + dividends +
│   │   │                            #   IPOs + central bank meetings; FRED release calendar, 60-min cache
│   │   ├── finnhub_service.py       # Thin Finnhub wrapper (IPOs, economic events, earnings estimates)
│   │   ├── edgar_service.py         # SEC EDGAR: Form 4 insider transactions, 13F institutional holdings
│   │   │
│   │   # --- Country Risk & Central Banks (Phase 16) ---
│   │   ├── country_risk_service.py  # 6-KPI traffic-light sovereign panel for ~200 countries (World Bank)
│   │   ├── centralbanks_service.py  # Policy rate history 2005–present for 7 CBs (Fed/ECB/BoE/BoJ/BoC/RBA/SNB);
│   │   │                            #   FRED IRSTCI01*/IR3TIB01* series + Fed balance sheet (WALCL)
│   │   │
│   │   # --- Sentiment ---
│   │   ├── sentiment_service.py     # News headline sentiment scoring (keyword-based, reuses _POS_WORDS/_NEG_WORDS)
│   │   │
│   │   # --- Persistence & Jobs (Phase 17) ---
│   │   ├── jobs.py                  # APScheduler background jobs: daily price/quote/FX refresh,
│   │   │                            #   screener cache warm, backfill checks
│   │   ├── funding_service.py       # Funding/liquidity panel (Phase 18B deferred, basic stub)
│   │   │
│   │   # --- Utilities ---
│   │   └── ... (helpers imported by above)
│   │
│   ├── sources/                # Macro data source adapters (waterfall pattern)
│   │   ├── __init__.py
│   │   ├── source_fred.py           # FRED (Federal Reserve) — US series via fredapi / pandas-datareader
│   │   ├── source_worldbank.py      # World Bank (wbgapi) — global GDP, CPI, unemployment
│   │   ├── source_imf.py            # IMF (imfp) — WEO projections
│   │   ├── source_ecb.py            # ECB (ecbdata) — Eurozone series
│   │   ├── source_dbnomics.py       # DB.nomics — multi-source aggregator
│   │   ├── source_datareader.py     # pandas-datareader fallback
│   │   └── source_frankfurter.py    # Frankfurter API — ECB-sourced FX rates
│   │
│   └── scripts/                # One-time data backfill scripts
│       ├── backfill_ohlcv.py        # Backfill DailyPrice table with historical OHLCV
│       └── backfill_macro.py        # Backfill DailyMacro table with historical FRED/World Bank data
│
├── tests/                      # pytest test suite (508+ tests)
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures (FastAPI TestClient, mock info dicts, statement DataFrames)
│   ├── test_smoke.py           # Smoke tests: every router returns HTTP 200
│   ├── test_dcf_engine.py      # Two-stage DCF engine unit tests
│   ├── test_valuation_engine.py     # 8-model valuation + composite scoring + CAPM implied
│   ├── test_fundamentals.py    # Piotroski, Beneish, Ohlson, DuPont, ROIC, CCC
│   ├── test_analyst_service.py # Analyst ratings + price target + earnings surprise parsing
│   ├── test_fama_french.py     # FF3/FF5 factor loading regression
│   ├── test_fx_service.py      # FX rate fetching + base conversion
│   ├── test_regime_service.py  # Macro regime classification rules
│   ├── test_discount_rates.py  # WACC / risk-free rate / ERP helpers
│   ├── test_calendar_service.py     # Earnings + macro + IPO + CB event merging
│   ├── test_constituents.py    # Wikipedia MediaWiki API index parsing
│   ├── test_dashboard_services.py   # Breadth, indices, Fear & Greed, movers
│   ├── test_screener_universe.py    # Universe loading + Parquet cache
│   ├── test_treemap.py         # Treemap tile generation + drill-down
│   ├── test_cache.py           # Cache hit/miss/eviction unit tests
│   ├── test_database.py        # SQLAlchemy ORM model + session tests
│   ├── test_atlas_service.py   # Atlas choropleth data + regional bloc filtering
│   ├── test_econ_lab_service.py     # Pooled OLS regression engine
│   ├── test_momentum_service.py     # Cross-sectional momentum deciles
│   ├── test_risk_parity_service.py  # Risk parity (inverse-vol + ERC) backtest
│   ├── test_carry_service.py   # FX carry table + backtest
│   ├── test_realized_moments_service.py  # Garman-Klass variance + realized skew/kurtosis
│   ├── test_country_risk_service.py     # Sovereign risk KPI scoring
│   ├── test_centralbanks_service.py     # CB policy rate history + Fed balance sheet
│   ├── test_credit_market.py   # Credit market pulse indicators
│   ├── test_policy_service.py  # Policy divergence + carry differentials
│   ├── test_yield_curve_service.py     # Spot curve + TIPS + breakevens
│   ├── test_sovereign_risk_service.py  # Sovereign risk rankings
│   ├── test_jobs.py            # APScheduler job orchestration
│   └── test_api_optimization.py # Composite endpoint + Nginx gzip + lazy-loading perf
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
