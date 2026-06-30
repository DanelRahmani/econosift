# Changelog — Axiom Finance

> Concise build history. See commits for details.
> All phases shipped via Docker Compose on a self-hosted Windows machine.

---

## Phase 37: Tauri Desktop App (2026-06-30)

- **Frontend:** Switched to `output: "export"` (static HTML); API client uses configurable base URL (`NEXT_PUBLIC_API_URL`); added `generateStaticParams` for `country/[iso2]` dynamic routes
- **Desktop:** New `desktop/` Tauri v2 Rust project; Rust sidecar manager spawns Python backend binary, polls health check, shows error dialog on failure; placeholder icons generated
- **Backend:** PyInstaller `build.spec` to compile Python into `axiom-backend` binary; data directory resolves via `AXIOM_DATA_DIR` env var with OS-standard fallback; settings.json read for API keys
- **Settings UI:** New `SettingsPanel.tsx` modal for FRED/Finnhub/Gemini API keys; saves via Tauri FS plugin (Docker admin API fallback); gear icon in navbar
- **CI/CD:** GitHub Actions matrix build on `windows-latest`, `macos-latest`, `ubuntu-latest`; pipeline: PyInstaller → Next.js static export → Tauri build → GitHub Release on tag
- **Auto-update:** Tauri updater via GitHub Releases; signing keys generated with pubkey in `tauri.conf.json`

## Phase 36 — P1 Bug Fixes (2026-06-30)

| ID | Description |
|----|-------------|
| P1-03 | Atlas map — added error state, key prop on ComposableMap, improved geojson fetch |
| P1-04 | Rate-limit batching — BATCH_SIZE 5→10, progressive backoff in `yfinance_service.py` |
| P1-05 | Multi-country macro — World Bank fallback for non-US `/macro/inflation` and `/macro/employment` |
| P1-06 | CountrySelector — `timeoutRef` cleared on `pick()` to prevent stale dropdown reopen |
| P1-07 | Dashboard React #425 — defensive `String()` wrapping in `FearGreedGauge` and `BreadthBar` |
| P1-08 | 30Y breakeven — `DGS30 − DFII30` fallback when `T30YIE` FRED series empty |
| P1-09 | Scenario Lab — dedicated `/scenario` page with Suspense boundary, nav entries in Navbar + MobileNav |
| P1-10 | Econometric Lab — error handling in `runRegression()`, surfaces failures to UI |
| P1-11 | BIS credit gaps — `bis_credit_gap` added to `BIS_DATASETS` and download URL map |
| P1-12 | DCF share count — `marketCap / currentPrice` cross-validation heuristic in `dcf_engine.py` + `valuation_engine.py` |
| P1-13 | Piotroski F-Score — `_prior_val()` with quarterly fallback for prior-year data (AAPL: 8/9, was 4/9) |
| P1-14 | Beneish M-Score — same fix as P1-13 (AAPL: −2.00, 7/8 components, was null) |

All 12 P1 issues resolved. 85 DCF/valuation tests pass. TypeScript compiles clean.

| Phase | Date | Description | Commit |
|-------|------|-------------|--------|
| Setup | — | Deps, pytest + Playwright harness, Finnhub config | `02f5028` |
| Phase 0 | — | DCF engine, FX rates panel, regime clock | `390438b` |
| Phase 1 | — | Valuation engine (8-model), extended fundamentals, analyst data, Fama-French | `4b21fae` |
| UI Polish | — | Metrics colour coding, ratio guide, cleaner macro chart tooltips | `374a49a` |
| Phase 2 | — | Dashboard breadth, indices, Fear & Greed, top movers | `7937e9c` |
| Phase 3 | — | S&P 500 Treemap with sector/industry drill-down | `4bd7393` |
| Phase 4 | — | Calendar: macro, earnings, dividends, IPOs, CB meetings | `06c613a` |
| Phase 5 | — | Screener: cached universe, presets, 9 result tabs, sparkline gallery | `a9dbb8b` |
| Phase 6 | — | Risk: rolling metrics, GARCH/Hurst/cointegration, stress/Monte Carlo | `dccc5f5` |
| Phase 7 | — | Options: IV analytics, Greeks, term structure, OI, binomial/MC pricing | `4c7f01a` |
| Phase 8 | — | Macro expansion (10 tabs), 13F/Form 4 panels | `1815c9e` |
| Phase 9 | — | Snowflake composite score: 5-axis radar + batch endpoint | `9ec9d71` |
| Phase 10 | — | Sectors: SPDR ETF KPIs, return charts, rotation clock, industry drill-down | `10e9c0b` |
| Phase 11 | — | Portfolio: efficient frontier, Black-Litterman, Monte Carlo, Fama-French, stress | `aee9c35` |
| Phase 12 | — | Advanced technicals: MACD/BB/Ichimoku/Fibonacci/Pivots on Markets + Screener | `c061511` |

---

## Phase 13–24: Expansion

