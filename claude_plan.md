# Axiom Finance — Claude Code Execution Plan

## Stack
- **Backend**: Python FastAPI
- **Frontend**: Next.js (TypeScript, React)
- **Data**: All free — yfinance (primary), FRED (fredapi), Eurostat, World Bank, OECD, IMF WEO, Finnhub (free tier), FinanceDatabase, Wikipedia MediaWiki API, CFTC (direct file download), SEC EDGAR (edgartools), NY Fed (direct file download)
- **Cost**: $0 — no paid APIs, no web scraping
- **Rule**: Only use free APIs, pip-installable libraries, or direct structured file downloads (CSV/Excel/ZIP from stable government/institutional URLs). No HTML scraping of any kind.

---

## Global UX Rule — Information Hierarchy

**Every data analysis section must follow this two-tier layout:**

1. **Top tier — Key indicators** (always visible, no scroll): The 3–6 most intuitive, decision-relevant metrics for that section. These should be immediately readable by someone without a finance background. Examples: Price, Market Cap, P/E, Beta, Dividend Yield for a stock overview; CPI YoY, Unemployment Rate, Fed Funds Rate for macro.
2. **Bottom tier — Full extended list** (below a divider or in expandable panels): Every computed metric, model output, and advanced indicator for that section. It is acceptable — and expected — for a metric like Beta to appear in both the top KPI row and again in the detailed Risk section below. Repetition in service of clarity is correct.

This rule applies to: stock overview, valuation tab, risk tab, options tab, macro sub-tabs, screener columns, and portfolio analytics.

---

## Compute Classification Policy

Every feature is classified by compute cost. This classification must be respected at implementation time.

- 🟢 **Default** — runs automatically on page load and in overnight cron. Milliseconds per ticker.
- 🟡 **On-demand** — shown as a greyed-out panel with a "Calculate" button. Triggered per user request, runs in 1–5 seconds. Never in cron.
- 🔴 **User-triggered only** — shown as a locked panel with a prominent "Run Analysis" button and a warning: *"This calculation is compute-intensive and may take 15–60 seconds."* Never on page load, never in cron, never triggered automatically.

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

---

## Index Constituent Lists — Wikipedia MediaWiki API

All index constituent lists are fetched via the **Wikipedia MediaWiki Action API** — a free structured JSON API, not HTML scraping.

- Call `https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&page={title}&format=json`
- Parse returned wikitext with `wikitextparser` (`pip install wikitextparser`) to extract table rows
- Cache weekly. Pages: `"List of S&P 500 companies"`, `"Nasdaq-100"`, `"Dow Jones Industrial Average"`

```python
import requests, wikitextparser as wtp
params = {"action": "parse", "prop": "wikitext", "page": "List of S&P 500 companies", "format": "json"}
r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers={"User-Agent": "AxiomFinance/1.0"})
table = wtp.parse(r.json()["parse"]["wikitext"]["*"]).tables[0]
data = table.data()  # list of lists — no HTML parsed
```

---

## Phase 0 — Bug Fixes (Do First)

**0.1 DCF panel blank** — Two-stage DCF with slider inputs. Fetch TTM FCF + shares from yfinance. Output: intrinsic value, Bear/Base/Bull table, 7×7 sensitivity heatmap (FCF Growth vs WACC).

**0.2 FX Rates panel empty** — 15+ pairs via yfinance (`EURUSD=X`). Rate, 1D/1W/1M/1Y change%, 30-day sparkline, base currency switcher.

**0.3 Regime Classifier stuck** — 2×2 Goldilocks matrix: FRED `GDPC1` × `CPIAUCSL` → Goldilocks/Reflation/Stagflation/Recession. Eurozone via Eurostat API, Japan via OECD.Stat. 4-quadrant scatter, animated dot, time scrubber from 2000. Label "as of [latest available period]" — Eurozone/Japan lag 6–8 weeks.

---

## Phase 1 — Valuation Engine

**Architecture**: `CountrySelector` auto-detects listing country from Yahoo exchange code → fetches 10Y gov bond yield (FRED) → applies Damodaran 2026 ERP (`backend/data/damodaran_erp_2026.json`) → computes WACC. All models share these rates.

### Stock Page — Top KPI Row 🟢
Price, Market Cap, P/E (TTM), Forward P/E, EPS (TTM), Dividend Yield, 52W High/Low, Beta, Average Volume.

