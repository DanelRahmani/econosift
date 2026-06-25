# Axiom Finance — CLAUDE.md

## What This App Does

Axiom Finance is a self-hosted financial analytics dashboard built on FastAPI + Next.js 14, containerized via Docker Compose. It has two main pillars:

- **Markets**: Analyze stocks globally — price charts, risk metrics (VaR, Sharpe, Beta), CAPM/DCF valuation, financial ratios, correlation matrices
- **Macro**: Compare macroeconomic indicators (GDP, CPI, unemployment, etc.) across 20+ countries via a 7-source data pipeline (FRED, World Bank, IMF, ECB, DB.nomics, etc.)

No paid APIs required. Optional free FRED API key for richer US data.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, yfinance, pandas
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Recharts
- **Infra**: Docker Compose, Nginx reverse proxy

---

## Active Build: Phases 0–12 (see `claude_plan.md`)

We are executing the `claude_plan.md` roadmap **one phase at a time, verifying
each in Docker before the next**. This section is the source of truth for
cross-machine continuation (the `~/.claude` auto-memory does **not** travel with
the repo).

### Progress

- ✅ **Setup** (`02f5028`) — Phase 0–12 deps, pytest + Playwright harness, Finnhub config.
- ✅ **Phase 0** (`390438b`) — two-stage DCF engine, FX rates panel, regime clock.
- ✅ **Phase 1** (`b50afc1`, `4b21fae`) — valuation engine (8 models + Axiom
  composite), extended fundamentals (Piotroski/Beneish/Ohlson/DuPont/ROIC/CCC),
  analyst data, Fama-French attribution, Damodaran ERP + sector multiples.
- ✅ **Phase 2** (`7937e9c`) — market breadth, ~25 global indices, 7-signal Fear &
  Greed, top movers, `/dashboard` landing page. Foundational
  `services/constituents.py` (S&P 500 / Nasdaq-100 / Dow via Wikipedia MediaWiki
  API, weekly cache) is reused by Phases 3 & 5. **Verified live in Docker** (all 5
  dashboard endpoints return real data; `/dashboard` HTTP 200). 267 pytest pass.
- ✅ **UI polish** (`374a49a`) — Ratios tab now colour-codes every metric
  (Favorable/Average/Caution) with an expandable per-ratio guide (meaning +
  Good/Average/Caution ranges + exceptions) via new `frontend/lib/ratioGuide.ts`
  (covers all 23 `/api/ratios` keys); macro chart tooltips rounded to 2 dp (were
  showing 10-decimal floats). **Frontend-only — needs a `frontend` rebuild to
  view; not yet visually verified in Docker.**

- ✅ **Phase 3** — S&P 500 Treemap. Interactive `d3-hierarchy` squarified
  treemap (area = log(market cap), colour = return% −5% red→0 white→+5% green),
  sector→industry→stock drill-down + breadcrumb, lazy-P/E hover card, controls
  (period, index S&P/NDX/Dow, group-by, colour-by). New `/treemap` page + nav
  tab (desktop + mobile). Backend: `constituents.py` now parses GICS
  Sub-Industry (`industry` field); new `treemap_service.py` + threaded
  `yfinance_service.get_market_caps`; new `routers/treemap.py`. **284 pytest
  pass, tsc clean. Verified live in Docker:** `/treemap` HTTP 200,
  `/api/treemap?index=dow` returns 30/30 real tiles.
  - ⚠️ **KNOWN ISSUE (deferred):** market caps come from `fast_info` →
    `get_shares_full()`, which Yahoo **rate-limits past ~30 tickers**. So **dow
    works** but **ndx/sp500 return 0 caps / 504** on cold load (stocks w/o mcap
    are dropped → empty treemap). Fix later: compute `mcap = last_close ×
    sharesOutstanding` (last_close is free from `get_close_frame`) with a
    long-TTL background-warmed shares cache (Phase 5 cron pattern), or batch
    `v7/finance/quote`. See `claude_plan.md` Phase 3.

