# Axiom Finance — Claude Code Execution Plan

## Stack
- **Backend**: Python FastAPI
- **Frontend**: Next.js (TypeScript, React)
- **Data**: All free — yfinance (primary), FRED (fredapi), Eurostat, World Bank, OECD, IMF WEO, Finnhub (free tier), FinanceDatabase, Wikipedia scraping
- **Cost**: $0 — no paid APIs

---

## Phase Map
Execute phases in order. Phase 0 unblocks user trust; Phases 1–10 build out the platform.

| Phase | Feature | Priority |
|---|---|---|
| 0 | Critical Bug Fixes | Immediate |
| 1 | Valuation Engine (8 models) | High |
| 2 | Market Breadth & Dashboard | High |
| 3 | S&P 500 Treemap | High |
| 4 | Economic Calendar | Medium |
| 5 | Screener Overhaul | Medium |
| 6 | Rolling Quantitative Metrics | Medium |
| 7 | Options & IV Module | Medium |
| 8 | Macro Expansion | Medium |
| 9 | Snowflake Composite Score | Low |
| 10 | Sector Performance Charts | Low |

---

## Phase 0 — Bug Fixes (Do First)

**0.1 Valuation Tab — DCF panel is blank**
Two-stage DCF using slider inputs (Risk-Free Rate, Market Premium, FCF Growth, Terminal Growth). Fetch TTM FCF and shares outstanding from `yfinance`. Output: intrinsic value per share, Bear/Base/Bull scenario table, 7×7 sensitivity heatmap (FCF Growth vs WACC), colour-coded by upside/downside vs current price.

**0.2 Macro Tab — FX Rates panel empty**
Fetch 15+ major currency pairs via yfinance (`EURUSD=X` format). Show current rate, 1D/1W/1M/1Y change %, 30-day sparkline per pair. Add base currency switcher (USD/EUR/GBP).

**0.3 Macro Tab — Regime Classifier stuck on "Detecting..."**
Implement 2×2 Goldilocks matrix: GDP trend (FRED `GDPC1`) × CPI trend (FRED `CPIAUCSL`) → Goldilocks / Reflation / Stagflation / Recession. Also for Eurozone (Eurostat) and Japan (OECD). Output: 4-quadrant scatter, animated dot, regime badge, time scrubber from 2000.

---

## Phase 1 — Valuation Engine

**Architecture**: Single `CountrySelector` at top of Valuation tab auto-detects stock's listing country from Yahoo exchange code, fetches live 10Y government bond yield (FRED), applies Damodaran Jan 2026 ERP (store in `backend/data/damodaran_erp_2026.json`), computes WACC. All 8 models share these rates.

**8 Valuation Models** (each as an expandable card in a 2×4 grid):

1. **DCF (Two-Stage)** — 10-year FCF projection + terminal value. Heatmap + scenario table.
2. **DDM (Gordon Growth)** — `P₀ = D₁ / (r − g)`. Only render if `dividendRate > 0`, else grey locked card.
3. **Graham Formula** — `V* = EPS × (8.5 + 2g) × 4.4 / Y`. Y = live AAA yield from FRED series `AAA`. `g` is expressed as a whole number (e.g. 8 for 8% growth).
4. **Graham Number** — `√(22.5 × EPS × BVPS)`. Requires EPS > 0 and BVPS > 0. 22.5 = Graham's max P/E (15) × max P/B (1.5).
5. **Peter Lynch / PEG** — Fair value = `EPS × growth_rate`, where `growth_rate` is expressed as a whole number (e.g. 15 for 15%). Cap growth_rate at 20 to prevent unrealistic valuations. PEG = `(P/E) / growth_rate`. PEG verdict badge.
6. **EV/EBITDA Comps** — Sector median from live peers (FinanceDatabase) or fallback static `sector_multiples.json`. Not applicable for Financials sector.
7. **Residual Income (RIM)** — `Intrinsic Value = BVPS + PV(RI stream)`. Best for banks/REITs.
8. **EPV (Earnings Power Value)** — `EPV (firm) = Adjusted NOPAT / WACC`. To get per-share intrinsic value: `(EPV − net debt) / shares outstanding`. Net debt = total debt − cash. No-growth conservative floor.

**Axiom Fair Value** (Phase 1.9): Weighted composite of applicable models (DCF 30%, Comps 20%, RIM 15%, EPV 15%, Graham Formula 10%, Lynch 5%, DDM 5%). Verdict: Significantly Under/Modestly Under/Fair/Modestly Over/Significantly Overvalued. Display as gauge + needle at top of tab.

