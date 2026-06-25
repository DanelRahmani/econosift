# Axiom Finance — UI Review Report

**Review date:** 2026-06-25  
**Environment:** `http://localhost` (Docker Compose: nginx → frontend + backend)  
**Viewport tested:** Desktop ~1440×900 and mobile ~390×844  
**Method:** Pass 1 — live walkthrough + API spot-checks. **Pass 2 — exhaustive tab matrix, every sub-tab, light + dark theme on chart-heavy views.**

---

## Executive Summary

The application is functionally rich across 12+ pages with a consistent visual language (maroon accent, card-based layout, Recharts). Core equity workflows (Markets, Portfolio, Options, Research) generally render data correctly. However, several **critical** issues undermine trust and usability:

1. **Dark-mode chart Y-axis corruption** on Markets → Technicals (prices shown as hundreds of millions).
2. **Ratios Dividend Yield 37%** for AAPL — `dividendYield: 0.37` from API double-scaled by `fmtPctFromFraction` (true yield ≈0.5%).
3. **Calendar macro feed quality** — hundreds of low-value FRED “release calendar” entries drown out real economic events; initial load takes ~15–20s with a blank skeleton.
4. **Navigation overflow** — 12 top-nav items overflow on desktop and mobile without scroll/hamburger; mobile bottom nav omits Treemap, Calendar, and Sectors.
5. **Repeated loading/empty states** — Treemap, Calendar, and Risk pages show long blank areas before content appears, with weak loading feedback.

---

## Severity Legend

| Level | Meaning |
|-------|---------|
| **Critical** | Broken data display, misleading numbers, or page unusable |
| **Major** | Significant UX/visual defect or data quality problem |
| **Minor** | Polish, consistency, accessibility |

---

## Cross-Page / Global Issues

### Navigation & Layout

| ID | Severity | Issue |
|----|----------|-------|
| G-01 | **Major** | **Top navbar overflows** at 1440px width — only Dashboard through Research (or Markets) visible; Risk, Options, Macro, Atlas clipped with no horizontal scroll or overflow menu. |
| G-02 | **Major** | **Mobile bottom nav (`MobileNav`)** shows 9 cramped items; **Treemap, Calendar, and Sectors are missing** while Dashboard is duplicated at the bottom. |
| G-03 | **Major** | **Navbar vs MobileNav inconsistency** — different page sets and order; users cannot reach Treemap/Calendar/Sectors from mobile bottom nav. |
| G-04 | **Minor** | **Theme toggle** only in desktop navbar; no theme control in mobile bottom nav. |
| G-05 | **Minor** | **Admin page** (`/admin`) exists (Backend Health) but is **not linked** anywhere in navigation. |
| G-06 | **Minor** | Logo uses serif `font-display`; body UI is sans-serif — intentional but slightly disjointed. |
| G-07 | **Minor** | **Redundant navigation** — Markets sub-tabs duplicate Screener/Sectors links already in main nav. |

### Loading & Performance

| ID | Severity | Issue |
|----|----------|-------|
| G-08 | **Major** | **Slow initial loads** without meaningful progress: Treemap (~8s blank), Calendar API (~15–20s), Risk rolling metrics slow. Users see empty pink/skeleton panels that look broken. |
| G-09 | **Minor** | Loading text often appears in corner (“Loading rolling metrics…”) rather than centered in the content area. |

### Theming

| ID | Severity | Issue |
|----|----------|-------|
| G-10 | **Critical** | **Dark mode breaks Markets → Technicals price chart Y-axis** — labels show values like `788417899` / `732055664` instead of ~$250–280. Light mode appears correct. |
| G-11 | **Minor** | Dark mode generally usable elsewhere; calendar legend/filter selected states use same red for all event types (see Calendar). |

### Formatting & Copy

| ID | Severity | Issue |
|----|----------|-------|
| G-12 | **Minor** | **Raw ISO timestamps** shown to users (e.g. Screener: `as of 2026-06-25T14:40:30.375288+00:00`). |
| G-13 | **Minor** | Compute-tier indicators inconsistent — Options Monte Carlo tab shows `🔴` emoji in label; Research uses `🔴 Run Backtest` text. |
| G-14 | **Minor** | **Theme persistence** — dark mode survives cross-page navigation (good); toggling on one page affects all. |
| G-15 | **Minor** | **Active tab styling inconsistency** — main nav uses filled maroon pill; many sub-tabs use underline only; period/overlay buttons use outline style. |

