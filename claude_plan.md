# Axiom Finance — Claude Code Execution Plan

## Stack
- **Backend**: Python FastAPI
- **Frontend**: Next.js (TypeScript, React)
- **Data**: All free — yfinance (primary), FRED (fredapi), Eurostat, World Bank, OECD, IMF WEO, Finnhub (free tier), FinanceDatabase, Wikipedia scraping, CFTC, SEC EDGAR
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
8. **EPV (Earnings Power Value)** — `EPV (firm) = Adjusted NOPAT / WACC`. Per-share: `(EPV − net debt) / shares outstanding`. Net debt = total debt − cash. No-growth conservative floor.

**Axiom Fair Value** (Phase 1.9): Weighted composite of applicable models (DCF 30%, Comps 20%, RIM 15%, EPV 15%, Graham Formula 10%, Lynch 5%, DDM 5%). Verdict: Significantly Under/Modestly Under/Fair/Modestly Over/Significantly Overvalued. Display as gauge + needle at top of tab.

**Stock page KPI additions** (display alongside price/market cap):
- **EV/FCF** — Enterprise Value / TTM Free Cash Flow. Fetched from yfinance `Ticker.info` and `Ticker.cashflow`.
- **FCF Yield** — `(TTM FCF / shares outstanding) / current price`. Display as %.
- **Short Float %** — `yfinance Ticker.info["shortPercentOfFloat"]`. Display as % with colour: >20% red, 10–20% orange, <10% neutral.
- **Short Ratio** — `yfinance Ticker.info["shortRatio"]` (days to cover).
- **Earnings Revision** — Direction of analyst EPS estimate changes over last 30/60/90 days from `yfinance Ticker.earnings_forecasts`. Show as ↑ / ↓ / ↔ badge with magnitude.
- **ROIC** — `NOPAT / (total equity + total debt − cash)`. NOPAT = EBIT × (1 − effective tax rate). From `Ticker.financials` and `Ticker.balance_sheet`.

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

**2.1 Breadth Bar** — S&P 500 constituents from Wikipedia (`pandas.read_html`), cached weekly. Batch-download 1Y daily prices via `yf.download()` in chunks of 100. Compute: Advancing/Declining, New Highs/Lows, % Above SMA50, % Above SMA200, McClellan Oscillator, Cumulative A/D Line. Display as segmented bars, sticky at top of Markets page.

**McClellan Oscillator formula** — Use the ratio-adjusted version:
- Ratio-Adjusted Net Advances (RANA) = `(Advances − Declines) / (Advances + Declines)`
- McClellan Oscillator = `19-day EMA of RANA − 39-day EMA of RANA`
- 19-day EMA multiplier = 0.10; 39-day EMA multiplier = 0.05

**Cumulative A/D Line** — Running cumulative sum of daily (Advances − Declines) going back 3 years. Plot as a time-series chart overlaid with the S&P 500 price. Divergence (index makes new high but A/D line does not confirm) is a classic warning signal. Compute from existing constituent price cache, no additional data needed.

**2.2 Global Indices Table** — ~25 indices across Americas/Europe/Asia-Pacific via yfinance (e.g. `^GSPC`, `^GDAXI`, `^N225`). Show price, 1D%, 5-day sparkline, 1M%, YTD%. Region tabs, sortable columns.

**2.3 Fear & Greed Index** — 8 signals scored 0–100, averaged:
1. S&P 500 vs 125-day SMA (z-score normalised)
2. New 52W Highs vs Lows ratio
3. **McClellan Summation Index** (cumulative sum of ratio-adjusted McClellan Oscillator, percentile-ranked over 2Y lookback)
4. Put/Call Ratio — primary: SPY options chain from yfinance (`yf.Ticker("SPY").option_chain(nearest_expiry)`), aggregate put OI / call OI. Secondary: FRED `CBOE/PUTCALL` if available. Inverted.
5. VIX (`^VIX`, inverted percentile over 2Y lookback)
6. Stocks vs Bonds relative return (^GSPC vs TLT, 20-day rolling)
7. HY Credit Spread (FRED `BAMLH0A0HYM2`, inverted)
8. **AAII Sentiment** — Weekly retail investor survey (% bullish − % bearish), scraped from `aaii.com/sentiment-survey/data` (CSV download link, no auth required). Normalise bullish–bearish spread to 0–100 percentile over 2Y. Classic contrarian signal: extreme retail bullishness = fear score low.