- ✅ **Phase 4** — Economic Calendar. Unified `/calendar`: four event streams in
  one common schema — macro (`backend/data/cb_meetings.json` 2026 Fed/ECB/BoE/BoJ
  dates + FRED release calendar + Finnhub economic), earnings & dividends
  (threaded `yf.Ticker.earnings_dates`/`exDividendDate` fan-out,
  `ThreadPoolExecutor(max_workers=10)`, selectable index, default Dow 30), IPOs
  (Finnhub). New `finnhub_service.py` (thin, reusable Phases 5/7), `calendar_service.py`,
  `routers/calendar.py`. Frontend: `/calendar` page + `components/calendar/*`
  (weekly Mon–Sun grid, today highlighted, category filters + impact/country/tz,
  beat/miss colouring, <24h countdowns) + nav tabs. **On-demand + 60-min cache**
  (no scheduler infra — matches Phases 0–3). **316 pytest pass (+32), tsc clean.
  Verified live in Docker:** `/calendar` HTTP 200; `/api/calendar?index=dow`
  returns real macro (75 from FRED+CB) + 19 Dow earnings in the Jul Q2 window with
  EPS estimates.
  - ℹ️ **Graceful degradation:** IPOs need a Finnhub key (empty without, UI says so);
    FRED releases need `FRED_API_KEY` (present on this machine). CB meetings always
    work (shipped JSON). Large universes (sp500) may be slow/throttled on cold load —
    same Yahoo caveat as the treemap mcaps.

- ✅ **Phase 5** (`a9dbb8b`) — Screener Overhaul. High-performance screener at `/screener`:
  universes (S&P 500 / Nasdaq 100 / Dow 30 via Wikipedia API + FinanceDatabase small-cap),
  overnight-warmed Parquet/SQLite cache (`screener_cache.py`, `screener_service.py`),
  preset signal pills (20+ presets incl. Golden Cross, High ROIC, Insider Buying, Activist
  Target via EDGAR Form 4/SC 13D), 9 result tabs (Overview/Performance/Technicals/…),
  canvas sparkline gallery (200×120px, 3M closes + SMA50). **Verified live in Docker.**

- ✅ **Phase 6** (`dccc5f5`) — Risk & Rolling Metrics. Standalone `/risk` page with 5 tabs:
  - **Rolling Metrics**: Sharpe, Vol, Beta, Sortino, MaxDD, VaR95/99 as time series —
    window selector (20/60/120/252D), Overlay vs 2×3 Grid view.
  - **Extended**: Calmar, Omega, Treynor, Jensen's Alpha, CAPM variance decomposition
    (systematic vs idiosyncratic), CVaR 95%/99% — colour-coded, CSV export.
  - **Correlation**: Rolling pairwise heatmap with date scrubber (requires 2+ tickers).
  - **On-Demand 🟡**: GARCH(1,1) (`arch` library), Hurst exponent (R/S analysis),
    Ornstein-Uhlenbeck fit (OLS), Engle-Granger cointegration — each has a Calculate button.
  - **Stress & Monte Carlo 🔴**: GBM Monte Carlo VaR (configurable sims + horizon, histogram),
    historical stress testing across 4 scenarios (2008 GFC / 2020 COVID / 2022 rate shock /
    2000 dot-com) — replay actual price sequences, cumulative return chart per scenario.
  New files: `services/advanced_risk.py`, `routers/risk.py` (8 endpoints under `/api/risk`),
  7 React components in `frontend/components/risk/`. "Risk" added to desktop + mobile nav.
  **368 pytest pass, tsc clean. Verified live in Docker:** `/risk` HTTP 200,
  `/api/risk/rolling?tickers=AAPL&period=1y&window=252` returns real data,
  `/api/risk/extended?tickers=AAPL&period=3y` returns full extended metrics.