---

## Page-by-Page Findings

### `/dashboard`

| ID | Severity | Issue |
|----|----------|-------|
| D-01 | **Major** | **Fear & Greed gauge** — needle overlaps the numeric value and “Fear” label; unconventional thick arc design reads as visually broken vs standard semicircle gauges. |
| D-02 | **Minor** | Fear & Greed signal bars: score `26` labeled “Fear” uses amber bar; score `46` labeled “Neutral” also amber — color scale doesn’t clearly distinguish fear vs neutral. |
| D-03 | **Major** | **Global Indices table** — price/change columns **clipped off** right edge of card on desktop; only index names visible. |
| D-04 | **Minor** | Market breadth advancing/declining bar shows no gray segment for “0 unchanged” despite label. |
| D-05 | **Minor** | McClellan Summation signal labeled “Extreme Greed” at 81 while composite index is 44 “Fear” — may be correct per-signal but confusing without explanation. |

### `/markets`

| ID | Severity | Issue |
|----|----------|-------|
| M-01 | **Critical** | See G-10 — dark mode Technicals chart Y-axis corruption. |
| M-02 | **Major** | **Snowflake Score layout** — strength scores (green `10.0`) visually align between Strengths and Risks columns; risk scores (`0.5`, `1.1`, `1.7`) appear misaligned and easy to misread. |
| M-03 | **Minor** | Normalised price chart has **no legend** — cannot tell which line is AAPL vs MSFT vs benchmark. |
| M-04 | **Minor** | Sub-tab row overflows — FX tab may be cut off on narrower widths; 10 sub-tabs is dense. |
| M-05 | **Minor** | Ticker chips (AAPL, MSFT) slightly misaligned vertically vs search input. |
| M-06 | **Minor** | Earnings event chips use tan color outside main palette. |
| M-07 | **Major** | **Valuation tab** — Snapshot KPI strip truncates values (`$27…`, `$4…`, `33…`) — unreadable on desktop. |
| M-08 | **Critical** | **Ratios tab — Dividend Yield shows 37.00%** for AAPL; API returns `dividendYield: 0.37` and UI applies `×100` via `fmtPctFromFraction`. yfinance value is likely already %-scaled or wrong field — true yield ≈0.5%. Same normalisation gap documented in `screener_service.py` not applied here. |
| M-09 | **Minor** | Valuation fair-value gauge has black rectangular artifacts at arc endpoints. |
| M-10 | **Minor** | Valuation Dupont decomposition bar label truncated (“N. Asset T…”). |
| M-11 | **Minor** | **Technicals (dark)** — “Watchlist” button truncated to “Watchlis…”. |
| M-12 | **Minor** | Technicals RSI 33.1 labeled “Neutral” — borderline oversold; threshold UX debatable. |
| M-13 | **Minor** | Technicals page is very long (price + 6+ indicator charts); no sticky sub-nav — heavy scroll. |
| M-14 | **Minor** | Markets **Portfolio** sub-tab (allocation sliders) works; distinct from `/portfolio` page — naming collision. |
| M-15 | **Minor** | Markets **Rankings** tab loads relative-strength table (light mode OK). |
| M-16 | **Minor** | Markets **Sectors / Screener** sub-tabs embed full-page components — functional but redundant with main nav routes. |
| M-17 | **Minor** | Markets **FX** sub-tab loads rates panel + base-currency selector (USD/EUR/…). |

### `/treemap`

| ID | Severity | Issue |
|----|----------|-------|
| T-01 | **Major** | **~8 second blank state** before treemap renders; no spinner or “Loading treemap…” in the main panel. |
| T-02 | **Major** | **Sector/industry labels clipped** at top of treemap container (text cut off). |
| T-03 | **Major** | **Poor text contrast** — white ticker text on light green/red cells; black text on some cells inconsistent. |
| T-04 | **Minor** | “Group by Sector › Industry” chevron suggests navigation, not drill-down toggle. |
| T-05 | **Minor** | Subtitle says “Colour = 1D return” but doesn’t update when period filter changes (e.g. 1W). |

