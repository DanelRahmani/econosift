# Axiom Finance — CLAUDE.md

## What This App Does

Axiom Finance is a self-hosted financial analytics platform built on FastAPI + Next.js 14, containerized via Docker Compose. It covers the full investment research stack across 14 pages:

- **Markets** (`/markets`): Price charts, technical indicators (MACD/BB/Ichimoku/Fibonacci/Pivots), risk metrics (VaR/Sharpe/Beta/GARCH), valuation (8-model engine + DCF + Snowflake score), ratios, options & IV, news feed, 13F/Form 4, sector drill-down, treemap
- **Dashboard** (`/dashboard`): Market breadth, global indices, Fear & Greed, top movers
- **Screener** (`/screener`): S&P 500 / Nasdaq 100 / Dow 30 universe with 20+ preset signals, overnight-warmed cache, 9 result tabs
- **Portfolio** (`/portfolio`): Efficient frontier, Black-Litterman, Monte Carlo, Fama-French attribution, stress testing, scenario analysis
- **Risk** (`/risk`): Rolling metrics, GARCH, Hurst, cointegration, historical stress scenarios
- **Options** (`/options`): IV analytics, Greeks, term structure, OI profile, binomial pricing
- **Calendar** (`/calendar`): Earnings, dividends, macro releases, IPOs, CB meetings
- **Macro** (`/macro`): 9-tab macro hub — overview, inflation, growth & employment, housing, commodities, FX, leading indicators, financial & funding conditions, sentiment & positioning
- **Atlas** (`/atlas`): Choropleth world map of 6 macro indicators across ~200 countries (2000–2024) with year-slider animation, regional blocs (G7/G20/Eurozone/EM), color legend, KPI strip, and Top/Bottom-10 rankings
- **Research** (`/research`): 5-tab quant hub — Risk Parity, FX Carry, Momentum, Realized Moments, Econometric Lab
- **Yield** (`/yield`): US Treasury spot curve, TIPS real yields, breakevens, ACM term premium
- **Policy** (`/policy`): Central bank policy rate divergence, G10 carry differentials, sovereign risk rankings
- **Sovereign** (`/sovereign`): Country risk heatmap, sovereign credit metrics
- **Wiki** (`/wiki`): Searchable financial dictionary of 410+ terms across 26 categories — each with a detailed 3-5 sentence explanation covering what it is, how it's used, and why it matters. Category sidebar, debounced search, expandable term cards, related-term cross-linking. Backed by `wiki_service.py` and `GET /api/wiki/terms?search=&category=` endpoint.

No paid APIs required. Optional free FRED API key for richer US data.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, yfinance, pandas
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Recharts
- **Infra**: Docker Compose, Nginx reverse proxy

---

## Build History: Phases 0–24 ✅ COMPLETE