**Key files to create:**
- `backend/routes/valuation.py`
- `backend/services/valuation_engine.py`
- `backend/services/discount_rates.py`
- `backend/services/peer_fetcher.py`
- `backend/data/damodaran_erp_2026.json`
- `backend/data/sector_multiples.json`
- `frontend/app/markets/tabs/Valuation.tsx`
- `frontend/components/valuation/` (CountrySelector, CompositePanel, ValuationGauge, ModelCard, SensitivityHeatmap, ScenarioTable, WarningFlags)

---

## Phase 2 — Market Breadth & Dashboard

**2.1 Breadth Bar** — S&P 500 constituents from Wikipedia (`pandas.read_html`), cached weekly. Batch-download 1Y daily prices via `yf.download()` in chunks of 100. Compute: Advancing/Declining, New Highs/Lows, % Above SMA50, % Above SMA200, McClellan Oscillator. Display as 5 segmented bars, sticky at top of Markets page.

**McClellan Oscillator formula** — Use the ratio-adjusted version for comparability across different constituent counts:
- Ratio-Adjusted Net Advances (RANA) = `(Advances − Declines) / (Advances + Declines)`
- McClellan Oscillator = `19-day EMA of RANA − 39-day EMA of RANA`
- 19-day EMA multiplier = 0.10; 39-day EMA multiplier = 0.05

**2.2 Global Indices Table** — ~25 indices across Americas/Europe/Asia-Pacific via yfinance (e.g. `^GSPC`, `^GDAXI`, `^N225`). Show price, 1D%, 5-day sparkline, 1M%, YTD%. Region tabs, sortable columns.

**2.3 Fear & Greed Index** — 7 signals scored 0–100, averaged:
1. S&P 500 vs 125-day SMA (z-score normalised)
2. New 52W Highs vs Lows ratio
3. **McClellan Summation Index** (running cumulative sum of the ratio-adjusted McClellan Oscillator, percentile-ranked over 2Y lookback). Note: this is advance-decline breadth based, not volume-based.
4. Put/Call Ratio — primary source: SPY options chain from yfinance (`yf.Ticker("SPY").option_chain(nearest_expiry)`), aggregate put OI / call OI. Secondary/cross-check: FRED `CBOE/PUTCALL` if available. Inverted (high ratio = fear = low score).
5. VIX (`^VIX`, inverted percentile over 2Y lookback)
6. Stocks vs Bonds relative return (^GSPC vs TLT, 20-day rolling)
7. HY Credit Spread (FRED `BAMLH0A0HYM2`, inverted)

Verdicts: 0–20 Extreme Fear → 80–100 Extreme Greed. Speedometer gauge, 90-day history chart, 7 signal breakdown.

**2.4 Dashboard Page** — New route `/dashboard` as default landing page. Layout: Breadth Bar → 3-column header (Fear&Greed / Session status / Regime badge) → Global Indices Table → Yield Curve + Top Movers → Sector bars → Mini calendar strip.

**2.5 Top Movers** — From constituent cache: Top 5 Gainers, Losers, Unusual Volume (>2× avg), 52W Highs/Lows. Tabbed compact table on dashboard.

---

## Phase 3 — S&P 500 Treemap

Hierarchical JSON: S&P 500 → Sector → Industry → Stock. Rectangle area = log(market cap), colour = daily return % on red-white-green diverging scale (−5% deep red, 0% white, +5% deep green).

Rendering: `d3-hierarchy` squarified treemap for layout computation; React renders SVG rects. Hover tooltip (name, price, 1D%, mkt cap, P/E, 52W range). Click stock → navigate to Markets tab. Click sector → drill down.

Controls: Period selector (1D/1W/1M/3M/YTD/1Y), Index selector (S&P 500/Nasdaq 100/Dow 30), Group by (Sector/Industry), Colour by (Return/Mkt Cap/Volume).

Replace existing Sectors tab heatmap with treemap as primary view. Embed compact non-interactive version on Dashboard.

---

## Phase 4 — Economic Calendar

Route `/calendar`. Sub-tabs: Economic / Earnings / Dividends / IPO.

**Data sources:**
- **Macro events**: FRED release calendar + Finnhub `/calendar/economic`. Store central bank meeting dates in `backend/data/cb_meetings.json` (FOMC, ECB, BOE, BOJ etc.)
- **Earnings**: `yf.Ticker(t).calendar` for all S&P 500 tickers + Finnhub `/calendar/earnings`
- **Dividends**: `yf.Ticker(t).info[exDividendDate]` batch computed
- **IPO**: Finnhub `/calendar/ipo`

**UX**: Weekly grid Mon–Sun, today highlighted. Filter by impact (★★★/★★/★), country, category, timezone. Actual vs Consensus colouring (green = beat, red = miss). Countdown timers for events within 24h.

---

## Phase 5 — Screener Overhaul

**Problem**: Current screener requires manual ticker entry. Replace with universe-based approach.