### Stock Page — Extended Fundamentals 🟢
- **EV/FCF** — `enterpriseValue` / TTM FCF from `Ticker.cashflow`
- **FCF Yield** — `(TTM FCF / shares) / price` %
- **Short Float %** — `Ticker.info["shortPercentOfFloat"]`. >20% red, 10–20% orange. `N/A` if None
- **Short Ratio** — `Ticker.info["shortRatio"]` (days to cover)
- **Earnings Revision** — `Ticker.earnings_forecasts` (yfinance ≥0.2.28, guard with `hasattr`). ↑/↓/↔ badge vs 30/60/90 days ago
- **ROIC** — `NOPAT / (equity + debt − cash)`. NOPAT = `EBIT × (1 − tax_rate)`
- **CAPM Required Return** 🟢 — `Rf + β × (Rm − Rf)`. Rf = FRED `DGS10`, β from 60M regression vs `^GSPC`, Rm = 10% historical assumption. Display as "Required Return: X%" vs current earnings yield
- **Cash Conversion Cycle** 🟢 — `DIO + DSO − DPO` from balance sheet. Lower = better capital efficiency
- **DuPont Decomposition** 🟢 — ROE = Net Margin × Asset Turnover × Equity Multiplier (3-factor). Extended 5-factor: also Tax Burden × Interest Burden. Show waterfall breakdown
- **Piotroski F-Score** 🟢 — 9-point binary score across profitability (4), leverage (3), efficiency (2). >7 = strong, <3 = weak. Fully computed from `Ticker.financials` + `Ticker.balance_sheet`
- **Beneish M-Score** 🟢 — 8-variable earnings manipulation detection. M > −1.78 = possible manipulator. All inputs from yfinance
- **Ohlson O-Score** 🟢 — bankruptcy probability logistic model. Complement to Altman Z-Score; more reliable for financial firms
- **ESG Scores** 🟢 — `Ticker.sustainability` (Yahoo/Sustainalytics). Environment, Social, Governance scores + controversy level. `N/A` if unavailable

### Analyst Data 🟢
- **Price Target** — `Ticker.analyst_price_targets`: mean, high, low, upside% vs current price. Display as band on price chart
- **Consensus Rating** — `Ticker.recommendations_summary`: Strong Buy/Buy/Hold/Sell/Strong Sell counts as bar. 12-month history of rating changes
- **Earnings Surprise History** — `Ticker.earnings_history`: actual vs estimated EPS last 8 quarters, surprise % per quarter. Chart with beat/miss colour coding
- **Forward Estimates Table** — `Ticker.earnings_estimate` + `revenue_estimate`: current Q, next Q, current year, next year
- **Growth Estimates** — `Ticker.growth_estimates`: EPS growth vs sector and S&P 500

### 8 Valuation Models (2×4 grid) 🟢
1. **DCF (Two-Stage)** — 10Y FCF projection + terminal value. Heatmap + scenario table
2. **DDM (Gordon Growth)** — `P₀ = D₁ / (r − g)`. Lock if `dividendRate = 0`
3. **Graham Formula** — `V* = EPS × (8.5 + 2g) × 4.4 / Y`. Y = FRED `AAA`. g = whole number
4. **Graham Number** — `√(22.5 × EPS × BVPS)`. Requires EPS > 0 and BVPS > 0
5. **Peter Lynch / PEG** — Fair value = `EPS × growth_rate` (whole number, cap 20). PEG verdict badge
6. **EV/EBITDA Comps** — `sector_multiples.json` primary; FinanceDatabase peer fetch optional only. Not for Financials
7. **Residual Income (RIM)** — `BVPS + PV(RI stream)`. ROE from `Ticker.info` or computed from financials; lock if unavailable
8. **EPV** — `Adjusted NOPAT / WACC` firm value; subtract net debt, divide by shares

### Additional Valuation Models
- **CAPM Implied Fair Value** 🟢 — back out price implied by CAPM required return vs forward EPS
- **Fama-French 3-Factor** 🟡 — regress stock returns on market (MKT-RF), size (SMB), value (HML). Factor data from Ken French Data Library (direct CSV download, free). Show factor loadings + expected return
- **Fama-French 5-Factor** 🟡 — extends 3F with profitability (RMW) and investment (CMA) factors

**Axiom Fair Value** — weighted composite of applicable models (DCF 30%, Comps 20%, RIM 15%, EPV 15%, Graham Formula 10%, Lynch 5%, DDM 5%). Gauge + needle. Verdict: Significantly Under → Significantly Overvalued.

**Key files**: `backend/routes/valuation.py`, `backend/services/valuation_engine.py`, `backend/services/discount_rates.py`, `backend/data/damodaran_erp_2026.json`, `backend/data/sector_multiples.json`

---

## Phase 2 — Market Breadth & Dashboard

**2.1 Breadth Bar** — S&P 500 constituents via Wikipedia MediaWiki API, cached weekly. `yf.download()` in chunks of 100. Advancing/Declining, New Highs/Lows, % Above SMA50/200, McClellan Oscillator, Cumulative A/D Line. Sticky at top of Markets page.

