# UX Restructuring & Navigation Reshuffle Plan

## 1. Current Information Architecture Audit

The current top-level navigation is a **flat 16-item bar** with no grouping, mixing micro (per-ticker) tools with macro (global) tools and reference pages. This creates severe cognitive load.

### Top‑Level Nav (Desktop, left‑to‑right order)

| # | Nav Label | Route | Type | Sub‑Tabs (internal) |
|---|-----------|-------|------|---------------------|
| 1 | Dashboard | `/dashboard` | Overview page | — (breadth, indices, Fear & Greed, movers, regime clock, yield curve, sector perf) |
| 2 | Treemap | `/treemap` | Visualisation | Index/Period/Group‑by/Colour‑by selectors |
| 3 | Calendar | `/calendar` | Reference | Type (Macro/Earnings/Dividend/IPO), Impact, Time zone |
| 4 | Screener | `/screener` | Screening | Universe selector (Dow/Nasdaq/S&P), signal presets, Table/Charts view |
| 5 | Sectors | `/sectors` | Sector analysis | Return periods, ETF fundamentals, rotation clock, industry drill‑down |
| 6 | Portfolio | `/portfolio` | Portfolio tools | Overview / Risk / Attribution / Optimize |
| 7 | Research | `/research` | Quant strategies | Risk Parity / FX Carry / Momentum / Realized Moments |
| 8 | Markets | `/markets` | Per‑ticker hub | Overview / Risk / Technicals / Valuation / Ratios / Portfolio / Rankings / Sectors / Screener / FX |
| 9 | Risk | `/risk` | Per‑ticker risk | Rolling Metrics / Extended / Correlation / On‑Demand (GARCH/Hurst/OU/Cointegration) / Stress & Monte Carlo |
| 10 | Options | `/options` | Options analytics | Chain / Volatility / OI Profile / Monte Carlo 🔴 |
| 11 | Macro | `/macro` | Macro hub | Overview / Rates & Yields / Inflation / Growth & Employment / Housing / Commodities / FX / Leading Indicators / Financial Conditions / Positioning / Econometric Lab / Country Risk / Central Banks / Funding & Liquidity / Sentiment Signals |
| 12 | Yield | `/yield` | Yield curves | US Curve / Foreign Spreads / Real & Breakeven |
| 13 | Policy | `/policy` | Policy tracker | — (CB divergence table, G10 carry differentials) |
| 14 | Sovereign | `/sovereign` | Sovereign risk | — (WB 6‑KPI traffic‑light) |
| 15 | Atlas | `/atlas` | World map | Indicator / Year slider / Regional blocs |
| 16 | Wiki | `/wiki` | Dictionary | Search / Category sidebar / Term cards |

### Orphaned Pages (not in navbar)

| Route | Purpose | Sub‑Tabs |
|-------|---------|----------|
| `/scenario` | Scenario stress tester | Historical / Custom |
| `/admin` | Backend admin | Cache stats, job history |

### Markets Page (Micro Hub) — 10 Sub‑Tabs

Each tab renders below a common search bar / ticker chips / period selector / benchmark selector.

1. **Overview** — Price chart (normalised), Snowflake radar + strengths/risks, News feed
2. **Risk** — Risk‑metrics table (VaR, Sharpe, Beta, etc.), correlation matrix
3. **Technicals** — MACD, BB, Ichimoku, RSI, StochRSI, Williams %R, OBV, CMF, ATR, Fibonacci, Pivots
4. **Valuation** — 8‑model engine, DCF (sensitivity heatmap), analyst data, composite score
5. **Ratios** — Financial & risk ratios (beta, Sharpe, Sortino, Z‑score, liquidity, leverage, etc.)
6. **Portfolio** — Mini portfolio builder with equal‑weight / analyze
7. **Rankings** — Relative strength ranking across tickers
8. **Sectors** — Sector heatmap
9. **Screener** — Inline screener
10. **FX** — FX rates panel (16 pairs)

### Macro Page (Macro Hub) — 15 Sub‑Tabs

