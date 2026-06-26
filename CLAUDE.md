# Axiom Finance — CLAUDE.md

## What This App Does

Axiom Finance is a self-hosted financial analytics platform built on FastAPI + Next.js 14, containerized via Docker Compose. It covers the full investment research stack across 11 pages:

- **Markets** (`/markets`): Price charts, technical indicators (MACD/BB/Ichimoku/Fibonacci/Pivots), risk metrics (VaR/Sharpe/Beta/GARCH), valuation (8-model engine + DCF + Snowflake score), ratios, options & IV, news feed, 13F/Form 4
- **Dashboard** (`/dashboard`): Market breadth, global indices, Fear & Greed, top movers
- **Screener** (`/screener`): S&P 500 / Nasdaq 100 / Dow 30 universe with 20+ preset signals, overnight-warmed cache, 9 result tabs
- **Portfolio** (`/portfolio`): Efficient frontier, Black-Litterman, Monte Carlo, Fama-French attribution, stress testing
- **Risk** (`/risk`): Rolling metrics, GARCH, Hurst, cointegration, historical stress scenarios
- **Options** (`/options`): IV analytics, Greeks, term structure, OI profile, binomial pricing
- **Sectors** (`/sectors`): SPDR ETF returns, rotation clock, industry drill-down
- **Treemap** (`/treemap`): S&P 500 / Nasdaq / Dow squarified treemap with sector drill-down
- **Calendar** (`/calendar`): Earnings, dividends, macro releases, IPOs, CB meetings
- **Macro** (`/macro`): 12-tab macro hub — rates, inflation, growth, housing, commodities, FX, leading indicators, financial conditions, COT positioning, Econometric Lab, Country Risk, Central Banks
- **Atlas** (`/atlas`): Choropleth world map of 6 macro indicators across ~200 countries (2000–2024) with year-slider animation, regional blocs (G7/G20/Eurozone/EM), color legend, KPI strip, and Top/Bottom-10 rankings

No paid APIs required. Optional free FRED API key for richer US data.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, yfinance, pandas
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Recharts
- **Infra**: Docker Compose, Nginx reverse proxy

---

## Build History: Phases 0–13 ✅ COMPLETE

All phases 0–13 of the `claude_plan.md` roadmap are fully shipped and verified in Docker.
The original build plan is done; future work should start a new phase plan.
This section is the source of truth for cross-machine continuation.

### Completed Phases