**McClellan Oscillator**: RANA = `(A−D)/(A+D)`. Oscillator = 19-day EMA(RANA) − 39-day EMA(RANA). Multipliers: 0.10 / 0.05.

**Cumulative A/D Line**: 3Y rolling sum of (A−D). Overlaid on S&P 500 price. Divergence = warning signal.

**2.2 Global Indices** — ~25 indices via yfinance. Price, 1D%, 5-day sparkline, 1M%, YTD%. Region tabs.

**2.3 Fear & Greed Index** — 7 signals scored 0–100:
1. S&P 500 vs 125-day SMA (z-score)
2. New 52W Highs vs Lows ratio
3. McClellan Summation Index (percentile over 2Y)
4. Put/Call Ratio — SPY options chain via yfinance, put OI / call OI. Inverted
5. VIX (`^VIX`) inverted percentile over 2Y
6. Stocks vs Bonds 20-day return (`^GSPC` vs `TLT`)
7. HY Credit Spread (FRED `BAMLH0A0HYM2`) inverted

Speedometer gauge, 90-day history, signal breakdown panel.

**2.4 Dashboard** — `/dashboard` default landing. Breadth Bar → Fear&Greed / Regime badge / Session status → Global Indices → Yield Curve + Top Movers → Sector bars → Mini calendar strip.

**2.5 Top Movers** — Gainers, Losers, Unusual Volume (>2× avg), 52W Highs/Lows from constituent cache.

---

## Phase 3 — S&P 500 Treemap

S&P 500 → Sector → Industry → Stock. Constituent list via Wikipedia MediaWiki API. Area = log(market cap), colour = return% (−5% deep red, 0% white, +5% deep green). `d3-hierarchy` squarified layout. Hover tooltip: name, price, 1D%, mkt cap, P/E, 52W range. Controls: period, index (S&P/NDX/Dow), group by, colour by.

---

## Phase 4 — Economic Calendar

Route `/calendar`. Sub-tabs: Economic / Earnings / Dividends / IPO.
- **Macro**: Finnhub `/calendar/economic` primary + FRED release calendar
- **CB dates**: `backend/data/cb_meetings.json`, updated 2× per year
- **Earnings**: `yf.Ticker(t).calendar` + Finnhub `/calendar/earnings`. Overnight cron, `ThreadPoolExecutor(max_workers=10)`
- **Dividends**: `Ticker.info["exDividendDate"]` batch in same cron
- **IPO**: Finnhub `/calendar/ipo`

Weekly grid, today highlighted. Filter by impact (★★★/★★/★), country, timezone. Green/red beat/miss colouring. Countdown timers within 24h.

---

## Phase 5 — Screener Overhaul

**Universes**: S&P 500 / Nasdaq 100 / Dow 30 (Wikipedia MediaWiki API, weekly cache), Small-Cap proxy (FinanceDatabase, label "Small-Cap Universe ~3,000–5,000 tickers", not "Russell 2000"), Custom.

**Pipeline**: Overnight cron → Wikipedia API fetch → yfinance batch fundamentals → Parquet/SQLite cache. `ThreadPoolExecutor(max_workers=10)`.

### Screener Top Columns (default visible) 🟢
Ticker, Name, Price, 1D%, Market Cap, P/E, Forward P/E, EPS, Dividend Yield, Beta, Volume, Sector.

### Screener Extended Columns 🟢
P/B, EV/EBITDA, EV/FCF, FCF Yield, ROIC, Short Float%, Short Ratio, Gross Margin, Net Margin, ROE, ROA, Debt/Equity, Current Ratio, Revenue Growth YoY, EPS Growth YoY, Earnings Revision 30D, Piotroski F-Score, Altman Z-Score, ESG Score.

**Preset Signal Pills**:
- Price Action: Top Gainers, Biggest Losers, New 52W High/Low, Above/Below SMA200, Golden/Death Cross
- Volume: Unusual Volume, Overbought (RSI>70), Oversold (RSI<30), High Beta
- Fundamentals: Undervalued, High Dividend, High ROIC, Quality Growth, Deep Value, High Short Interest (>20%)
- Situations: Earnings This Week, Post-Earnings, Pre-Earnings Dip, Insider Buying (Form 4 code-P last 30 days), Activist Target (SC 13D filed last 90 days)

**Result View Tabs**: Overview | Performance | Technicals | Valuation | Profitability | Dividends | Financials | Balance Sheet | All Columns. Sortable, CSV-exportable.

**Charts View**: 200×120px sparkline gallery (3M closes + SMA50), canvas-based.