All phases 0–24 of the `claude_plan.md` roadmap are fully shipped and verified in Docker.
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
- ✅ **Phase 16**: Country Risk + Central Bank Tracker (extend `/macro`). Country Risk tab: 6-KPI traffic-light sovereign panel for ~200 countries via World Bank. Central Banks tab: policy rate history 2005–present for 7 CBs (Fed/ECB/BoE/BoJ/BoC/RBA/SNB) using `IRSTCI01*`/`IR3TIB01*` FRED series + Fed balance sheet (`WALCL`). New services: `country_risk_service.py`, `centralbanks_service.py`. CB meetings JSON extended 32→52 entries.
- ✅ **Phase 17**: Performance & Persistence Layer. SQLite (WAL mode) with 6 ORM tables, APScheduler background jobs (daily price/quote/FX refresh), React Query v5 frontend caching, HybridCache (memory→SQLite two-tier), composite `/api/market/composite` endpoint, admin `/api/admin/performance`, Nginx gzip, progressive tab lazy-loading with Suspense. Backfill scripts for OHLCV and macro data.
- ✅ **Phase 18A**: Macro-Financial Intelligence. 5 new backend services (credit_market, yield_curve, policy, sovereign_risk, macro_regime), 3 new frontend pages (`/yield`, `/policy`, `/sovereign`). US spot curve, TIPS real yields, breakevens, ACM term premium, CB divergence score, G10 carry differentials, sovereign risk rankings. 563 tests passing.
- ✅ **Phase 19**: UI & Data Quality Fixes (`0d3a005`→`72477bd`). 5 sub-phases (A–E), 21 fixes. P0: dividend yield scaling, dark-mode chart Y-axis, calendar FRED filter, loading UX, KPI truncation. P1: nav overflow + mobile nav pages, treemap UX, dashboard null-safety, options IV clamp. P2: timestamp formatting, portfolio placeholders, calendar category colors, mobile theme toggle. Backend: yfinance 401 retry, DNS fix, dead Phase 18B code removal. Live-verified: all pages HTTP 200, builds green, pytest passing.
- ✅ **Phase 20** (2026-06-26): Macro Policy Pages overhaul — 6 backend fixes, 8 frontend fixes. **Backend**: Fixed broken `funding_service.py` (wrong imports/wrong function signatures — M2, SOFR, CP spread now work). Commodities switched from yfinance `=F` tickers to FRED primary (DCOILWTICO, GOLDAMGBD228NLBR, etc.). FX heatmap switched from yfinance `=X` to FRED DEX* series (EUR/USD, GBP/USD, etc.). PPP endpoint rewritten to use FRED DEX spot rates + CPI (8 pairs). Financial Conditions: WALCL Fed BS scaled to $T, C&I loans fixed (BUSLOANS series), ciLoans added to KPIs. Leading Indicators: base year normalization added (`?base_year=2020`), ISLMPC data normalized to index=100. Inflation: Quantity Theory now computes YoY changes with dual-axis chart. COT service: multiple URL fallbacks, expanded column name candidates. **Frontend**: CentralBanksTab — time span selector (1Y/5Y/10Y/All) with proper tick formatting, full CB names (US Federal Reserve, etc.), correct Fed BS label. FinancialConditions — EPU log scale toggle. GrowthEmployment — NFP 5Y/All time buttons, fixed existing home sales Y-axis (3M–5M). Housing — existing home sales scaling (÷1M). LeadingIndicators — base year selector dropdown, ISLMPC current position dots, index labels. RegimeClock — quadrant labels centered, country selector in MacroOverview. CommoditiesTab — KPI cards and data table rendering from FRED. **Note**: COT/Positioning tab may still show empty data (CFTC source issue); Econ Lab API works but frontend needs investigation; Atlas map rendering unreliable.
- ✅ **Phase 21** (2026-06-26): Wiki/Dictionary page. **Backend**: New `wiki_service.py` with 410 financial terms across 26 categories, each with detailed 3-5 sentence explanations. New `wiki.py` router with `GET /api/wiki/categories`, `GET /api/wiki/terms?search=&category=`, `GET /api/wiki/term/{slug}`. **Frontend**: New `/wiki` page with debounced search, category sidebar (desktop) / horizontal pills (mobile), expandable term cards with related-term cross-linking. New components: `WikiSearch.tsx`, `WikiTermCard.tsx`, `WikiCategoryNav.tsx`. Navbar/MobileNav updated with Wiki tab. Wiki types added to `types.ts`, API methods added to `api.ts`. **Bug fixes**: Fixed 3 `data.baseYear` → `baseYear` references in `LeadingIndicators.tsx`; fixed `nominalGdpYoY`/`m2YoY` → `nominalGdp`/`m2` in `InflationTab.tsx`. Live-verified: `/wiki` HTTP 200, search works, category filter works, expand/collapse works, related-term links navigate correctly.
- ✅ **Phase 22** (2026-06-27): UI Theming Overhaul. **Color system**: Light mode surfaces switched from warm beige (`250,245,246`) to clean near-white (`248,248,251`); dark mode background from reddish-black (`15,6,8`) to neutral greyish-black (`12,12,14`). All text/border/surface tokens updated to neutral greys. Maroon accent preserved. Chart palette (`chartPalette()` in `ui.tsx`, `CHART_COLORS` in `format.ts`) synced to new backgrounds. **Components**: New `PageSkeleton` (centered spinner) and `EmptyState` (icon + title + description) base components added to `ui.tsx`, applied to `InflationTab.tsx`. **Fear & Greed gauge**: Redesigned SVG semicircle with tick marks (0/25/50/75/100), value below needle pivot, thinner stroke. **Verification**: 17 pages HTTP 200 in both themes, `tsc` clean, Docker build + recreate, 568 backend tests passing.
- ✅ **Phase 23** (2026-06-27): UI Polish Pass. PageSkeleton rollout to heavy pages, sticky tab bars, mobile nav collapse, screener persistence, Yield+Policy merge, country search in EconLab, live FRED risk-free rates with per-country DCF discount rate selector.
- ✅ **Phase 24** (2026-06-28): Bulk Data Pipeline, BIS Integration, Macro Regime Overhaul. **BIS source** (`source_bis.py`): ZIP-based API fallback for CPI, policy rates, FX rates, credit gaps — exchange rates correctly converted from BIS "foreign per USD" to standard convention (XM/GB/AU/NZ inverted). **Bulk data downloads** (`bulk_data_service.py`): 4-source pipeline — World Bank (55K rows), IMF WEO (55K rows), Fama-French, BIS (3 datasets, 42K rows) — stored as parquet, weekly refresh (Sun 4:00 UTC). **Prefetch system** (`prefetch_service.py`): 95-task cache warming with rate-limited staggering (1.5s normal / 5.0s heavy), admin UI with progress bar. **HybridCache persistence**: `@cached`/`@async_cached` decorators wired into SQLite `cache_entry` table — data survives container restarts. **Scheduler fixes**: Fixed yfinance imports in `jobs.py`, added `refresh_daily_macro` (10 FRED indicators), startup trigger for all 5 jobs. **Macro regime**: Fixed duplicate `/regime` routes (Phase 0 now `/regime-series`, Phase 18A serves classifier). `macro_regime_service` now returns quadrant (1-4), growth_z & inflation_z z-scores, numeric allocation % per regime. `regime_service` rewritten to use World Bank parquet data for all ~200 countries (iso2→iso3 via pycountry). **Frontend**: `RegimeOverlay` rewritten with typed `MacroRegimeData`, quadrant-colored banner, σ-scaled z-scores, asset allocation pills, dark mode. Admin page shows DB health (6 table row counts), Finnhub key status, Bulk Data Downloads table with BIS. New components: `DataFreshnessBadge`, `useKeyboardShortcuts`, `ExportPdfButton`, `ScrollableTabBar`. Navbar cleanup: merged Sectors+Treemap into Markets, Scenario into Portfolio. **Infra**: Docker healthcheck on backend with nginx `condition: service_healthy`, nginx `proxy_next_upstream` retry for 502 handling. **Verification**: 568+ tests passing, BIS CPI matches World Bank exactly (US 2023: 4.12%), all FX rates verified against real-world end-2024 values.

