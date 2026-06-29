# Axiom Finance — Backend File Structure

> **Last updated:** 2026-06-29 — reflects all phases through Phase 31.
> Routers: 33 · Services: 68 · Tests: 568+

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
│   ├── database.py             # SQLAlchemy engine + SessionLocal + init_db (SQLite WAL mode, auto-creates)
│   ├── db_models.py            # ORM: DailyPrice, DailyQuote, DailyMacro, DailyFX, CacheEntry, JobExecution
│   ├── middleware.py           # DeduplicationMiddleware stub (future: duplicate request guard)
│   │
│   ├── data/
│   │   ├── damodaran_erp_2026.json  # Damodaran equity risk premia by country/sector
│   │   └── sector_multiples.json    # Damodaran sector valuation multiples
│   │
│   ├── routers/                # 33 FastAPI routers — one file per feature area
│   │   ├── __init__.py
│   │   ├── admin.py            # /api/admin — cache stats, source health, config GET/PUT, latency, performance
│   │   ├── atlas.py            # /api/atlas/timeline|snapshot — choropleth (6 indicators, ~200 countries)
│   │   ├── calendar.py         # /api/calendar — earnings, macro, IPO, dividend, CB meeting events
│   │   ├── corporate.py        # /api/corporate/health — Altman Z, Piotroski 9-pt, Beneish M
│   │   ├── credit.py           # /api/credit/pulse — IG/HY spreads, SOFR/OIS, credit impulse
│   │   ├── crossborder.py      # /api/crossborder/* — BIS locational banking, debt securities
│   │   ├── dashboard.py        # /api/dashboard/breadth|indices|fear-greed|movers
│   │   ├── dividend.py         # /api/dividend/* — yield, growth, payout, aristocrats, DDM
│   │   ├── factbook.py         # /api/factbook/* — CIA World Factbook country profiles
│   │   ├── insider.py          # /api/insider/aggregate — cluster buying, sector sentiment, smart money index
│   │   ├── macro.py            # /api/macro/* — 16+ sub-tab endpoints: overview, rates, inflation, employment,
│   │   │                       #   housing, commodities, fx, leading, financial-conditions, positioning,
│   │   │                       #   country-risk, central-banks, lab, fiscal, labor, energy, inequality
│   │   ├── market.py           # /api/market/* — prices, quote, risk, sectors, events, news
│   │   ├── market_data.py      # /api/market/13f, /api/market/form4 — EDGAR filings
│   │   ├── mergers.py          # /api/mergers/* — M&A deal tracking, sector activity heatmap
│   │   ├── options.py          # /api/options/* — expiries, ivmetrics, chain, termstructure, smile, oiprofile, mc
│   │   ├── policy.py           # /api/policy/tracker — CB divergence, G10 carry, sovereign risk
│   │   ├── portfolio.py        # /api/portfolio/* — 13 endpoints: analyze, correlation, risk-contribution,
│   │   │                       #   capm, rolling, kelly, ff, frontier, montecarlo, blacklitterman, stress
│   │   ├── ratios.py           # /api/ratios — 23 fundamental ratios + Z-score, beta, Sharpe, Sortino
│   │   ├── research.py         # /api/research/* — risk-parity, carry, momentum, realized-moments, cross-section
│   │   ├── risk.py             # /api/risk/* — rolling, extended, correlation, garch, hurst, ou, cointegration, mc, stress
│   │   ├── scenario.py         # /api/scenario/run — stress scenario designer/lab (Phase 18B deferred stub)
│   │   ├── screener.py         # /api/screener/universe|presets|status|refresh — cached multi-index screener
│   │   ├── search.py           # /api/search — ticker autocomplete (yfinance + local cache)
│   │   ├── sector.py           # /api/sector/returns|fundamentals|rotation|drill
│   │   ├── snowflake.py        # /api/snowflake + /api/snowflake/batch — 5-axis composite score
│   │   ├── sovereign.py        # /api/sovereign/risk — 6-KPI traffic-light rankings, ~200 countries
│   │   ├── stability.py        # /api/stability/currency-crisis|banking — EWS models, KLR methodology
│   │   ├── technicals.py       # /api/technicals — SMA, EMA, MACD, RSI, BB, Ichimoku, Fib, Pivot Points
│   │   ├── treemap.py          # /api/treemap — S&P 500 / NDX / Dow squarified treemap
│   │   ├── valuation.py        # /api/valuation/full|dcf|factors — 8-model + CAPM + Axiom Fair Value
│   │   ├── wiki.py             # /api/wiki/categories|terms|term — 410-term financial dictionary
│   │   └── yield_curve.py      # /api/yield/curve — US spot curve, TIPS, breakevens, ACM term premium
│   │
│   ├── services/               # Business logic — called by routers (68 services)
│   │   ├── __init__.py
│   │   │
│   │   # --- Market data & pricing ---
│   │   ├── yfinance_service.py      # Low-level yfinance wrappers: close/volume frames, info+statements bundle,
│   │   │                            #   quotes (fast_info), market caps (threaded), news, events, retry logic
│   │   ├── fx_service.py            # Frankfurter FX rates + base conversion
│   │   ├── indices_service.py       # ~25 global indices (price + return) via yfinance
│   │   ├── movers_service.py        # Top gainers / losers from screener cache
│   │   ├── trade_service.py         # Trade flows: exports/imports %GDP, openness, BIS effective FX
│   │   │
│   │   # --- Fundamentals & valuation ---
│   │   ├── fundamentals.py          # Piotroski F-Score, Beneish M-Score, Ohlson O-Score, ROIC, CCC
│   │   ├── valuation_engine.py      # 8-model valuation + Axiom composite fair value
│   │   ├── dcf_engine.py            # Two-stage DCF with terminal value, 3 scenarios, 7×7 sensitivity heatmap
│   │   ├── discount_rates.py        # WACC, CAPM cost of equity, country-specific risk-free rate, ERP
│   │   ├── analyst_service.py       # Analyst ratings + consensus price targets, earnings surprises, forward estimates
│   │   ├── fama_french.py           # FF3/FF5 factor loading via Ken French CSVs
│   │   ├── snowflake_service.py     # 5-axis composite score (Value/Growth/Performance/Health/Dividend)
│   │   ├── corporate_health_service.py  # Altman Z-Score, extended Piotroski/Beneish with multi-period data
│   │   ├── dividend_service.py      # Dividend yield, growth rate, payout ratio, aristocrats screener
│   │   ├── dupont_service.py        # Sector-level DuPont decomposition (margin × turnover × leverage)
│   │   │
│   │   # --- Risk ---
│   │   ├── metrics.py               # Core risk: log_returns, Sharpe, Sortino, VaR/CVaR, Beta, CAPM,
│   │   │                            #   Altman Z-Score, 23 financial ratios compute_ratios()
│   │   ├── advanced_risk.py         # GARCH(1,1), Hurst exponent, OU mean-reversion, cointegration, MC GBM, stress
│   │   │
│   │   # --- Options ---
│   │   ├── options_engine.py        # Black-Scholes + 5 Greeks, IV backsolve (brentq), CRR binomial tree,
│   │   │                            #   IV30/Rank/Percentile, Max Pain, term structure, smile, OI, MC
│   │   │                            #   ⚠️ KNOWN BUG: IV30 ~0.001% (see ACTIVE_ISSUES.md P1-01)
│   │   │
│   │   # --- Portfolio ---
│   │   ├── portfolio.py             # 12 portfolio functions: performance, correlation, risk contribution,
│   │   │                            #   CAPM, rolling, Kelly, FF, frontier (SLSQP), MC, BL, stress
│   │   │
│   │   # --- Market structure ---
│   │   ├── breadth_service.py       # Advance/decline, new highs/lows, McClellan oscillator
│   │   ├── feargreed_service.py     # 7-signal Fear & Greed composite index
│   │   ├── constituents.py          # Index constituents via Wikipedia MediaWiki API (weekly cache)
│   │   ├── treemap_service.py       # Treemap tile data: mcap, return%, GICS sector/industry
│   │   ├── screener_service.py      # 20+ signal presets, 9 result views, cached universe
│   │   ├── screener_cache.py        # Overnight Parquet/SQLite warmer for screener universe
│   │   ├── sector_service.py        # SPDR ETF returns, fundamentals, rotation clock, industry drill-down
│   │   ├── short_interest_service.py # Most-shorted stocks, squeeze candidates, sector aggregate SI
│   │   │
│   │   # --- Technical Analysis ---
│   │   ├── technicals_service.py    # SMA, EMA, MACD, RSI, BB, Ichimoku, Fibonacci, Pivot Points
│   │   │
│   │   # --- Research (Quant Tools) ---
│   │   ├── risk_parity_service.py   # Inverse-vol + ERC (SLSQP), monthly-rebalanced backtest vs 60/40
│   │   ├── carry_service.py         # G10 FX carry: carry table + long-top3/short-bottom3 backtest
│   │   ├── momentum_service.py      # Cross-sectional momentum: 1M/3M/6M/12M-1M deciles
│   │   ├── realized_moments_service.py  # GK variance + rolling skew/kurtosis + cross-section
│   │   ├── econ_lab_service.py      # Pooled OLS regression on WB panel (numpy+scipy, no statsmodels)
│   │   ├── scenario_lab.py          # Stress scenario designer (Phase 18B deferred, basic stub)
│   │   │
│   │   # --- Macro ---
│   │   ├── macro_service.py         # Core macro: GDP, CPI, unemployment — 7-source waterfall
│   │   ├── macro_expansion_service.py   # Housing, employment, leading indicators, financial conditions, IS-LM-PC
│   │   ├── macro_regime_service.py  # Macro regime overlay: growth/inflation quadrant
│   │   ├── rates_service.py         # US Treasury yield curve (3M–30Y), TIPS, breakevens, Taylor Rule, ACM
│   │   ├── regime_service.py        # 2×2 Goldilocks regime classification via GDP × CPI
│   │   ├── cot_service.py           # CFTC COT report — 6 key contracts, net speculator COT Index
│   │   ├── fiscal_service.py        # Fiscal sustainability: revenue, expenditure, tax, savings, r-g dynamics
│   │   ├── labor_service.py         # Labor market: LFPR, youth unemployment, vulnerable employment, wages
│   │   ├── energy_service.py        # Energy transition: CO₂, renewable share, fossil fuel dependency
│   │   ├── inequality_service.py    # Inequality: Gini, income decile shares, poverty headcounts
│   │   ├── business_service.py      # Business dynamism: new business density, Doing Business historical
│   │   ├── currency_crisis_service.py   # KLR early warning: reserves, CA, FX overvaluation, inflation, ST debt
│   │   ├── banking_stability_service.py # NPL ratios, capital adequacy, Z-scores, BIS credit gaps
│   │   ├── sovereign_default_service.py # Logit default probability model (Reinhart & Rogoff)
│   │   ├── ma_service.py            # M&A deal tracking, sector activity heatmap
│   │   │
│   │   # --- Macro-Financial Intelligence (Phase 18A) ---
│   │   ├── credit_market.py         # IG/HY OAS, BBB spread, funding stress, TED
│   │   ├── yield_curve_service.py   # Full US spot curve, interpolation, TIPS/breakevens
│   │   ├── policy_service.py        # CB divergence score, G10 carry differentials
│   │   ├── sovereign_risk_service.py # 6-KPI traffic-light sovereign rankings, ~200 countries
│   │   │
│   │   # --- Atlas ---
│   │   ├── atlas_service.py         # 6 macro indicators across ~200 countries, 2000–2024
│   │   │
│   │   # --- Events & filings ---
│   │   ├── calendar_service.py      # Unified event schema: macro + earnings + dividends + IPOs + CB meetings
│   │   ├── finnhub_service.py       # Finnhub wrapper (IPOs, economic events, earnings)
│   │   ├── edgar_service.py         # SEC EDGAR: Form 4, 13F institutional holdings
│   │   ├── insider_aggregator.py    # Aggregate insider buy/sell ratio, cluster detection, smart money index
│   │   │
│   │   # --- Country Risk & Central Banks ---
│   │   ├── country_risk_service.py  # 6-KPI traffic-light sovereign panel (World Bank)
│   │   ├── centralbanks_service.py  # Policy rate history 2005–present for 7 CBs
│   │   │
│   │   # --- Factbook ---
│   │   ├── factbook_service.py      # CIA World Factbook: country profiles, geography, demographics
│   │   ├── factbook_profiles_service.py # Country-specific factbook profile data
│   │   │
│   │   # --- Sentiment ---
│   │   ├── sentiment_service.py     # News headline sentiment scoring (keyword-based)
│   │   │
│   │   # --- Persistence & Jobs (Phase 17) ---
│   │   ├── jobs.py                  # APScheduler: daily price/quote/FX refresh, screener warm, backfill
│   │   ├── funding_service.py       # Funding/liquidity panel (M2, SOFR, CP spread)
│   │   ├── bulk_data_service.py     # WB/IMF/Fama-French/BIS bulk downloads to parquet
│   │   ├── prefetch_service.py      # 95-task cache warming with rate-limited staggering
│   │   ├── risk_free_service.py     # Per-country risk-free rate (FRED + Damodaran ERP)
│   │   ├── wiki_service.py          # 410-term financial dictionary across 26 categories
│   │   │
│   │   # --- Utilities ---
│   │   └── ... (helpers imported by above)
│   │
│   ├── sources/                # Macro data source adapters (waterfall pattern)
│   │   ├── __init__.py
│   │   ├── source_bis.py            # BIS ZIP downloads: CPI, policy rates, FX, credit gaps, property prices, effective FX
│   │   ├── source_fred.py           # FRED — US series via fredapi / pandas-datareader
│   │   ├── source_worldbank.py      # World Bank (wbgapi) — GDP, CPI, employment, trade
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
├── tests/                      # pytest test suite (568+ tests)
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
