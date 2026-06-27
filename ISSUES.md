# Axiom Finance — Issue Tracker

**Generated:** 2026-06-27 · **Last phase:** 23 (UI Polish Pass)  
**Test status:** 568 backend tests passing · All pages HTTP 200

---

## 🔴 P0 — Broken / Critical

| ID | Issue | File(s) | Details |
|----|-------|---------|---------|
| **P0-01** | **Scheduler startup failed** | `database.py`, APScheduler config | `Unrecognized expression "[9" for field "hour"` — nightly cache warming for screener, prices, macro data is broken. No auto-refresh happening. |
| **P0-02** | **Backend 502 on restart** | `nginx/default.conf`, `docker-compose.yml` | Backend takes 30–60s to start (FRED warmup, Damodaran Excel download). Nginx returns 502 until it's ready. Add health-check `depends_on` or retry logic. |
| **P0-03** | **Wiki returns 0 terms** | `wiki_service.py`, wiki router | `GET /api/wiki/terms` returns 0 results. The 410-term dictionary loads but isn't served. Known deferred from Phase 22. |
| **P0-04** | **Calendar drowned in FRED noise** | Calendar page, `calendar_service.py` | FRED "release calendar" entries ("Coinbase Cryptocurrencies", "Tri-Party GC Rate") aren't actionable macro events. Need an impact filter or source weighting. |
| **P0-05** | **Econometric Lab frontend broken** | `EconLabTab.tsx` | Backend API works (nObs=40, R²=0.078 via `POST /api/macro/regress`) but frontend component doesn't render results. From Phase 20 — still open. |

---

## 🟡 P1 — Important / Feature Gaps

| ID | Issue | Details |
|----|-------|---------|
| **P1-01** | **COT/Positioning tab empty** | CFTC source format changes frequently — multiple URL fallbacks added but data often shows empty. Needs a reliable COT data pipeline. |
| **P1-02** | **Atlas map rendering unreliable** | `react-simple-maps` has rendering artifacts; world map sometimes blank or misaligned. Consider `d3-geo` + Canvas or switch to `react-leaflet`. |
| **P1-03** | **Yahoo market cap rate-limits** | Large S&P 500 treemap queries hit `yfinance` rate limits. Needs chunked/batched fetching with backoff. |
| **P1-04** | **Inflation/Rates/Macro Overview — US-only** | Country selectors exist but only US data renders. Other country data endpoints return empty. Needs country parameter wiring. |
| **P1-05** | **ACM term premium / 30Y breakeven N/A** | FRED series (ACM, T30YIE) sometimes lag; graceful fallback works but data is occasionally missing. Could fall back to simpler models. |
| **P1-06** | **`/scenario` lab page missing from nav** | Stress scenario designer was deferred from Phase 18B. Backend exists, frontend doesn't. |

---

## 🟢 P2 — Polish / UX

| ID | Issue | Details |
|----|-------|---------|
| **P2-01** | **PageSkeleton not rolled out** | `PageSkeleton` component exists but only used in `InflationTab.tsx`. Calendar, Treemap, Risk rolling metrics, and other heavy pages still use bare `animate-pulse`. |
| **P2-02** | **Sub-tab scroll arrows needed** | Macro (9 tabs) and Markets (7 tabs) sub-tab bars overflow. Sticky positioning was added (Phase 23) but no left/right scroll arrows yet. |
| **P2-03** | **500 errors on Taylor Rule** | Addressed with `/taylor-rule` endpoint (Phase 23) but the Econometric Lab still shows "Failed to load Taylor Rule data" — needs frontend wiring fix. |
| **P2-04** | **Mobile bottom nav cramped** | 5 primary + More + Theme toggle = 7 items. Still tight on small phones. Could collapse to icon-only on <375px. |
| **P2-05** | **Error boundaries** | No React error boundaries — any render error whites out the page. Add `<ErrorBoundary>` with friendly "Something went wrong" + retry button. |
| **P2-06** | **Data freshness badges** | No indication of when data was last updated. Add "Updated X ago" / "Stale — tap to refresh" badges on every data panel. |
| **P2-07** | **Keyboard shortcuts** | No keyboard navigation. `Ctrl+K` global search, number keys for tab switching, arrow keys for period navigation — power-user features financial users expect. |
| **P2-08** | **Export PDF button** | Print styles exist in `globals.css` (`@media print`) but no "Export" button on any page. Add a one-click PDF export. |

---

## 🔵 P3 — New Features (Speculative)

| ID | Feature | Rationale |
|----|---------|-----------|
| **P3-01** | **Price alerts** | Set target prices, RSI thresholds, earnings dates — get in-app notifications. No notification system exists. |
| **P3-02** | **Compare mode on Markets** | Side-by-side metric comparison (PE, EV/EBITDA, Beta, etc.) for selected tickers instead of only overlay charts. |
| **P3-03** | **Mobile PWA** | One `manifest.json` + service worker away from installable mobile app with offline cache. |
| **P3-04** | **Portfolio transaction log** | Add buy/sell dates, cost basis, and realized P&L tracking. Currently portfolio is theoretical allocations only. |
| **P3-05** | **Custom screener formulas** | Let users type `pe < 15 && roe > 0.15 && marketCap > 1e9` instead of only clicking presets. |
| **P3-06** | **Pattern library** | `<KpiGrid>`, `<KpiCard>`, `<TabBar>`, `<ControlBar>` — every page hand-rolls these. Standardizing cuts future dev time. |
| **P3-07** | **`datetime.utcnow()` deprecation** | Multiple files (`policy_service.py`, `admin.py`, tests) use deprecated `datetime.utcnow()`. Switch to `datetime.now(datetime.UTC)`. |
| **P3-08** | **Dark mode chart consistency** | Some Recharts components have hardcoded `stroke="#333"` or `background: "#1f2937"` instead of using `chartPalette()`. Audit and fix. |

---

## ✅ Recently Fixed

| ID | Issue | Phase |
|----|-------|-------|
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

---

## Priority Order for Next Session

1. **P0-01** — Fix Scheduler (restore nightly cache warming)
2. **P0-02** — Fix 502 on restart (add health-check dependency)
3. **P0-03** — Fix Wiki data loading
4. **P0-04** — Filter Calendar FRED noise
5. **P2-01** — Roll out PageSkeleton to remaining heavy pages
6. **P2-02** — Add sub-tab scroll arrows
7. **P2-02** — P2-03 — Wire up Taylor Rule frontend fix
8. Then P1 items, then P3 features