- ✅ **Phase 7** (`4c7f01a`) — Options & IV Module. Standalone `/options` page with
  full IV analytics: IV30 (linear interpolation between expiries bracketing 30 DTE),
  IV Rank/Percentile, Put/Call OI Ratio, Max Pain, Implied Earnings Move. Black-Scholes
  pricing + 5 Greeks (Δ/Γ/Θ/V/ρ), IV backsolve via `brentq`, CRR American binomial tree
  (100-step). Charts: IV Term Structure, IV Smile (moneyness 0.70–1.30), OI Profile
  (horizontal bar with Max Pain line). Chain table (Calls | Strikes | Puts, ITM tinted,
  OTM-only toggle, BS price + delta columns). 🔴 Monte Carlo Options Pricing (10k GBM
  paths, distribution histogram). New files: `services/options_engine.py`,
  `routers/options.py` (7 endpoints under `/api/options`), 6 React components in
  `frontend/components/options/`. "Options" added to desktop + mobile nav.
  **368 pytest pass. Verified live in Docker:** `/options` HTTP 200,
  `/api/options/expiries?ticker=AAPL` returns 23 expiries,
  `/api/options/ivmetrics?ticker=AAPL` returns real IV30/Rank/MaxPain data.

- ✅ **Phase 8** (`1815c9e`, `783dc81`) — Macro Expansion. `/macro` page replaced with a
  10-sub-tab macro intelligence hub: **Overview** (migrated FxWidget, YieldCurve, RegimeClock,
  InflationHeatmap, CountryComparison), **Rates & Yields** (full yield curve 3M–30Y, TIPS
  breakevens, real yields, credit spreads, Taylor Rule overlay, ACM term-premium), **Inflation**
  (CPI/PCE/PPI/M2/breakevens, Quantity Theory dual-axis), **Growth & Employment** (Sahm Rule
  with recession shading, JOLTS, industrial production), **Housing** (Case-Shiller, starts,
  mortgage, home sales), **Commodities** (~25 futures table + Bitcoin), **FX** (currency
  heatmap + PPP valuation for G10), **Leading Indicators** (LEI/CLI/CFNAI/PMI + IS-LM-PC
  3-panel + GSCPI), **Financial Conditions** (NFCI/STLFSI4/Fed balance sheet/EPU),
  **Positioning** (COT Report — 6 key contracts, net speculator position, COT Index). Markets
  page gains **Institutional Holders (13F)** and **Insider Activity (Form 4)** panels.
  New services: `macro_expansion_service`, `rates_service`, `cot_service`, `edgar_service`;
  new router `market_data` (`/api/market/13f`, `/api/market/form4`); 10 new routes on `macro`
  router. **368 pytest pass. Verified live in Docker:** all 7 new endpoints return HTTP 200
  with real data (`/api/macro/rates`, `/inflation`, `/commodities`, `/positioning`,
  `/api/market/13f?ticker=AAPL`, `/api/market/form4?ticker=AAPL`).

- ✅ **Phase 9** (`9ec9d71`) — Snowflake Composite Score. Pentagon radar chart scoring each stock 0–10
  on 5 axes (Value, Growth, Performance, Health, Dividend), sector-normalised via percentile ranking
  within screener cache peer universe. Full endpoint `/api/snowflake?ticker=` uses yfinance historical
  financials for 3Y CAGRs + full 9/9 Piotroski (prior-year support added to `fundamentals.py`) +
  Ohlson O-Score + ROIC−WACC spread (FRED DGS10 via `discount_rates.py`) + interest coverage.
  Batch endpoint `/api/snowflake/batch?tickers=` for lightweight screener SparkCard thumbnails.
  Frontend: `SnowflakeChart` (full radar + strengths/risks panel) in Markets Overview + Valuation tabs
  with axis-click tab navigation; `SnowflakeMini` (compact 100×100) in Screener Charts view.
  **368 pytest pass. Verified live:** AAPL → 7.11 Strong; batch and pages HTTP 200.

- ✅ **Phase 10** — Sector Performance Charts. New `/sectors` page + "Sectors" nav tab.
  **KPI strip**: 11 SPDR ETF cards (1D return, red/green, clickable to trigger drill-down).
  **Returns charts**: period tabs (1D/1W/1M/3M/YTD/1Y) each rendering a sorted horizontal bar
  chart (green/red per sign). **Fundamentals table**: 4 sub-tabs (Overview/Valuation/Performance/
  Volatility) with AUM, P/E, P/B, div yield, beta, vol30d, max drawdown.
  **Sector Rotation Clock**: Recharts ScatterChart bubble plot — X=vs SPY 3M, Y=3M return,
  bubble size=AUM; Sam Stovall 4-phase (Early/Mid/Late/Recession) implied from outperformance
  ranking; regime cross-validation via `regime_service.regime_series("US")`.
  **Industry drill-down**: click any sector bar or bubble → queries screener SQLite cache for
  top-3 stocks per GICS industry within that sector; chips link to `/markets?ticker=`; "See all"
  links to `/screener?sector=`.
  New backend: `services/sector_service.py` (4 functions, all `@cached` 60 min) +
  `routers/sector.py` (`/api/sector/returns`, `/fundamentals`, `/rotation`, `/drill`).
  **368 pytest pass. Docker rebuild clean. Verified live:** all 4 endpoints return real data;
  `/sectors` HTTP 200.

