# FIXES_Phase19.md — Axiom Finance UI & Data Quality Fix Plan

**Date:** 2026-06-26  |  **Branch:** `beta`  |  **Last commit:** `75247f2`
**Based on:** `UI_report.md` (2026-06-25) + `EVALUATION.md` (2026-06-26)

---

## ═══════ PROGRESS LOG (2026-06-26 Session 1) ═══════

### ✅ DEPLOYED & VERIFIED — 11 fixes, 3 commits on `beta`
**P0:** Div Yield 0.39%, Dark chart $166-$330, Calendar clean, Calendar spinner, KPI no truncation
**P1:** Nav overflow scroll, Mobile +Treemap/Calendar/Sectors/Theme, Treemap spinner, Dashboard null-safety, Options IV clamp ≤500%

### 📝 CODED ON DISK — needs `docker compose build && commit`
- `formatAsOf()` in `format.ts` + used in `treemap/page.tsx`
- Portfolio `"AAPL"` → `"Ticker"` in `PortfolioInput.tsx`
- `_retry_yf()` in `yfinance_service.py` (2 retries for 401/crumb)
- DNS `8.8.8.8`/`8.8.4.4` in `docker-compose.yml`

### ❌ NOT STARTED — 11 steps
Steps 9, 12, 13, 15, 16, 17, 19, 21, 22, 23, 27

### 🔧 MANUAL DEPLOY
```
cd C:\Users\danel\Coding\axiomfinance
git add -A && git commit -m "Phase 19C/D" && git push origin beta
docker compose build --no-cache frontend backend && docker compose up -d --force-recreate
```

---

## Phase 19A — P0 Critical Data & Display Fixes

These 5 items affect trust in displayed numbers. Fix first, verify independently.

### Step 1: Fix Dividend Yield Double-Scaling (M-08)

**Root cause:** `ValuationKpiPanel.tsx` line 33-35 calls `fmtPct(v * 100)`. The `fmtPct` helper already multiplies by 100, so `v * 100` pre-scales again. yfinance returns `dividendYield` as a decimal fraction (e.g. 0.0037 for 0.37%), so `0.0037 * 100 = 0.37` → `fmtPct(0.37)` → `"37.00%"`.

**Fix:** In `ValuationKpiPanel.tsx`, use `fmtPctFromFraction(v)` for the dividend yield tile instead of `fmtPct(v * 100)`. Also audit other KPI tiles using the same helper for any similar double-scale risk.

**Files to modify:** `frontend/components/markets/ValuationKpiPanel.tsx` (line ~183)

**Verification:**
- Open `/markets` → Ratios tab, check AAPL dividend yield shows ~0.5% not 37%
- Spot-check MSFT, GOOGL yields
- Run `tsc` for type errors

### Step 2: Fix Dark-Mode Technicals Chart Y-Axis (G-10, M-01)

**Root cause:** `TechnicalsTab.tsx` and `PriceChart.tsx` use `chartPalette(theme)` for tick colors but no `tickFormatter` on YAxis. Dark mode may expose a Recharts rendering issue where the Y-axis domain or tick values are miscalculated. Need to reproduce interactively to diagnose exact cause.

**Fix approach (discovery first, then fix):**
1. Open `/markets` in dark mode, confirm values like "788417899"
2. Inspect Recharts YAxis props — check `domain`, `tickFormatter`, `dataKey`
3. Likely fix: add explicit `tickFormatter` that formats prices as currency (e.g. `$277.50`), or fix `domain` calculation if it's reading wrong data field
4. Test with single ticker (AAPL) and multi-ticker

**Files to modify:** `frontend/components/markets/TechnicalsTab.tsx` (lines ~134-136, ~310-313), possibly `frontend/components/markets/PriceChart.tsx` (lines ~41-42, ~152-154)

**Verification:**
- Toggle dark mode on `/markets` → Technicals tab
- Confirm Y-axis shows realistic prices (~$250-280 for AAPL)
- Verify light mode still works
- Verify multi-ticker chart still works

### Step 3: Filter Calendar Macro Events (C-01)

**Root cause:** `calendar_service.py` `macro_events()` (lines 68-129) appends ALL FRED release calendar entries with no filtering. A single FRED series release (e.g. "Coinbase Cryptocurrencies") becomes a "macro event."