- ✅ **Setup** (`02f5028`): Phase 0–12 deps, pytest + Playwright harness, Finnhub config.
- ✅ **Phase 0** (`390438b`): DCF engine, FX rates panel, regime clock.
- ✅ **Phase 1**: Valuation engine, extended fundamentals, analyst data, Fama-French attribution.
- ✅ **Phase 2** (`7937e9c`): Dashboard breadth, indices, Fear & Greed, top movers, shared universe sources.
- ✅ **UI polish** (`374a49a`): Metrics colour coding, ratio guide, cleaner macro chart tooltips.
- ✅ **Phase 3**: Treemap page with sector/industry drill-down and market cap service. Known issue: Yahoo market cap rate-limits large universes.
- ✅ **Phase 4**: Calendar page with macro releases, earnings, dividends, IPOs, and CB meetings.
- ✅ **Phase 5** (`a9dbb8b`): Screener overhaul with cached universe, presets, 9 result tabs, and sparkline gallery.
- ✅ **Phase 6** (`dccc5f5`): Risk page with rolling metrics, extended analytics, correlation, GARCH/Hurst/cointegration, and stress/Monte Carlo.
- ✅ **Phase 7** (`4c7f01a`): Options page with IV analytics, Greeks, term structure, OI profile, binomial pricing, and Monte Carlo.
- ✅ **Phase 8** (`1815c9e`, `783dc81`): Macro expansion to 10 tabs plus 13F/Form 4 market panels.
- ✅ **Phase 9** (`9ec9d71`): Snowflake composite score with 5-axis radar and batch endpoint.
- ✅ **Phase 10**: Sectors page with SPDR ETF KPIs, return charts, fundamentals, rotation clock, and industry drill-down.
- ✅ **Phase 11** (`aee9c35`, `7aa2e5f`): Portfolio analytics page with overview, risk, attribution, optimization, Black-Litterman, and stress testing.
- ✅ **Phase 12**: Advanced technicals on Markets plus screener technical indicators and presets.
- ✅ **Phase 13**: Atlas page with world choropleth, 6 macro indicators, year slider, regional blocs, and WB/IMF data.
- ✅ **Phase 14**: Research Hub (`/research`) — 3 tabs: Risk Parity (inverse-vol + ERC via SLSQP, monthly-rebalanced backtest vs 60/40 SPY+AGG), FX Carry (G10 carry table + long-top3/short-bottom3 backtest vs DXY), Cross-Sectional Momentum (1M/3M/6M/12M-1M deciles, Dow default + Nasdaq/S&P opt-in). Backtests + large-universe momentum gated behind 🔴 buttons. **Carry data note:** the plan's legacy `INTDSR*` discount-rate series ended ~2021 and fail the 120-day staleness guard — replaced with OECD immediate central-bank rates (`IRSTCI01*`) + 3-month interbank fallback (`IR3TIB01*`); USD=FEDFUNDS, EUR=ECBMRRFR. NOK/SEK omitted (no reliable G10 series). Live-verified: AUD top / JPY·CHF bottom carry, ERC weights sum to 1, top decile > bottom decile.
- ✅ **Phase 15**: Two new quantitative tools. **Realized Moments** (4th `/research` tab): Garman-Klass realized variance + rolling realized skew/excess-kurtosis (21/63/252d) per ticker from daily OHLC (`GET /api/research/moments`), plus a cross-sectional tail-return test ranking a universe by prior-1M realized skew → forward-1M return by decile (`GET /api/research/moments/crosssection`, Dow auto / ndx·sp500 behind 🔴). New `realized_moments_service.py`; added `get_ohlc_frame` to `yfinance_service.py`. GK σ² clipped at 0 before sqrt (can go negative); cross-section uses disjoint formation/forward bars (no lookahead). **Econometric Lab** (new `/macro` "Lab" tab): user-selectable pooled OLS across World Bank country panel data (`POST /api/macro/regress`), returning coefficients/SE/t/p with significance stars, R²/adjR²/AIC/BIC, residual scatter. New `econ_lab_service.py` — **numpy + scipy only (no statsmodels)**, reusing the `fama_french._ols` math pattern + `scipy.stats.t` for p-values; inner-joins (country,year) and drops incomplete rows; flags near-singular design matrices. Live-verified: all 3 endpoints HTTP 200, `/research` & `/macro?tab=lab` render 200, 508 backend tests green.

### Backend module map (added by this build)

`services/`: `dcf_engine`, `fx_service`, `regime_service`, `valuation_engine`, `snowflake_service`, `discount_rates`, `fundamentals`, `analyst_service`, `fama_french`, `constituents`, `breadth_service`, `indices_service`, `feargreed_service`, `movers_service`, `treemap_service`, `finnhub_service`, `calendar_service`, `screener_service`, `screener_cache`, `advanced_risk`, `options_engine`, `macro_expansion_service`, `rates_service`, `cot_service`, `edgar_service`, `sector_service`, `technicals_service`, `atlas_service`, `risk_parity_service`, `carry_service`, `momentum_service`, `realized_moments_service`, `econ_lab_service`, `country_risk_service`, `centralbanks_service`, `jobs`.
Routers: `valuation`, `dashboard`, `treemap`, `calendar`, `screener`, `risk`, `options`, `market_data` (+ `/composite`), `snowflake`, `sector`, `technicals`, `atlas`, `portfolio`, `macro`, `research`, `admin` (+ `/performance`).
Database: `database.py` (SQLAlchemy engine, SessionLocal), `db_models.py` (DailyPrice, DailyQuote, DailyMacro, DailyFX, JobExecution, CacheEntry).
Middleware: `middleware.py` (DeduplicationMiddleware stub).
All external calls cached via `@cached` / `@async_cached` in `cache.py`. `HybridCache` class available for two-tier memory+SQLite caching.
🟡/🔴 endpoints in `risk.py` and `options.py` are intentionally uncached (compute-on-demand).

---

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

---

## Upcoming Phases (14–16) — see `claude_plan.md` for full spec

New pages extending the platform into quantitative research. All data infrastructure already exists; gaps are frontend visualization and new signal logic only. No new API keys required.

- ✅ **Phase 13 — Global Macro Atlas** (`/atlas`) — **DONE** (see Phase 13 entry above for the full shipped feature set + live verification).

- ✅ **Phase 14 — Research Hub** (`/research`) — **DONE** (see Phase 14 entry above). **Next: Phase 15.** Note for Phase 16 Central Bank Tracker: do **not** use the plan's `INTDSR*` series — they're discontinued; reuse Phase 14's `IRSTCI01*`/`IR3TIB01*` series from `carry_service.py`.