- ✅ **Phase 11** (`aee9c35`, `7aa2e5f`) — Portfolio Analytics. New `/portfolio` page + "Portfolio" nav tab.
  Holdings stored in localStorage; default portfolio AAPL 40%/MSFT 30%/GOOGL 20%/BRK-B 10%.
  **4-tab layout**: Overview | Risk | Attribution | Optimize.
  **Overview 🟢**: performance chart vs ^GSPC + AGG (base-100 cumulative), drawdown underwater curve,
  holdings table (weight/return/contribution).
  **Risk 🟢**: NxN correlation heatmap, variance risk-contribution horizontal bars, rolling
  Sharpe/Vol/Beta with window selector (20/60/120/252D).
  **Attribution 🟢/🟡**: CAPM decomposition (annualised alpha, beta, R², systematic vs idiosyncratic
  variance); 🟡 Kelly criterion position sizing (`f* = μ/σ²`); 🟡 Fama-French FF3/FF5 factor loadings
  via Ken French daily CSVs.
  **Optimize 🔴**: Efficient Frontier (SLSQP, long-only, 50-point sweep + max-Sharpe star);
  Monte Carlo random-weight cloud (10k Dirichlet, 5k points returned, coloured by Sharpe);
  Black-Litterman (τ=0.05, δ=2.5 risk aversion, user views form → posterior returns + optimal weights);
  Stress Testing (GFC/COVID/rates/dotcom replay on weighted portfolio).
  Backend: extended `services/portfolio.py` (12 new functions) + `routers/portfolio.py`
  (13 endpoints under `/api/portfolio/`; 🟢 cached 60 min, 🟡/🔴 uncached).
  Frontend: 15 new components in `components/portfolio/`.
  **368 pytest pass. tsc clean (Next.js build). Verified live in Docker:** all 12 endpoints return
  HTTP 200 with real data including Black-Litterman posterior returns; `/portfolio` HTTP 200.

- ✅ **Phase 12** — Advanced Technicals. New "Technicals" tab on the Markets page between "Risk" and "Valuation".
  **KPI strip**: Trend (SMA50 vs SMA200), RSI-14, MACD signal (Bullish/Bearish), Volume vs 20D avg, 52-week position %.
  **Price chart overlays**: toggle pills for Bollinger Bands (upper/mid/lower), Ichimoku Cloud (Tenkan/Kijun/Senkou A+B/Chikou), Fibonacci Retracement (7 levels from 6M swing H/L), Classic Pivot Points (daily/weekly/monthly P/R1/R2/S1/S2).
  **Sub-charts** (7 panels): MACD (line + signal + histogram), RSI-14, Stochastic RSI (K/D), Williams %R, OBV, CMF-20, ATR-14.
  **Fibonacci table** and **Pivot Points table** below charts.
  **5 new screener presets** (category: "technical"): `bb_squeeze` (Bollinger Squeeze), `ichimoku_bull` (Ichimoku Bullish), `ichimoku_bear` (Ichimoku Bearish), `obv_divergence` (OBV Divergence), `cmf_rsi` (CMF+ & RSI<50).
  **Screener cache**: 8 new columns added (`macd`, `macd_signal`, `bb_pct_b`, `bb_squeeze`, `obv`, `cmf20`, `ichimoku_bullish`, `obv_divergence`) with idempotent `ALTER TABLE` migration.
  **Screener Technicals tab** now shows new columns (MACD, BB %B, BB Squeeze, CMF 20, Ichimoku Bullish, OBV Divergence).
  New backend: `services/technicals_service.py` (full pandas_ta computation, `@cached` 60 min) + `routers/technicals.py` (`GET /api/technicals?ticker=&period=`). Dockerfile upgraded to run `pip install --upgrade pip setuptools wheel` before requirements to fix `pkg_resources` build error.
  **368 pytest pass. tsc clean. Verified live in Docker:** `/api/technicals?ticker=AAPL&period=1y` returns real data for all 9 indicator arrays (macd:319, bollinger:325, ichimoku:344, rsi:343, stochRsi:328, williamsR:331, obv:343, cmf:325, atr:331, fibLevels:7, pivotPoints with daily/weekly/monthly); 5 new presets visible in `/api/screener/presets`; `/markets` HTTP 200.

