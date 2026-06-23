# Axiom Finance — Build Plan

## Project Context
Full-stack financial analytics platform. **Backend**: Python FastAPI. **Frontend**: Next.js (TypeScript/React). **Cost**: $0 — free APIs, pip libraries, or direct structured file downloads only (CSV/Excel/ZIP from stable government/institutional URLs). No paid APIs, no HTML scraping, no BeautifulSoup/Selenium.

---

## Core Constraints (Always Enforce)

- **Data sources**: yfinance, FRED (fredapi), Eurostat, World Bank, OECD, IMF WEO, Finnhub (free tier), FinanceDatabase, Wikipedia MediaWiki API, CFTC ZIP, SEC EDGAR (edgartools), NY Fed Excel, Ken French CSV, Damodaran Excel.
- **Index constituents**: Wikipedia MediaWiki Action API (`action=parse&prop=wikitext`) + `wikitextparser`. Never HTML scrape.
- **Compute tiers** — enforce on every feature:
  - 🟢 **Default**: runs on page load and nightly cron.
  - 🟡 **On-demand**: greyed panel with "Calculate" button; never in cron.
  - 🔴 **User-triggered**: locked panel with "Run Analysis" button + warning "This calculation is compute-intensive and may take 15–60 seconds." Never on page load or in cron.
- **UI layout** — every section must have: (1) 3–6 key indicator KPIs always visible at top, (2) full extended metrics list below. Repetition across tiers is intentional.
- **yfinance safety**: always `.get()` with fallbacks — any `Ticker.info` field can be `None`. Use `yf.download()` for batch prices; never loop `Ticker()` for large universes.
- **Display rules**: yfinance IV is decimal → multiply ×100. Options data labelled "delayed ~15min". Eurozone/Japan macro labelled "as of [latest available period]". 13F labelled "45-day reporting lag". All data shows "as of" date.
- **Small-cap label**: "Small-Cap Universe (~3,000–5,000 tickers)" — never "Russell 2000".
- **Caching**: `cachetools` in dev, Redis in prod. Cache key includes all params.

---

## Caching Schedule

| Frequency | Data |
|---|---|
| 15min (market hours) / hourly (off) | Prices, FX, commodities, VIX, constituent prices |
| Daily 11pm UTC | Screener metrics, Fear & Greed, breadth, movers, options chains, sector ETFs, rolling risk, Snowflake scores |
| Weekly Fri 6pm ET | COT (CFTC), earnings calendar, constituent lists |
| Weekly Thu | Initial jobless claims (`ICSA`) |
| Monthly | OECD CLI, Eurostat, FRED monthly series, World Bank, GSCPI, M2, LEI, CFNAI, housing |
| Quarterly | 13F holdings |
| Annually (Jan) | Damodaran ERP + multiples, Ken French factor data |
| Biannually (Apr/Oct) | IMF WEO |

---

## Phase Map

| Phase | Feature | Priority |
|---|---|---|
| 0 | Critical Bug Fixes | Immediate |
| 1 | Valuation Engine | High |
| 2 | Market Breadth & Dashboard | High |
| 3 | S&P 500 Treemap | High |
| 4 | Economic Calendar | Medium |
| 5 | Screener Overhaul | Medium |
| 6 | Risk & Rolling Metrics | Medium |
| 7 | Options & IV Module | Medium |
| 8 | Macro Expansion | Medium |
| 9 | Snowflake Composite Score | Low |
| 10 | Sector Performance Charts | Low |
| 11 | Portfolio Analytics | Low |
| 12 | Advanced Technicals | Low |

> **Dependency**: Phase 9 (Snowflake) and Phase 11 🔴 features require Phase 5 cache.

---

## Phase 0 — Bug Fixes

**Goal**: Fix three broken panels before any new development.

- **0.1 DCF panel**: Two-stage DCF with slider inputs. Output intrinsic value, Bear/Base/Bull table, 7×7 sensitivity heatmap (FCF Growth vs WACC). Data: TTM FCF + shares from yfinance.
- **0.2 FX Rates panel**: 15+ pairs via yfinance (`EURUSD=X`). Show rate, 1D/1W/1M/1Y change%, 30-day sparkline, base currency switcher.
- **0.3 Regime Classifier**: 2×2 Goldilocks matrix (FRED `GDPC1` × `CPIAUCSL`). Eurozone via Eurostat, Japan via OECD. 4-quadrant scatter with animated dot, time scrubber from 2000.