1. **Overview** — Yield curve, sector performance, regime clock, country selector, KPI strip
2. **Rates & Yields** — Full yield curve, Taylor Rule, ACM decomposition, credit spreads
3. **Inflation** — CPI, Core CPI, PCE, Core PCE, PPI, breakevens, M2, Quantity Theory
4. **Growth & Employment** — GDP, unemployment, NFP, claims, JOLTS, Sahm Rule, IP
5. **Housing** — Case‑Shiller, housing starts, mortgage rate, existing home sales
6. **Commodities** — WTI, Brent, NG, gold, silver, copper, wheat, corn, soybeans, Gold/Oil ratio, Axiom Index
7. **FX** — FX heatmap (12 crosses), PPP table (8 pairs)
8. **Leading Indicators** — LEI, CFNAI, ISM PMI, GSCPI, IS‑LM‑PC framework
9. **Financial Conditions** — NFCI, STLFSI, Fed balance sheet, C&I loans, delinquency, EPU
10. **Positioning** — CFTC COT net speculator positioning (6 futures)
11. **Econometric Lab** — Pooled OLS regression of WB panel data
12. **Country Risk** — 6‑KPI traffic‑light (200 countries)
13. **Central Banks** — Policy rate history (7 CBs) + Fed balance sheet
14. **Funding & Liquidity** — M2, SOFR, CP spread
15. **Sentiment Signals** — Finnhub news sentiment

---

## 2. Redundancy & Deletion Audit

### A. Markets Sub‑Tabs That Duplicate Full Pages

| Redundant Tab | Duplicates | Rationale |
|---------------|------------|-----------|
| **Markets > Sectors** | `/sectors` | Identical sector heatmap. The full Sectors page adds ETF fundamentals, rotation clock, and industry drill‑down — the Markets tab shows only the heatmap. **Merge:** remove tab; route Markets > Sectors clicks to the full `/sectors` page (cross‑link). |
| **Markets > Screener** | `/screener` | Inline screener is a subset of the full Screener page (fewer filters, no cache‑aware universe). **Merge:** remove tab; add a "Open Screener" link in the Screener page or cross‑link from Markets. |
| **Markets > Portfolio** | `/portfolio` | Mini portfolio builder with only equal‑weight / analyze, missing attribution, optimization, Black‑Litterman, stress testing. **Merge:** remove tab; link to `/portfolio` with pre‑filled tickers. |
| **Markets > FX** | `/macro` > FX tab | The FX rates panel (16 pairs) is a subset of what Macro > FX shows (heatmap + PPP). **Merge:** remove tab; link to `/macro?tab=FX`. |
| **Markets > Risk** | `/risk` | Risk metrics table + correlation matrix vs. full Risk page with rolling metrics, extended ratios, GARCH, Hurst, cointegration, stress testing. **Merge:** remove risk data from Markets Overview; keep only a **mini risk KPI strip** (VaR 95%, Sharpe, Beta) in Overview. Route the full Risk tab click to `/risk?t=TICKER`. |

### B. Macro Sub‑Tabs That Duplicate Standalone Pages

| Redundant Tab | Duplicates | Rationale |
|---------------|------------|-----------|
| **Macro > Rates & Yields** | `/yield` | Nearly identical: US curve, foreign spreads, real yields, breakevens, term premium. The Yield page has its own 3‑tab structure. **Merge:** remove tab; redirect to `/yield`. |
| **Macro > Country Risk** | `/sovereign` | Both show WB 6‑KPI traffic‑light sovereign rankings. **Merge:** remove tab; redirect to `/sovereign`. |
| **Macro > Central Banks** | `/policy` | Policy rate divergence table and carry differentials are the core of the Policy page. **Merge:** remove tab; redirect to `/policy`. |
| **Macro > FX** | Markets > FX (already flagged) | The FX heatmap + PPP in Macro > FX is a richer version of the Markets FX tab. Keep in Macro only (see below). |
| **Macro > Econometric Lab** | — | Unique, but mis‑placed. It's a quant research tool, not a macro dashboard widget. **Move** to `/research` as a 5th tab. |
| **Macro > Positioning** | — | Unique (COT data), but narrow in scope. Could become a **mini widget** inside Macro > Overview or remain as a tab. No duplicate, but low usage justifies demoting to a sub‑section. |
| **Macro > Funding & Liquidity** | Macro > Financial Conditions | Partial overlap (Fed balance sheet, credit conditions). Keep both but rename/clarify boundaries (see Reshuffle below). |

### C. Other Redundancies