### `/calendar`

| ID | Severity | Issue |
|----|----------|-------|
| C-01 | **Critical** | **Macro event data quality** — API returns hundreds of FRED release-calendar entries per day (“Coinbase Cryptocurrencies”, “Tri-Party General Collateral Rate Data”, etc.) that are **not actionable economic calendar events**. Calendar is unusable for macro planning. |
| C-02 | **Major** | **~15–20s load time** — large skeleton/blank area; users perceive page as broken before data arrives. |
| C-03 | **Major** | When loaded, **Fri column clipped** on typical viewport; horizontal scroll not obvious. |
| C-04 | **Major** | **Very long event titles** (e.g. full Fed paper titles) create uneven column heights and poor scannability. |
| C-05 | **Minor** | Filter buttons (Macro/Earnings/Dividend/IPO) all use same red when selected; legend uses blue/yellow/green/purple — **selected state doesn’t match category colors**. |
| C-06 | **Minor** | “This Week” disabled styling looks like a broken button (opacity only). |
| C-07 | **Minor** | Default index is **Dow 30**; most users expect S&P 500 default. |
| C-08 | **Minor** | Earnings array empty for Dow 30 this week — may be data gap; no empty-state message per category. |
| C-09 | **Minor** | Impact filter uses text stars (`★`) instead of icons; low visual polish. |

### `/screener`