---

## Phase 1 — Valuation Engine

**Goal**: Compute and display 8 valuation models per stock, a weighted composite fair value, and full fundamental data.

**Architecture**: `CountrySelector` detects listing country from Yahoo exchange code → fetches 10Y gov bond yield (FRED) → applies Damodaran 2026 ERP (`damodaran_erp_2026.json`) → computes WACC shared across all models.

**Key files**: `backend/routes/valuation.py`, `backend/services/valuation_engine.py`, `backend/services/discount_rates.py`, `backend/data/damodaran_erp_2026.json`, `backend/data/sector_multiples.json`

### Stock KPIs 🟢
Top row: Price, Market Cap, P/E (TTM), Forward P/E, EPS (TTM), Dividend Yield, 52W High/Low, Beta, Avg Volume.

### Extended Fundamentals 🟢
EV/FCF, FCF Yield, Short Float% (>20% red, 10–20% orange), Short Ratio, Earnings Revision (↑/↓/↔ badge vs 30/60/90d ago — requires yfinance ≥0.2.28, guard with `hasattr`), ROIC, CAPM Required Return, Cash Conversion Cycle, DuPont (3-factor + 5-factor waterfall), Piotroski F-Score (9-point), Beneish M-Score, Ohlson O-Score, ESG Scores. Short data: US-listed only.

### Analyst Data 🟢
Price target band (mean/high/low + upside%), consensus rating bar (12-month history), earnings surprise history (8 quarters), forward estimates table, growth estimates vs sector/S&P.

### 8 Valuation Models (2×4 grid) 🟢
1. **DCF (Two-Stage)** — 10Y FCF + terminal value. Heatmap + scenario table.
2. **DDM (Gordon Growth)** — `P₀ = D₁ / (r − g)`. Locked if `dividendRate = 0`.
3. **Graham Formula** — `V* = EPS × (8.5 + 2g) × 4.4 / Y`. Y = FRED `AAA`. `g` is a whole number.
4. **Graham Number** — `√(22.5 × EPS × BVPS)`. Requires EPS > 0 and BVPS > 0.
5. **Peter Lynch / PEG** — Fair value = `EPS × growth_rate` (whole number, cap 20).
6. **EV/EBITDA Comps** — `sector_multiples.json`. Not for Financials sector.
7. **Residual Income (RIM)** — `BVPS + PV(RI stream)`. Lock if ROE unavailable.
8. **EPV** — `Adjusted NOPAT / WACC` → subtract net debt → divide by shares.

Inapplicable models → grey locked card with explanation, never hidden.

### Additional Models
- **CAPM Implied Fair Value** 🟢 — back out price implied by CAPM vs forward EPS.
- **Fama-French 3-Factor** 🟡 — factor data from Ken French Library (direct CSV: `http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip`).
- **Fama-French 5-Factor** 🟡 — extends 3F with RMW + CMA.

**Axiom Fair Value**: weighted composite (DCF 30%, Comps 20%, RIM 15%, EPV 15%, Graham Formula 10%, Lynch 5%, DDM 5%). Gauge + needle + verdict (Significantly Under → Significantly Overvalued).

---

## Phase 2 — Market Breadth & Dashboard

**Goal**: Build a breadth bar, global indices table, Fear & Greed Index, and a unified dashboard landing page.

- **Breadth Bar** 🟢: S&P 500 constituents via Wikipedia API, cached weekly. Advancing/Declining, New Highs/Lows, % Above SMA50/200, McClellan Oscillator (use RANA = `(A−D)/(A+D)`, then 19/39-day EMA diff), Cumulative A/D Line. Sticky top of Markets page.
- **Global Indices** 🟢: ~25 indices via yfinance. Price, 1D%, 5-day sparkline, 1M%, YTD%. Region tabs.
- **Fear & Greed Index** 🟢: 7 signals scored 0–100 (S&P 500 vs 125-day SMA z-score, New Highs/Lows ratio, McClellan Summation Index 2Y percentile, Put/Call OI ratio inverted, VIX 2Y percentile inverted, Stocks vs Bonds 20-day return, HY Credit Spread `BAMLH0A0HYM2` inverted). Speedometer gauge + 90-day history + signal breakdown.
- **Top Movers** 🟢: Gainers, Losers, Unusual Volume (>2× avg), 52W Highs/Lows from constituent cache.
- **Dashboard** (`/dashboard`): Breadth Bar → Fear&Greed/Regime badge/Session status → Global Indices → Yield Curve + Top Movers → Sector bars → Mini calendar strip.