| Issue | Rationale |
|-------|-----------|
| **Dashboard Regime Clock** overlaps with **Macro > Overview regime** | Same data (GDP × CPI 4‑quadrant). Both can coexist since Dashboard is a high‑level snapshot and Macro is the deep dive. Acceptable. |
| **Scenario page** is orphaned (no nav link) | Must be integrated. It's a portfolio stress‑testing tool that logically belongs under **Portfolio** or **Risk**. |
| **Markets > Rankings** duplicates **Screener** ranking | Relative strength ranking is a narrow signal the Screener already provides as a preset. Remove Markets > Rankings; route to `/screener`. |

### D. Summary of Pages/Tabs to Remove

| What | Action | Surviving Destination |
|------|--------|----------------------|
| Markets > Sectors | **Remove tab** | Link to `/sectors` |
| Markets > Screener | **Remove tab** | Link to `/screener` |
| Markets > Portfolio | **Remove tab** | Link to `/portfolio` with pre‑filled tickers |
| Markets > FX | **Remove tab** | Link to `/macro?tab=FX` |
| Markets > Risk (full) | **Remove tab** → keep mini strip in Overview | Link to `/risk?t=TICKER` |
| Markets > Rankings | **Remove tab** | Link to `/screener` |
| Macro > Rates & Yields | **Remove tab** | Redirect to `/yield` |
| Macro > Country Risk | **Remove tab** | Redirect to `/sovereign` |
| Macro > Central Banks | **Remove tab** | Redirect to `/policy` |
| Macro > Econometric Lab | **Move tab** | `/research` — 5th tab |
| Macro > FX | **Keep** (merge Markets > FX into it) | Macro > FX (enriched) |
| Scenario page | **Integrate** into nav | Under Portfolio or Risk |

---

## 3. Proposed Navigation Hierarchy (The Reshuffle)

### Principle

Group nav items into **5 pillars** — the user's mental model when researching an investment:

1. **Discover** → what's happening now (overviews, screens, calendars)
2. **Analyze** → security‑level deep dives (per‑ticker tools)
3. **Build** → portfolio construction & quant strategies
4. **Macro** → global & systematic context
5. **Learn** → reference & dictionary

### New Navigation Bar (11 items, grouped)

```
[Axiom Finance]

── Discover ──    ── Analyze ──    ──── Build ────    ──────── Macro ────────    ── Learn ──
Dashboard         Markets           Portfolio           Macro Overview           Wiki
Screener          Risk              Research            Yield
Treemap           Options           Scenario            Policy & Sovereign
Calendar                                                 Atlas
```

### Full Detailed Hierarchy

#### Pillar 1: Discover (Overview & Discovery)
```
Dashboard      /dashboard       — Breadth, Fear & Greed, top movers, regime clock, yield snapshot
Screener       /screener        — Universe (Dow/Nasdaq/S&P), 20+ presets, 9 result tabs
Treemap        /treemap         — S&P500 / Nasdaq / Dow squarified treemap
Calendar       /calendar        — Earnings, dividends, macro releases, IPOs, CB meetings
```

#### Pillar 2: Analyze (Per‑Security Deep Dive)
```
Markets        /markets         — Search tickers → 5 streamlined tabs:
                                   ├─ Overview (price chart, Snowflake, news, mini risk KPI strip)
                                   ├─ Technicals (MACD, BB, Ichimoku, RSI, Fibonacci, pivots)
                                   ├─ Valuation (8‑model engine, DCF, analyst data, composite)
                                   ├─ Ratios (financial & risk ratios)
                                   └─ News & Events (13F, Form 4, earnings calendar)

Risk           /risk            — Per‑ticker rolling/extended risk, GARCH/Hurst/cointegration,
                                   stress & Monte Carlo

Options        /options         — IV surface, chain, Greeks, OI profile, binomial pricing, MC
```

> **Markets tabs removed vs. today:** Sectors → `/sectors`, Screener → `/screener`, Portfolio → `/portfolio`,
> Rankings → `/screener`, FX → Macro > FX. **Risk tab** replaced by a mini KPI strip in Overview;
> full risk analysis lives at `/risk`.