**Fix:** Add a whitelist filter in `macro_events()` for high-impact US releases. Only include FRED events matching known series IDs for CPI, NFP, GDP, FOMC, retail sales, industrial production, housing starts, consumer confidence, etc. Alternatively, prefer Finnhub economic calendar (already in the merge list) and deprioritize/drop raw FRED release calendar entries, keeping only the curated Finnhub feed + CB meetings.

**Files to modify:** `backend/backend/services/calendar_service.py` (lines ~85-110)

**Verification:**
- Curl `GET /api/calendar/macro` — confirm <50 events per month (not hundreds)
- Open `/calendar`, verify macro tab shows recognizable events (CPI, NFP, GDP, FOMC minutes)
- Confirm CB meetings still appear
- Run `pytest tests/test_calendar_service.py`

### Step 4: Add Calendar Loading UX (C-02, G-08)

**Root cause:** Calendar page shows blank skeleton for 15-20s while API fetches. No centered spinner or progress indicator.

**Fix:** In the Calendar page component, add a centered spinner + "Loading calendar…" message during the fetch state. Consider wrapping the calendar endpoint in a backend cache (already `@async_cached`?) or adding a pre-warm on app startup.

**Files to modify:** `frontend/app/calendar/page.tsx` (or the calendar client component), `frontend/components/calendar/` — check current loading state handling

**Verification:**
- Open `/calendar`, confirm spinner appears within 1s
- Confirm spinner is centered (not corner text)
- After data loads, spinner disappears and calendar renders

### Step 5: Fix Valuation KPI Truncation (M-07)

**Root cause:** `ValuationKpiPanel.tsx` uses `lg:grid-cols-9` — 9 columns on desktop squeezes each tile too narrow. Combined with `truncate` class, values like "$277.50" become "$27…"

**Fix:** Change `lg:grid-cols-9` to `lg:grid-cols-5` or `lg:grid-cols-6` (fewer columns, wider tiles), or use `lg:grid-cols-4 xl:grid-cols-6` for better breakpoint distribution. Ensure `min-w-0` allows proper flex shrinking. Alternatively, use a horizontal scrollable strip for the KPIs instead of a 9-column grid.

**Files to modify:** `frontend/components/markets/ValuationKpiPanel.tsx` (line ~209)

**Verification:**
- Open `/markets` → Valuation tab
- Confirm Market Cap, Price, P/E display fully without truncation
- Check at 1440px and 1280px widths

---

## Phase 19B — P1 Major UX/Visual Fixes

Grouped into sub-phases for independent verification.

### Sub-Phase 19B-1: Navigation Overhaul (G-01, G-02, G-03, MOB-01, MOB-02)

### Step 6: Fix Desktop Navbar Overflow (G-01, MOB-02)

**Root cause:** `Navbar.tsx` has 15 items in a single `flex` row with no overflow handling. At 1440px, items clip.

**Fix:** Add `overflow-x-auto` with scrollbar-hide styling, or implement a "More" dropdown for overflow items. Also add responsive breakpoint: on `<lg`, hide desktop nav and show only MobileNav (currently both render together in layout.tsx).

**Files to modify:** `frontend/components/Navbar.tsx` (lines ~7, ~28-34), `frontend/app/layout.tsx` (lines ~22-24)

### Step 7: Fix MobileNav Coverage (G-02, G-03, MOB-01)

**Root cause:** `MobileNav.tsx` lists 10 items but misses Treemap, Calendar, Sectors. Dashboard is duplicated.

**Fix:** Add Treemap, Calendar, Sectors to MobileNav. Remove duplicate Dashboard entry. If >7 items is too cramped, consolidate to a "More" overflow or reduce to essential 7. Add `pb-safe` padding on main content to prevent bottom nav overlap (MOB-03).

**Files to modify:** `frontend/components/MobileNav.tsx` (lines ~6, ~22)

**Verification (Steps 6-7):**
- Open any page at 1440px — all nav items visible or accessible via overflow
- Resize to 390px — desktop nav hides, mobile nav shows all essential pages
- Navigate to Treemap, Calendar, Sectors from mobile nav
- Check no content overlap with bottom nav

### Sub-Phase 19B-2: Treemap Polish (T-01, T-02, T-03)

### Step 8: Add Treemap Loading State & Fix Contrast

**Root cause:** No spinner during ~8s treemap load. White text on light green/red cells is unreadable.

