# Axiom Finance — Feature Idea List

> Last cleaned: 2026-06-30 — Phase 40 shipped (Navigation Reshuffle). All P3 items + nav reshuffle complete.
> Remaining: 0 ideas. IDEA_LIST is fully delivered.

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

## 3. 🧠 Remaining Ideas

### P3 — Portfolio Transaction Log ✅ DONE (Phase 37)
Add buy/sell dates, cost basis, and realized P&L tracking (currently theoretical allocations only).
- **Data:** User input only — no external data needed.

### P3 — Cross-Asset & Factor Analytics (Research-Grade) ✅ DONE (Phase 39)
Multi-country portfolio builder, factor attribution, FX/commodity macro-link panels, cross-asset correlation heatmaps.
- **Data:** All existing data — pure calculation + visualization. Significant effort.

### P3 — Learning Layers ✅ DONE (Phase 38)
Beginner-friendly toggles, narrative walkthroughs explaining metrics, academic-style embedded notebooks.
- **Data:** No new data — educational UX layer.

---

## 4. 🧭 Navigation Reshuffle Plan ✅ DONE (Phase 40)

**Updated:** 2026-06-30 — Revised after Phase 37–39 delivery. Primary bar unchanged per user direction.

### Problem

The current top-level navigation has a **flat 14-item "More" dropdown** with no grouping, mixing micro tools with macro tools and reference pages. The primary bar (7 items) works well and stays unchanged.

### Decision: Primary Bar Unchanged

`Dashboard` · `Markets` · `Screener` · `Portfolio` · `Research` · `Macro` · `Atlas`

Treemap and Sectors stay as Markets sub-tabs (innate to stock analysis). Atlas stays primary.

### Proposed: Grouped "More" Dropdown

Restructure the 14-item flat dropdown into 5 groups with section headers:

```
── Discover ──
  Calendar
── Analyze ──
  Risk · Options
── Markets & Data ──
  Corporate Health · Dividends · Insider Trading · M&A
── Global ──
  Trade · Cross-Border · Stability · Countries · Yield · Policy & Sovereign
── Reference ──
  Wiki · Admin
```

### Changes from Current

| Change | Detail |
|--------|--------|
| Add section headers | 5 visual group labels in the More dropdown |
| Reorder items | Grouped logically instead of alphabetical |
| Rename "Rates & Policy" → "Yield" | More accurate label |
| Rename "M&A" → "Mergers & Acquisitions" | Clearer |
| No URL changes | All existing routes preserved |
| No tab removals | Markets/Macro tabs unchanged |
| No redirects needed | Zero breakage |

### Implementation Order
1. Update `Navbar.tsx` — restructure `moreTabs` array into groups with section headers
2. Update `MobileNav.tsx` — restructure `drawerTabs` with same grouping
3. Test: `tsc --noEmit` + Docker rebuild + click through each link
4. Verify: no 404s, all existing pages still accessible
