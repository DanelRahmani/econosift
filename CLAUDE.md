# Axiom Finance — CLAUDE.md

## What This App Does

Axiom Finance is a self-hosted financial analytics platform built on FastAPI + Next.js 14, containerized via Docker Compose. It covers the full investment research stack across 25 pages:

- **Dashboard** (`/dashboard`): Market breadth (advancing/declining, McClellan Oscillator, cumulative A-D line), global indices, Fear & Greed Index with sub-components, top movers. Beginner-mode walkthrough available.
- **Markets** (`/markets`): Price charts, technical indicators (MACD, Bollinger Bands, Ichimoku Cloud, Fibonacci, Pivot Points), risk metrics (VaR, Sharpe, Beta, GARCH), 8-model valuation engine + DCF with per-country discount rate selector + Snowflake composite score, financial ratios, options & IV analytics, news feed, 13F institutional holdings, Form 4 insider transactions. Sub-tabs: Overview, Technicals, Valuation, Ratios, News & Events, Sectors, Treemap
- **Screener** (`/screener`): S&P 500 / Nasdaq 100 / Dow 30 universe, 20+ preset signals, overnight-warmed cache, 9 result tabs with sparkline gallery
- **Portfolio** (`/portfolio`): Efficient frontier, Black-Litterman, Monte Carlo, Fama-French 3/5-factor attribution, Kelly criterion, risk contribution decomposition, stress testing, scenario lab, transaction log (buy/sell tracking with cost basis and realized P&L)
- **Scenario Lab** (`/scenario`): Dedicated page for historical stress tests (GFC, COVID, dot-com, 2022 rates) and custom macro shock simulation. Reuses the backend scenario engine from Portfolio.
- **Research** (`/research`): 9-tab quant hub — Risk Parity (ERC/inverse-vol), FX Carry (G10), Momentum (decile backtest), Realized Moments (GK variance, skew, cross-section), Cross-Asset Correlation (stocks/bonds/commodities/FX matrix), FX-Macro Link (commodity pair lead/lag), Multi-Country Portfolio (FX-adjusted returns), Sector DuPont, Econometric Lab (pooled OLS)
- **Macro** (`/macro`): 16-tab hub — Overview, Inflation, Growth & Employment, Housing, Commodities, FX, Leading Indicators, Financial & Funding Conditions, Positioning, Country Risk, Central Banks, Econometric Lab, Fiscal, Labor, Energy & Climate, Inequality
- **Risk** (`/risk`): Rolling metrics (20D/60D/120D/252D), GARCH(1,1), Hurst exponent, OU mean-reversion, Engle-Granger cointegration, correlation matrix, historical stress scenarios
- **Options** (`/options`): IV30, IV Rank/Percentile, Greeks (Δ/Γ/Θ/V/ρ), term structure, volatility smile, OI profile, max pain, Black-Scholes, CRR binomial tree, Monte Carlo
- **Calendar** (`/calendar`): Economic releases, earnings with EPS surprise, ex-dividend dates, IPOs, central bank meetings
- **Yield** (`/yield`): US Treasury spot curve, TIPS real yields, breakevens, ACM term premium, multi-country yield comparison
- **Policy & Sovereign** (`/policy`, `/sovereign`): CB divergence score, G10 carry differentials, sovereign risk rankings, 6-KPI traffic-light
- **Atlas** (`/atlas`): Choropleth world map of 6 macro indicators across ~200 countries (2000–2024), year-slider animation, regional blocs (G7/G20/Eurozone/EM), Top/Bottom-10 rankings
- **Wiki** (`/wiki`): Searchable financial dictionary — 410+ terms across 26 categories, each with a detailed explanation. Category sidebar, debounced search, expandable term cards, related-term cross-linking
- **Trade** (`/trade`): Exports/imports %GDP, trade balances, openness indices, BIS effective exchange rates
- **Corporate Health** (`/corporate`): Altman Z-Score, Piotroski F-Score (9-point), Beneish M-Score, sector aggregate Z
- **Dividends** (`/dividends`): Dividend yield, 5Y/10Y growth, payout ratio, aristocrats screener, DDM fair value
- **Insider** (`/insider`): Aggregate insider buy/sell ratio, cluster detection (≥3 insiders in 30d), sector sentiment, smart money index
- **Mergers** (`/mergers`): M&A deal tracking, deal values, acquisition premiums, sector activity heatmap
- **Stability** (`/stability`): Currency Crisis Early Warning System (KLR 1998), Banking Stability (NPL, capital adequacy, Z-scores, BIS credit gaps)
- **Cross-Border** (`/crossborder`): BIS locational banking statistics, international debt securities, global financial interconnectedness
- **Country Profiles** (`/country/{iso2}`): CIA World Factbook data per country — geography, demographics, economy
- **AI Summaries** (on-request): AI-powered company analysis with clickable ticker pills (select any combination on Markets), macro summary with searchable 20-country pill selector on Macro Overview, and daily market briefing on Dashboard. Uses Google Gemini free-tier API (2048 max output tokens) with model selector, SQLite caching, and source attribution for all summaries.
- **Admin** (`/admin`): Backend health dashboard, cache stats, API keys management (FRED/Finnhub/Gemini validation)