#### Pillar 3: Build (Portfolio & Quantitative Research)
```
Portfolio      /portfolio       — Holdings builder, 4 tabs:
                                   ├─ Overview (value series, metrics, drawdown, benchmarks)
                                   ├─ Risk (correlation, CAPM, risk contribution, rolling)
                                   ├─ Attribution (Fama‑French 3F/5F, Kelly)
                                   └─ Optimize (efficient frontier, Black‑Litterman)

Research       /research        — 5 tabs:
  (formerly 4)                    ├─ Risk Parity (ERC / inverse‑vol → backtest)
                                   ├─ FX Carry (G10 carry table → backtest)
                                   ├─ Momentum (1M/3M/6M/12M‑1M deciles → backtest)
                                   ├─ Realized Moments (GK variance, skew, cross‑section)
                                   └─ Econometric Lab ◂ MOVED FROM MACRO (pooled OLS)

Scenario       /scenario        — Stress test portfolios vs historical episodes + custom shocks
  ◂ ADDED TO NAV                   ├─ Historical (GFC, COVID, Rate Shock, Dot‑com)
                                   └─ Custom (beta‑based macro shocks)
```

#### Pillar 4: Macro (Global & Systematic Context)
```
Macro Overview /macro            — Condensed 8‑tab hub:
                                   ├─ Overview (yield curve, sector perf, regime clock, KPI strip)
                                   ├─ Inflation (CPI/PCE/PPI/M2/Quantity Theory)
                                   ├─ Growth & Employment (GDP/NFP/claims/JOLTS)
                                   ├─ Housing (Case‑Shiller, starts, mortgage rate)
                                   ├─ Commodities (WTI, gold, copper, Agri, Axiom Index)
                                   ├─ FX (heatmap + PPP) ◂ CONSOLIDATED
                                   ├─ Leading Indicators (LEI, CFNAI, ISM, IS‑LM‑PC)
                                   ├─ Financial Conditions (NFCI, STLFSI, funding, liquidity, COT)
                                   └─ Sentiment Signals (Finnhub news sentiment)

Yield          /yield            — Renamed "Yield & Credit":
                                   ├─ US Curve (spot curve, inversion detection)
                                   ├─ Foreign Spreads (10Y vs US, multi‑country)
                                   └─ Real & Breakeven (TIPS, breakevens, ACM term premium, credit pulse)

Policy &       /policy           ◂ MERGED Policy + Sovereign into one hub:
  Sovereign                       ├─ Policy Tracker (CB divergence table, G10 carry, Fed funds)
                                   └─ Sovereign Risk (6‑KPI traffic‑light, 200 countries, composite score)

Atlas          /atlas            — World choropleth map, 6 indicators, year slider, regional blocs
```

> **Macro tabs removed vs. today:** Rates & Yields → `/yield`, Country Risk → `/policy` (Sovereign tab),
> Central Banks → `/policy` (Policy tab), Econometric Lab → `/research`, Funding & Liquidity →
> merged into Financial Conditions tab.

#### Pillar 5: Learn (Reference)
```
Wiki           /wiki             — Financial dictionary, 410+ terms, 26 categories, search
```

### Mobile Nav (Bottom Bar, 8 items + theme toggle)

Given screen real estate limits, the mobile nav consolidates further:

```
Markets | Screener | Portfolio | Research | Macro | Calendar | Atlas | Wiki
```

The full 5‑pillar structure is accessible via a **hamburger/drawer** on mobile. Secondary pages
(Risk, Options, Treemap, Scenario, Yield, Policy & Sovereign) live in the drawer.

---

## 4. Transition & Redirection Strategy

### Merged Views — Data Migration

| Removed Tab | Data Integrated Into |
|-------------|---------------------|
| Markets > Risk (full table) | Reduced to a **mini KPI strip** in Markets > Overview showing VaR 95%, Sharpe, Beta. Full risk → `/risk?t=TICKER`. |
| Markets > Sectors | `/sectors` page. Add a **deep‑link anchor** (`#heatmap`) so Markets can link directly to the sector heatmap section. |
| Markets > Screener | `/screener` page. Add a **query param** `?preset=relative_strength` to replace Rankings. |
| Markets > Portfolio | `/portfolio` page. Accept **query param** `?t=AAPL,MSFT` to pre‑fill holdings. |
| Markets > FX | `/macro?tab=FX` — Macro > FX already has the richer heatmap + PPP. Ensure the old Markets FX component is the same as Macro > FX. |
| Macro > Rates & Yields | `/yield` page — all three subtabs (US Curve, Foreign Spreads, Real & Breakeven) already cover the same data. No data loss. |
| Macro > Country Risk | `/sovereign` — merged into Policy & Sovereign hub. The Sovereign risk table is identical. |
| Macro > Central Banks | `/policy` — policy rate divergence + CB meetings. The Policy page already renders the CB table. Add CB meetings calendar widget. |
| Macro > Econometric Lab | `/research` — new 5th tab "Econometric Lab". Keep the same UI; just move the component import. |
| Macro > Funding & Liquidity | Merged into Macro > Financial Conditions tab (or kept as a sub‑section within it). Rename tab to "Financial & Funding Conditions". |
| Scenario (orphan) | Promote to navbar under Pillar 3. Add a **Scenario** link between Research and Macro. |