---

## Phase 3 — S&P 500 Treemap

**Goal**: Interactive S&P 500 treemap with sector/industry/stock drill-down.

Area = log(market cap). Colour = return% (−5% deep red, 0% white, +5% deep green). `d3-hierarchy` squarified layout. Hover: name, price, 1D%, market cap, P/E, 52W range. Controls: period, index (S&P/NDX/Dow), group by, colour by. Constituent list via Wikipedia MediaWiki API.

---

## Phase 4 — Economic Calendar

**Goal**: A unified calendar at `/calendar` covering macro events, earnings, dividends, and IPOs.

- **Macro**: Finnhub `/calendar/economic` + FRED release calendar. CB meeting dates from `backend/data/cb_meetings.json` (updated 2× per year).
- **Earnings**: `yf.Ticker(t).calendar` + Finnhub `/calendar/earnings`. Overnight cron with `ThreadPoolExecutor(max_workers=10)`.
- **Dividends**: `Ticker.info["exDividendDate"]` batch in same cron.
- **IPO**: Finnhub `/calendar/ipo`.

Weekly grid, today highlighted. Filter by impact (★★★), country, timezone. Beat/miss colouring. Countdown timers within 24h.

---

## Phase 5 — Screener Overhaul

**Goal**: A high-performance stock screener with preset signals, multi-column views, and a sparkline charts view.

**Universes**: S&P 500 / Nasdaq 100 / Dow 30 (Wikipedia API, weekly cache), Small-Cap Universe (~3,000–5,000 tickers via FinanceDatabase), Custom.

**Pipeline**: Overnight cron → Wikipedia API → yfinance batch fundamentals → Parquet/SQLite cache. `ThreadPoolExecutor(max_workers=10)`.

**Default columns** 🟢: Ticker, Name, Price, 1D%, Market Cap, P/E, Forward P/E, EPS, Dividend Yield, Beta, Volume, Sector.

**Extended columns** 🟢: P/B, EV/EBITDA, EV/FCF, FCF Yield, ROIC, Short Float%, Short Ratio, Gross/Net Margin, ROE, ROA, D/E, Current Ratio, Revenue/EPS Growth YoY, Earnings Revision 30D, Piotroski F-Score, Altman Z-Score, ESG Score.

**Preset signal pills**: Top Gainers/Losers, 52W High/Low, Above/Below SMA200, Golden/Death Cross, Unusual Volume, Overbought/Oversold (RSI), High Beta, Undervalued, High Dividend, High ROIC, Quality Growth, Deep Value, High Short Interest (>20%), Earnings This Week, Post/Pre-Earnings Dip, Insider Buying (Form 4 code-P last 30 days — `time.sleep(0.15)` between EDGAR calls), Activist Target (SC 13D last 90 days).

**Result tabs**: Overview | Performance | Technicals | Valuation | Profitability | Dividends | Financials | Balance Sheet | All Columns. Sortable, CSV-exportable.

**Charts view**: 200×120px sparkline gallery (3M closes + SMA50), canvas-based.

---

## Phase 6 — Risk & Rolling Metrics

**Goal**: Provide a comprehensive risk dashboard per stock with rolling metrics, advanced risk ratios, and compute-gated tail risk models.

**Top KPIs** 🟢: Beta, 30-day Realised Volatility (annualised), Max Drawdown (3Y), Sharpe Ratio (1Y), VaR 95% (1-day parametric).

**Rolling metrics** 🟢 (windows: 20D/60D/120D/252D, 3Y history): Sharpe (Rf = FRED `DGS10`), Volatility (stddev × √252), Beta vs `^GSPC`, Sortino, Max Drawdown (filled area), Pairwise Correlation, VaR 95% and 99% parametric.

**Extended risk metrics** 🟢: CVaR/Expected Shortfall, Historical VaR, Calmar Ratio, Omega Ratio, Treynor Ratio, Jensen's Alpha, CAPM decomposition (systematic vs idiosyncratic variance).