No paid APIs required. Optional free FRED API key & FINNHUB API key for richer US data, and free Gemini API key for AI summaries.

## Tech Stack

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

---

## Build History

See [`CHANGELOG.md`](./CHANGELOG.md) for the full build history (Phases 0–35 ✅ COMPLETE).

The original `claude_plan.md` roadmap (Phases 0–12) is fully delivered, as is the Phase 13–24 expansion, the Phase 25–34 IDEA_LIST delivery, and Phase 35 AI summaries. All phases are shipped and verified in Docker. Future work should start a new phase plan (e.g. Phase 36+).

> **After completing each phase, add a one-line entry to [`CHANGELOG.md`](./CHANGELOG.md)** with phase number, date, and concise description of what was shipped.

### Windows Desktop Package (Tauri) — v1.0.0

Alongside the Docker deployment, Axiom Finance ships as a native Windows desktop app (`desktop/`). A Tauri v2 Rust shell hosts the static Next.js export and spawns the FastAPI backend — frozen with PyInstaller **onedir** (`backend/build.spec`, `collect_all()` over the full dependency stack) — as a child process on `127.0.0.1:8000`. App data lives in `%APPDATA%/AxiomFinance` via `AXIOM_DATA_DIR` (`database.py` resolves the SQLite path from `config.DATA_DIR`). Build with `desktop/build-windows.ps1`; the NSIS installer is published via Git LFS under `releases/` and built in CI by `.github/workflows/build-windows.yml`. See [`desktop/README.md`](./desktop/README.md) for build steps and DESK-01/DESK-02 in [`ACTIVE_ISSUES.md`](./ACTIVE_ISSUES.md) for known caveats.

### Module Maps

See the INFO folder for detailed file-by-file breakdowns of the backend and frontend:

| File | Covers |
|------|--------|
| [`INFO/backend_structure.md`](./INFO/backend_structure.md) | All 33 routers, 68 services, 8 source adapters, database, tests |
| [`INFO/frontend_structure.md`](./INFO/frontend_structure.md) | All 25 pages, 118 components, 8 lib files |

Key architecture notes:
- All external API calls are cached via `@cached` / `@async_cached` in `cache.py` (60-min TTL, cachetools TTLCache + SQLite HybridCache two-tier)
- 🟡/🔴 endpoints in `risk.py` and `options.py` are intentionally uncached (compute-on-demand)
- Middleware: `middleware.py` (DeduplicationMiddleware stub)
- Database: `database.py` (SQLAlchemy engine, SessionLocal), `db_models.py` (DailyPrice, DailyQuote, DailyMacro, DailyFX, CacheEntry, JobExecution)

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

## Active Issues

See [`ACTIVE_ISSUES.md`](./ACTIVE_ISSUES.md) for the consolidated issue tracker (P0–P3, all deferred items, and recently fixed items).

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