**Fix:** Add centered spinner + "Loading treemap…" in the treemap container while data fetches. For text contrast: use a text color that contrasts against the cell background (dark text on light cells, white on dark cells, or always use a high-contrast stroke). Fix label clipping at container top.

**Files to modify:** `frontend/app/treemap/page.tsx`, `frontend/components/treemap/` (whichever renders the treemap cells)

**Verification:**
- Open `/treemap`, spinner shown during load
- After render, all ticker labels readable (no white-on-light-green)
- Sector/industry labels not clipped at top

### Sub-Phase 19B-3: Dashboard Fixes (D-01, D-03, EVALUATION React errors)

### Step 9: Fix Fear & Greed Gauge (D-01)

**Root cause:** Needle overlaps value text and "Fear" label. Unconventional thick arc design.

**Fix:** Adjust needle z-index or text positioning. Reposition value above/below arc instead of inside it. Consider reducing stroke width of the arc.

**Files to modify:** `frontend/components/dashboard/FearGreedGauge.tsx`

### Step 10: Fix Global Indices Table Clipping (D-03)

**Root cause:** Price/change columns clipped off right edge of card.

**Fix:** Add `overflow-x-auto` to the table container, or make the table responsive with horizontal scroll. Ensure `min-w-0` doesn't clip columns.

**Files to modify:** `frontend/components/dashboard/GlobalIndices.tsx`

### Step 11: Fix Dashboard React Errors (EVALUATION #1)

**Root cause:** Minified React errors #425, #418, #423 in dashboard console. Likely from `BreadthBar`, `FearGreedGauge`, `GlobalIndices`, or `TopMovers` accessing undefined data properties.

**Fix:** Add null-safe access (`data?.total`, `data?.regions?.map`, etc.) in all dashboard child components. Add fallback empty states for missing data. Check API response shape matches component expectations.

**Files to modify:** `frontend/components/dashboard/BreadthBar.tsx`, `FearGreedGauge.tsx`, `GlobalIndices.tsx`, `TopMovers.tsx`

**Verification (Steps 9-11):**
- Open `/dashboard`, check console for React errors
- Fear & Greed gauge needle doesn't overlap text
- Global Indices table shows all columns
- Breadth bar, top movers render without console errors

### Sub-Phase 19B-4: Sectors & Atlas Fixes (SE-01, SE-02, A-01, A-02, A-03)

### Step 12: Fix Sectors Consistency (SE-01, SE-02, SE-03)

**Root cause:** KPI cards show 8 sectors but bar chart has 11. Missing bar labels on top sectors. Low-contrast Y-axis labels.

**Fix:** Ensure KPI cards and bar chart use the same sector universe (all 11 SPDR sectors). Add missing percentage labels to all bars. Darken Y-axis label color.

**Files to modify:** `frontend/app/sectors/page.tsx` or `frontend/components/sectors/`

### Step 13: Add Atlas Color Legend & Fix Truncation (A-01, A-02, A-03)

**Root cause:** `ColorLegend.tsx` component exists but may not be rendered on the page. Country names and indicator pills truncated.

**Fix:** Ensure `ColorLegend` is rendered prominently on the Atlas page (near the map or below the KPI strip). Add `title` tooltips to truncated country names. Allow indicator pills to wrap or use a wider container.

**Files to modify:** `frontend/app/atlas/page.tsx` (ensure ColorLegend imported + rendered), `frontend/components/atlas/ColorLegend.tsx`, indicator pill rendering

**Verification (Steps 12-13):**
- Open `/sectors`, all 11 sectors in both KPI cards and bar chart
- Bar labels present on all bars
- Open `/atlas`, color legend visible with min/mid/max
- Country names have tooltips on hover

### Sub-Phase 19B-5: Options & Risk Fixes (O-01, O-05, RK-01)

### Step 14: Clamp Options Deep ITM IV (O-01, O-05)

**Root cause:** `options_engine.py` passes through yfinance `impliedVolatility` with no upper bound clamp. Deep ITM near-expiry options can have nonsensical IV (771%).

**Fix:** In `_hydrate_chain_rows()` and `get_iv_metrics()`, clamp `iv_pct` to a sensible maximum (e.g. 300% or 500%). For IV Smile chart, cap the Y-axis domain. Add a flag or null-out IV values above threshold instead of displaying misleading numbers.