**On-demand** 🟡: Hurst Exponent (~2s), Ornstein-Uhlenbeck Fit via MLE (~2s/pair), GARCH(1,1) via `arch` library (`arch_model(returns, vol='Garch', p=1, q=1)`, ~3s), Pairs Cointegration (Engle-Granger or Johansen, ~3s/pair).

**User-triggered** 🔴: Monte Carlo VaR (10,000 GBM simulations), Stress Testing (2008 GFC / 2020 COVID / 2022 rate shock / 2000 dot-com — replay actual return sequences).

Two views: Overlay (all tickers, metric selector) and Grid (2×3).

---

## Phase 7 — Options & IV Module

**Goal**: Options chain with IV analytics, Greeks, and pricing models per stock.

**Top KPIs** 🟢: IV30 (linear interpolation between expiries bracketing 30 DTE; fallback: nearest expiry ATM IV, labelled "nearest expiry IV"), IV Rank (`(current − min_52w) / (max_52w − min_52w) × 100`), IV Percentile, Put/Call OI Ratio, Max Pain, Implied Earnings Move.

**Models** 🟢: Black-Scholes (closed-form via `scipy.stats.norm`; Greeks Δ, Γ, Θ, V, ρ; IV backsolve via `scipy.optimize.brentq`; display BS theoretical vs market price). Binomial Tree (100-step CRR, American-style — on-demand per row).

**Charts**: IV Term Structure (ATM IV vs DTE, annotate earnings date), IV Smile (IV vs moneyness 0.70–1.30), OI Profile (horizontal bar, calls right / puts left, max pain line).

**Chain table**: Calls | Strikes | Puts. ITM rows tinted. OTM-only toggle. Synced expiry selector. IV is decimal — multiply ×100. Labelled "delayed ~15min".

**User-triggered** 🔴: Monte Carlo Options Pricing (10,000 GBM paths per option, distribution of terminal prices + percentile payoff chart).

---

## Phase 8 — Macro Expansion

**Goal**: Build a full macro intelligence hub with sub-tabs for each domain, each following the key-indicators-top / full-chart-below layout rule.

Sub-tabs: Overview | Rates & Yields | Inflation | Growth & Employment | Housing | Commodities | FX | Leading Indicators | Financial Conditions | Positioning.

### Rates & Yields
**Top** 🟢: Fed Funds Rate (`FEDFUNDS`), 10Y (`DGS10`), 2Y (`DGS2`), 2Y10Y spread, 30Y mortgage (`MORTGAGE30US`).
**Full**: Yield curve (3M–30Y), 3M10Y spread, TIPS breakeven 5Y/10Y (`T5YIE`/`T10YIE`), real yields (`DFII10`), SOFR vs Fed Funds, IG/HY spreads, TED spread proxy, corporate bond yields (AAA→B, FRED BofA series).
**Taylor Rule** 🟢: `r = r* + π + 0.5(π − π*) + 0.5(Y − Y*)`. r*=0.5%, π*=2%, output gap = `(GDPC1 − GDPPOT) / GDPPOT × 100`. Chart implied vs actual `FEDFUNDS`.
**ACM Yield Curve Decomposition** 🟢: NY Fed Excel (`https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr340.xls`). Decompose 10Y into expectations component vs term premium.

### Inflation
**Top** 🟢: CPI YoY, Core CPI YoY, PCE YoY, Core PCE YoY, 5Y Breakeven.
**Full**: PPI, 5Y5Y Forward Inflation, 10Y Breakeven, M2 YoY overlaid with CPI.
**Quantity Theory** 🟢: MV=PQ. Plot M2 growth vs nominal GDP growth. Chart velocity of money V = nominal GDP / M2.

### Growth & Employment
**Top** 🟢: Real GDP YoY, Unemployment Rate, NFP MoM, Initial Jobless Claims, Labour Participation Rate.
**Full**: Continuing Claims, AHE YoY, JOLTS Openings/Quit Rate, Sahm Rule (shade red ≥ 0.50), Industrial Production, Capacity Utilization, Trade Balance.

### Housing
**Top** 🟢: Case-Shiller HPI YoY, Housing Starts, 30Y Mortgage Rate, Existing Home Sales. Chart all four with recession shading.