Verdicts: 0–20 Extreme Fear → 80–100 Extreme Greed. Speedometer gauge, 90-day history chart, signal breakdown panel.

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

**High-impact events to always include** (hardcode as impact=3 in `event_impact.json`):
- US: NFP, CPI, Core PCE, GDP advance, Retail Sales, FOMC Decision, ISM PMI, Weekly Jobless Claims (FRED `ICSA`, every Thursday — most frequent US labour signal)
- EU: ECB Rate Decision, Eurozone CPI Flash, Eurozone GDP
- UK: BOE Decision, UK CPI, UK GDP
- JP: BOJ Decision, Japan CPI

---

## Phase 5 — Screener Overhaul

**Problem**: Current screener requires manual ticker entry. Replace with universe-based approach.

**Universes**: S&P 500 (Wikipedia), Nasdaq 100 (Wikipedia), Dow 30 (static JSON), Russell 2000 proxy (FinanceDatabase, US mkt cap < $2B), Custom (manual).

**Pipeline**: At startup + weekly cron, scrape constituent list → batch-fetch all metrics from yfinance → cache in Parquet/SQLite. Refresh price metrics daily, fundamentals weekly.

**Screener columns to include** (in addition to standard P/E, P/B, EV/EBITDA etc.):
- Short Float % — `yfinance Ticker.info["shortPercentOfFloat"]`
- Short Ratio (days to cover) — `yfinance Ticker.info["shortRatio"]`
- ROIC — computed: `NOPAT / invested_capital` (see Phase 1 definition)
- FCF Yield — computed: `(TTM FCF / shares) / price`
- EV/FCF — computed from `Ticker.info` and `Ticker.cashflow`
- Earnings Revision 30D — from `Ticker.earnings_forecasts`

**Preset Signal Pills** (horizontal scrollable row above filter builder):
- Price Action: Top Gainers, Biggest Losers, New 52W High/Low, Above/Below SMA200, Golden/Death Cross
- Volume: Unusual Volume (>2× avg), Overbought (RSI>70), Oversold (RSI<30), High Beta
- Fundamentals: Undervalued, High Dividend, High ROIC, Quality Growth, Deep Value, High Short Interest (>20% float)
- Situations: Earnings This Week, Post-Earnings, Pre-Earnings Dip, Insider Buying (recent Form 4 buys)

**Result View Tabs**: Overview | Performance | Technicals | Valuation | Profitability | Dividends | Financials | Balance Sheet | All Columns. Every tab is sortable, CSV-exportable.

**Charts View**: Gallery of 200×120px sparkline thumbnails (last 3M daily closes + SMA50 overlay). Canvas-based rendering for performance.

---

## Phase 6 — Rolling Quantitative Metrics

Add "Rolling Metrics" section at bottom of existing Risk tab. Window selector: 20D / 60D (default) / 120D / 252D.

**Metrics** (time-series charts over 3Y history):
- Rolling Sharpe Ratio (annualised, using FRED `DGS10` as risk-free rate)
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

Reorganise Macro tab into sub-tabs: Overview | Rates & Yields | Inflation | Growth & Employment | Commodities | FX | Leading Indicators | Positioning.

**Commodities** (Phase 8.1): ~25 commodities via yfinance continuous futures (CL=F, GC=F, HG=F, ZC=F etc.). Special charts: Dr. Copper vs World Bank GDP, Gold/Oil ratio with FRED recession shading (`USREC`), Axiom Commodity Index.

**Rates & Yields sub-tab**:
- CB policy rates, yield curve spreads (2Y10Y, 3M10Y)
- TIPS/breakeven inflation (FRED `T5YIE`, `T10YIE`)
- Real yields (FRED `DFII10`)
- **SOFR** (FRED `SOFR`) — the LIBOR replacement, benchmark overnight rate. Chart vs Fed Funds Rate.
- **IG Credit Spread** (FRED `BAMLC0A0CM`) — Investment Grade OAS. Chart alongside HY spread (`BAMLH0A0HYM2`) for full credit risk spectrum view.
- **TED Spread** — proxy: 3-month T-bill (FRED `DTB3`) minus SOFR. Stress indicator; spikes signal interbank funding pressure.
- **Corporate bond yield by rating tier** — FRED BofA series: AAA (`BAMLC0A1CAAA`), AA (`BAMLC0A2CAA`), A (`BAMLC0A3CA`), BBB (`BAMLC0A4CBBB`), BB (`BAMLH0A1HYBB`), B (`BAMLH0A2HYB`). Plot all on one chart to show the full risk spectrum.