---

## Phase 6 — Risk & Rolling Metrics

### Top Risk KPIs (always visible) 🟢
Beta (vs S&P 500), 30-day Realised Volatility (annualised), Max Drawdown (3Y), Sharpe Ratio (1Y), VaR 95% (1-day parametric).

### Rolling Metrics 🟢
Window: 20D / 60D (default) / 120D / 252D. 3Y history.
- Rolling Sharpe Ratio (FRED `DGS10` as Rf)
- Rolling Volatility (stddev × √252)
- Rolling Beta (vs `^GSPC`)
- Rolling Sortino Ratio
- Rolling Max Drawdown (filled area)
- Rolling Correlation (between selected ticker pairs)
- Rolling VaR 95% and 99% (parametric)

### Extended Risk Metrics 🟢
- **Expected Shortfall / CVaR** — average loss beyond VaR threshold. More robust tail risk measure
- **Calmar Ratio** — annualised return / max drawdown. Favoured by hedge funds
- **Omega Ratio** — `∫(1−F(r))dr / ∫F(r)dr`. Captures full return distribution unlike Sharpe
- **Treynor Ratio** — `(Rp − Rf) / β`. Sharpe but using systematic risk only
- **Jensen's Alpha** — actual return minus CAPM-predicted return. Measures skill/outperformance
- **Historical VaR** — non-parametric, uses actual return distribution (complement to parametric VaR above)
- **CAPM Decomposition** — total risk split into systematic (β²×σ²_m) and idiosyncratic (residual) components

### On-Demand Risk Models 🟡
- **Hurst Exponent** — H > 0.5 = trending, H < 0.5 = mean-reverting, H ≈ 0.5 = random walk. ~2s per ticker
- **Ornstein-Uhlenbeck Fit** — estimate mean-reversion speed θ, long-run mean μ, vol σ via MLE. Signal for pairs trading. ~2s per pair
- **GARCH(1,1) Volatility Forecast** — conditional volatility model via `arch` library. Better forward vol estimate than rolling stddev. ~3s per ticker
- **Pairs Cointegration Test** — Engle-Granger or Johansen test between two tickers. Spread z-score chart. ~3s per pair

### User-Triggered Only 🔴
- **Monte Carlo VaR** — 10,000 GBM simulations, show full P&L distribution. Never on page load
- **Stress Testing** — simulate portfolio P&L under: 2008 GFC, 2020 COVID crash, 2022 rate shock, 2000 dot-com. Replay actual return sequences against user-defined portfolio weights

Two views: Overlay (all tickers, metric selector) and Grid (2×3).

---

## Phase 7 — Options Tab

### Top Options KPIs (always visible) 🟢
IV30, IV Rank, IV Percentile, Put/Call OI Ratio, Max Pain, Implied Earnings Move.

**IV Rank**: `(current_IV − min_52w) / (max_52w − min_52w) × 100`
**IV30 interpolation**: linear interpolation between two expiries bracketing 30 DTE. Fallback: nearest single expiry ATM IV, labelled "nearest expiry IV".

### Options Models 🟢
- **Black-Scholes Pricing** — call/put theoretical price for each strike/expiry. Greeks: Delta (Δ), Gamma (Γ), Theta (Θ), Vega (V), Rho (ρ). Computed via closed-form formula (`scipy.stats.norm`). IV backsolve via `scipy.optimize.brentq`. Display BS theoretical vs market price to surface mispricing
- **Binomial Tree Pricing** — American-style pricing (100-step CRR tree). Captures early-exercise premium that BS underestimates. On-demand per contract row

### Charts
- IV Term Structure (ATM IV vs DTE, annotate earnings date)
- IV Smile (IV vs moneyness 0.70–1.30)
- OI Profile: horizontal bar, calls (green) right / puts (red) left, max pain line

### Chain Table
Calls | Strikes | Puts. ITM rows tinted. OTM-only toggle. Synced expiry selector. All from `yf.Ticker(t).option_chain(expiry)`. IV is decimal — multiply ×100 for display. Label "delayed ~15min".

### User-Triggered Only 🔴
- **Monte Carlo Options Pricing** — 10,000 GBM path simulations per option. Distribution of terminal prices, percentile payoff chart. Warning: compute-intensive.

---

## Phase 8 — Macro Expansion

Macro tab sub-tabs: Overview | Rates & Yields | Inflation | Growth & Employment | Housing | Commodities | FX | Leading Indicators | Financial Conditions | Positioning.

### Each Sub-Tab Layout Rule
Top section: 3–5 headline numbers (e.g. Fed Funds Rate, 10Y yield, 2Y10Y spread for Rates). Full chart section below.