**Files to modify:** `backend/backend/services/options_engine.py` (lines ~284-307, ~363-424, ~619), frontend options chain/smile chart components

### Step 15: Fix Risk Max Drawdown Display (RK-01)

**Root cause:** 3Y max drawdown shows em dash (—) while other metrics populate. Possibly the API returns null for that field or the frontend binding is wrong.

**Fix:** Trace the data flow: API response → component prop → render. Check `rolling_max_drawdown()` for edge cases (e.g. insufficient data for 3Y window). If the value exists in the API response, fix the frontend binding.

**Files to modify:** `backend/backend/services/advanced_risk.py` (line ~93), `frontend/components/risk/RiskKPIRow.tsx` (line ~32)

**Verification (Steps 14-15):**
- Open `/options`, check deep ITM call IVs are ≤300%
- IV Smile chart Y-axis doesn't go to 360% for nonsensical wings
- Open `/risk`, Max Drawdown (3Y) shows a real percentage

### Sub-Phase 19B-6: Macro & Research Fixes (MC-01, MC-02, R-01, R-06)

### Step 16: Fix Macro Tab Overflow & Start Year Input (MC-01, MC-02)

**Root cause:** 10+ macro tabs overflow with redundant scrollbar. Start Year input truncates "2000" to "200".

**Fix:** Make tab row horizontally scrollable without page-level scrollbar. Widen Start Year input field to at least 70px.

**Files to modify:** `frontend/app/macro/page.tsx` (tab bar, year input)

### Step 17: Fix Research Chart Layouts (R-01, R-06)

**Root cause:** ERC weights chart Y-axis misaligned. Momentum decile chart missing D1-D10 x-axis labels.

**Fix:** Adjust Recharts margin/padding on ERC weights bar chart. Add explicit x-axis tick labels (D1 through D10) on momentum decile chart.

**Files to modify:** `frontend/components/research/` — RiskParityTab, MomentumTab

**Verification (Steps 16-17):**
- Open `/macro`, tabs scroll horizontally without page scrollbar
- Start Year shows full "2000"
- Open `/research` → Risk Parity, ERC bars align with Y-axis ticks
- Momentum tab shows D1-D10 labels on decile chart

---

## Phase 19C — P2 Polish & Consistency

### Step 18: Format Timestamps (G-12, S-01)

**Fix:** Create a shared `formatAsOf()` in `frontend/lib/format.ts` that converts ISO timestamps to readable format ("Jun 25, 2026 2:40 PM UTC"). Use in Screener "as of" line and anywhere else raw ISO is shown.

**Files to modify:** `frontend/lib/format.ts`, `frontend/components/screener/`

### Step 19: Screener Preset Overflow (S-02)

**Fix:** Wrap preset chips container with `flex-wrap` or horizontal scroll.

**Files to modify:** `frontend/components/screener/` preset row

### Step 20: Portfolio Placeholders (P-01)

**Fix:** Change hardcoded "AAPL" placeholder to generic "Ticker" in holdings input rows.

**Files to modify:** `frontend/components/portfolio/` holdings input

### Step 21: Calendar UI Polish (C-05, C-06, C-09)

**Fix:** Use category-colored filter chips (blue=earnings, yellow=dividend, green=macro, purple=IPO). Fix "This Week" disabled state (use gray, not opacity-only). Replace text stars with star icons for impact.

**Files to modify:** `frontend/components/calendar/`

### Step 22: Chart Legends & Copy Fixes (M-03, R-04)

**Fix:** Add line legend to normalized price chart (ticker names + benchmark). Update FX Carry footer copy to match actual sort order.

**Files to modify:** `frontend/components/markets/PriceChart.tsx`, `frontend/components/research/CarryTab`

### Step 23: Snowflake Score Layout (M-02)

**Fix:** Use CSS grid with aligned columns so Strength scores and Risk scores don't visually misalign.

**Files to modify:** `frontend/components/markets/SnowflakePanel.tsx` or the Snowflake score component

### Step 24: Theme Toggle in Mobile Nav (G-04)

**Fix:** Add theme toggle button to MobileNav component.

**Files to modify:** `frontend/components/MobileNav.tsx`

**Verification (Steps 18-24):**
- Screener shows "Jun 25, 2026 2:40 PM UTC" not raw ISO
- Preset chips wrap, not truncated
- Portfolio shows "Ticker" placeholder
- Calendar filters use category colors
- Normalized price chart has legend
- Mobile nav has theme toggle