- 🔲 **Phase 14 — Research Hub: Risk Parity + FX Carry + Momentum** (`/research`)
  Three-tab page covering quantitative research strategies.
  - **Risk Parity**: Inverse-vol and ERC (Equal Risk Contribution) weighting via SLSQP extension of `portfolio.py`. Multi-asset (equities/bonds/commodities). Backtest vs 60/40. New: `risk_parity_service.py`.
  - **FX Carry**: Long top-3 / short bottom-3 G10 pairs by interest differential. Policy rates from FRED `INTDSR*` series (BoE/BoC/RBA/SNB/BoJ/RBNZ — already have `fredapi`). Carry table + backtest chart. New: `carry_service.py`.
  - **Cross-Sectional Momentum**: Sort S&P 500 by 1M/3M/6M/12M-1M prior return into deciles; compute forward returns. Uses `screener_cache.py` SQLite. New: `momentum_service.py`.
  All in `routers/research.py`. `POST /api/research/riskparity`, `GET /api/research/carry`, `GET /api/research/momentum`.

- ✅ **Phase 15 — Realized Moments + Econometric Lab** — **DONE** (see Phase 15 entry in build history above). **Next: Phase 16.** Built with numpy + scipy (no statsmodels, per working agreement); reused `fama_french._ols` math pattern. `GET /api/research/moments`, `GET /api/research/moments/crosssection`, `POST /api/macro/regress`.

- ✅ **Phase 16 — Country Risk + Central Bank Tracker** (extend `/macro`) — **DONE**. Two new tabs added to the macro page.
  - **Country Risk tab**: 6-KPI traffic-light sovereign panel (debt/GDP, current account, inflation, fiscal balance, reserves growth, unemployment) for ~200-country WB universe, sorted by risk (most-red first). WB codes: `GC.DOD.TOTL.GD.ZS`, `BN.CAB.XOKA.GD.ZS`, `FP.CPI.TOTL.ZG`, `SL.UEM.TOTL.ZS` (reused from atlas_service) + `GC.BAL.CASH.GD.ZS` (fiscal balance) + `FI.RES.TOTL.CD` (reserves, YoY%). `GET /api/macro/country-risk?countries=`. New: `country_risk_service.py`.
  - **Central Banks tab**: Policy rate history 2005–present for 7 CBs (Fed/ECB/BoE/BoJ/BoC/RBA/SNB) using FRED `IRSTCI01*`/`IR3TIB01*` series (same as carry_service — **NOT** the discontinued `INTDSR*`). Fed balance sheet (`WALCL`). Multi-line Recharts chart + 7-CB KPI cards with next meeting countdown. `GET /api/macro/centralbanks`. New: `centralbanks_service.py`.
  - **CB meetings**: `backend/data/cb_meetings.json` extended from 32→52 entries with BoC (8), RBA (8), SNB (4) 2026 dates. ecocal library was investigated but not added (adds a scraping dep); hardcoded dates follow the established project pattern.
  - **Hashability fix**: `country_risk` endpoint passes countries as `tuple` (not list) to the `@async_cached` decorator.
  - Live-verified: both endpoints HTTP 200, traffic-light table and policy rate chart render in browser, 11 new unit tests passing.

- ✅ **Phase 17 — Performance & Persistence Layer** — **DONE**. SQLite persistence + APScheduler background jobs + React Query frontend caching.

