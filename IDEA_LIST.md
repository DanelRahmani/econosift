# Axiom Finance — Feature Idea List

> Generated 2026-06-28 from a full audit of all 12 data sources, 22 pages/tabs, 55+ services, and 24 routers.
> Every idea is verified implementable with data already in the pipeline or requiring only new indicator mappings (no new source infrastructure).

---

## How to Read This List

- **P0** — Data already in the pipeline; needs only calculation logic + router + frontend.
- **P1** — Needs new World Bank indicator codes or FRED series IDs added; no new source packages.
- **P2** — May need new static data, new source parsing, or upstream data exploration; still feasible without paid APIs.

Each entry includes: **what it does**, **what data it uses**, and **why it's implementable today**.

---

## 1. 🆕 New Pages (Standalone Routes)

> ✅ All 5 ideas in this section have been implemented (Phases 26–31): `/trade`, `/corporate`, `/dividends`, `/stability`, `/crossborder`.

---

## 2. 📊 New Macro Tabs (Expand `/macro`)

### ✅ P1 — Labor Market Deep Dive Tab — **DONE (Phase 32)**

Expand beyond headline unemployment to include labor force participation rate, youth unemployment
(ages 15-24), employment-to-population ratio, vulnerable employment share, and informal employment
estimates. US wage growth via FRED average hourly earnings. Cross-country productivity comparison
(GDP per employed person).

- **Data:** World Bank `SL.TLF.CACT.ZS` (LFPR), `SL.UEM.1524.ZS` (youth unemployment), `SL.EMP.TOTL.SP.ZS` (employment/population), `SL.EMP.VULN.ZS` (vulnerable employment), `SL.GDP.PCAP.EM.KD` (GDP per employed person). FRED `AHETPI` (average hourly earnings) and `OPHNFB` (nonfarm productivity).
- **Why implementable:** 5 new WB codes + 2 FRED series IDs. Can be built as a new tab in the existing `/macro` page using the same `MacroTabShell` pattern (add entry to `TABS` array, lazy-load new component).

<details>
<summary>📋 Implementation Plan</summary>

**What already exists:**
- ✅ Backend service `labor_service.py` — full implementation with WB data (LFPR, youth unemp, emp/pop ratio, vulnerable emp, GDP per worker)
- ✅ Frontend component `labor/LaborTab.tsx` — full UI with KPIs, bar charts, timeseries
- ✅ Registered in `MacroTabShell.tsx` TABS array as `"labor"`
- ✅ All 5 WB indicator codes mapped in `atlas_service.py` INDICATOR_MAP

**What's missing:**
- ❌ **No router endpoint** — `/macro/labor` does not exist in `macro.py`. The service exists but is not callable from the frontend
- ⚠️ **FRED wage/productivity data** — `labor_service.py` only uses WB data; it does NOT fetch FRED `AHETPI` or `OPHNFB`. These would add US-only wage growth and productivity charts
- ❌ **Types** — `LaborData` type likely missing or needs verification in `frontend/lib/types.ts`

**Changes needed:**
1. Add `@router.get("/labor")` to `macro.py` — wire to `labor_service.get_labor_data()`
2. Add FRED `AHETPI` and `OPHNFB` series to `labor_service.py` using the existing `macro_expansion_service.fetch_fred_series()` pattern
3. Verify/update `LaborData` type in `frontend/lib/types.ts`
4. Verify `api.macroLabor()` call in `frontend/lib/api.ts` (confirmed already mapped)

**Data sources:** All WB codes already mapped. FRED series are free, no API key needed beyond existing FRED_API_KEY.

**Conflicts:** None — the MacroTabShell already has the tab registered, so once the router endpoint is added, the tab will start working immediately.

**Testing:** `pytest` (new smoke test for `/macro/labor` endpoint) + manual browser check on `/macro?tab=labor`.
</details>

### ✅ P1 — Energy Transition & Climate Economics Tab — **DONE (Phase 32)**

CO2 emissions per capita, renewable energy share of consumption, fossil fuel dependency, energy
imports as % of energy use, and oil/gas/coal rents as % of GDP. Compare climate vulnerability vs
fiscal capacity to respond. Track progress toward Paris Agreement implied targets.

- **Data:** World Bank `EN.ATM.CO2E.PC` (CO2 per capita), `EG.FEC.RNEW.ZS` (renewable share), `EG.IMP.CONS.ZS` (energy imports), `NY.GDP.PETR.RT.ZS` (oil rents), `NY.GDP.NGAS.RT.ZS` (gas rents), `NY.GDP.COAL.RT.ZS` (coal rents).
- **Why implementable:** 6 new WB codes. All are annual country-level data. Same pattern as existing macro tabs. Energy transition is a high-demand topic with no current coverage in the app.

<details>
<summary>📋 Implementation Plan</summary>