### Backend module map (added by this build)

`services/`: `dcf_engine`, `fx_service`, `regime_service`, `valuation_engine`, `snowflake_service`, `discount_rates`, `fundamentals`, `analyst_service`, `fama_french`, `constituents`, `breadth_service`, `indices_service`, `feargreed_service`, `movers_service`, `treemap_service`, `finnhub_service`, `calendar_service`, `screener_service`, `screener_cache`, `advanced_risk`, `options_engine`, `macro_expansion_service`, `macro_regime_service`, `rates_service`, `funding_service`, `cot_service`, `edgar_service`, `sector_service`, `technicals_service`, `atlas_service`, `risk_parity_service`, `carry_service`, `momentum_service`, `realized_moments_service`, `econ_lab_service`, `country_risk_service`, `centralbanks_service`, `wiki_service`, `risk_free_service`, `bulk_data_service`, `prefetch_service`, `jobs`.
Routers: `valuation`, `dashboard`, `treemap`, `calendar`, `screener`, `risk`, `options`, `market_data` (+ `/composite`), `snowflake`, `sector`, `technicals`, `atlas`, `portfolio`, `macro`, `research`, `admin` (+ `/performance`), `wiki`, `credit`, `yield_curve`, `policy`, `sovereign`.
Sources: `source_datareader`, `source_worldbank`, `source_imf`, `source_bis`.
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

## Phases 14–24 — Research, Macro-Financial Intelligence, & UI Overhaul ✅ COMPLETE