### Working agreements (carry these forward)

- **Per-phase Docker gate:** after coding a phase, run `pytest` + `tsc`, then do a
  **Docker rebuild + recreate** (`docker compose build backend frontend &&
  docker compose up -d --force-recreate`) and run live checks (curl the new
  endpoints + page HTTP 200) before moving on. As of Phase 4 **Claude runs the
  rebuilds itself** (user authorised). **Prefer a cached `build`** — it's much
  faster and the Dockerfile `COPY` layer still invalidates on any changed source,
  so it does *not* keep stale code (the old "no-cache only" note was overcautious).
  Fall back to `--no-cache` only if a build behaves as if source is stale. If
  Docker errors, sound an **audible alert** (`[console]::beep(880,600)`) so the
  user can fix the environment.
- **Env keys on this machine:** `FRED_API_KEY` **is set** (FRED release calendar +
  US FRED macro data work live). `FINNHUB_API_KEY` **is now set** (confirmed Phase 9
  session) → Finnhub calendar, earnings, and economic endpoints are live.
- **Compute tiers:** 🟢 runs on page load · 🟡 "Calculate" button · 🔴 "Run
  Analysis" button. Never auto-trigger 🟡/🔴.
- **UI rule:** every section = 3–6 KPIs on top + full extended list below.
- **yfinance safety:** always `.get()` with fallbacks; any field may be `None`.
- **Never scrape HTML** (no BeautifulSoup/Selenium) — use MediaWiki API +
  wikitextparser, direct CSV/Excel/ZIP downloads. **Never fabricate data**; on a
  source failure, log + serve cached, then surface it.
- **Commit + push to `main` after each phase**, message focused on the "why".
- Optional: dispatch labelled sub-agents (Frontend/Backend/Math = sonnet,
  Data = haiku) for parallel work on disjoint file sets; the orchestrator wires
  shared files (`main.py`, `api.ts`, `types.ts`, pages, routers).

### Backend module map (added by this build)

`services/`: `dcf_engine`, `fx_service`, `regime_service`, `valuation_engine`,
`snowflake_service` (Phase 9 — 5-axis composite scoring, full + batch modes),
`discount_rates`, `fundamentals`, `analyst_service`, `fama_french`,
`constituents`, `breadth_service`, `indices_service`, `feargreed_service`,
`movers_service`, `treemap_service`, `finnhub_service`, `calendar_service`,
`screener_service`, `screener_cache`, `advanced_risk`, `options_engine`,
`macro_expansion_service`, `rates_service`, `cot_service`, `edgar_service`,
`sector_service` (Phase 10 — SPDR ETF returns/fundamentals/rotation/industry drill),
`technicals_service` (Phase 12 — full pandas_ta indicator suite: MACD/BB/Ichimoku/Fibonacci/Pivots/RSI/StochRSI/WilliamsR/OBV/CMF/ATR).
Routers: `valuation` (`/full`, `/dcf`, `/factors`), `dashboard` (`/breadth`,
`/indices`, `/fear-greed`, `/movers`, `/constituents`),
`treemap` (`/api/treemap?index=&period=`),
`calendar` (`/api/calendar?index=&start=&end=`),
`screener` (`/api/screener/universe`, `/presets`, `/status`, `/refresh`),
`risk` (`/api/risk/rolling`, `/extended`, `/correlation`, `/garch`, `/hurst`,
`/ou`, `/cointegration`, `/montecarlo`, `/stress`),
`options` (`/api/options/expiries`, `/ivmetrics`, `/chain`, `/termstructure`,
`/smile`, `/oiprofile`, `/montecarlo`),
`market_data` (`/api/market/13f`, `/api/market/form4`),
`snowflake` (`/api/snowflake`, `/api/snowflake/batch`),
`sector` (`/api/sector/returns`, `/api/sector/fundamentals`, `/api/sector/rotation`, `/api/sector/drill`),
`technicals` (`/api/technicals?ticker=&period=`),
`portfolio` (`/api/portfolio/analyze`, `/correlation`, `/risk-contribution`, `/capm`, `/rolling`,
`/kelly`, `/ff`, `/frontier`, `/montecarlo`, `/blacklitterman`, `/stress`),
`macro` — Phase 8 routes added: `/api/macro/rates`, `/inflation`, `/employment`,
`/housing`, `/commodities`, `/fx/heatmap`, `/fx/ppp`, `/leading`,
`/financial-conditions`, `/positioning`.
All external calls cached via `@cached` / `@async_cached` in `cache.py`.
🟡/🔴 endpoints in `risk.py` and `options.py` are intentionally uncached (compute-on-demand).