**Universes**: S&P 500 (Wikipedia), Nasdaq 100 (Wikipedia), Dow 30 (static JSON), Russell 2000 proxy (FinanceDatabase, US mkt cap < $2B), Custom (manual).

**Pipeline**: At startup + weekly cron, scrape constituent list → batch-fetch all metrics from yfinance → cache in Parquet/SQLite. Refresh price metrics daily, fundamentals weekly.

**Preset Signal Pills** (horizontal scrollable row above filter builder):
- Price Action: Top Gainers, Biggest Losers, New 52W High/Low, Above/Below SMA200, Golden/Death Cross
- Volume: Unusual Volume (>2× avg), Overbought (RSI>70), Oversold (RSI<30), High Beta
- Fundamentals: Undervalued, High Dividend, High ROIC, Quality Growth, Deep Value
- Situations: Earnings This Week, Post-Earnings, Pre-Earnings Dip

**Result View Tabs**: Overview | Performance | Technicals | Valuation | Profitability | Dividends | Financials | Balance Sheet | All Columns. Every tab is sortable, CSV-exportable.

**Charts View**: Gallery of 200×120px sparkline thumbnails (last 3M daily closes + SMA50 overlay). Canvas-based rendering for performance.

---

## Phase 6 — Rolling Quantitative Metrics

Add "Rolling Metrics" section at bottom of existing Risk tab. Window selector: 20D / 60D (default) / 120D / 252D.

**Metrics** (time-series charts over 3Y history):
- Rolling Sharpe Ratio (annualised, using FRED DGS10 as risk-free rate)
- Rolling Volatility (stddev × √252)
- Rolling Beta (vs ^GSPC)
- Rolling Sortino Ratio (downside deviation only)
- Rolling Max Drawdown (filled area chart)
- Rolling Correlation (between selected ticker pairs)
- Rolling VaR 95% and 99%

Two views: Overlay (all tickers on one chart, metric selector) and Grid (2×3, one chart per metric).

---

## Phase 7 — Options Tab

New tab "Options" in Markets page.

**KPI Cards**: IV30 (ATM IV interpolated to 30 DTE), IV Rank (current vs 52W range), IV Percentile, Put/Call OI Ratio, Max Pain, Implied Earnings Move (straddle price / spot).

**IV Rank formula**: `(current_IV − min_IV_52w) / (max_IV_52w − min_IV_52w) × 100`

**Charts**: IV Term Structure (ATM IV vs DTE across all expiries, annotate earnings date) + IV Smile (IV vs moneyness 0.70–1.30 for selected expiry, with put/call skew KPI).

**Chain Table**: Classic calls | strikes | puts layout. ITM rows tinted. OTM-only toggle. Synced expiry selector.

**OI Profile Chart**: Horizontal bar chart, calls (green) right, puts (red) left, by strike. Max pain line annotated.

All data from `yf.Ticker(t).option_chain(expiry)`. Note: yfinance returns IV as a decimal (e.g. 0.34 = 34%) — multiply by 100 for display. Data delayed ~15min.

---

## Phase 8 — Macro Expansion

Reorganise Macro tab into sub-tabs: Overview | Rates & Yields | Inflation | Growth & Employment | Commodities | FX | Leading Indicators.

**Commodities** (Phase 8.1): ~25 commodities via yfinance continuous futures (CL=F, GC=F, HG=F, ZC=F etc.). Special charts: Dr. Copper vs World Bank GDP, Gold/Oil ratio with FRED recession shading (`USREC`), Axiom Commodity Index.

**Additional macro indicators** (Phase 8.2): Expand country coverage to G20+. Add Current Account (World Bank), Government Debt (IMF WEO), Central Bank Policy Rate tracker (all major CBs on one chart via FRED), OECD CLI multi-country, Yield curve spreads (2Y10Y, 3M10Y), Breakeven inflation (FRED `T5YIE`, `T10YIE`), Real yields (FRED `DFII10`).

**FX sub-tab**: DXY chart (`DX-Y.NYB`), currency heatmap (grid of crosses, 1D change %), EM FX emphasis.

**Rates & Yields sub-tab**: CB policy rates, yield curve spreads, TIPS/breakeven, real yields.

---

## Phase 9 — Snowflake Composite Score

Pentagon radar chart scored 0–10 per axis, **sector-normalised** (percentile rank within sector peers from Phase 5 cache):

1. **Value** — P/E, EV/EBITDA, FCF Yield, P/B, PEG vs sector medians
2. **Future Growth** — EPS growth estimate, revenue growth YoY, earnings momentum, R&D intensity
3. **Past Performance** — 3Y revenue CAGR, 3Y EPS CAGR, ROE avg, gross margin trend, price alpha vs sector
4. **Financial Health** — Altman Z-Score (safe >3.0, grey 1.8–3.0, distress <1.8), interest coverage, current ratio, net cash position, debt/equity
5. **Dividend** — Yield vs peers, payout ratio, 5Y dividend CAGR, consistency, FCF coverage. Score 0 if no dividend.