### Rates & Yields
**Top**: Fed Funds Rate (`FEDFUNDS`), 10Y Treasury yield (`DGS10`), 2Y yield (`DGS2`), 2Y10Y spread, 30Y mortgage rate (`MORTGAGE30US`).
**Full list**: Yield curve (3M–30Y), 3M10Y spread, TIPS breakeven 5Y (`T5YIE`) & 10Y (`T10YIE`), real yields (`DFII10`), SOFR (`SOFR`) vs Fed Funds, IG spread (`BAMLC0A0CM`), HY spread (`BAMLH0A0HYM2`), TED spread proxy (`DTB3` − `SOFR`), corporate bond yields by rating (AAA→B, FRED BofA series).

**Taylor Rule** 🟢 — `r = r* + π + 0.5(π − π*) + 0.5(Y − Y*)`. r* = 0.5%, π* = 2%, output gap from FRED `GDPC1` vs CBO potential. Chart implied rate vs actual `FEDFUNDS`. Gap = policy deviation signal.

**Yield Curve Decomposition (ACM)** 🟢 — NY Fed ACM model data (direct Excel download, free). Decompose 10Y yield into expectations component (avg future short rates) vs term premium. Chart both over time.

### Inflation
**Top**: CPI YoY (`CPIAUCSL`), Core CPI YoY (`CPILFESL`), PCE YoY (`PCEPI`), Core PCE YoY (`PCEPILFE`), 5Y Breakeven (`T5YIE`).
**Full list**: PPI (`PPIACO`), 5Y5Y Forward Inflation (`T5YIFR`), 10Y Breakeven (`T10YIE`), M2 YoY growth overlaid with CPI (`M2SL`).

**Quantity Theory of Money** 🟢 — MV = PQ. Plot M2 growth (`M2SL`) vs nominal GDP growth. Compute velocity of money V = nominal GDP / M2. Chart V over time — declining velocity explains "missing inflation" post-QE.

### Growth & Employment
**Top**: Real GDP YoY (`GDPC1`), Unemployment Rate (`UNRATE`), NFP MoM (`PAYEMS`), Initial Jobless Claims (`ICSA`), Labour Participation Rate (`CIVPART`).
**Full list**: Continuing Claims (`CCSA`), Average Hourly Earnings YoY (`CES0500000003`), JOLTS Job Openings (`JTSJOL`), Quit Rate (`JTSQUR`), Sahm Rule (`SAHMREALTIME`) — shade red when ≥ 0.50, Industrial Production (`INDPRO`), Capacity Utilization (`TCU`), Trade Balance (`BOPGSTB`).

### Housing
**Top**: Case-Shiller HPI YoY (`CSUSHPISA`), Housing Starts (`HOUST`), 30Y Mortgage Rate (`MORTGAGE30US`), Existing Home Sales (`EXHOSLUSM495S`).
Housing starts lead construction sector by ~6 months. Chart all four with recession shading.

### Commodities
**Top**: WTI Crude (CL=F), Gold (GC=F), Natural Gas (NG=F), Copper (HG=F), Wheat (ZW=F).
**Full list**: ~25 futures via yfinance. Dr. Copper vs World Bank GDP, Gold/Oil ratio with `USREC` shading, Axiom Commodity Index (equal-weighted). Bitcoin (`CBBTCUSD` from FRED) on this tab.

### FX
**Top**: DXY (`DX-Y.NYB`), EUR/USD, USD/JPY, GBP/USD, USD/CNY.
**Full list**: Currency heatmap (grid of crosses, 1D change%), EM FX emphasis.
**PPP** 🟢 — for G10 pairs: compute PPP rate = (domestic CPI / foreign CPI) × base rate. Plot PPP vs spot. Over/undervaluation % badge. CPI data from FRED and Eurostat.

### Leading Indicators
**Top**: Conference Board LEI (`USSLIND`) YoY, OECD CLI (G7), CFNAI (`CFNAI`), ISM PMI (Finnhub calendar).
**Full list**: GSCPI (NY Fed Excel download — `https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx`), ISM historical via FRED `NAPM` through 2023 with 50-line threshold.

**IS-LM-PC Model** 🟢 — Interactive 3-panel chart:
- IS curve: output (GDP gap) vs interest rate, derived from FRED GDP + FEDFUNDS
- LM curve: money market equilibrium, M2 + nominal GDP
- Phillips Curve: unemployment vs inflation (FRED `UNRATE` + `CPIAUCSL`), show current position dot + 10Y trail
Annotate supply/demand shocks. Educational tool showing macro interdependencies.