**What already exists:**
- ✅ Backend service `energy_service.py` — full implementation with WB data (CO₂/capita, renewable share, energy imports, oil/gas/coal rents)
- ✅ Frontend component `macro/EnergyTab.tsx` — full UI with KPIs, bar charts, signal coloring
- ✅ Registered in `MacroTabShell.tsx` TABS array as `"energy"`
- ✅ All 6 WB indicator codes mapped in `atlas_service.py` INDICATOR_MAP

**What's missing:**
- ❌ **No router endpoint** — `/macro/energy` does not exist in `macro.py`. The service exists but can't be called from the frontend
- ❌ **Types** — `EnergyData` type likely missing or needs verification

**Changes needed:**
1. Add `@router.get("/energy")` to `macro.py` — wire to `energy_service.get_energy_data()`
2. Verify/update `EnergyData` type in `frontend/lib/types.ts`
3. Verify `api.macroEnergy()` call in `frontend/lib/api.ts` (confirmed already mapped)

**Data sources:** All 6 WB codes already mapped. No new data sources needed.

**Conflicts:** None — the tab is already registered in the shell. Adding the router is a ~5-line change.

**Testing:** `pytest` (new smoke test) + manual check on `/macro?tab=energy`.
</details>

### ✅ P1 — Inequality & Development Tab — **DONE (Phase 32)**

Gini coefficient, income share held by top 10% / bottom 40%, poverty headcount ratios at $2.15,
$3.65, and $6.85/day (World Bank international poverty lines), and GDP per capita (already mapped).
Lorenz curve visualization per country with decade-over-decade comparison.

- **Data:** World Bank `SI.POV.GINI` (Gini), `SI.DST.10TH.10` / `SI.DST.FRST.10` (income decile shares), `SI.POV.DDAY` ($2.15 poverty), `SI.POV.LMIC` ($3.65), `SI.POV.UMIC` ($6.85). GDP per capita already mapped via `NY.GDP.PCAP.KD`.
- **Why implementable:** 5 new WB codes. Coverage is spottier than macro indicators (Gini may have gaps for some developing countries) but sufficient for major economies and aggregate trends. Lorenz curve is a straightforward cumulative distribution chart.

<details>
<summary>📋 Implementation Plan</summary>

**What already exists:**
- ✅ Backend service `inequality_service.py` — full implementation: Gini, income top 10%, poverty $2.15/$3.65
- ✅ Frontend component `macro/InequalityTab.tsx` — full UI with KPIs, bar charts, signal coloring
- ✅ Registered in `MacroTabShell.tsx` TABS array as `"inequality"`
- ✅ WB indicator codes mapped in `atlas_service.py` INDICATOR_MAP (gini, income_top10, income_bottom40, poverty_215, poverty_365, poverty_685)

**What's missing:**
- ❌ **No router endpoint** — `/macro/inequality` does not exist in `macro.py`
- ❌ **Poverty $6.85** — `inequality_service.py` only fetches `poverty_215` and `poverty_365`; `poverty_685` is mapped in atlas_service but not used by the service
- ❌ **Lorenz curve** — Not implemented anywhere. Requires cumulative income share data per country (not just top 10%)
- ❌ **Types** — `InequalityData` type needs verification

**Changes needed:**
1. Add `@router.get("/inequality")` to `macro.py` — wire to `inequality_service.get_inequality_data()`
2. Optionally add `poverty_685` fetch to `inequality_service.py` (low effort, nice to have)
3. Lorenz curve is a pure frontend visualization — needs a `LorenzCurve.tsx` Recharts component using income decile data (requires `income_bottom40` or full decile series from WB)
4. Verify/update `InequalityData` type in `frontend/lib/types.ts`
5. Verify `api.macroInequality()` call in `frontend/lib/api.ts` (confirmed already mapped)

**Data sources:** All WB codes already mapped. Lorenz curve may need additional WB indicator `SI.DST.02ND.20` through `SI.DST.10TH.10` (income shares by decile).

**Conflicts:** None — same pattern as labor and energy.

**Testing:** `pytest` (new smoke test) + manual check on `/macro?tab=inequality`.
</details>

---

## 3. 🛠️ New Tools & Analytical Models

### P1 — Currency Crisis Early Warning System

Composite early warning model using: foreign reserves decline rate (already in country risk),
current account deficit (already mapped), real exchange rate overvaluation (BIS effective FX +
Frankfurter spot), inflation (already mapped), and short-term external debt. Output: traffic-light
warning (green/yellow/red) per country with contributing factor breakdown.

