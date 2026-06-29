# Axiom Finance — Feature Idea List

> Last cleaned: 2026-06-29 — 28 items removed (Phases 18A, 25–35), AI Company & AI Macro summaries now shipped in Phase 35.
> Remaining: 5 pending/partial ideas + Navigation Reshuffle Plan.

---

## 2. Data Source Quick Reference

| Source | Package | Coverage | Currently Mapped | Untapped Potential |
|--------|---------|----------|------------------|-------------------|
| World Bank | `wbgapi` | ~200 countries, ~1,400 indicators | 19 indicators | 1,380+ indicators |
| FRED | `fredapi` | US-focused, 800K+ series | ~40 series | Massive untapped US data |
| IMF WEO | `imfp` | ~190 countries, forecasts | 6 indicators | Additional WEO indicators |
| BIS | httpx + ZIP | 50+ countries, 6 datasets | CPI, policy, FX, credit gaps, property prices, effective FX | Banking stats |
| ECB | `ecbdata` | Eurozone only | Inflation, policy rate | ECB SDW has hundreds of series |
| Frankfurter | httpx | 30+ currencies | Spot + history FX | — |
| DB.nomics | `dbnomics` | OECD + BIS | 4 indicators | Full OECD database |
| yfinance | `yfinance` | US + international stocks | Price/OHLC only | Full financial statements, dividends, info |
| Finnhub | httpx | US + some global | Calendar, news, earnings | Short interest, M&A, corporate actions |
| EDGAR | `edgartools` | US-listed companies | 13F, Form 4 per ticker | Aggregate insider analysis |
| CFTC | httpx + ZIP | US futures | COT reports | Disaggregated COT, supplemental reports |
| Local | JSON + Parquet | Damodaran ERP, sector multiples, CB meetings, bulk cache | 4 local files | Expand static datasets |

---

## 3. 🧠 Additional Ideas — Pending & Partially Done

Older brainstorming ideas. Only items not yet fully shipped are listed below.

### ✅ P2 — Shareable URLs / Deep Linking — **Done Phase 36**
Encode dashboard state (selected tickers, period, active tab) in URL query string for bookmarking/sharing.
- **Data:** URL state only. Pure frontend.
- **Status:** Rolled out to all 11 pages with user-selectable state via `useUrlState` hook.

### ✅ P2 — Configurable Benchmark Override — **Done Phase 36**
Let users manually override auto-detected benchmark (e.g., AAPL vs ^NDX instead of ^GSPC) via UI dropdown.
- **Data:** No new data needed. Backend already supported `&benchmark=` param.
- **Status:** Benchmark dropdown now on Markets (Overview + Technicals) and Risk page, wired to all backend endpoints.

### P3 — Portfolio Transaction Log
Add buy/sell dates, cost basis, and realized P&L tracking (currently theoretical allocations only).
- **Data:** User input only — no external data needed.

### P3 — Cross-Asset & Factor Analytics (Research-Grade)
Multi-country portfolio builder, factor attribution, FX/commodity macro-link panels, cross-asset correlation heatmaps.
- **Data:** All existing data — pure calculation + visualization. Significant effort.

### P3 — Learning Layers
Beginner-friendly toggles, narrative walkthroughs explaining metrics, academic-style embedded notebooks.
- **Data:** No new data — educational UX layer.

---

## 4. 🧭 Navigation Reshuffle Plan

### Problem

The current top-level navigation is a **flat 16-item bar** with no grouping, mixing micro (per-ticker) tools with macro (global) tools and reference pages. This creates severe cognitive load.

### Proposed Nav Hierarchy (5 Pillars)

| Pillar | Items |
|--------|-------|
| **Discover** | Dashboard, Screener, Treemap, Calendar |
| **Analyze** | Markets (5 streamlined tabs), Risk, Options |
| **Build** | Portfolio, Research (5 tabs, incl. Econ Lab moved from Macro), Scenario |
| **Macro** | Macro Overview (8 condensed tabs), Yield, Policy & Sovereign (merged), Atlas |
| **Learn** | Wiki |

### Markets Tab Reductions (10 → 5)
- **Remove**: Sectors (→ `/sectors`), Screener (→ `/screener`), Portfolio (→ `/portfolio`), Rankings (→ `/screener`), FX (→ `/macro?tab=FX`), Risk (replace with mini KPI strip in Overview)
- **Keep**: Overview, Technicals, Valuation, Ratios, News & Events

### Macro Tab Reductions (15 → 8)
- **Remove/redirect**: Rates & Yields (→ `/yield`), Country Risk (→ `/policy`), Central Banks (→ `/policy`), Econometric Lab (→ `/research`), Funding (merged into Financial Conditions)
- **Keep**: Overview, Inflation, Growth & Employment, Housing, Commodities, FX, Leading Indicators, Financial & Funding Conditions, Sentiment Signals

### Pages to Promote
- **`/scenario`** — orphaned stress lab → promoted to nav under Build pillar
- **`/admin`** — orphaned health dashboard → optionally add under Settings/gear icon

### URL Redirects (301 / next.config.js rewrites)
12 old URLs need redirects, preserving query params where applicable (e.g., `/markets?tab=Portfolio&t=AAPL` → `/portfolio?t=AAPL`).

### Implementation Order
1. Navbar restructure (Navbar.tsx + MobileNav.tsx)
2. Markets tab removals
3. Macro tab removals/redirects
4. Move Econometric Lab → /research
5. Merge Policy + Sovereign
6. Promote /scenario to nav
7. Add next.config.js rewrites
8. Test: pytest + tsc + Docker rebuild + curl each path

---

## Summary Matrix

| # | Idea | Category | Priority | New Data Needed? | Effort | Status |
|---|------|----------|----------|------------------|--------|--------|
| 1 | Labor Market Deep Dive | Macro Tab | P1 | 5 WB codes + 2 FRED | Medium | ✅ DONE Phase 32 |
| 2 | Energy Transition & Climate | Macro Tab | P1 | 6 new WB codes | Medium | ✅ DONE Phase 32 |
| 3 | Inequality & Development | Macro Tab | P1 | 5 new WB codes | Medium | ✅ DONE Phase 32 |
| 4 | Currency Crisis Early Warning | Tool | P1 | 1 new WB code | Medium | ✅ DONE Phase 33 |
| 5 | Supply Chain → Atlas Overlay | Enhance | P1 | 2 WB codes + bilateral data | Medium | ✅ DONE Phase 34 |

**Completed:** 22/22 · **Remaining:** 0 🎉