---

## Phase 19D — Backend Stability (from EVALUATION.md)

### Step 25: Investigate & Mitigate yfinance 401 Errors

**Root cause:** yfinance occasionally returns 401 "Invalid Crumb" — likely rate limiting or cookie expiry.

**Fix:** Add retry logic (2 retries with exponential backoff) in `yfinance_service.py` quote/download calls. Ensure cache fallback serves stale data when yfinance fails.

**Files to modify:** `backend/backend/services/yfinance_service.py`

### Step 26: Fix IMF/WB DNS Resolution

**Root cause:** `dataservices.imf.org` DNS fails in Docker container.

**Fix:** Check Docker DNS config. Add `--dns 8.8.8.8` to the backend service in `docker-compose.yml`, or add fallback data sources when IMF/WB is unreachable.

**Files to modify:** `docker-compose.yml`, possibly `backend/backend/services/atlas_service.py`

### Step 27: Composite Endpoint Performance (<500ms target)

**Root cause:** Batch OHLCV download + per-symbol quote fetches via `asyncio.gather` exceed 500ms.

**Fix:** Profile the endpoint. Consider parallel `asyncio.to_thread` for the OHLCV frame + all quotes simultaneously. Ensure quote fetches use cached data when available. Accept slight target relaxation if yfinance latency is the bottleneck (document if so).

**Files to modify:** `backend/backend/routers/market_data.py`

**Verification (Steps 25-27):**
- Check Docker logs for yfinance 401 count reduction
- Atlas/Macro data fetches succeed (no DNS errors in logs)
- Composite endpoint returns <600ms (or documented reason if not)

---

## Verification Gates (per CLAUDE.md working agreements)

After each Phase, run:
1. `docker compose ps` — all 3 containers up
2. `docker compose logs --tail=50 backend` — no new errors
3. `docker compose logs --tail=50 frontend` — no new errors
4. `pytest` — all tests passing (target: ≥558, current baseline from Phase 18A)
5. `tsc` — no TypeScript errors
6. Live browser checks for each fixed page

After Phase 19D (final):
7. `docker compose build backend frontend && docker compose up -d --force-recreate`
8. Curl all modified endpoints → HTTP 200
9. Navigate all fixed pages in browser
10. Commit + push with message: "Phase 19: UI & data quality fixes — criticals + majors + polish"

---

## Decisions & Assumptions

- **Ordering:** Critical data bugs (P0) first because they affect trust. Navigation (P1) second because it blocks access. Visual polish (P2) last.
- **Backend vs Frontend separation:** Steps 14, 15, 25-27 touch backend; all others are frontend-only. Frontend steps can largely be verified without full Docker rebuilds — use `tsc` for type safety.
- **No new dependencies:** All fixes use existing libraries (Recharts, Tailwind, d3-scale).
- **Calendar approach:** Prefer Finnhub economic calendar + CB meetings; drop raw FRED release calendar entries entirely (they're the wrong data source for a macro events calendar).
- **Dark mode chart:** Requires interactive debugging — Step 2 is "discovery first" rather than a predetermined fix.

---

## Explicitly Excluded from This Phase

- New features or pages (this is a fix/polish phase only)
- Admin page navigation link (minor, can be P2 follow-up)
- Markets sub-tab redundancy with main nav (minor, cosmetic)
- Fear & Greed per-signal explanation copy (D-05 — minor, documentation issue)
- Atlas map rendering artifacts (A-04 — likely a library limitation)
- Mobile bottom nav 9-item cramped layout (mitigated by adding correct pages; full redesign deferred)
- Dashboard McClellan signal explanation (D-05 — minor documentation)
- Options ~15min delay badge restyle (O-04 — minor)
- Compute-tier indicator consistency (G-13 — minor)
- Active tab styling inconsistency (G-15 — minor)

## Further Considerations

1. **Docker rebuild timing:** Frontend-only fixes (Steps 1-2, 4-13, 16-24) can use `docker compose build frontend && docker compose up -d --force-recreate frontend` without rebuilding backend, saving time.
2. **yfinance 401 root cause:** If retries don't help, we may need to update the yfinance package version or add cookie refresh logic — this could expand scope.
3. **Atlas legend already exists:** `ColorLegend.tsx` is implemented but may not be rendered. The fix might be as simple as adding the component to the page layout.