### Financial Conditions
**Top**: NFCI (`NFCI`) — Chicago Fed National Financial Conditions Index, STLFSI4 (`STLFSI4`) — St. Louis Financial Stress Index, Fed Balance Sheet total assets (`WALCL`).
**Full list**: Credit card delinquency rate (`DRCCLACBS`), consumer loan delinquency (`DRCLACBS`), C&I loans (`TOTCI`), Economic Policy Uncertainty (`USEPUINDXD`).
NFCI < 0 = looser than average, > 0 = tighter. WALCL chart shows QE/QT cycles.

### Positioning
**COT Report** — CFTC ZIP downloads (`https://www.cftc.gov/dcom/files/dcotnoc.zip` current, historical archive). `pandas.read_csv(skipinitialspace=True)`, always `.strip()` columns. Key contracts: S&P 500 E-mini (13874+), NDX E-mini (209742), EUR/USD (099741), Gold (088691), WTI (067651), 10Y Note (043602). COT Index = `(net_spec − min_52w) / (max_52w − min_52w) × 100`.

**SEC Form 4 Insider Trades** — EDGAR REST API (free, no key): `https://efts.sec.gov/LATEST/search-index?q="{ticker}"&forms=4`. Code P = buy, S = sell, A = award (exclude). Timeline on price chart. `time.sleep(0.15)` between calls.

**SEC 13F Institutional Holdings** — `edgartools` (`pip install edgartools`). `Company(ticker).get_filings(form="13F-HR")`. Top 10 holders, QoQ change, filing date. Label "45-day reporting lag". `time.sleep(0.1)`.

**SC 13D/G Beneficial Ownership** — `edgartools`. When entity accumulates >5% of shares — activist investor signal. Show on stock page as "Activist Watch" badge.

**DEF 14A Executive Compensation** — `edgartools`. CEO total comp, pay ratio. Display on stock page fundamentals panel.

**8-K Material Events** — `edgartools`. Earnings releases, M&A announcements, leadership changes. Timeline on stock page.

---

## Phase 9 — Snowflake Composite Score

Pentagon radar chart, 0–10 per axis, sector-normalised (percentile rank within sector peers).

**Top display**: Overall score badge + 5-axis radar. Verdict text + top 3 Rewards (✓) + top 3 Risks (⚠).

1. **Value** 🟢 — P/E, EV/EBITDA, EV/FCF, FCF Yield, P/B, PEG
2. **Future Growth** 🟢 — EPS growth estimate, revenue growth YoY, earnings revision 30D, R&D intensity
3. **Past Performance** 🟢 — 3Y revenue CAGR, 3Y EPS CAGR, ROE avg, gross margin trend, price alpha vs sector
4. **Financial Health** 🟢 — Altman Z-Score, Piotroski F-Score, Ohlson O-Score, Beneish M-Score flag, ROIC vs WACC spread, interest coverage, current ratio, net cash, debt/equity
5. **Dividend** 🟢 — Yield vs peers, payout ratio, 5Y CAGR, consistency, FCF coverage. Score 0 if no dividend

Invert percentile for lower-is-better metrics. Fallback to industry → market-wide if <10 sector peers.

Placement: Overview tab, Screener Charts view thumbnail, Valuation tab next to Axiom Fair Value. `recharts RadarChart`. Click axis → navigate to relevant tab.

---

## Phase 10 — Sector Performance Charts

11 SPDR ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLB, XLRE, XLC, XLU) from yfinance.

**Top**: 1D return bar chart for all 11 sectors at a glance.
**Full**: 6 horizontal bar charts (1D/1W/1M/3M/YTD/1Y), sorted by return. Fundamentals table (Overview/Valuation/Performance/Volatility tabs). Industry drill-down: click sector → top-3 stocks per industry → Screener filtered view.

**Sector Rotation Clock**: Sam Stovall 4-quadrant (Early/Mid/Late/Recession). Sectors sized/coloured by relative performance vs S&P 500. Implied phase from 3M ETF returns. Cross-validate with Phase 0.3 Regime Clock.

---

## Phase 11 — Portfolio Analytics

Route `/portfolio`. User inputs a list of tickers + weights (or equal-weight default).

### Top Portfolio KPIs (always visible) 🟢
Total Return, Annualised Return, Annualised Volatility, Sharpe Ratio, Max Drawdown, Beta vs S&P 500.

### Portfolio Analytics 🟢
- **Performance vs Benchmark** — portfolio return overlaid with `^GSPC` and `AGG` (bonds). Time period selector.
- **CAPM Attribution** — portfolio alpha + beta vs market. Jensen's Alpha displayed prominently
- **Correlation Matrix** — heatmap of pairwise correlations between holdings. `seaborn`-style diverging colour scale
- **Contribution to Risk** — % of total portfolio variance contributed by each holding
- **Drawdown Chart** — underwater equity curve, annotate recovery periods
- **Rolling Metrics** — portfolio-level rolling Sharpe, Vol, Beta (same as Phase 6 but portfolio-level)

