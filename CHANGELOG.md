# Changelog — Axiom Finance

> Concise build history. See commits for details.
> All phases shipped via Docker Compose on a self-hosted Windows machine.

---

## Phase 0–12: Foundation (Original Roadmap)

| Phase | Date | Description | Commit |
|-------|------|-------------|--------|
| Setup | — | Deps, pytest + Playwright harness, Finnhub config | `02f5028` |
| Phase 0 | — | DCF engine, FX rates panel, regime clock | `390438b` |
| Phase 1 | — | Valuation engine (8-model), extended fundamentals, analyst data, Fama-French | — |
| UI Polish | — | Metrics colour coding, ratio guide, cleaner macro chart tooltips | `374a49a` |
| Phase 2 | — | Dashboard breadth, indices, Fear & Greed, top movers | `7937e9c` |
| Phase 3 | — | S&P 500 Treemap with sector/industry drill-down | — |
| Phase 4 | — | Calendar: macro, earnings, dividends, IPOs, CB meetings | — |
| Phase 5 | — | Screener: cached universe, presets, 9 result tabs, sparkline gallery | `a9dbb8b` |
| Phase 6 | — | Risk: rolling metrics, GARCH/Hurst/cointegration, stress/Monte Carlo | `dccc5f5` |
| Phase 7 | — | Options: IV analytics, Greeks, term structure, OI, binomial/MC pricing | `4c7f01a` |
| Phase 8 | — | Macro expansion (10 tabs), 13F/Form 4 panels | `1815c9e` |
| Phase 9 | — | Snowflake composite score: 5-axis radar + batch endpoint | `9ec9d71` |
| Phase 10 | — | Sectors: SPDR ETF KPIs, return charts, rotation clock, industry drill-down | — |
| Phase 11 | — | Portfolio: efficient frontier, Black-Litterman, Monte Carlo, Fama-French, stress | `aee9c35` |
| Phase 12 | — | Advanced technicals: MACD/BB/Ichimoku/Fibonacci/Pivots on Markets + Screener | — |

---

## Phase 13–24: Expansion

| Phase | Date | Description |
|-------|------|-------------|
| Phase 13 | 2026-06-25 | Atlas: world choropleth, 6 indicators, year slider, regional blocs WB/IMF data |
| Phase 14 | 2026-06-25 | Research Hub: Risk Parity (ERC/inverse-vol), FX Carry (G10), Momentum (decile backtests) |
| Phase 15 | 2026-06-26 | Realized Moments (GK variance, skew, cross-section) + Econometric Lab (pooled OLS, no statsmodels) |
| Phase 16 | 2026-06-26 | Country Risk (6-KPI traffic-light) + Central Bank Tracker (7 CBs, IRSTCI01/IR3TIB01) |
| Phase 17 | 2026-06-27 | SQLite persistence (6 ORM tables), APScheduler jobs, React Query v5, HybridCache, composite endpoint, admin performance, Nginx gzip, progressive tab loading |
| Phase 18A | 2026-06-27 | Macro-Financial Intelligence: credit_market, yield_curve, policy, sovereign_risk, macro_regime services. /yield, /policy, /sovereign pages |
| Phase 19 | 2026-06-27 | UI & Data Quality fixes (5 sub-phases, 21 fixes): dividend yield scaling, dark chart Y-axis, calendar FRED filter, nav overflow, treemap UX, dashboard null-safety, options IV clamp, yfinance 401 retry, Docker DNS |
| Phase 20 | 2026-06-26 | Macro Policy Pages: funding_service fix, commodities→FRED, FX→FRED, PPP rewrite, COT fallbacks, CentralBanksTab, FinancialConditions, LeadingIndicators, RegimeClock |
| Phase 21 | 2026-06-26 | Wiki: 410 financial terms, 26 categories, debounced search, category sidebar, expandable cards, related-term cross-linking |
| Phase 22 | 2026-06-27 | UI Theming: neutral grey palette, PageSkeleton + EmptyState components, Fear & Greed SVG gauge, maroon accent |
| Phase 23 | 2026-06-27 | UI Polish: PageSkeleton rollout, sticky tab bars, mobile nav collapse, screener persistence, Yield+Policy merge, country search in EconLab, live FRED risk-free rates |
| Phase 24 | 2026-06-28 | Bulk Data Pipeline (WB/IMF/BIS/Fama-French parquet), BIS integration (CPI/policy/FX/credit gaps), macro regime overhaul, prefetch system (95 tasks), Docker healthcheck |