- **Data:** All inputs already in the pipeline — reserves via `FI.RES.TOTL.CD` (country risk), current account via `BN.CAB.XOKA.GD.ZS` (atlas/macro), effective FX via BIS (source_bis.py), inflation via `FP.CPI.TOTL.ZG` (atlas/macro). Short-term debt as % of total external debt via WB `DT.DOD.DSTC.ZS`.
- **Why implementable:** Pure model logic. Only one new WB code needed (short-term debt share). The methodology follows well-known academic early warning literature (Kaminsky, Lizondo & Reinhart 1998; IMF Vulnerability Exercises).

<details>
<summary>📋 Implementation Plan</summary>

**What already exists:**
- ✅ Backend service `currency_crisis_service.py` — 4-signal composite model: CA deficit, inflation >10%, short-term debt >15%, debt/GDP >90%, twin deficits signal
- ✅ Frontend component `stability/CurrencyCrisisPanel.tsx` — traffic-light UI with KPI row and per-country breakdown
- ✅ Router endpoint — wired via `stability.py` at `/api/stability/currency-crisis`
- ✅ Stability page — `/stability` has a "Currency Crisis" tab that renders `CurrencyCrisisPanel`
- ✅ All WB indicator codes mapped in `atlas_service.py` INDICATOR_MAP

**What's missing/needs improvement:**
- ❌ **Reserves decline rate** — Not in the model. WB `FI.RES.TOTL.CD` is mapped in `country_risk_service.py` but not in `atlas_service.py`. Would need to either add to atlas_service or wire from country_risk_service
- ❌ **Real FX overvaluation** — Not in the model. Requires BIS effective FX data from `source_bis.py` (already downloaded) compared against long-term average, plus Frankfurter spot rate
- ❌ **Current approach is simplified** — Uses CA deficit as proxy for reserves decline, and inflation differential as proxy for FX overvaluation. Adding actual reserves data and BIS effective FX would make the model more rigorous

**Changes needed (enhancement):**
1. Add `FI.RES.TOTL.CD` (reserves) to `atlas_service.py` INDICATOR_MAP
2. Update `currency_crisis_service.py` to fetch reserves and compute decline rate (% YoY change)
3. Add BIS effective FX data to the model via `source_bis.get_effective_fx_bulk()` or compute overvaluation vs 5-year average
4. Add Frankfurter spot rate deviation from PPP as additional signal
5. The existing 4-signal model already works and is shippable — reserves + FX overvaluation are enhancements

**Data sources:** `FI.RES.TOTL.CD` needs new WB mapping. BIS effective FX and Frankfurter are already in the pipeline.

**Conflicts:** None — adding signals only strengthens the existing model.

**Testing:** `pytest` (update stability test) + manual check on `/stability`.
</details>

---

## 4. 🔧 Enhancements (Expand Existing Pages)

### ✅ P1 — Government Bond Global Comparison → `/yield` — **DONE (Phase 18A)**

Already implemented in Phase 18A. The `/yield` page includes a full "Global Yields" tab with:
- 23 foreign 10Y government bond yields via FRED `IRLTLT01` series
- Spread matrix (vs US, Germany, Japan) with color-coded table
- Real yields (nominal yield − WB CPI inflation)
- Bar chart ranking and historical line chart
- KPI strip showing highest/lowest/average/widest spread

**Files:** `yield_curve_service.py` (23-country foreign yield data + spread matrix), `yield/page.tsx` (GlobalYieldsTab component), `MultiCountryYieldChart.tsx`, types in `frontend/lib/types.ts`.

### P1 — Supply Chain Vulnerability → Atlas Overlay

Compute import concentration (Herfindahl index of import partners), food import dependency, and
energy import dependency per country. Add as a new Atlas map layer. Identify countries vulnerable
to trade disruptions based on concentrated import sources and essential goods dependency.

- **Data:** World Bank trade indicators (already partially mapped). Bilateral trade data from IMF Direction of Trade Statistics (DOTS) if available via imfp, or computed from WB merchandise trade data. Food import share via `TM.VAL.FOOD.ZS.UN` and fuel import share via `TM.VAL.FUEL.ZS.UN`.
- **Why implementable:** The Atlas already has 6 map layers with the year slider — adding a 7th is a straightforward extension. Trade concentration needs bilateral data which may require IMF DOTS exploration (the main P1 uncertainty), but the food/fuel import shares are direct WB indicators.

<details>
<summary>📋 Implementation Plan</summary>

**What already exists:**
- ✅ `food_imports` (TM.VAL.FOOD.ZS.UN) mapped in `atlas_service.py` and registered in INDICATORS list
- ✅ `fuel_imports` (TM.VAL.FUEL.ZS.UN) mapped in `atlas_service.py` and registered in INDICATORS list
- ✅ Both are served through the generic `/api/atlas/timeline?indicator=food_imports` endpoint
- ✅ These two indicators are already live in the Atlas UI as selectable map layers

