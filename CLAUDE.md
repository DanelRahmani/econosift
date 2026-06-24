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
  API, weekly cache) is reused by Phases 3 & 5.
- ⏭️ **Phase 3 — S&P 500 Treemap** is next. Then Phases 4–12.

### Working agreements (carry these forward)

- **Per-phase Docker gate:** after coding a phase, run `pytest` + `tsc`, then the
  user does a **full no-cache rebuild** (`docker compose build --no-cache backend
  frontend && docker compose up -d --force-recreate`) — cached builds silently
  keep stale source. The user runs the rebuild and says when it's "live"; then
  run live checks (curl the new endpoints + page HTTP 200) before moving on.
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
`discount_rates`, `fundamentals`, `analyst_service`, `fama_french`,
`constituents`, `breadth_service`, `indices_service`, `feargreed_service`,
`movers_service`. Routers: `valuation` (`/full`, `/dcf`, `/factors`),
`dashboard` (`/breadth`, `/indices`, `/fear-greed`, `/movers`, `/constituents`).
All external calls cached via `@cached` / `@async_cached` in `cache.py`.

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

### Git & GitHub
- Commit to GitHub regularly — after every meaningful unit of work (a feature, a fix, a refactor). Don't batch unrelated changes into one commit.
- Use clear, descriptive commit messages focused on the "why", not just the "what".
- Push to `main` after each commit unless told otherwise.

### Skills
- Automatically invoke available skills whenever they are relevant to the task at hand — do not wait to be asked.
- Examples: use `/senior-frontend` or `/senior-backend` when implementing features, `/api-design-reviewer` when adding routes, `/financial-analyst` when working on finance-related features, `/ui-ux-pro-max` for UI work, `/security-review` before pushing sensitive changes, `/spec-driven-workflow` for planning larger features.
