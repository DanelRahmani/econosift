# Active Issues — Axiom Finance

> **Generated:** 2026-06-30 · **Test status:** 568+ backend tests passing
> Single source of truth for all known issues, consolidated from QA audits, deferred items, and the issue tracker.

---

## 🔴 P0 — Broken / Critical

*(No active P0 issues — all previously tracked P0 items have been resolved in earlier phases. See ✅ Recently Fixed below.)*

---

## 🟡 P1 — Important / Feature Gaps

*(All 12 P1 issues resolved in Phase 36. See ✅ Recently Fixed below.)*

---

## 🟢 P2 — Polish / UX

| ID | Issue | Source | Details |
|----|-------|--------|---------|
| P2-01 | **PageSkeleton not rolled out fully** | `ISSUES.md`, CLAUDE.md (Phase 22) | `PageSkeleton` now used in most pages (Yield, Trade, Screener, Portfolio, MacroTabShell, DuPont, TaylorRule, RollingMetrics, Inflation). Calendar, Treemap, Risk still use bare `animate-pulse`. |
| P2-02 | **Sub-tab scroll arrows needed** | `ISSUES.md` | Macro (9 tabs) and Markets sub-tabs overflow. Sticky position added (Phase 23) but no scroll arrows. |
| P2-03 | **Taylor Rule 500 errors (frontend)** | `ISSUES.md` | `/taylor-rule` endpoint exists (Phase 23) but Econ Lab shows "Failed to load Taylor Rule data" — frontend wiring fix needed. |
| P2-04 | **Mobile bottom nav cramped** | `ISSUES.md`, `UI_report.md` | 5 primary + More + Theme = 7 items. Tight on small phones. |
| P2-05 | **No React error boundaries** | `ISSUES.md` | Any render error whites out the page. Add `<ErrorBoundary>` with retry button. |
| P2-06 | **Data freshness badges** | `ISSUES.md` | No indication of when data was last updated. "Updated X ago" badges per panel. |
| P2-07 | **Keyboard shortcuts** | `ISSUES.md` | No keyboard nav. Ctrl+K search, number keys for tabs, arrow keys for periods. |
| P2-08 | **Export PDF button** | `ISSUES.md` | Print styles exist in `globals.css` but no "Export" button on any page. |
| P2-09 | **Fear & Greed per-signal explanation** | CLAUDE.md (Phase 19), `UI_report.md` | McClellan "Extreme Greed" at 81 while composite is 44 "Fear" — confusing without explanation. |
| P2-10 | **Markets sub-tab redundancy** | CLAUDE.md (Phase 19/22) | Main nav items overlap with Markets page sub-tabs (cosmetic). Also tracked in `UX_Reshuffle.md`. |
| P2-11 | **Active tab styling inconsistency** | CLAUDE.md (Phase 19), `UI_report.md` | Main nav uses filled maroon pill; sub-tabs use underline; period buttons use outline. |
| P2-12 | **Options ~15min delay badge restyle** | CLAUDE.md (Phase 19) | Badge styling differs from other page badges (minor). |
| P2-13 | **Compute-tier indicator consistency** | CLAUDE.md (Phase 19), `UI_report.md` | Options uses `🔴` emoji in label; Research uses `🔴 Run Backtest` text. |
| P2-14 | **Calendar event quality** | CLAUDE.md (Phase 23) | FRED entries drown out real events. Prioritize CPI/NFP/FOMC/GDP over routine releases. |
| P2-15 | **Pattern Library** | CLAUDE.md (Phase 23) | No shared component library for KPI strips, tab bars, control bars. Every page hand-rolls these. |
| P2-16 | **Bar chart Y-axis labels suppressed** | CLAUDE.md (Phase 25) | Recharts auto-suppresses labels for vertical BarChart with 18+ countries. `shortCountryName()` + `width={90}` partial mitigation. |
| P2-22 | **COT/Positioning tab data unreliable** | `ISSUES.md`, CLAUDE.md (Phase 24) | CFTC source format changes frequently — downgraded from P1-02. Multiple URL fallbacks exist but data often empty. |
| P2-17 | **BIS Credit-to-GDP gaps cold-start** | CLAUDE.md (Phase 24/25) | Now wired into `refresh_all_bulk_data` via Phase 36 (P1-11). First cold-start still takes 90-120s but subsequent refreshes use cached parquet. |
| P2-18 | **Browser refresh needed after redeploy** | CLAUDE.md (Phase 25) | Stale JS bundles served after `docker compose up -d`. Hard-refresh required. |
| P2-19 | **`@async_cached` persistent cache trap** | CLAUDE.md (Phase 25) | Broken function run caches `{}` permanently in SQLite. Fix: clear both tiers (`_caches.clear()` + delete CacheEntry rows). |
| P2-20 | **Dividend yield display inconsistency** | `FACT_CHECK.md` | `ValuationKpiPanel` uses `fmtPct(v * 100)` for dividend yield — fragile pattern. Standardize percent formatting. |
| P2-21 | **Raw ISO timestamps shown to users** | `UI_report.md` (G-12) | Screener shows `as of 2026-06-25T14:40:30...` instead of readable format. |
| P2-23 | **Dark mode chart consistency** | `ISSUES.md` (P3-08) | Some Recharts components have hardcoded `stroke="#333"` instead of using `chartPalette()`. |