### On-Demand 🟡
- **Kelly Criterion Position Sizing** — `f* = (bp − q) / b`. Estimate win-rate + avg win/loss from historical returns. Display optimal sizing per holding. ~2s
- **Fama-French Attribution** 🟡 — decompose portfolio returns into MKT-RF, SMB, HML (3F) or + RMW, CMA (5F). Factor data from Ken French Data Library (direct CSV download). ~3s

### User-Triggered Only 🔴
- **Efficient Frontier (MPT)** — `scipy.optimize` minimisation over covariance matrix. Plot minimum variance portfolio, maximum Sharpe portfolio, full frontier curve. Input: tickers from Phase 5 cache, lookback period selector. Warning: slow for >20 holdings
- **Monte Carlo Portfolio Simulation** — 10,000 random weight portfolios. Scatter plot risk vs return, colour by Sharpe. Overlay efficient frontier
- **Black-Litterman Model** — blend CAPM equilibrium returns with user-specified views (view input form: "I think AAPL will outperform by X%"). Output: BL posterior expected returns + optimal weights. Depends on efficient frontier
- **Stress Testing** — replay 2008 GFC / 2020 COVID / 2022 rate shock / 2000 dot-com return sequences against portfolio weights. Show max drawdown per scenario table

---

## Phase 12 — Advanced Technicals

All indicators 🟢 unless noted. Added to the existing chart/technical tab on stock pages and screener.

### Top Technical Summary (always visible) 🟢
Trend (SMA50 vs SMA200 → Bullish/Bearish), RSI (14-day), MACD signal, Volume vs 20-day avg, 52W position (% from high/low).

### Extended Technical Indicators 🟢
- **Bollinger Bands** — 20-day SMA ± 2σ. %B = `(price − lower) / (upper − lower)`. Bandwidth = `(upper − lower) / SMA`. Squeeze when Bandwidth at 6M low
- **ATR (Average True Range)** — `max(H−L, |H−C_prev|, |L−C_prev|)` 14-day. Absolute volatility, stop-loss sizing reference
- **OBV (On-Balance Volume)** — cumulative volume momentum. Divergence from price = early reversal signal
- **Chaikin Money Flow (CMF)** — 20-period. Positive = buying pressure, negative = selling pressure
- **VWAP** — Volume Weighted Average Price. Intraday institutional reference. Reset daily
- **Stochastic RSI** — RSI of RSI(14). More sensitive overbought/oversold than standard RSI
- **Williams %R** — momentum oscillator −100 to 0. <−80 = oversold, >−20 = overbought
- **Ichimoku Cloud** — Tenkan (9), Kijun (26), Senkou A & B (52), Chikou. Price above cloud = uptrend; below = downtrend. Show toggleable overlay on price chart
- **Fibonacci Retracement** — auto-detect last significant swing high/low from 1Y price data. Draw 23.6%, 38.2%, 50%, 61.8%, 78.6% levels
- **Pivot Points** — daily/weekly/monthly classic pivot + S1/S2/R1/R2 from OHLC

### Screener Technical Presets (additions to Phase 5)
- Bollinger Squeeze Active
- Ichimoku Bullish/Bearish Cross
- OBV Divergence (price new high but OBV not confirming)
- CMF Positive + RSI < 50 (accumulation before breakout)

---

## Data Source Quick Reference

| Source | Install / Access | Key | Used For |
|---|---|---|
| yfinance | `pip install yfinance` | None | Prices, fundamentals, options, FX, futures, ESG, analyst data |
| FRED | `pip install fredapi` | Free key | All macro: yields, inflation, employment, credit, M2, housing etc. |
| Eurostat | `pip install eurostat` | None | EU GDP, HICP, unemployment |
| World Bank | `pip install wbdata` | None | Global GDP, debt |
| OECD.Stat | HTTP REST API | None | CLI, MEI, Japan macro |
| IMF WEO | Direct Excel download | None | 190-country forecasts (Apr/Oct) |
| Finnhub | `pip install finnhub-python` | Free key | Earnings/IPO/economic calendar |
| FinanceDatabase | `pip install financedatabase` | None | Small-cap universe, sector classification |
| Wikipedia MediaWiki API | `pip install wikitextparser` + `requests` | None | S&P 500, Nasdaq 100, Dow 30 constituent lists |
| Damodaran | Direct Excel download | None | Country ERP, sector multiples |
| CFTC | Direct ZIP download | None | COT positioning data |
| SEC EDGAR | `pip install edgartools` | None | 13F, Form 4, 10-K/Q, 8-K, SC 13D, DEF 14A |
| NY Fed | Direct Excel download | None | GSCPI, ACM yield curve decomposition |
| Ken French | Direct CSV download | None | Fama-French factor returns (3F + 5F) |
| `scipy` | `pip install scipy` | None | Optimisation (efficient frontier), Black-Scholes IV solve |
| `arch` | `pip install arch` | None | GARCH(1,1) volatility modelling |