| Phase | Date | Description | Commit |
|-------|------|-------------|--------|
| Phase 13 | 2026-06-25 | Atlas: world choropleth, 6 indicators, year slider, regional blocs WB/IMF data | `34148aa` |
| Phase 14 | 2026-06-25 | Research Hub: Risk Parity (ERC/inverse-vol), FX Carry (G10), Momentum (decile backtests) | `ae01e35` |
| Phase 15 | 2026-06-26 | Realized Moments (GK variance, skew, cross-section) + Econometric Lab (pooled OLS, no statsmodels) | `49048c4` |
| Phase 16 | 2026-06-26 | Country Risk (6-KPI traffic-light) + Central Bank Tracker (7 CBs, IRSTCI01/IR3TIB01) | `8003fa8` |
| Phase 17 | 2026-06-27 | SQLite persistence (6 ORM tables), APScheduler jobs, React Query v5, HybridCache, composite endpoint, admin performance, Nginx gzip, progressive tab loading | `466be45` |
| Phase 18A | 2026-06-27 | Macro-Financial Intelligence: credit_market, yield_curve, policy, sovereign_risk, macro_regime services. /yield, /policy, /sovereign pages | `ebe152d` |
| Phase 19 | 2026-06-27 | UI & Data Quality fixes (5 sub-phases, 21 fixes): dividend yield scaling, dark chart Y-axis, calendar FRED filter, nav overflow, treemap UX, dashboard null-safety, options IV clamp, yfinance 401 retry, Docker DNS | `72477bd` |
| Phase 20 | 2026-06-26 | Macro Policy Pages: funding_service fix, commodities→FRED, FX→FRED, PPP rewrite, COT fallbacks, CentralBanksTab, FinancialConditions, LeadingIndicators, RegimeClock | `6ba3a5e` |
| Phase 21 | 2026-06-26 | Wiki: 410 financial terms, 26 categories, debounced search, category sidebar, expandable cards, related-term cross-linking | `6403132` |
| Phase 22 | 2026-06-27 | UI Theming: neutral grey palette, PageSkeleton + EmptyState components, Fear & Greed SVG gauge, maroon accent | `5644c34` |
| Phase 23 | 2026-06-27 | UI Polish: PageSkeleton rollout, sticky tab bars, mobile nav collapse, screener persistence, Yield+Policy merge, country search in EconLab, live FRED risk-free rates | `07ca909` |
| Phase 24 | 2026-06-28 | Bulk Data Pipeline (WB/IMF/BIS/Fama-French parquet), BIS integration (CPI/policy/FX/credit gaps), macro regime overhaul, prefetch system (95 tasks), Docker healthcheck | `d5eb553` |

---

## Phase 25–36: IDEA_LIST Delivery

| Phase | Date | Description | Commit |
|-------|------|-------------|--------|
| Phase 25 | 2026-06-29 | Fiscal Sustainability tab (/macro), BIS Property Prices → Housing tab, BIS Credit Gaps → Financial Conditions tab | `9ec9e91` |
| Phase 26 | 2026-06-29 | Trade Flows & Globalization page (/trade): exports/imports, trade balances, openness indices, BIS effective FX | `9ec9e91` |
| Phase 27 | 2026-06-29 | Corporate Health Monitor (/corporate): Altman Z, Piotroski 9-pt, Beneish M. Dividend Analysis (/dividends): yield, growth, payout, aristocrats. Insider Trading Aggregator. Sector DuPont Analysis. Inflation Expectations → Inflation tab | `9ec9e91` |
| Phase 30 | 2026-06-29 | Business Dynamism tab, M&A/Corporate Actions tracker, Demographics→Atlas overlay, Short Interest→Markets panel | `df7dae8` |
| Phase 31 | 2026-06-29 | Banking & Financial Stability (/stability): NPL, capital adequacy, Z-scores, BIS credit gaps. Cross-Border Finance (/crossborder): BIS locational banking stats, debt securities. Sovereign Default Probability Model | `282703f` |
| Phase 32 | 2026-06-29 | Wired 3 macro tabs that were built but missing router endpoints: Labor Market Deep Dive (/macro?tab=labor), Energy Transition & Climate (/macro?tab=energy), Inequality & Development (/macro?tab=inequality) | `9a6a297` |
| Phase 33 | 2026-06-29 | Currency Crisis Early Warning: upgraded to 6-signal KLR model with reserves decline + FX overvaluation signals | `78ae75b` |
| Phase 34 | 2026-06-29 | Supply Chain Vulnerability Atlas layer: 13th indicator — choropleth map. IDEA_LIST: 22/22 complete 🎉 | `b496559` |
| Phase 35 | 2026-06-29 | AI-Powered Summaries: Google Gemini — company/macro/dashboard summaries with SQLite caching, model selector, clickable chips, source attribution | `5875bbb` |
| Phase 36 | 2026-06-29 | Shareable URLs / Deep Linking + Configurable Benchmark Override on Markets + Risk pages | `e14ee06` |

---

## Phase 37–40: Remaining P3 Features

| Phase | Date | Description |
|-------|------|-------------|
| Phase 37 | 2026-06-30 | Portfolio Transaction Log: buy/sell tracking with cost basis, realized P&L (FIFO lot matching), localStorage + optional SQLite sync. New Transactions tab on /portfolio. | `b661e68` |
| Phase 38 | 2026-06-30 | Learning Layers: beginner/expert mode toggle, 60+ metric tooltips with explanations, page walkthrough banners on Dashboard/Markets/Portfolio. | `fdbae7c` |
| Phase 39 | 2026-06-30 | Cross-Asset & Factor Analytics: 3 new Research Hub tabs — Cross-Asset Correlation (stocks/bonds/commodities/FX matrix), FX-Macro Link (6 commodity pairs with lead/lag), Multi-Country Portfolio (FX-adjusted returns, currency exposure). | `ace186b` |
| Phase 40 | 2026-06-30 | Navigation Reshuffle: grouped More dropdown with 5 section headers (Discover/Analyze/Markets & Data/Global/Reference). Renamed "M&A" → "Mergers & Acquisitions", "Rates & Policy" → "Yield". Primary bar unchanged per user direction. IDEA_LIST: all 3 P3 items complete. | `6e4a752` |

---

## Legend

- All phases have verified commit references from git history
- Phases 13–40 were shipped via the per-phase Docker gate workflow (build → recreate → curl → browser check)