---

## Phase 25–31: IDEA_LIST Delivery

| Phase | Date | Description |
|-------|------|-------------|
| Phase 25 | 2026-06-29 | Fiscal Sustainability tab (/macro), BIS Property Prices → Housing tab, BIS Credit Gaps → Financial Conditions tab |
| Phase 26 | 2026-06-29 | Trade Flows & Globalization page (/trade): exports/imports, trade balances, openness indices, BIS effective FX |
| Phase 27 | 2026-06-29 | Corporate Health Monitor (/corporate): Altman Z, Piotroski 9-pt, Beneish M. Dividend Analysis (/dividends): yield, growth, payout, aristocrats. Insider Trading Aggregator. Sector DuPont Analysis. Inflation Expectations → Inflation tab |
| Phase 30 | 2026-06-29 | Business Dynamism tab, M&A/Corporate Actions tracker, Demographics→Atlas overlay, Short Interest→Markets panel |
| Phase 31 | 2026-06-29 | Banking & Financial Stability (/stability): NPL, capital adequacy, Z-scores, BIS credit gaps. Cross-Border Finance (/crossborder): BIS locational banking stats, debt securities. Sovereign Default Probability Model |
| Phase 32 | 2026-06-29 | Wired 3 macro tabs that were built but missing router endpoints: Labor Market Deep Dive (/macro?tab=labor), Energy Transition & Climate (/macro?tab=energy), Inequality & Development (/macro?tab=inequality). ~15 lines in macro.py — services, frontend, and WB data were already complete |
| Phase 33 | 2026-06-29 | Currency Crisis Early Warning: upgraded from 5-signal proxy model to 6-signal KLR model. Added real reserves decline (FI.RES.TOTL.CD via WB) and FX overvaluation (BIS effective FX vs 5Y average) signals. Registered stability router in main.py (was missing). Updated frontend to show 6-KPI grid per country with Score: X/6 flags |
| Phase 34 | 2026-06-29 | Supply Chain Vulnerability Atlas layer: created supply_chain_service.py computing composite score from food_imports + fuel_imports (both already live). Added as 13th Atlas indicator — choropleth map + color scale + rankings auto-render. IMF DOTS (Tier A) and WB partner shares (Tier B) investigated but inaccessible. IDEA_LIST: 22/22 complete 🎉 |
| Phase 35 | 2026-06-29 | AI-Powered Summaries: Google Gemini integration for 3 on-request summaries — Company (per-ticker on Markets), Macro (per-country on Macro Overview), Dashboard (daily briefing). Prompts use Gemini's built-in knowledge (no server-side data gathering). SQLite-cached with regenerate button, model selector, clickable stock/country chips, and source attribution. Admin page Gemini key management. Nginx 360s timeout for AI endpoints. |
| Phase 36 | 2026-06-29 | Shareable URLs / Deep Linking: rolled out URL state sync to all 11 pages with user-selectable state using new shared `useUrlState` hook. Configurable Benchmark Override: benchmark dropdown now visible on Markets Technicals tab + new benchmark dropdown on Risk page, wired to all backend endpoints that already supported `&benchmark=`. |

---

## Legend

- Commits from Phase 0–12 are referenced where available from git history
- All phases after 13 were shipped via the per-phase Docker gate workflow (build → recreate → curl → browser check)