---

## 🔵 P3 — Future Features / Speculative

| ID | Feature | Source | Rationale |
|----|---------|--------|-----------|
| P3-01 | **Price alerts** | `ISSUES.md` | Set target prices, RSI thresholds, earnings dates — in-app notifications. No notification system exists. |
| P3-02 | **Compare mode on Markets** | `ISSUES.md` | Side-by-side metric comparison (P/E, EV/EBITDA, Beta) for selected tickers. |
| P3-03 | **Mobile PWA** | `ISSUES.md` | One `manifest.json` + service worker from installable app with offline cache. |
| P3-04 | **Portfolio transaction log** | `ISSUES.md` | Add buy/sell dates, cost basis, realized P&L. Currently theoretical allocations only. |
| P3-05 | **Custom screener formulas** | `ISSUES.md` | Let users type `pe < 15 && roe > 0.15` instead of only presets. |
| P3-06 | **`datetime.utcnow()` deprecation** | `ISSUES.md`, CLAUDE.md (Phase 18A) | `policy_service.py`, `admin.py`, tests use deprecated `datetime.utcnow()`. Switch to `datetime.now(datetime.UTC)`. |
| P3-07 | **EM sovereign risk watch** | CLAUDE.md (Phase 18A) | Extend sovereign risk panel to emerging markets. |
| P3-08 | **Regime overlays on Atlas/Macro** | CLAUDE.md (Phase 18A) | Overlay macro regime quadrant on Atlas map and Macro charts. |
| P3-09 | **OECD SDMX integration** | CLAUDE.md (Phase 24) | API too complex for bulk download; deferred. |
| P3-10 | **Econometric Lab enhancements** | CLAUDE.md (Phase 18A) | Additional regression diagnostics (fixed effects, lag selection). |
| P3-11 | **Taylor Rule calculator revival** | CLAUDE.md (Phase 18A) | Phase 18B stub removed in Phase 19E. If revived, use `fetch_fred_series()` from `macro_expansion_service.py`. |

---

## ✅ Recently Fixed

These items are verified as fixed in shipped phases. Listed here for reference to avoid re-reporting.

