# Axiom Finance Alpha 0.4

A self-hosted, Dockerised financial analytics platform covering the full investment research stack — from macroeconomics to options pricing, portfolio optimisation to financial term dictionary.

**No paid APIs required.** Optional free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) for richer US macro data, [Finnhub API key](https://finnhub.io/) for earnings and insider transactions, and [Gemini API key](https://aistudio.google.com/apikey) for AI-powered company, macro, and dashboard summaries.

---

## 📊 What's Inside

### Pages (24 total)

| Page | Path | Description |
|------|------|-------------|
| **Dashboard** | `/dashboard` | Market breadth (advancing/declining, McClellan Oscillator, cumulative A-D line), global indices, Fear & Greed Index with sub-components, top gainers/losers |
| **Markets** | `/markets` | Price charts, technical indicators (MACD, Bollinger Bands, Ichimoku Cloud, Fibonacci, Pivot Points), risk metrics (VaR, Sharpe, Beta, GARCH), 8-model valuation engine + DCF with per-country discount rate selector (live FRED risk-free rates for US, EU, UK, Japan, etc.) + Snowflake composite score, financial ratios, options & IV analytics, news feed, 13F institutional holdings, Form 4 insider transactions. Sub-tabs: Overview, Technicals, Valuation, Ratios, News & Events, Sectors, Treemap, Short Interest |
| **Screener** | `/screener` | S&P 500 / Nasdaq 100 / Dow 30 universe, 20+ preset signals (Golden Cross, Undervalued, Quality Growth, High Short Interest, etc.), overnight-warmed cache, 9 result tabs with sparkline gallery |
| **Portfolio** | `/portfolio` | Efficient frontier, Black-Litterman model, Monte Carlo simulation, Fama-French 3/5-factor attribution, Kelly criterion position sizing, risk contribution decomposition, stress testing, scenario lab, transaction log (buy/sell tracking, cost basis, realized P&L) |
| **Research** | `/research` | 9-tab quant hub: **Risk Parity** (ERC/inverse-vol backtest), **FX Carry** (G10 carry + backtest), **Momentum** (decile backtest), **Realized Moments** (GK variance, skew, cross-sectional tail test), **Cross-Asset Correlation** (stocks/bonds/commodities/FX matrix), **FX-Macro Link** (commodity pair lead/lag), **Multi-Country Portfolio** (FX-adjusted returns), **Sector DuPont**, **Econometric Lab** (pooled OLS) |
| **Macro** | `/macro` | 14-tab hub: **Overview** (FX rates, country comparison, regime clock with WB data for ALL countries), **Inflation**, **Growth & Employment**, **Housing**, **Fiscal**, **Labor**, **Energy & Climate**, **Inequality**, **Business Dynamism**, **Commodities** (FRED primary), **FX**, **Leading Indicators**, **Financial & Funding Conditions**, **Sentiment & Positioning** |
| **Risk** | `/risk` | Rolling metrics (20D/60D/120D/252D), GARCH(1,1) volatility forecasting, Hurst exponent, Ornstein-Uhlenbeck mean-reversion, Engle-Granger cointegration, correlation matrix, historical stress scenarios (2008, COVID, 2022 rates, dot-com) |
| **Options** | `/options` | Implied volatility (IV30, IV Rank, IV Percentile), Greeks (Delta, Gamma, Theta, Vega, Rho), term structure, volatility smile, OI profile, max pain, Black-Scholes pricing, CRR binomial tree, Monte Carlo options pricing |
| **Calendar** | `/calendar` | Economic releases (CPI, NFP, FOMC, GDP, etc.), earnings reports with EPS surprise, ex-dividend dates, IPOs, central bank meeting schedule — sourced from FRED + Finnhub |
| **Yield** | `/yield` | US Treasury spot curve, foreign spreads, real yields & breakevens, ACM term premium |
| **Policy** | `/policy` | Central bank policy rate divergence, G10 carry differentials, sovereign risk rankings, default probability model. Merged from `/sovereign` (Phase 23) |
| **Sovereign** | `/sovereign` | 6-KPI traffic-light sovereign risk rankings, ~200 countries |
| **Atlas** | `/atlas` | Choropleth world map of 6 macro indicators across ~200 countries (2000–2024), year-slider animation, regional blocs (G7, G20, Eurozone, Emerging Markets), Top-10/Bottom-10 rankings |
| **Wiki** | `/wiki` | 🔍 Searchable financial dictionary — **410+ terms** across **26 categories**, each with a detailed 3-5 sentence explanation. Category sidebar, debounced search, expandable cards, related-term cross-linking |
| **Trade** | `/trade` | Exports/imports %GDP, trade balances, openness indices, BIS effective exchange rates |
| **Corporate Health** | `/corporate` | Altman Z-Score, Piotroski F-Score (9-point), Beneish M-Score, sector aggregate Z. Prior-year financial data via quarterly fallback for full Piotroski (8-9/9) and Beneish scoring. |
| **Scenario Lab** | `/scenario` | Stress-test portfolios against historical crises (GFC, COVID, dot-com, 2022 rates) and custom macro shocks. Reuses backend scenario engine. |
| **Dividends** | `/dividends` | Dividend yield, 5Y/10Y growth, payout ratio, aristocrats screener, DDM fair value |
| **Insider** | `/insider` | Aggregate insider buy/sell ratio, cluster detection, sector sentiment, smart money index |
| **Mergers** | `/mergers` | M&A deal tracking, deal values, acquisition premiums, sector activity heatmap |
| **Stability** | `/stability` | Currency Crisis Early Warning (KLR), Banking Stability (NPL, Z-scores, BIS credit gaps) |
| **Cross-Border** | `/crossborder` | BIS locational banking statistics, international debt securities |
| **Country Profiles** | `/country/{iso2}` | CIA World Factbook data — geography, demographics, economy |
| **Admin** | `/admin` | Backend health dashboard, cache stats, job execution history, API keys management |

> **Navigation:** Primary bar (Dashboard · Markets · Screener · Portfolio · Research · Macro · Atlas) is unchanged. The More dropdown is grouped into Discover / Analyze / Markets & Data / Global / Reference sections. **Scenario Lab** is now accessible from the Analyze section of the More dropdown. Beginner/Expert mode toggle is in the navbar. Sectors and Treemap views are embedded as sub-tabs within the Markets page.

### Wiki Dictionary — 26 Categories

📊 Market Indices & Benchmarks · 📈 Technical Indicators · 💰 Valuation Models · 📋 Fundamental Financial Ratios · ⚠️ Risk Metrics · 🔮 Options & Implied Volatility · 🌍 Macroeconomic Indicators · 📉 Yield Curve & Fixed Income · 🏦 Central Banks & Monetary Policy · 💱 Foreign Exchange (FX) · 🎯 Portfolio Theory & Analytics · 🔬 Research Strategies · 🏭 Sector & Industry Analysis · 🔍 Screening & Signals · 🛡️ ESG & Fraud Detection · ❄️ Snowflake Composite Score · 🖥️ Dashboard & Market Breadth · 🔄 Macro Regime Classification · 💳 Financial Conditions & Credit · 🏛️ Sovereign & Country Risk · 🧪 Econometric Lab · 🗺️ Atlas (Global Macro Map) · 📅 Economic Calendar · 🗂️ Treemap Visualization · 💥 Stress Testing & Monte Carlo · ⚙️ Misc / Infrastructure

---

## 🎨 Theme

Axiom Finance includes a built-in light/dark theme toggle (persisted to `localStorage`).

| Token | Light | Dark |
|-------|-------|------|
| Background | Pure white (`#ffffff`) | Greyish-black (`#0c0c0e`) |
| Card surface | Near-white (`rgb(248,248,251)`) | Dark grey (`rgb(22,22,26)`) |
| Accent | Deep maroon (`#6b0f1a`) | Crimson (`#c4394a`) |
| Text | Charcoal (`rgb(15,15,20)`) | Near-white (`rgb(242,242,247)`) |

The maroon/crimson accent is the Axiom brand signature — it provides a distinctive pop against the neutral grey backgrounds in both themes. All chart palettes, borders, and secondary text tokens automatically adapt when toggling themes.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, uvicorn |
| **Data** | yfinance ≥0.2.40, pandas, numpy, scipy, pandas-datareader, fredapi, wbgapi, imfp, ecbdata, dbnomics |
| **Quant** | arch (GARCH), pyarrow (parquet), pandas-ta, openpyxl, cachetools |
| **Persistence** | SQLAlchemy ≥2.0, APScheduler ≥3.10, SQLite (WAL mode) |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Recharts |
| **Data Fetching** | @tanstack/react-query v5 (server cache), React Suspense + lazy (code splitting) |
| **Infra** | Docker Compose, Nginx reverse proxy (gzip, proxy_next_upstream retry) |
| **Testing** | pytest, pytest-asyncio (backend) · Playwright (E2E) |
| **Sources** | Yahoo Finance, FRED, World Bank, IMF, BIS, OECD, Ken French Data Library, Finnhub, ECB, DB.nomics, Eurostat, CFTC, EDGAR, Wikipedia MediaWiki API |

---

## 🚀 Quick Start

```bash
git clone https://github.com/your-username/axiomfinance.git
cd axiomfinance

cp .env.example .env   # optional: add FRED_API_KEY + FINNHUB_API_KEY (both have free tiers)
docker compose up -d    # builds and starts everything
```

Open **http://localhost** — the dashboard loads immediately.

```bash
docker compose logs -f  # tail all logs
docker compose down     # stop everything
```

**No paid API keys required.** FRED_API_KEY and FINNHUB_API_KEY are optional and have free tiers. Without FRED, macro data falls back to World Bank / IMF / BIS. Without Finnhub, calendar earnings/news/insider data is unavailable.

---

## 📡 API Endpoints

The backend serves under `/api` (proxied by Nginx). Key endpoint groups:

### Market Data
| Endpoint | Purpose |
|----------|---------|
| `GET /api/market/prices` | Normalised price history + benchmarks |
| `GET /api/market/quote/{ticker}` | Real-time quote |
| `GET /api/market/risk` | VaR, CVaR, Sharpe, Sortino, Beta |
| `GET /api/market/composite` | Combined prices + risk + quotes |
| `GET /api/market/events/{ticker}` | Earnings, dividends, splits |
| `GET /api/market/news/{ticker}` | News feed |
| `GET /api/market/13f?ticker=` | Institutional holders (13F filings) |
| `GET /api/market/form4?ticker=` | Insider transactions (Form 4) |

### Valuation & Fundamentals
| Endpoint | Purpose |
|----------|---------|
| `GET /api/valuation/capm-dcf` | CAPM expected return + DCF target |
| `GET /api/valuation/full?ticker=` | Full 8-model valuation engine + fundamentals + analyst data |
| `GET /api/valuation/factors?ticker=&model=` | Fama-French 3/5-factor attribution |
| `GET /api/ratios/{ticker}` | Liquidity, leverage, efficiency, profitability ratios |
| `GET /api/valuation/dcf?ticker=` | Two-stage DCF with sensitivity grid |
| `GET /api/snowflake?ticker=` | 5-axis Snowflake composite score |
| `GET /api/snowflake/batch?tickers=` | Batch Snowflake scores |

### Corporate Health
| Endpoint | Purpose |
|----------|---------|
| `GET /api/corporate/health?ticker=` | Altman Z-Score, Piotroski 9-pt, Beneish M-Score |

### Dividends
| Endpoint | Purpose |
|----------|---------|
| `GET /api/dividend?ticker=` | Dividend yield, growth rate, payout ratio, aristocrats status |
| `GET /api/dividend/ddm?ticker=` | DDM fair value estimation |

### Insider
| Endpoint | Purpose |
|----------|---------|
| `GET /api/insider/aggregate` | Aggregate buy/sell ratio, cluster detection, smart money index |

### Mergers
| Endpoint | Purpose |
|----------|---------|
| `GET /api/mergers` | M&A deals, deal values, premiums, sector heatmap |

### Stability
| Endpoint | Purpose |
|----------|---------|
| `GET /api/stability/currency-crisis` | KLR early warning system (traffic-light per country) |
| `GET /api/stability/banking` | NPL ratios, capital adequacy, Z-scores, BIS credit gaps |

### Cross-Border
| Endpoint | Purpose |
|----------|---------|
| `GET /api/crossborder/claims` | BIS locational banking statistics |
| `GET /api/crossborder/securities` | International debt securities |

### Country Profiles
| Endpoint | Purpose |
|----------|---------|
| `GET /api/factbook/country/{iso2}` | CIA World Factbook profile (geography, demographics, economy) |

### Macro
| Endpoint | Purpose |
|----------|---------|
| `GET /api/macro/data` | Cross-country indicator series |
| `GET /api/macro/fx` | Live FX rates |
| `GET /api/macro/rates` | US yield curve, Taylor Rule, ACM decomposition |
| `GET /api/macro/inflation` | CPI, PCE, breakevens, Quantity Theory |
| `GET /api/macro/employment` | NFP, unemployment, JOLTS, Sahm Rule |
| `GET /api/macro/housing` | Case-Shiller, housing starts, mortgage rates |
| `GET /api/macro/commodities` | WTI, gold, natural gas, copper, wheat |
| `GET /api/macro/fx/heatmap` | FX cross grid with daily changes |
| `GET /api/macro/fx/ppp` | Purchasing Power Parity estimates |
| `GET /api/macro/leading` | LEI, CFNAI, ISM PMI, GSCPI, IS-LM-PC framework |
| `GET /api/macro/financial-conditions` | NFCI, STLFSI, Fed balance sheet, EPU |
| `GET /api/macro/positioning` | COT speculative/commercial positions |
| `GET /api/macro/regime` | 4-quadrant macro regime classifier (growth × inflation) with Z-scores, asset allocation signals |
| `GET /api/macro/regime-series` | Historical regime time series for any country (World Bank data, ~200 countries) |
| `GET /api/macro/country-risk` | 6-KPI traffic-light sovereign panel |
| `GET /api/macro/centralbanks` | Policy rates for 7 CBs, meeting calendar, Fed BS |
| `POST /api/macro/regress` | Pooled OLS econometric lab |

### Dashboard, Screener, Calendar, Sectors, Atlas
| Endpoint | Purpose |
|----------|---------|
| `GET /api/dashboard/breadth` | Market breadth for S&P 500 |
| `GET /api/dashboard/indices` | Global index snapshot |
| `GET /api/dashboard/fear-greed` | Fear & Greed Index |
| `GET /api/dashboard/movers` | Top gainers/losers |
| `GET /api/screener/universe` | Cached screener with presets |
| `GET /api/screener/presets` | Preset definitions |
| `GET /api/calendar` | Economic calendar events |
| `GET /api/sector/returns` | Sector performance across periods |
| `GET /api/sector/rotation` | Sector rotation clock |
| `GET /api/atlas/timeline` | Country indicator time series |
| `GET /api/atlas/snapshot` | Single-year choropleth data |

### Portfolio & Risk
| Endpoint | Purpose |
|----------|---------|
| `POST /api/portfolio/analyze` | Full portfolio analysis |
| `POST /api/portfolio/frontier` | Efficient frontier |
| `POST /api/portfolio/blacklitterman` | Black-Litterman optimisation |
| `POST /api/portfolio/montecarlo` | Portfolio Monte Carlo simulation |
| `POST /api/portfolio/ff` | Fama-French attribution |
| `POST /api/portfolio/stress` | Historical stress tests |
| `GET /api/risk/rolling` | Rolling risk metrics |
| `GET /api/risk/extended` | Extended risk analytics |
| `POST /api/risk/garch` | GARCH(1,1) volatility forecast |
| `POST /api/risk/hurst` | Hurst exponent |
| `POST /api/risk/cointegration` | Engle-Granger cointegration test |
| `POST /api/risk/stress` | Historical stress scenarios |
| `POST /api/risk/montecarlo` | Asset Monte Carlo simulation |

### Options
| Endpoint | Purpose |
|----------|---------|
| `GET /api/options/ivmetrics?ticker=` | IV30, IV Rank, IV Percentile, max pain |
| `GET /api/options/chain?ticker=&expiry=` | Full options chain with Greeks |
| `GET /api/options/termstructure?ticker=` | IV term structure |
| `GET /api/options/smile?ticker=&expiry=` | Volatility smile |
| `GET /api/options/oiprofile?ticker=&expiry=` | Open interest profile |
| `POST /api/options/montecarlo` | Monte Carlo options pricing |

### Research Strategies
| Endpoint | Purpose |
|----------|---------|
| `POST /api/research/riskparity` | Risk parity weights (inverse-vol / ERC) |
| `GET /api/research/carry` | G10 FX carry table + backtest |
| `GET /api/research/momentum` | Cross-sectional momentum deciles |
| `GET /api/research/moments` | Garman-Klass realised variance, skew, kurtosis |
| `GET /api/research/moments/crosssection` | Tail-return cross-sectional test |

### Credit, Yield, Policy, Sovereign
| Endpoint | Purpose |
|----------|---------|
| `GET /api/credit/pulse` | IG/HY OAS, BBB spread, funding stress |
| `GET /api/yield/curves` | US spot curve, TIPS real yields, breakevens, ACM |
| `GET /api/policy/tracker` | CB divergence score, carry differentials |
| `GET /api/sovereign/risk` | Sovereign risk rankings |

### Wiki
| Endpoint | Purpose |
|----------|---------|
| `GET /api/wiki/categories` | List 26 categories with term counts |
| `GET /api/wiki/terms?search=&category=` | Search/filter terms (410+ total) |
| `GET /api/wiki/term/{slug}` | Single term detail by URL slug |

### Admin
| Endpoint | Purpose |
|----------|---------|
| `GET /api/admin/health` | Backend health, uptime, cache stats, DB row counts |
| `POST /api/admin/prefetch` | Trigger cache warming (95 tasks, rate-limited) |
| `GET /api/admin/prefetch/status` | Prefetch progress with completion % |
| `GET /api/admin/bulk-data/status` | Bulk data download status (World Bank, IMF, Fama-French, BIS) |
| `POST /api/admin/bulk-data/refresh` | Trigger bulk data refresh (runs in background) |
| `GET /api/health` | Health check |

---

## 📁 Project Structure

```
axiomfinance/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── backend/
│       ├── main.py              # FastAPI entrypoint, router registration
│       ├── cache.py             # @cached / @async_cached decorators, HybridCache
│       ├── database.py          # SQLAlchemy engine + session
│       ├── db_models.py         # ORM models (DailyPrice, DailyQuote, etc.)
│       ├── models.py            # Pydantic models
│       ├── config.py            # Environment config
│       ├── routers/             # 25+ route modules
│       │   ├── wiki.py          # Wiki dictionary endpoints
│       │   ├── market.py        # Market data endpoints
│       │   ├── valuation.py     # Valuation engine endpoints
│       │   └── ...
│       ├── services/            # 38+ service modules
│       │   ├── wiki_service.py       # 410-term dictionary data
│       │   ├── bulk_data_service.py  # WB/IMF/Fama-French/BIS bulk downloads
│       │   ├── prefetch_service.py   # Cache warming with rate limiting
│       │   └── ...
│       └── sources/             # 4-source macro data pipeline (World Bank, IMF, BIS, FRED)
├── frontend/
│   ├── Dockerfile
│   ├── next.config.js
│   ├── app/                     # Next.js 14 App Router (24 pages)
│   │   ├── wiki/page.tsx
│   │   ├── markets/page.tsx
│   │   └── ...
│   ├── components/              # React components
│   │   ├── wiki/                # Wiki dictionary components
│   │   ├── macro/               # 12 macro tab components
│   │   └── ...
│   └── lib/
│       ├── api.ts               # API client (React Query)
│       └── types.ts             # Shared TypeScript types
├── nginx/
│   └── default.conf             # Reverse proxy config
├── docker-compose.yml
└── README.md
```

---

## ⚙️ Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `FRED_API_KEY` | No | US economic data from St. Louis Fed (free tier available) |
| `FINNHUB_API_KEY` | No | Earnings, news, insider transactions (free tier available) |

Without API keys, the platform gracefully degrades — using World Bank, IMF, and BIS for macro data; calendar/news/insider data will be unavailable without Finnhub.

---

## 🧪 Development

```bash
# Run tests
cd backend && pytest -q

# Frontend type-check (requires Node.js)
cd frontend && npx tsc --noEmit

# Rebuild and restart a single service
docker compose build frontend && docker compose up -d --force-recreate frontend
```

---

## 📝 License

MIT