**What's missing:**
- ❌ **Import concentration (Herfindahl index)** — Requires bilateral trade partner data (what % of imports come from each partner country). This data comes from IMF Direction of Trade Statistics (DOTS), which `imfp` package may support
- ❌ **Composite supply chain vulnerability score** — No service combines food_imports, fuel_imports, and Herfindahl into a single overlay
- ❌ **Duplicate in Section 6** — This same idea ("Supply Chain Vulnerability → Atlas Overlay") also appears in Section 6 (Additional Ideas) as a P2 item. Decision needed: keep one, remove the other

**Changes needed:**
1. **Short-term (easy):** The food_imports and fuel_imports layers are already live in Atlas. No additional work needed for these.
2. **Medium-term:** Create a new `supply_chain_service.py` that computes:
   - Import Herfindahl score (if IMF DOTS data is available via `imfp`)
   - Composite vulnerability score = weighted combination of Herfindahl + food_imports + fuel_imports
3. **Atlas layer:** Add new indicator `supply_chain_vulnerability` to INDICATORS list with the composite score
4. **Resolve duplicate:** Remove the P2 entry from Section 6 since it's redundant with this P1 entry

**Data sources:** IMF DOTS via `imfp` (needs investigation — may need new package or direct API). Food/fuel import shares already mapped.

**Conflicts:**
- ⚠️ Section 6 has a P2 duplicate of this same idea. One must be removed.
- ⚠️ IMF DOTS data quality/availability via `imfp` is uncertain — if unavailable, can approximate Herfindahl using WB "Import partner shares" data

**Testing:** Manual Atlas UI check — food_imports and fuel_imports should already render as map layers.
</details>

---

## 5. Data Source Quick Reference

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

## 6. 🧠 Additional Ideas (from `project_ideas.md`)

Older brainstorming ideas that don't overlap with the main list. Included for reference.

### P1 — AI-Powered Company Summary
Add a "Summarize" button on Markets that calls Claude API with financial ratios, valuation signals, risk metrics → returns a plain-English analyst-style paragraph.
- **Data:** Existing valuation/ratios/risk endpoints. Needs API key integration.

### P1 — Country Comparison Cards
Side-by-side snapshot card view for any two selected countries showing all macro indicators with traffic-light coloring.
- **Data:** All macro indicators already mapped. Pure frontend component work.

### P1 — Macro Indicator Forecasts
Pull IMF WEO projections and overlay forecast lines on existing historical charts with dashed style.
- **Data:** IMF WEO already downloaded via `bulk_data_service.py`. Needs frontend chart overlay.

### P1 — Global Inflation Comparison Heatmap
Year-by-year heatmap grid (countries × years) for CPI inflation, color-coded from low (blue) to high (red).
- **Data:** CPI inflation already mapped in Atlas/macro. Pure frontend visualization.

### P2 — Shareable URLs / Deep Linking
Encode dashboard state (selected tickers, period, active tab) in URL query string for bookmarking/sharing.
- **Data:** URL state only. Pure frontend.

### P2 — Configurable Benchmark Override
Let users manually override auto-detected benchmark (e.g., AAPL vs ^NDX instead of ^GSPC) via UI dropdown.
- **Data:** No new data needed. Backend already supports arbitrary benchmark tickers.

### P2 — Watchlist with Price Alerts
Persistent watchlist panel where users pin tickers and set price-level/percentage-change alerts via browser Notifications API.
- **Data:** No new data — uses existing quote endpoint + localStorage.

### P3 — Portfolio Transaction Log
Add buy/sell dates, cost basis, and realized P&L tracking (currently theoretical allocations only).
- **Data:** User input only — no external data needed.

### P3 — AI Macro Summary
Generate automated briefing paragraphs for the Macro page using macro data + LLM API.
- **Data:** All macro data already in pipeline.

### P3 — Cross-Asset & Factor Analytics (Research-Grade)
Multi-country portfolio builder, factor attribution, FX/commodity macro-link panels, cross-asset correlation heatmaps.
- **Data:** All existing data — pure calculation + visualization. Significant effort.

### P3 — Learning Layers
Beginner-friendly toggles, narrative walkthroughs explaining metrics, academic-style embedded notebooks.
- **Data:** No new data — educational UX layer.

---

## 7. 🧭 Navigation Reshuffle Plan

**Status:** Not started — detailed audit in [`UX_Reshuffle.md`](./UX_Reshuffle.md) (will be deleted after this is done).

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
| 4 | Currency Crisis Early Warning | Tool | P1 | 1 new WB code | Medium | 🟡 Needs reserves + FX overvaluation signals |
| 5 | Supply Chain → Atlas Overlay | Enhance | P1 | 2 WB codes + bilateral data | Medium | 🟢 Food/fuel import layers live; Herfindahl TBD |

**Completed:** 20/22 · **Remaining:** 2 (0 P0 · 2 P1 · 0 P2)