---

## Caching Strategy

| Frequency | What |
|---|---|
| 15min (market hours) / hourly (off-hours) | Prices, FX, commodities, VIX, constituent prices |
| Daily (11pm UTC) | Screener metrics, Fear & Greed, breadth, movers, options chains, sector ETFs, rolling risk, Snowflake scores |
| Weekly (Fri 6pm ET) | COT (CFTC), earnings calendar, constituent lists (Wikipedia API) |
| Weekly (Thu) | Initial jobless claims (`ICSA`) |
| Monthly | OECD CLI, Eurostat, FRED monthly series, World Bank, GSCPI, M2, LEI, CFNAI, housing |
| Quarterly | 13F holdings (edgartools, 45-day lag) |
| Annually (Jan) | Damodaran ERP + multiples, Ken French factor data |
| Biannually (Apr/Oct) | IMF WEO |

Dev: `cachetools`. Prod: Redis. Cache key must include all params. Expose `/api/admin/cache/clear`.

---

## Notes for Claude Code
- **No web scraping** — never `BeautifulSoup`, HTML `requests`, or `Selenium`. APIs, pip libs, or direct file downloads only
- **Wikipedia** — MediaWiki API (`action=parse&prop=wikitext`) + `wikitextparser`. JSON API call, not HTML scraping
- **Compute policy** — 🟢 default on page load; 🟡 "Calculate" button, never in cron; 🔴 "Run Analysis" button with warning, never on page load or cron
- **Information hierarchy** — every section: key indicators at top (3–6 metrics), full extended list below. Repetition is correct
- Safe `.get()` with fallbacks on all `Ticker.info` fields — any can be `None`
- `yf.download()` for batch price; never loop `Ticker()` for large universes
- Phase 9 (Snowflake) depends on Phase 5 cache — implement Phase 5 first
- Phase 11 (Portfolio) 🔴 features depend on Phase 5 cache for covariance matrix
- Inapplicable valuation models → grey locked card with explanation, never hidden
- Sector normalisation: percentile rank within sector peers; invert for lower-is-better metrics
- yfinance IV is decimal (0.34 = 34%) — always ×100 for display
- Peter Lynch `growth_rate` and Graham `g` are whole numbers (15 = 15%)
- EPV: firm-level value — subtract net debt, divide by shares outstanding
- McClellan Oscillator: use RANA (ratio-adjusted), not raw A−D
- Form 4: P = open-market buy, S = open-market sell, A = award (exclude)
- `edgartools` calls: `time.sleep(0.1)` between requests; Form 4: `time.sleep(0.15)`
- CFTC COT CSV: `skipinitialspace=True` + `.strip()` all column names and values
- GSCPI Excel URL: `https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx` — if 404, log + serve cached
- ISM PMI: FRED `NAPM` for history through 2023; live via Finnhub calendar only
- Sahm Rule: shade red when `SAHMREALTIME ≥ 0.50`
- Black-Scholes IV backsolve: `scipy.optimize.brentq` on the BS price function
- GARCH: use `arch` library, `arch_model(returns, vol='Garch', p=1, q=1)`
- Fama-French factors: Ken French Data Library direct CSV — `http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip`
- Efficient frontier: `scipy.optimize.minimize` with `method='SLSQP'`, constraints: weights sum to 1, all ≥ 0
- Taylor Rule: r* = 0.5%, π* = 2%, output gap = `(GDPC1 − GDPPOT) / GDPPOT × 100` (FRED `GDPPOT`)
- ACM data: NY Fed publishes at `https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr340.xls` — direct Excel download
- Short Float%, Short Ratio, analyst data: US-listed tickers only; `N/A` for non-US
- RIM: if `Ticker.info["returnOnEquity"]` is None, compute from financials; lock card if still unavailable
- `Ticker.earnings_forecasts` requires yfinance ≥0.2.28 — guard with `hasattr` + version check
- Small-cap label: "Small-Cap Universe (~3,000–5,000 tickers)", never "Russell 2000"
- Eurozone/Japan macro: label "as of [latest available period]" — 6–8 week lag
- 13F holdings: label "as of [quarter end] — 45-day reporting lag"
- All financial data: display "as of" date. Options: label "delayed ~15min"