| ID | Severity | Issue |
|----|----------|-------|
| S-01 | **Minor** | See G-12 — raw ISO cache timestamp. |
| S-02 | **Minor** | Preset button **“Overbought (RSI>70)” truncated** to “Overbought (RSI>7…” — container doesn’t wrap/scroll presets. |
| S-03 | **Minor** | Technical preset row has uneven layout (second row indented under Technical label). |
| S-04 | **Minor** | Default universe **Dow 30** (30 stocks shown) vs typical S&P 500 screener expectation. |
| S-05 | **Minor** | **Charts view** — sparkline gallery loads for Dow 30 universe (pass 2). |
| S-06 | **Minor** | Result tabs **Performance, Technicals, Valuation, Profitability, Dividends, All Columns** — switch without error; table columns change per tab. |
| S-07 | **Minor** | **Dark mode** — screener readable; preset overflow issue (S-02) persists. |

### `/sectors`

| ID | Severity | Issue |
|----|----------|-------|
| SE-01 | **Major** | **“Today’s Returns” cards show 8 sectors** but bar chart below includes **Utilities and Financials** — inconsistent sector coverage. |
| SE-02 | **Major** | Bar chart **missing percentage labels** on top 3 sectors (Industrials, Health Care, Materials). |
| SE-03 | **Minor** | Y-axis sector labels very low contrast (light gray on white). |
| SE-04 | **Minor** | Bar chart bottom clipped — Technology label partially cut off. |

### `/portfolio`

| ID | Severity | Issue |
|----|----------|-------|
| P-01 | **Minor** | Holdings ticker inputs use placeholder **“AAPL”** for every row (MSFT, GOOGL, BRK-B rows still show AAPL placeholder). |
| P-02 | **Minor** | Overview tab underline slightly thick/off-center. |
| P-03 | **Minor** | Holdings card has large empty area to the right of inputs. |
| P-04 | **Minor** | **Optimize** tab — four 🟡 sections (Efficient Frontier, Monte Carlo, Black-Litterman, Stress) with emoji-prefixed run buttons; empty states until run. |
| P-05 | **Minor** | **Risk** / **Attribution** tabs — lazy-fetch on first visit (brief loading); Attribution includes Kelly + Fama-French panels. |

*Note: KPIs and charts load correctly for default portfolio; metrics appear internally consistent.*

### `/research`

| ID | Severity | Issue |
|----|----------|-------|
| R-01 | **Major** | **Risk Parity ERC weights chart** — Y-axis tick labels misaligned with bars; X-axis baseline stops before final tick. |
| R-02 | **Minor** | Tab underline wider than “Risk Parity” text. |
| R-03 | **Minor** | FX Carry table **right column truncated** (“30d…” header cut off). |
| R-04 | **Minor** | Footer says “High-yielders (AUD/NZD) top the table” but **GBP ranks above NZD** in carry sort — copy doesn’t match sort order. |
| R-05 | **Minor** | Backtest charts require explicit button press (correct per compute tier) but empty state copy is minimal. |
| R-06 | **Minor** | **Momentum** tab — decile bar chart lacks **D1–D10 x-axis labels**; top decile prior return ~105% on Dow 30 / 12M-1M (verify scaling). |
| R-07 | **Minor** | **Momentum** — universe/signal selectors use inconsistent active styles (maroon vs gray). |
| R-08 | **Minor** | **Realized Moments** tab — requires “🔴 Run Cross-Section” for decile panel; ticker-level GK variance chart loads on tab open. |

### `/risk`

| ID | Severity | Issue |
|----|----------|-------|
| RK-01 | **Major** | **Max Drawdown (3Y)** shows em dash (`—`) in summary while other metrics populate. |
| RK-02 | **Major** | Rolling metrics tab **slow to load**; “Loading rolling metrics…” in corner for extended period. |
| RK-03 | **Minor** | Summary card shows 30-day realised vol while rolling window selector defaults to 252D — relationship unclear. |
| RK-04 | **Minor** | Beta summary doesn’t state benchmark index. |
| RK-05 | **Minor** | **On-Demand** tab — four 🟡 Calculate panels (GARCH, Hurst, OU, Cointegration) render correctly; cointegration needs second ticker (message shown). |
| RK-06 | **Minor** | **Extended** tab — CAPM variance decomposition loads; Export CSV present. |
| RK-07 | **Minor** | **Stress & Monte Carlo** tab — Monte Carlo path count + horizon selectors; explicit “Run Analysis” / “Run Stress Analysis” buttons (correct 🟡 gating). |
| RK-08 | **Minor** | **Correlation** tab — not deeply verified in pass 2 but tab switches without error. |

### `/options`

| ID | Severity | Issue |
|----|----------|-------|
| O-01 | **Major** | Deep ITM call ($110 strike) shows **IV 771.9%** — likely calculation/display bug for near-expiry deep ITM options. |
| O-02 | **Minor** | Several chain rows show `—` for bid/ask but non-zero OI — unclear if stale or expected. |
| O-03 | **Minor** | IV Rank bar at 2.2 shows dot at far left — scale (0–100 vs 0–1) should be verified for user clarity. |
| O-04 | **Minor** | `~15min delay` badge styling differs from other page badges. |
| O-05 | **Major** | **Volatility tab** — IV Smile Y-axis extends to **360%**; deep ITM wing IVs unreliable (same class as chain 771% issue). |
| O-06 | **Minor** | Volatility tab adds **Max Pain** and **Implied Move** KPIs not visible on Chain tab — good data but inconsistent KPI strip across tabs. |
| O-07 | **Minor** | **OI Profile** tab loads open-interest chart (light mode). |
| O-08 | **Minor** | **Monte Carlo 🔴** tab — compute-gated; not executed in review (requires user click). |

### `/macro`

| ID | Severity | Issue |
|----|----------|-------|
| MC-01 | **Major** | **Tab bar horizontal scrollbar** — 10+ tabs overflow; scrollbar appears even when tabs fit awkwardly. |
| MC-02 | **Major** | **Start Year input truncates** “2000” to “200” — field too narrow. |
| MC-03 | **Minor** | Countries counter shows **3/8 selected** but only US and Germany visibly highlighted; Japan appears in regime panel (third selection off-screen or logic mismatch). |
| MC-04 | **Minor** | Germany/Japan regime shows **“Detecting…”** indefinitely while US shows “Expansion”. |
| MC-05 | **Minor** | Phase 16 tabs (**Country Risk**, **Central Banks**) not present — expected if not yet shipped. |
| MC-06 | **Minor** | Econometric Lab tab present (Phase 15) — verified in pass 2. |
| MC-07 | **Minor** | **Econometric Lab** — “Run Regression” uses red dot prefix; End Year defaults to 2026; country chip grid tight vertically. |
| MC-08 | **Minor** | **Positioning** tab — loads (COT/positioning charts); tab bar shows “Econ…” truncated for Econometric Lab at 1440px. |
| MC-09 | **Minor** | **Rates & Yields** — loads yield-curve style charts (pass 2 spot-check via `?tab=rates`). |
| MC-10 | **Minor** | Remaining tabs (`inflation`, `employment`, `housing`, `commodities`, `fx`, `leading`, `financial`) — URL-navigated; content loads with standard macro chart layout (no empty-state failures observed). |

### `/atlas`

| ID | Severity | Issue |
|----|----------|-------|
| A-01 | **Major** | **No color legend** on choropleth map — users cannot interpret red vs green magnitudes. |
| A-02 | **Major** | **Country names truncated** in KPI cards (“West Bank and Ga…”). |
| A-03 | **Major** | **Indicator pills truncated** — “Government Debt (% of GDP)” cut off at container edge. |
| A-04 | **Minor** | Map rendering **artifacts** (stray colored pixels in oceans); Canada/Greenland clipped at top. |
| A-05 | **Minor** | Canada shown bright red for GDP Growth — verify data year vs color scale (may be correct for a bad year but surprising without legend). |
| A-06 | **Minor** | Highest GDP growth 43.82% Guyana — plausible for single-year oil boom; label should clarify **which year** the KPI reflects. |

### `/admin`

| ID | Severity | Issue |
|----|----------|-------|
| AD-01 | **Minor** | Page reachable but **hidden** — no nav link; intentional for ops but hurts discoverability for self-hosted operators. |

---

## Factual / Data Quality Notes

These are observations where displayed data may mislead users. (App “as of” date is 2026-06-25 throughout — prices like AAPL ~$277 are plausible for that date.)

| Area | Observation |
|------|-------------|
| Calendar macro | FRED release calendar treats every data series release as a “macro event” — **not** equivalent to CPI/jobs/GDP release calendar. |
| Calendar earnings | Empty for Dow 30 this week — verify Finnhub earnings window vs index constituents. |
| Options IV | 771% IV on deep ITM near-expiry calls; IV Smile wing to 360% (O-05). |
| Ratios dividend yield | API `dividendYield: 0.37` → UI 37.00% (M-08) — normalization bug. |
| Markets dark chart | Y-axis values in hundreds of millions — **definite display bug**, not market data. |
| Fear & Greed | Per-signal labels (e.g. McClellan “Extreme Greed”) can disagree with composite “Fear” — may be by design; needs UI explanation. |
| FX Carry | Policy rates and carry spreads appear reasonable; sort order vs footer copy mismatch. |
| Atlas KPIs | Extreme values (Guyana +43%, West Bank -26%) need **year context** on the KPI strip. |

---

## Accessibility & Mobile

| ID | Severity | Issue |
|----|----------|-------|
| A11Y-01 | **Major** | Low contrast text in Sectors bar chart Y-axis labels. |
| A11Y-02 | **Major** | Treemap cell text contrast fails on light green/red backgrounds. |
| A11Y-03 | **Minor** | Many filter buttons lack visible focus ring in keyboard navigation testing. |
| MOB-01 | **Major** | Bottom nav 9 items — labels/icons too small; horizontal overflow scrollbar on page. |
| MOB-02 | **Major** | Top nav on mobile truncates at “Markets” — no hamburger menu. |
| MOB-03 | **Minor** | Fixed bottom nav overlaps page content (Fear & Greed card clipped in mobile view). |

---

## Claude Code Fix Backlog

Prioritized tasks for an autonomous Claude Code session. Group by theme; each item references issue IDs above.

### P0 — Critical (fix first)

1. **Fix dark-mode Technicals chart Y-axis** (G-10, M-01) — inspect Recharts/theme tick formatter in Markets technicals price chart; ensure price domain and tick formatting work in dark mode (confirmed broken with AAPL single-ticker too).
2. **Normalize dividendYield** (M-08) — apply same fraction normalisation as `screener_service.py` in `metrics.py` / RatiosTab; verify AAPL shows ~0.5% not 37%.
3. **Filter calendar macro events** (C-01) — backend `calendar_service` / FRED integration: whitelist high-impact US releases (CPI, NFP, GDP, FOMC, etc.) or use Finnhub economic calendar; cap daily macro count; exclude routine data series updates.
4. **Add calendar load UX** (C-02, G-08) — show centered spinner + “Loading calendar…”; consider backend caching/warmup for calendar endpoint.
5. **Fix Valuation KPI truncation** (M-07) — widen KPI strip or use `min-w-0` / responsive grid so Price, Market Cap, P/E display fully.

### P1 — Major UX / Visual

4. **Navbar overflow** (G-01, MOB-02) — collapsible hamburger on `<md`, or horizontal scroll with fade, or split nav into “More” dropdown; ensure all 12 pages reachable.
5. **Align MobileNav with Navbar** (G-02, G-03, MOB-01) — add Treemap, Calendar, Sectors; remove duplicate Dashboard or use 5-item max + “More”; add `pb-safe` padding on main content for fixed bottom nav.
6. **Treemap loading state** (T-01) — spinner in treemap container; fix label clipping (T-02) and text contrast (T-03, A11Y-02).
7. **Dashboard Global Indices clipping** (D-03) — fix table/card overflow or horizontal scroll on indices table.
8. **Fear & Greed gauge polish** (D-01) — adjust needle/text z-order; consider standard semicircle SVG or reduce stroke width.
9. **Sectors consistency** (SE-01, SE-02, SE-03) — show all 11 SPDR sectors in KPI cards; add missing bar labels; darken Y-axis labels.
10. **Snowflake layout** (M-02) — use grid so strength/risk scores align with correct columns.
11. **Atlas legend + truncation** (A-01, A-02, A-03) — add color scale legend with min/mid/max; `truncate` with tooltip for long country names; wrap indicator pills.
12. **Macro tab overflow** (MC-01) — scrollable tab row without redundant page scrollbar; widen Start Year input (MC-02).
13. **Risk Max Drawdown** (RK-01) — fix API or frontend binding for 3Y max drawdown field.
14. **Options deep ITM IV** (O-01, O-05) — clamp or hide nonsensical IV on chain and smile charts.
15. **Momentum decile labels** (R-06) — add D1–D10 ticks on x-axis.

### P2 — Polish & Consistency

15. **Format timestamps** (G-12, S-01) — shared `formatAsOf()` for screener/cache dates (e.g. “Jun 25, 2026 2:40 PM UTC”).
16. **Screener preset overflow** (S-02) — wrap preset chips or horizontal scroll container.
17. **Portfolio placeholders** (P-01) — generic placeholder “Ticker” instead of hardcoded AAPL.
18. **Calendar UI** (C-05, C-06, C-09) — category-colored filter chips; clearer disabled “This Week”; star icons for impact.
19. **Chart legends** (M-03) — normalized price chart line legend for tickers/benchmark.
20. **Research charts** (R-01, R-03) — fix Recharts layout on ERC weights; ensure FX table responsive.
21. **Research copy** (R-04) — update footer to match actual sort or fix sort to AUD, NZD, GBP…
22. **Treemap period label** (T-05) — dynamic subtitle reflecting selected period.
23. **Admin link** (G-05, AD-01) — optional footer link “Admin” for operators or document in README.
24. **Compute tier badges** (G-13) — consistent styled badge component instead of emoji in tab labels.
25. **Default index** (C-07, S-04) — consider S&P 500 as default for Calendar and Screener.
26. **Macro regime “Detecting…”** (MC-04) — timeout fallback message or retry for Germany/Japan.
27. **Atlas KPI year label** (A-06) — show selected slider year on Highest/Lowest cards.
28. **Valuation gauge artifacts** (M-09) — fix SVG arc stroke caps.
29. **Technicals Watchlist truncation** (M-11) — navbar overflow / button shrink.
30. **Options KPI consistency** (O-06) — show Max Pain / Implied Move on Chain tab or document tab-specific KPIs.
31. **Macro tab truncation** (MC-08) — scroll hint or shorter labels for Econometric Lab.
32. **Unified active-state styles** (G-15) — design tokens for tab/button selected states.

### Suggested Claude Code invocation

```bash
cd C:\Users\danel\Coding\axiomfinance
claude --worktree ui-fixes -p "Implement P0 and P1 items from UI_report.md at repo root. Run pytest, frontend tsc, docker compose build + recreate, verify fixes in browser. Do not change unrelated code." --permission-mode acceptEdits
```

---

## Pass 2 — Exhaustive Tab & Theme Matrix

**Viewport:** 1440×900 desktop. **Themes:** Light and dark tested on Markets Technicals, Screener, Calendar (dark), Risk (dark), Options Volatility, Macro Lab.

### Coverage matrix

| Page | Tabs / sections tested | Light | Dark | Notes |
|------|------------------------|-------|------|-------|
| `/dashboard` | Breadth, Fear&Greed, Regime, Global Indices, Yield Curve, Movers, Sector heatmap | ✅ | ✅ (pass 1) | No sub-tabs; scroll full page |
| `/treemap` | S&P500/Nasdaq/Dow · 1D–1Y · Sector/Industry drill | ✅ | — | Slow load (T-01) |
| `/calendar` | Index · week nav · type/impact filters · grid | ✅ | ✅ | Macro noise (C-01); Fri column clipped |
| `/screener` | 7 result tabs · Table/Charts view · 20 presets · 3 universes | ✅ | ✅ | ISO timestamp (S-01) |
| `/sectors` | 6 periods · rotation clock · industry drill-down | ✅ | — | SE-01/02 |
| `/portfolio` | Overview · Risk · Attribution · Optimize | ✅ | — | Optimize 🟡 buttons |
| `/research` | Risk Parity · FX Carry · Momentum · Realized Moments | ✅ | — | All 4 tabs |
| `/markets` | Overview · Risk · Technicals · Valuation · Ratios · Portfolio · Rankings · Sectors · Screener · FX | ✅ | ✅ Technicals | **All 10 sub-tabs** |
| `/risk` | Rolling · Extended · Correlation · On-Demand · Stress&MC | ✅ | ✅ | All 5 tabs |
| `/options` | Chain · Volatility · OI Profile · Monte Carlo | ✅ | — | MC tab not run |
| `/macro` | overview · rates · inflation · employment · housing · commodities · fx · leading · financial · positioning · lab | ✅ | — | **All 11 tabs** via `?tab=` |
| `/atlas` | 6 indicators · 5 blocs · year slider · rankings | ✅ | — | Pass 1 + indicator pills |
| `/admin` | Health · cache table | ✅ | — | Hidden from nav |

### Markets sub-tab summary (pass 2)

| Tab | Loads | Critical issues |
|-----|-------|-----------------|
| Overview | ✅ | Snowflake layout (M-02); no chart legend (M-03) |
| Risk | ✅ | Correlation matrix + metrics table |
| Technicals | ✅ | **Dark Y-axis bug (G-10)**; rich indicator suite |
| Valuation | ✅ | KPI truncation (M-07); DCF + 8-model engine |
| Ratios | ✅ | **Dividend yield 37% (M-08)**; Interest Coverage — |
| Portfolio | ✅ | Allocation sliders 50/50 default |
| Rankings | ✅ | 3M relative strength table |
| Sectors | ✅ | Embedded sector heatmap |
| Screener | ✅ | Embedded screener (duplicate route) |
| FX | ✅ | Base currency dropdown |

### Dark-mode regression summary

| Component | Light | Dark | Regression? |
|-----------|-------|------|-------------|
| Markets Technicals price chart | ✅ Correct ~$200–315 axis | ❌ Y-axis `732055664` | **Yes — G-10** |
| Markets Technicals indicator charts | ✅ | ✅ Appear OK | No |
| Dashboard / Portfolio charts | ✅ | ✅ | No |
| Calendar filters | ✅ | ✅ Readable | Filter colors (C-05) |
| Screener table | ✅ | ✅ | No |
| Macro charts | ✅ | — | Not fully dark-tested |

### Root page

| `/` | Redirects to `/markets` (default landing) — consistent with logo link. |

---

## Pages Reviewed (updated)

All primary routes and **every documented sub-tab** were visited in pass 2. Compute-gated actions (Options Monte Carlo, Portfolio Optimize runs, Research backtests, Risk On-Demand Calculate) were verified for **UI presence** but not executed end-to-end (correct per 🟡/🔴 tier rules).

---

*End of report.*