---

## Feature Ideas

### High-Impact / Core Enhancements

1. **Portfolio Builder & Tracker**
   Allow users to create a named portfolio by adding multiple tickers with share counts or weights. Show aggregate performance, total P&L, weighted risk metrics, and a portfolio-level Sharpe ratio. Persist portfolios in localStorage or a lightweight SQLite backend.

2. **Earnings Calendar & Event Overlay**
   Surface upcoming earnings dates, dividend ex-dates, and stock splits directly on the price chart as vertical event markers. yfinance already provides this data via `ticker.calendar` and `ticker.dividends`.

3. **Sector & Industry Heatmap**
   A color-coded grid (red/green) showing intraday or weekly performance by S&P 500 sector, similar to Finviz. Use yfinance sector ETFs (XLK, XLF, XLE, etc.) as proxies. Gives users an instant macro-to-micro view.

4. **Watchlist with Price Alerts**
   A persistent watchlist panel where users can pin tickers and set price-level or percentage-change alerts. Alerts could trigger browser notifications (Notifications API) or write to a local log.

5. **Technical Indicators on Price Chart**
   Add toggleable overlays: SMA (20/50/200), EMA, Bollinger Bands, RSI (sub-chart), MACD. All computable from existing OHLCV data without new dependencies (or add `pandas-ta`).

---

### Analytics & Intelligence

6. **AI-Powered Company Summary**
   On the Markets page, add a "Summarize" button that calls the Claude API (claude-sonnet-4-6) with the company's financial ratios, valuation signals, and risk metrics and returns a plain-English analyst-style paragraph. Great for non-technical users.

7. **Multi-Factor Screening**
   A stock screener where users set filters (P/E < 15, Debt/Equity < 0.5, Sharpe > 1, etc.) against a user-defined universe of tickers. Returns a ranked table. Runs entirely on the existing `/api/ratios` and `/api/market/risk` endpoints.

8. **Macro Regime Detector**
   Classify the current macro environment (expansion, slowdown, stagflation, recession) using a simple rules engine over GDP growth, CPI, and unemployment for a selected country. Display a color-coded "regime badge" on the Macro page.

9. **Relative Strength Rankings**
   Rank a basket of tickers by rolling 1/3/6-month returns, normalized vs. their benchmark. Useful for momentum-based screening. Extend the `/api/market/prices` endpoint to accept multiple tickers and return a sorted ranking.

10. **News Feed Integration**
    Pull recent news headlines per ticker from a free source (Yahoo Finance RSS via yfinance `ticker.news`, or GNews free tier). Display as a sidebar panel on the Markets page with sentiment scoring (positive/neutral/negative) using a lightweight keyword classifier.

---

### Macro Enhancements

11. **Country Comparison Cards**
    A side-by-side snapshot card view for any two selected countries showing all 9 macro indicators at once, with traffic-light coloring (green = healthy, yellow = watch, red = warning) based on configurable thresholds.