**Growth & Employment sub-tab**:
- Existing: GDP, unemployment rate, NFP
- **Weekly Initial Jobless Claims** (FRED `ICSA`) — most frequent US labour market data point. Chart with 4-week moving average overlay and recession shading.
- **Continuing Claims** (FRED `CCSA`) — lagging but confirms trend.
- **M2 Money Supply** (FRED `M2SL`) — YoY growth rate chart. Overlay with CPI to show liquidity-inflation relationship.
- **Sahm Rule Real-Time Indicator** (FRED `SAHMREALTIME`) — Recession trigger: fires when 3-month avg unemployment rate rises ≥0.5pp above prior 12-month low. Show current value, threshold line at 0.50, and historical trigger dates highlighted.

**Inflation sub-tab** additions:
- **PCE Deflator** (FRED `PCEPI`) and Core PCE (FRED `PCEPILFE`) — the Fed’s preferred inflation measure, separate from CPI.
- **PPI** (FRED `PPIACO`) — Producer Price Index as a leading inflation indicator.
- **5Y5Y Forward Inflation Expectation** (FRED `T5YIFR`) — market-implied long-run inflation expectations.

**Leading Indicators sub-tab** (new):
- **Conference Board LEI** (FRED `USSLIND`) — composite leading index. Chart with recession shading; flag when YoY change turns negative.
- **OECD CLI** — multi-country composite leading indicator via OECD.Stat API. Show G7 + major EMs.
- **Global Supply Chain Pressure Index (GSCPI)** — published monthly by the New York Fed. Download free CSV from `https://www.newyorkfed.org/research/policy/gscpi`. Values above 0 = above-average pressure. Chart with COVID spike annotated.
- **Chicago Fed National Activity Index (CFNAI)** (FRED `CFNAI`) — broad monthly activity composite. Values below −0.7 historically associated with recession.
- **ISM PMI** (Manufacturing `MANEMP` proxy + Services) — already in calendar, also chart here as time series with 50-line threshold.

**FX sub-tab**: DXY chart (`DX-Y.NYB`), currency heatmap, EM FX emphasis.

**Positioning sub-tab** (new — institutional flow data, all free):

**COT Report (Commitment of Traders)**
- Source: CFTC publishes every Friday at `https://www.cftc.gov/dcom/files/dcotnoc.zip` (legacy format) or use `https://www.quandl.com` proxy if available. Direct CFTC CSV download is free, no key required.
- Parse the "Disaggregated" or "Legacy" COT report for key futures markets: S&P 500 E-mini (CME), Nasdaq 100 E-mini, EUR/USD, GBP/USD, Gold, WTI Crude, 10Y Treasury Note.
- For each contract show: net positioning of Commercial Hedgers, Large Speculators (non-commercial), and Small Speculators over time as a stacked area or bar chart.
- Also compute and display **COT Index** = `(current_net − min_52w) / (max_52w − min_52w) × 100` as a sentiment gauge. Extreme speculators long (COT Index >80%) = contrarian bearish signal.

**SEC Form 4 Insider Trades**
- Source: SEC EDGAR full-text search API (free, no key): `https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt=DATE&enddt=DATE&forms=4`
- For individual stock pages: show last 12 months of insider buys and sells (officer/director transactions only, filter out automatic RSU vesting by checking transaction code — use codes `P` = open market purchase, `S` = open market sale).
- Display as a timeline chart (buy = green arrow up, sell = red arrow down) overlaid on the price chart.
- Aggregate metric: Insider Buy/Sell ratio over last 90 days. Ratio >2.0 = strong insider conviction signal.
- For the screener: add "Insider Buying" preset filter (Form 4 code P transactions in last 30 days).