### Commodities
**Top** 🟢: WTI (CL=F), Gold (GC=F), Natural Gas (NG=F), Copper (HG=F), Wheat (ZW=F).
**Full**: ~25 futures via yfinance. Dr. Copper vs World Bank GDP, Gold/Oil ratio with `USREC` shading, Axiom Commodity Index (equal-weighted). Bitcoin (`CBBTCUSD` from FRED).

### FX
**Top** 🟢: DXY, EUR/USD, USD/JPY, GBP/USD, USD/CNY.
**Full**: Currency heatmap (grid of crosses, 1D change%), EM FX emphasis.
**PPP** 🟢: For G10 pairs: PPP rate = (domestic CPI / foreign CPI) × base rate. Plot PPP vs spot. Over/undervaluation % badge.

### Leading Indicators
**Top** 🟢: Conference Board LEI (`USSLIND`) YoY, OECD CLI (G7), CFNAI, ISM PMI (Finnhub; FRED `NAPM` for history through 2023).
**Full**: GSCPI (NY Fed Excel: `https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx` — if 404 log + serve cached).
**IS-LM-PC Model** 🟢: Interactive 3-panel chart (IS curve from GDP+FEDFUNDS, LM curve from M2+nominal GDP, Phillips Curve from `UNRATE`+`CPIAUCSL` with current position dot + 10Y trail).

### Financial Conditions
**Top** 🟢: NFCI (`NFCI`), STLFSI4 (`STLFSI4`), Fed Balance Sheet (`WALCL`).
**Full**: Credit card delinquency (`DRCCLACBS`), consumer loan delinquency, C&I loans (`TOTCI`), Economic Policy Uncertainty (`USEPUINDXD`).

### Positioning
- **COT Report**: CFTC ZIP (`https://www.cftc.gov/dcom/files/dcotnoc.zip`). Parse with `pandas.read_csv(skipinitialspace=True)` + `.strip()` all columns. Key contracts: S&P E-mini (13874+), NDX E-mini (209742), EUR/USD (099741), Gold (088691), WTI (067651), 10Y Note (043602). COT Index = `(net_spec − min_52w) / (max_52w − min_52w) × 100`.
- **SEC Form 4**: EDGAR REST API (`https://efts.sec.gov/LATEST/search-index?q="{ticker}"&forms=4`). Code P = buy, S = sell, A = award (exclude). `time.sleep(0.15)`.
- **13F Holdings**: `edgartools`. Top 10 holders, QoQ change, labelled "45-day reporting lag". `time.sleep(0.1)`.
- **SC 13D/G**: `edgartools`. >5% accumulation → "Activist Watch" badge on stock page.
- **DEF 14A**: `edgartools`. CEO total comp + pay ratio on stock fundamentals panel.
- **8-K Events**: `edgartools`. Earnings, M&A, leadership changes. Timeline on stock page.

---

## Phase 9 — Snowflake Composite Score

**Goal**: A pentagon radar chart scoring each stock 0–10 per axis, sector-normalised (percentile rank within sector peers).

**5 axes** 🟢: Value (P/E, EV/EBITDA, EV/FCF, FCF Yield, P/B, PEG), Future Growth (EPS/revenue growth estimates, earnings revision, R&D intensity), Past Performance (3Y revenue/EPS CAGR, ROE avg, gross margin trend, price alpha vs sector), Financial Health (Altman Z, Piotroski, Ohlson, Beneish flag, ROIC−WACC spread, interest coverage, current ratio, net cash, D/E), Dividend (yield vs peers, payout ratio, 5Y CAGR, consistency, FCF coverage — score 0 if no dividend).

Invert percentile for lower-is-better metrics. Fallback to industry → market-wide if <10 sector peers. Use `recharts RadarChart`. Click axis → navigate to relevant tab. Display: overall score badge + radar + verdict + top 3 Rewards (✓) + top 3 Risks (⚠).

**Placements**: Overview tab, Screener Charts view thumbnail, Valuation tab next to Axiom Fair Value.

---

## Phase 10 — Sector Performance Charts

**Goal**: Sector-level return comparison, rotation analysis, and industry drill-down.

11 SPDR ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLB, XLRE, XLC, XLU) via yfinance. Top: 1D return bar for all 11 sectors. Full: 6 horizontal bar charts (1D/1W/1M/3M/YTD/1Y sorted by return). Fundamentals table with Overview/Valuation/Performance/Volatility tabs. Industry drill-down: click sector → top-3 stocks per industry → Screener filtered view.