12. **Yield Curve Visualizer**
    Plot the full government bond yield curve (2Y, 5Y, 10Y, 30Y) for US, EU, and UK using FRED and ECB data. Show inversion detection (2Y > 10Y) as a warning badge — historically a recession signal.

13. **Macro Indicator Forecasts**
    Pull IMF World Economic Outlook projections (already partially available via imfp) and overlay forecast lines on existing historical charts with a dashed style.

14. **Global Inflation Comparison Heatmap**
    A year-by-year heatmap grid (countries × years) for CPI inflation, color-coded from low (blue) to high (red). Instantly surfaces which countries have chronic inflation problems.

---

### UX / Developer Experience

15. **Shareable URLs / Deep Linking**
    Encode the current dashboard state (selected tickers, time period, active tab) in the URL query string. Users can bookmark or share a specific view without re-entering inputs.

16. **Export to CSV / PDF**
    Add an export button on the Risk Metrics and Ratios tabs. CSV for data; PDF using browser `window.print()` with a print-optimized stylesheet. No additional dependencies needed.

17. **Dark/Light Theme Persistence**
    Currently the theme toggle likely resets on page reload. Persist the preference in `localStorage` so the chosen theme survives refreshes.

18. **Backend Health Dashboard**
    An `/admin` page showing cache hit rates, data-source success/failure counts per macro source, and API response time percentiles. Useful for debugging which fallback sources are actually firing.

19. **Configurable Benchmark Override**
    Let users manually override the auto-detected benchmark (e.g., compare AAPL to ^NDX instead of ^GSPC) via a UI dropdown on the Markets page. The backend already supports arbitrary benchmark tickers.

20. **Mobile Bottom Navigation**
    Replace the top navbar with a fixed bottom tab bar on small screens (Markets | Macro | Watchlist) for better mobile ergonomics. Tailwind's responsive utilities make this straightforward.

---

## Recently Shipped Features

- Company switcher in Ratios tab, ratio explanations, professional PDF export
- Watchlist, SMA indicators (20/50/200), URL deep-linking, CSV export, macro regime detector
- Portfolio builder (#1), sector heatmap (#3), watchlist price alerts (#4),
  multi-factor screener (#7), relative-strength rankings (#9), backend health
  dashboard (#18) — all yfinance-backed
- Earnings/dividend/split chart overlays (#2), news feed with keyword sentiment
  (#10), configurable benchmark override (#19)
- Country comparison cards (#11), yield-curve visualizer with inversion badge
  (#12), IMF WEO forecast overlays (#13), inflation heatmap (#14)
- Mobile bottom navigation (#20); theme persistence (#17) confirmed
- **Phase 0–2 build** (see "Active Build" above): two-stage DCF, FX panel, regime
  clock; valuation engine + composite + fundamentals + analyst + Fama-French;
  market breadth, global indices, Fear & Greed, top movers, `/dashboard` page.

Note: AI-powered company summary (#6) intentionally not implemented — keeps the
app free of paid-API dependencies.

---

## Development Notes

- All external API calls are cached 60 min via `@cached` in `backend/backend/cache.py`
- Macro data sourcing uses a priority waterfall defined in `backend/backend/sources/`
- Frontend API client is at `frontend/lib/api.ts` — add new endpoint calls here
- Shared TypeScript types live in `frontend/lib/types.ts`
- To add a new backend route: create a router in `backend/backend/routers/`, register it in `main.py`

---

## Workflow Instructions
Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
### Git & GitHub
- Commit to GitHub regularly — after every meaningful unit of work (a feature, a fix, a refactor). Don't batch unrelated changes into one commit.
- Use clear, descriptive commit messages focused on the "why", not just the "what".
- Push to `main` after each commit unless told otherwise.

### Skills
- Automatically invoke available skills whenever they are relevant to the task at hand — do not wait to be asked.
- Examples: use `/senior-frontend` or `/senior-backend` when implementing features, `/api-design-reviewer` when adding routes, `/financial-analyst` when working on finance-related features, `/ui-ux-pro-max` for UI work, `/security-review` before pushing sensitive changes, `/spec-driven-workflow` for planning larger features.
