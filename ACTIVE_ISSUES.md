# Active Issues — Axiom Finance

> **Generated:** 2026-06-29 · **Test status:** 568+ backend tests passing
> Single source of truth for all known issues, consolidated from QA audits, deferred items, and the issue tracker.

---

## 🔴 P0 — Broken / Critical

| ID | Issue | Source | File(s) | Details |
|----|-------|--------|---------|---------|
| P0-01 | **Scheduler startup failed** | `ISSUES.md` | `database.py`, APScheduler config | `Unrecognized expression "[9" for field "hour"` — nightly cache warming for screener, prices, macro data is broken. No auto-refresh happening. |
| P0-02 | **Backend 502 on restart** | `ISSUES.md` | `nginx/default.conf`, `docker-compose.yml` | Backend takes 30–60s to start (FRED warmup, Damodaran Excel download). Nginx returns 502 until ready. Add health-check `depends_on` or retry logic. |
| P0-03 | **Wiki returns 0 terms** | `ISSUES.md`, CLAUDE.md (Phase 22) | `wiki_service.py`, wiki router | `GET /api/wiki/terms` returns 0 results. The 410-term dictionary loads but isn't served. Known deferred from Phase 22. |
| P0-04 | **Calendar drowned in FRED noise** | `ISSUES.md`, CLAUDE.md (Phase 23) | `calendar_service.py` | FRED release calendar entries ("Coinbase Cryptocurrencies", "Tri-Party GC Rate") aren't actionable macro events. Need impact filter or source weighting. |
| P0-05 | **Econometric Lab frontend broken** | `ISSUES.md`, CLAUDE.md (Phase 24) | `EconLabTab.tsx` | Backend API works (nObs=40, R²=0.078) but frontend component doesn't render results. From Phase 20 — still open. |
| P0-06 | **yfinance missing keys** | `FACT_CHECK.md`, `ACTION_PLAN.md` | `yfinance_service.py`, `valuation.py` | `trailingEps`, `forwardEps`, `freeCashflow`, `sector`, `industry`, `beta` are null in yfinance info dict. Blocks ~40% of features (6 valuation models, DCF, FCF KPIs). Fix: inject from alternative yfinance accessors (earnings_estimate, cashflow statement, fast_info). |

---

## 🟡 P1 — Important / Feature Gaps

| ID | Issue | Source | Details |
|----|-------|--------|---------|
| P1-01 | **Options IV30 = 0.001% (systemic)** | `FACT_CHECK.md`, `ACTION_PLAN.md` | yfinance `impliedVolatility` column returns near-zero values. All IV-derived metrics (IV Rank, IV Percentile, IV Smile, Term Structure, Greeks) are broken. Fix: back-solve IV from option mid-price using existing `_bs_iv` Brent solver, or diagnose yfinance column name changes. |
| P1-02 | **COT/Positioning tab empty** | `ISSUES.md`, CLAUDE.md (Phase 24) | CFTC source format changes frequently. Multiple URL fallbacks added but data often empty. Needs reliable COT pipeline. |
| P1-03 | **Atlas map rendering unreliable** | `ISSUES.md`, CLAUDE.md (Phase 24) | `react-simple-maps` rendering artifacts; world map sometimes blank or misaligned. Consider d3-geo + Canvas or react-leaflet. |
| P1-04 | **Yahoo market cap rate-limits** | `ISSUES.md`, CLAUDE.md (Phase 3) | Large S&P 500 treemap queries hit yfinance rate limits. Needs chunked/batched fetching with backoff. |
| P1-05 | **US-only macro data** | `ISSUES.md`, CLAUDE.md (Phase 24) | Inflation/Rates/Macro Overview country selectors exist but only US data renders. Country parameter wiring incomplete. |
| P1-06 | **ACM term premium / 30Y breakeven N/A** | `ISSUES.md`, CLAUDE.md (Phase 18A) | FRED series (ACM, T30YIE) sometimes lag; graceful fallback works but data occasionally missing. |
| P1-07 | **`/scenario` lab page missing from nav** | `ISSUES.md`, CLAUDE.md (Phase 18A) | Stress scenario designer deferred from Phase 18B. Backend exists, frontend doesn't. |
| P1-08 | **Fama-French parsing truncated** | CLAUDE.md (Phase 24) | Only 12 rows captured; CSV parser truncates historical data (pre-2000 rows not parsed). |
| P1-09 | **BIS Credit-to-GDP gaps not wired** | CLAUDE.md (Phase 24) | CSV format explored but not wired into `refresh_all_bulk_data`. |
| P1-10 | **DCF MSFT share count wrong** | `FACT_CHECK.md`, `ACTION_PLAN.md` | `info.get("sharesOutstanding")` returns 428M (DCF) vs 7.43B (EPV) — ~17× discrepancy. Suspect type coercion or caching issue in `dcf_engine.py`. |
| P1-11 | **Piotroski F-Score maxes at 4/9** | `FACT_CHECK.md`, `ACTION_PLAN.md` | 5 criteria need t−1 financial data. Needs multi-period financial statement fetching. |
| P1-12 | **Beneish M-Score always null** | `FACT_CHECK.md` | All 8 variables need t and t−1 data. Same root cause as P1-11. |
| P1-13 | **Beta null in KPIs (computed beta available in ratios)** | `FACT_CHECK.md`, `ACTION_PLAN.md` | `_kpis()` uses `g("beta")` which reads null from yfinance. `_beta_for()` in same file correctly computes it. Wire computed beta into KPI strip. |

---

## 🟢 P2 — Polish / UX

| ID | Issue | Source | Details |
|----|-------|--------|---------|
| P2-01 | **PageSkeleton not rolled out** | `ISSUES.md`, CLAUDE.md (Phase 22) | `PageSkeleton` component exists but only used in `InflationTab.tsx`. Calendar, Treemap, Risk still use bare `animate-pulse`. |
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
| P2-17 | **Credit Gaps endpoint cold-start timeout** | CLAUDE.md (Phase 25) | BIS ZIP download takes 90-120s; first HTTP call returns 0. Workaround: `docker exec` to warm cache first. |
| P2-18 | **Browser refresh needed after redeploy** | CLAUDE.md (Phase 25) | Stale JS bundles served after `docker compose up -d`. Hard-refresh required. |
| P2-19 | **`@async_cached` persistent cache trap** | CLAUDE.md (Phase 25) | Broken function run caches `{}` permanently in SQLite. Fix: clear both tiers (`_caches.clear()` + delete CacheEntry rows). |
| P2-20 | **Dividend yield display inconsistency** | `FACT_CHECK.md` | `ValuationKpiPanel` uses `fmtPct(v * 100)` for dividend yield — fragile pattern. Standardize percent formatting. |
| P2-21 | **Raw ISO timestamps shown to users** | `UI_report.md` (G-12) | Screener shows `as of 2026-06-25T14:40:30...` instead of readable format. |
| P2-22 | **Admin page no nav link** | CLAUDE.md (Phase 19), `UI_report.md` | `/admin` only accessible via direct URL. |
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