- ✅ **Phase 18A — Macro-Financial Intelligence (backend + core pages)** — **DONE** (`ebb59da`→`066decd`). Turns Axiom into a macro-financial intelligence system with 5 new backend services, 3 new frontend pages, and 4 new router families.
  - **Credit Pulse** (`services/credit_market.py`, `GET /api/credit/pulse`): IG/HY OAS, BBB spread, SOFR/DTB3 funding spread splice with TEDRATE history. Stress signal when HY OAS >700bps or funding spread >50bps.
  - **Yield Curves** (`services/yield_curve_service.py`, `GET /api/yield/curves`): US spot curve (11 tenors), TIPS real yields (4 tenors), breakeven inflation (5Y/10Y/30Y), ACM term premium, 8 foreign 10Y spreads vs US (Germany/UK/Japan/France/Italy/Canada/Australia/Spain). Spread convention: 10Y−2Y (long minus short).
  - **Policy Intelligence** (`services/policy_service.py`, `GET /api/policy/tracker`): CB divergence score + stance classification (tightening/easing/on_hold) for Fed/ECB/BoE/BoJ/BoC/RBA/SNB using Phase 14's `IRSTCI01*`/`IR3TIB01*` series with freshness-ranked fallback. G10 carry differentials vs USD.
  - **Sovereign Risk** (`services/sovereign_risk_service.py`, `GET /api/sovereign/risk`): 10Y spread vs US Treasury + WB composite macro score (debt/GDP, fiscal balance, CA balance, inflation, unemployment) for 8 countries. Traffic-light risk signal.
  - **Macro Regime** (`services/macro_regime_service.py`, `GET /api/macro/regime`): 4-quadrant growth×inflation regime classifier with regime-adjusted asset allocation signals.
  - **Frontend**: `/yield` (US curve/real yields/breakevens), `/policy` (CB divergence table/stance badges/carry), `/sovereign` (risk rankings/spread panels) — all 3 pages HTTP 200 and rendering live data. Navbar updated.
  - **Live-verified**: all 5 endpoints HTTP 200, all 3 pages rendering data (US 10Y 4.41%, Fed easing 3.63%, UK sovereign risk score 46.1 vs Germany 13.6). 563 tests passing.
  - **Known minor items for 18B cleanup**: `datetime.utcnow()` deprecation warning in `policy_service.py`; ACM term premium and 30Y breakeven show N/A when FRED series lags (graceful fallback working).
  - **Deferred to Phase 18B**: `/scenario` lab, Econometric Lab enhancements, EM sovereign risk watch, regime overlays on Atlas/Macro, funding/liquidity panel.
  - **Database** (`database.py`, `db_models.py`): SQLite (WAL mode) with 6 ORM tables: `DailyPrice`, `DailyQuote`, `DailyMacro`, `DailyFX`, `JobExecution`, `CacheEntry`. Volume-mounted at `/app/data` for persistence across restarts. `init_db()` called on startup (idempotent).
  - **Job Infrastructure** (`services/jobs.py`): APScheduler `BackgroundScheduler` with 3 cron jobs: `refresh_daily_prices` (16:00 UTC), `refresh_daily_quotes` (17:00 UTC), `refresh_fx_rates` (09/15/21 UTC). Job execution logged to `JobExecution` table. Controlled via `SCHEDULER_ENABLED` env var.
  - **HybridCache** (added to `cache.py`): Two-tier cache — in-memory `TTLCache` → SQLite `CacheEntry` fallback. Existing `@cached`/`@async_cached` decorators unchanged. Stats track `hits_mem`, `hits_db`, `misses`. `get_stale_while_revalidate()` for SWR pattern.
  - **Composite endpoint** (`GET /api/market/composite`): Single OHLCV fetch returns `{prices, risk, quotes}` — eliminates 3-request waterfall. Registered in `market_data.py`. `DeduplicationMiddleware` stub in `middleware.py`.
  - **Admin endpoint** (`GET /api/admin/performance`): Returns cache stats + last-24h job execution log + DB connection info.
  - **Nginx**: gzip enabled for JSON/JS/CSS, `proxy_read_timeout` reduced 120s → 60s.
  - **React Query v5** (`@tanstack/react-query@5.101.1`): `queryClient.ts` with staleTime 5min / gcTime 30min. `Providers` wrapper in `frontend/components/providers.tsx`, wired into `layout.tsx`.
  - **Markets page refactor**: 4 `useState` vars + 2 manual `useEffect` blocks replaced with 3 `useQuery` hooks. `PriceChart` gains `isLoading` skeleton prop.
  - **Progressive tab loading**: 8 heavy tabs (`ValuationTab`, `TechnicalsTab`, `RatiosTab`, `PortfolioTab`, `RankingsTab`, `SectorHeatmap`, `ScreenerTab`, `FxRatesPanel`) converted to `lazy()` + `<Suspense fallback={<TabSkeleton />}>`. Overview and Risk tabs remain eager.
  - **Backfill scripts**: `backend/scripts/backfill_ohlcv.py` (5Y OHLCV for S&P 500 + NDX + Dow in batches of 50) and `backend/scripts/backfill_macro.py` (12 FRED series from 2000–present). Run once post-deployment inside Docker.
  - **Docker**: `sqlite_data` named volume added. No new containers.
  - Live-verified: 557 tests passing (38 new), all Phase 0–16 endpoints HTTP 200, composite endpoint returns prices+quotes in <500ms, DB persists across `docker compose down/up`.

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