| ID | Issue | Fixed In |
|----|-------|----------|
| ✅ | Color system: beige → true white, reddish-black → greyish-black | Phase 22 |
| ✅ | Fear & Greed gauge redesign with tick marks | Phase 22 |
| ✅ | Admin nav link added | Phase 23 |
| ✅ | Screener remembers universe choice | Phase 23 |
| ✅ | Sticky sub-tab bars on all pages | Phase 23 |
| ✅ | Mobile nav collapse to 5 primary | Phase 23 |
| ✅ | Yield + Policy merge → "Rates & Policy" | Phase 23 |
| ✅ | Country search in Econometric Lab (200 countries) | Phase 23 |
| ✅ | Live FRED risk-free rates (13 countries) | Phase 23 |
| ✅ | Live Damodaran ERP (ctryprem.xlsx auto-download) | Phase 23 |
| ✅ | DCF discount rate selector with regional rates | Phase 23 |
| ✅ | Research Hub ticker SearchBar | Phase 23 |
| ✅ | Dark-mode Technicals Y-axis fix | Phase 19 |
| ✅ | Dividend yield double-scaling fix | Phase 19 |
| ✅ | Macro: Funding, Commodities, FX, PPP, Financial Conditions, NFP, ISLMPC, Quantity Theory, Central Banks, EPU, RegimeClock all fixed | Phase 20 |
| ✅ | Nav overflow scroll (desktop) | Phase 19 |
| ✅ | Mobile nav + Treemap/Calendar/Sectors/Theme | Phase 19 |
| ✅ | Treemap spinner + text contrast | Phase 19 |
| ✅ | Dashboard null-safety | Phase 19 |
| ✅ | Options IV clamp ≤500% | Phase 19 |
| ✅ | Portfolio "AAPL" → "Ticker" placeholder | Phase 19 |
| ✅ | yfinance 401 retry (2 retries) | Phase 19 |
| ✅ | Docker DNS (8.8.8.8/8.8.4.4) | Phase 19 |
| ✅ | Nginx healthcheck + proxy_next_upstream | Phase 24 |
| ✅ | BIS CPI matches World Bank exactly (US 2023: 4.12%) | Phase 24 |
| ✅ | Admin API keys management | Phase 24 |
| ✅ | Scheduler cron expression fixed (P0-01) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Backend 502 on restart — healthcheck + nginx retry (P0-02) | Phase 24 |
| ✅ | Wiki returns terms correctly (P0-03) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Calendar FRED noise removed — dropped in Phase 19 (P0-04) | Phase 19 |
| ✅ | yfinance missing keys — Fix 1–6 injected in `get_info()` (P0-06) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Options IV30 backsolve via `iv_backsolve()` Brent solver (P1-01) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Fama-French CSV parser no longer truncates (P1-10) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Beta computed & injected in `get_info()` KPI fix (P1-15) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | **P1-03**: Atlas map — added error state, key prop, improved geojson fetch | Phase 36 |
| ✅ | **P1-04**: Yahoo rate-limit batching — BATCH_SIZE 5→10, progressive backoff | Phase 36 |
| ✅ | **P1-05**: Multi-country macro — World Bank fallback for non-US inflation/employment | Phase 36 |
| ✅ | **P1-06**: CountrySelector typeahead — timeoutRef cleared on pick to prevent stale dropdown | Phase 36 |
| ✅ | **P1-07**: Dashboard React error #425 — defensive `String()` wrapping in FearGreedGauge/BreadthBar | Phase 36 |
| ✅ | **P1-08**: 30Y breakeven — DGS30−DFII30 fallback when T30YIE FRED series empty | Phase 36 |
| ✅ | **P1-09**: Scenario Lab — dedicated `/scenario` page created + nav entries | Phase 36 |
| ✅ | **P1-10**: Econometric Lab — error handling added to runRegression(), TaylorRuleWidget wrapped | Phase 36 |
| ✅ | **P1-11**: BIS Credit-to-GDP gaps — wired into `BIS_DATASETS` bulk refresh | Phase 36 |
| ✅ | **P1-12**: DCF share count — marketCap/price cross-validation heuristic added | Phase 36 |
| ✅ | **P1-13**: Piotroski F-Score — prior-year data via `_prior_val()` with quarterly fallback (AAPL: 8/9, was 4/9) | Phase 36 |
| ✅ | **P1-14**: Beneish M-Score — same fix as P1-13 (AAPL: −2.00, 7/8 components, was null) | Phase 36 |