**Sector Rotation Clock**: Sam Stovall 4-quadrant (Early/Mid/Late/Recession). Sectors sized/coloured by relative performance vs S&P 500. Implied phase from 3M ETF returns. Cross-validate with Phase 0.3 Regime Clock.

---

## Phase 11 — Portfolio Analytics

**Goal**: Let users input ticker + weight lists and get full portfolio performance, risk, and optimisation analytics.

Route: `/portfolio`.

**Top KPIs** 🟢: Total Return, Annualised Return, Annualised Volatility, Sharpe Ratio, Max Drawdown, Beta vs S&P 500.

**Analytics** 🟢: Performance vs `^GSPC` + `AGG` overlay, CAPM Attribution (Jensen's Alpha), Correlation Matrix heatmap, Contribution to Risk (% variance per holding), Drawdown Chart (underwater equity curve), Rolling Metrics (portfolio-level Sharpe, Vol, Beta).

**On-demand** 🟡: Kelly Criterion Position Sizing (`f* = (bp − q) / b`, ~2s), Fama-French Attribution (3F + 5F, Ken French CSV, ~3s).

**User-triggered** 🔴: Efficient Frontier (`scipy.optimize.minimize`, method='SLSQP', weights sum to 1, all ≥ 0; warn for >20 holdings), Monte Carlo Portfolio Simulation (10,000 random weight portfolios, risk/return scatter coloured by Sharpe), Black-Litterman (blend CAPM equilibrium returns with user views; user input form; output BL posterior returns + optimal weights; depends on efficient frontier), Stress Testing (2008 GFC / 2020 COVID / 2022 rate shock / 2000 dot-com replay).

---

## Phase 12 — Advanced Technicals

**Goal**: Enrich stock pages and the screener with a full technical indicator suite and additional signal presets.

**Top Technical Summary** 🟢: Trend (SMA50 vs SMA200 → Bullish/Bearish), RSI (14), MACD signal, Volume vs 20-day avg, 52W position (% from high/low).

**Extended indicators** 🟢: Bollinger Bands (20-day ±2σ, %B, Bandwidth squeeze alert), ATR (14-day), OBV, CMF (20-period), VWAP (intraday, reset daily), Stochastic RSI, Williams %R, Ichimoku Cloud (Tenkan 9, Kijun 26, Senkou A/B 52, Chikou — toggleable overlay), Fibonacci Retracement (auto-detect last swing high/low, draw 23.6%/38.2%/50%/61.8%/78.6%), Pivot Points (daily/weekly/monthly classic + S1/S2/R1/R2).

**Screener presets (additions to Phase 5)**: Bollinger Squeeze Active, Ichimoku Bullish/Bearish Cross, OBV Divergence (price new high but OBV not confirming), CMF Positive + RSI < 50.

---

## Data Sources

| Source | Install | Used For |
|---|---|---|
| yfinance | `pip install yfinance` | Prices, fundamentals, options, FX, futures, ESG, analyst data |
| FRED | `pip install fredapi` (free key) | Macro: yields, inflation, employment, credit, M2, housing |
| Eurostat | `pip install eurostat` | EU GDP, HICP, unemployment |
| World Bank | `pip install wbdata` | Global GDP, debt |
| OECD.Stat | HTTP REST API | CLI, MEI, Japan macro |
| IMF WEO | Direct Excel download | 190-country forecasts (Apr/Oct) |
| Finnhub | `pip install finnhub-python` (free key) | Earnings/IPO/economic calendar |
| FinanceDatabase | `pip install financedatabase` | Small-cap universe, sector classification |
| Wikipedia MediaWiki API | `pip install wikitextparser` + requests | S&P 500, Nasdaq 100, Dow 30 constituent lists |
| Damodaran | Direct Excel download | Country ERP, sector multiples |
| CFTC | Direct ZIP download | COT positioning data |
| SEC EDGAR | `pip install edgartools` | 13F, Form 4, 10-K/Q, 8-K, SC 13D, DEF 14A |
| NY Fed | Direct Excel download | GSCPI, ACM yield curve decomposition |
| Ken French | Direct CSV download | Fama-French factor returns (3F + 5F) |
| scipy | `pip install scipy` | Efficient frontier optimisation, Black-Scholes IV solve |
| arch | `pip install arch` | GARCH(1,1) volatility modelling |