**SEC 13F Institutional Holdings**
- Source: SEC EDGAR company search API (free): `https://data.sec.gov/submissions/CIK{cik}.json` and `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
- 13F filings are quarterly (45-day lag after quarter end). Parse to extract top holders, total shares held, QoQ change in holdings.
- For individual stock pages: show top 10 institutional holders with QoQ change (new position / increased / decreased / sold out).
- Display as a table: fund name | shares held | % of float | QoQ change | filing date.
- Note: 13F data has a 45-day reporting lag — label accordingly.

**NYSE Margin Debt**
- Source: FINRA publishes monthly margin statistics free at `https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics` (downloadable CSV).
- Chart total margin debt over time with S&P 500 overlaid (dual axis). YoY rate of change is the key signal — sharp declines in margin debt historically precede or coincide with bear markets.
- Show on the Positioning sub-tab and as a macro overlay option on the Dashboard.

---

## Phase 9 — Snowflake Composite Score

Pentagon radar chart scored 0–10 per axis, **sector-normalised** (percentile rank within sector peers from Phase 5 cache):

1. **Value** — P/E, EV/EBITDA, EV/FCF, FCF Yield, P/B, PEG vs sector medians
2. **Future Growth** — EPS growth estimate, revenue growth YoY, earnings revision momentum (30D), R&D intensity
3. **Past Performance** — 3Y revenue CAGR, 3Y EPS CAGR, ROE avg, gross margin trend, price alpha vs sector
4. **Financial Health** — Altman Z-Score (safe >3.0, grey 1.8–3.0, distress <1.8), ROIC vs WACC spread, interest coverage, current ratio, net cash position, debt/equity
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

| Source | Install / Access | Key | Used For |
|---|---|---|---|
| yfinance | `pip install yfinance` | None | Prices, fundamentals, options, FX, commodities, short interest |
| FRED | `pip install fredapi` | Free key required | Macro series, yields, inflation, employment, credit spreads |
| Eurostat | `pip install eurostat` | None | EU GDP, HICP, unemployment |
| World Bank | `pip install wbdata` | None | Global GDP, debt, current account |
| OECD.Stat | HTTP requests | None | CLI, MEI, Japan macro |
| IMF WEO | Download Excel | None | 190-country forecasts, debt (update Apr/Oct) |
| Finnhub | `pip install finnhub-python` | Free key required | Earnings/IPO/Economic calendar |
| FinanceDatabase | `pip install financedatabase` | None | Universe construction, sector classification |
| Wikipedia | `pandas.read_html` | None | S&P 500, Nasdaq 100, Dow 30 constituent lists |
| Damodaran | Download Excel (annual) | None | Country ERP, sector multiples |
| CFTC | Direct CSV download (`cftc.gov`) | None | COT positioning data |
| SEC EDGAR | `https://data.sec.gov` REST API | None | 13F institutional holdings, Form 4 insider trades |
| NY Fed | Direct CSV download | None | GSCPI (supply chain pressure) |
| FINRA | Direct CSV download (`finra.org`) | None | NYSE margin debt |
| AAII | Direct CSV download (`aaii.com`) | None | Weekly retail investor sentiment |

---

## Caching Strategy

| Frequency | What |
|---|---|
| Every 15min (market hours), daily (off-hours) | Index prices, FX, commodities, VIX, S&P 500 constituent prices |
| Daily (11pm UTC) | Screener metrics, Fear & Greed (incl. AAII), breadth stats + cumulative A/D, movers, options chains, sector ETFs, rolling risk, Snowflake scores |
| Weekly (Friday after 6pm ET) | COT report (CFTC releases Fridays), constituent lists, sector/industry classification, earnings calendar |
| Weekly (Thursday) | AAII sentiment survey (published Thursdays), initial jobless claims |
| Monthly | OECD CLI, Eurostat, FRED monthly series, World Bank, GSCPI (NY Fed), margin debt (FINRA), M2, LEI, CFNAI |
| Quarterly | 13F institutional holdings (SEC EDGAR, 45-day lag) |
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
- COT data: use transaction codes P (open market buy) and S (open market sell) for Form 4; exclude RSU vesting (code A)
- EDGAR 13F and Form 4 endpoints are unauthenticated REST — respect rate limits with `time.sleep(0.1)` between calls
- GSCPI CSV URL may change — implement a fallback to parse the NY Fed page if direct link fails
- Sahm Rule threshold is exactly 0.50 — shade background red when `SAHMREALTIME ≥ 0.50`
- All financial data should display its "as of" date
- Label all options data as "delayed ~15min"
- Label all 13F holdings data as "as of [quarter end], filed [date] (45-day lag)"