Scoring: raw metric → sector percentile rank → map to 0–10. Invert percentile for "lower = better" metrics (P/E, debt/equity etc.). Fallback to industry-wide → market-wide if <10 sector peers.

**Placement**: Primary on Overview tab (Snapshot section alongside price chart). Compact thumbnail in screener Charts view. Also shown in Valuation tab next to Axiom Fair Value.

**Additional**: Automated rules-based verdict text + top 3 Rewards (green ✓) and top 3 Risks (red ⚠) from sub-metric scores.

Rendering: `recharts RadarChart`. Click axis → navigate to relevant tab.

---

## Phase 10 — Sector Performance Charts

Replace/enhance Sectors tab. 11 SPDR sector ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLB, XLRE, XLC, XLU) from yfinance.

**Bar Charts**: 6 stacked horizontal bar charts (1D, 1W, 1M, 3M, YTD, 1Y). Sectors sorted by return per chart (independent). Reference dashed line at S&P 500 return for that period.

**Fundamentals Table**: Tabs — Overview / Valuation / Performance / Volatility. Computed from sector ETF prices + median of constituent fundamentals from Phase 5 cache.

**Industry Drill-Down**: Click sector → show industries within it (top-3 stocks by mkt cap per industry as proxy). Breadcrumb navigation. Deepest level → Screener table filtered to that industry.

**Sector Rotation Clock**: Circular diagram (Sam Stovall framework). 4 quadrants: Early/Mid/Late/Recession. Sectors placed in canonical quadrant, colour/size by recent relative performance vs S&P 500. Data-driven implied phase from 3M ETF returns. Cross-validate with Phase 0.3 Regime Clock.

---

## Data Source Quick Reference

| Source | Install | Key | Used For |
|---|---|---|---|
| yfinance | `pip install yfinance` | None | Prices, fundamentals, options, FX, commodities |
| FRED | `pip install fredapi` | Free key required | Macro series, yields, inflation, employment |
| Eurostat | `pip install eurostat` | None | EU GDP, HICP, unemployment |
| World Bank | `pip install wbdata` | None | Global GDP, debt, current account |
| OECD.Stat | HTTP requests | None | CLI, MEI, Japan macro |
| IMF WEO | Download Excel | None | 190-country forecasts, debt (update Apr/Oct) |
| Finnhub | `pip install finnhub-python` | Free key required | Earnings/IPO/Economic calendar |
| FinanceDatabase | `pip install financedatabase` | None | Universe construction, sector classification |
| Wikipedia | `pandas.read_html` | None | S&P 500, Nasdaq 100, Dow 30 constituent lists |
| Damodaran | Download Excel (annual) | None | Country ERP, sector multiples |

---

## Caching Strategy

| Frequency | What |
|---|---|
| Every 15min (market hours), daily (off-hours) | Index prices, FX, commodities, VIX, S&P 500 constituent prices |
| Daily (11pm UTC) | Screener metrics, Fear & Greed, breadth stats, movers, options chains, sector ETFs, rolling risk, Snowflake scores |
| Weekly | Constituent lists, sector/industry classification, earnings calendar |
| Monthly | OECD CLI, Eurostat, FRED monthly series, World Bank |
| Annually (Jan) | Damodaran ERP + multiples |
| Biannually (Apr/Oct) | IMF WEO |

Use `cachetools` for development, Redis for production. Cache key must include all relevant parameters (ticker, period, country). Expose `/api/admin/cache/clear` for manual invalidation.

---

## Notes for Claude Code
- Always implement safe `.get()` with fallbacks on `yf.Ticker(t).info` — fields can return `None`
- Use `yf.download()` for batch requests, never loop individual `Ticker()` calls for large universes
- Phase 9 (Snowflake) depends on Phase 5 universe cache — implement Phase 5 first
- For inapplicable valuation models, render a grey locked card with explanation — never hide it
- Sector normalisation in Phase 9 uses percentile rank within sector peers; invert percentile for "lower = better" metrics
- yfinance IV is always in decimal format (0.34 = 34%) — multiply by 100 before displaying
- Peter Lynch growth rate and Graham Formula `g` are whole numbers (15 = 15%), not decimals
- EPV produces a firm-level value — always subtract net debt and divide by shares outstanding for per-share output
- McClellan Oscillator: use ratio-adjusted net advances (RANA), not raw advances − declines
- All financial data should display its "as of" date
- Label all options data as "delayed ~15min"