### URL Redirects (301 / next.config.js rewrites)

| Old URL | Redirect To | Notes |
|---------|-------------|-------|
| `/markets?tab=Sectors` | `/sectors` | With optional `#heatmap` anchor |
| `/markets?tab=Screener` | `/screener` | |
| `/markets?tab=Portfolio` | `/portfolio?t=…` | Preserve ticker query param |
| `/markets?tab=FX` | `/macro?tab=FX` | |
| `/markets?tab=Risk` | `/risk?t=…` | Preserve ticker & period params |
| `/markets?tab=Rankings` | `/screener?preset=relative_strength` | |
| `/macro?tab=Rates%20%26%20Yields` | `/yield` | |
| `/macro?tab=Country%20Risk` | `/sovereign` | After merge, redirect to `/policy?tab=sovereign` |
| `/macro?tab=Central%20Banks` | `/policy` | |
| `/macro?tab=Econometric%20Lab` | `/research?tab=lab` | |
| `/macro?tab=Funding%20%26%20Liquidity` | `/macro?tab=Financial%20Conditions` | |

### Implementation Order (Recommended)

1. **Navbar restructure** — update both `Navbar.tsx` and `MobileNav.tsx` with the new 5‑pillar grouping and 11‑item bar.
2. **Markets tab removal** — delete the 6 redundant tabs from `markets/page.tsx`; add mini risk KPI to Overview.
3. **Macro tab removal** — delete the 5 redundant tabs from `macro/page.tsx` (Rates, Country Risk, Central Banks, Econ Lab, Funding).
4. **Move Econ Lab** — copy component to `research/` pages; add 5th tab to Research Hub.
5. **Merge Policy & Sovereign** — combine into a single `/policy` page with a tab selector (Policy Tracker / Sovereign Risk).
6. **Promote Scenario** — add `/scenario` to navbar under Build pillar.
7. **Add redirects** — set up `next.config.js` rewrites for all old URLs.
8. **Test** — `pytest` + `tsc` + Docker rebuild + curl each new path.

### Visual Summary

```
BEFORE (16 flat items):
  Dashboard | Treemap | Calendar | Screener | Sectors | Portfolio | Research |
  Markets | Risk | Options | Macro | Yield | Policy | Sovereign | Atlas | Wiki

AFTER (11 grouped items):
  [Discover]          [Analyze]          [Build]                    [Macro]                      [Learn]
  Dashboard           Markets            Portfolio                  Macro Overview               Wiki
  Screener            Risk               Research                   Yield
  Treemap             Options            Scenario ◂ NEW             Policy & Sovereign ◂ MERGED
  Calendar                                                          Atlas

Markets sub-tabs BEFORE (10):     Markets sub-tabs AFTER (5):
  Overview                          Overview (w/ mini risk KPI)
  Risk                              Technicals
  Technicals                        Valuation
  Valuation                         Ratios
  Ratios                            News & Events
  Portfolio ───→ /portfolio
  Rankings  ───→ /screener
  Sectors   ───→ /sectors
  Screener  ───→ /screener
  FX        ───→ /macro?tab=FX

Macro sub-tabs BEFORE (15):        Macro sub-tabs AFTER (8):
  Overview                          Overview
  Rates & Yields ──→ /yield         Inflation
  Inflation                         Growth & Employment
  Growth & Employment               Housing
  Housing                           Commodities
  Commodities                       FX (heatmap + PPP) ◂ CONSOLIDATED
  FX                                Leading Indicators
  Leading Indicators                Financial & Funding Conditions ◂ MERGED
  Financial Conditions              Sentiment Signals
  Positioning ──→ merged into Fin'l Conditions
  Econometric Lab ──→ /research
  Country Risk ──→ /policy
  Central Banks ──→ /policy
  Funding & Liquidity ──→ merged
  Sentiment Signals
```