All phases 14 through 24 are fully shipped. Phases 18B was merged into 18A. Phase 19 (UI/data quality), 20 (macro policy pages), 21 (wiki), 22 (UI theming), 23 (UI polish pass), and 24 (BIS integration, bulk data pipeline, macro regime overhaul, prefetch system) are all shipped.

No remaining planned phases — the `claude_plan.md` roadmap is fully delivered. Future work should start a new phase plan (e.g. Phase 25+).

---

## Deferred Issues

Items explicitly excluded from completed phases — tracked for future work.

### From Phase 18A (Macro-Financial Intelligence)
- **`/scenario` lab page** — stress scenario designer, deferred from Phase 18B
- **Econometric Lab enhancements** — additional regression diagnostics, deferred from Phase 18B
- **EM sovereign risk watch** — extend sovereign risk panel to emerging markets
- **Regime overlays on Atlas/Macro** — overlay macro regime quadrant on Atlas map and Macro charts
- **`datetime.utcnow()` deprecation** — `policy_service.py` uses deprecated `datetime.utcnow()`, should switch to `datetime.now(datetime.UTC)`
- **ACM term premium / 30Y breakeven N/A** — FRED series sometimes lag, graceful fallback works but data is occasionally missing

### From Phase 19 (UI & Data Quality)
- **Admin page navigation link** — no navbar link to `/admin`, only accessible via direct URL (minor)
- **Markets sub-tab redundancy** — main nav items overlap with Markets page sub-tabs (cosmetic)
- **Fear & Greed per-signal explanation** (D-05) — documentation/minor
- **Atlas map rendering artifacts** (A-04) — likely a library limitation (react-simple-maps)
- **Mobile bottom nav 9-item layout** — pages added but full redesign deferred (cramped on small screens)
- **Dashboard McClellan signal explanation** (D-05) — minor documentation
- **Options ~15min delay badge restyle** (O-04) — minor
- **Compute-tier indicator consistency** (G-13) — minor
- **Active tab styling inconsistency** (G-15) — minor

### From Phase 24 (2026-06-28 — Bulk Data & BIS Integration)
- **Fama-French parsing** — only 12 rows captured; CSV parser truncates historical data (pre-2000 rows not parsed)
- **OECD SDMX integration** — API too complex for bulk download; deferred for future
- **BIS Credit-to-GDP gaps** — CSV format explored but not yet wired into `refresh_all_bulk_data`
- **COT/Positioning** — multiple URL fallbacks added; may still show empty (CFTC source format changes frequently)
- **Econ Lab frontend** — API works but frontend component needs investigation
- **Atlas map rendering** — unreliable, likely react-simple-maps limitation
- **Inflation/Rates/Overview country selectors** — not yet implemented (US-only)

### From Phase 22 (2026-06-27 — UI Theming Overhaul)
- **Wiki backend data loading** — API returns 0 terms for `/api/wiki/terms`; `wiki_service.py` data not loaded at startup
- **PageSkeleton rollout** — `PageSkeleton` component created but only applied to `InflationTab.tsx`; other heavy pages (Calendar, Treemap, Risk rolling metrics) still use bare `animate-pulse`
- **Markets sub-tab redundancy** — main nav items still overlap with Markets page sub-tabs (cosmetic, pre-existing)

### From Phase 23 (2026-06-27 — UI Polish Pass)
- **Calendar event quality** — FRED release calendar entries are non-actionable and drown out real economic events. A filter or source weighting pass is needed to prioritize high-impact macro releases (CPI, NFP, FOMC, GDP) over routine data releases.
- **Pattern Library** — The app has no shared component library for KPI strips, tab bars, or control bars. Each page hand-rolls these patterns. A `<KpiGrid>` + `<KpiCard>`, `<TabBar>`, and `<ControlBar>` component set would reduce duplication and enforce visual consistency across all 14 pages.

### From Phase 3 (Treemap)
- **Yahoo market cap rate-limits** — large universes (S&P 500) hit rate limits on `yfinance` market cap queries

### From Phase 18A (Removed Dead Code)
- **Taylor Rule calculator** (`econ_lab_service.py`) — Phase 18B stub removed in Phase 19E. Had broken `_fetch_fred_series` import and was never wired to any router. If revived, use `fetch_fred_series()` from `macro_expansion_service.py` (async, batch-oriented).

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
