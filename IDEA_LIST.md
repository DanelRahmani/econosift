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

### ✅ P0 — Trade Flows & Globalization (`/trade`) — **DONE (Phase 26)**

Visualize exports/imports as % GDP, trade balances, and openness indices across ~200 countries.
Add bilateral trade partner concentration metrics (Herfindahl index of trade partners) and a trade
balance heatmap. Complement with BIS effective exchange rates (already downloaded but not wired to
any frontend) to show competitiveness linkages.

- **Data:** World Bank `NE.EXP.GNFS.ZS` (exports), `NE.IMP.GNFS.ZS` (imports), `TG.VAL.TOTL.GD.ZS` (merchandise trade). BIS effective FX via `WS_EER_csv_flat.zip` (already in `source_bis.py`).
- **Why implementable:** All 3 WB indicators need only new entries in `INDICATOR_MAP`. BIS effective FX already downloaded — just needs a router endpoint. No new source packages.

### P0 — Corporate Health Monitor (`/corporate`)

Altman Z-Score, Piotroski F-Score (9-point fundamental strength), and Beneish M-Score (earnings
manipulation detection) for any ticker. Aggregate by sector/industry to show systemic bankruptcy
risk trends. Market-cap-weighted aggregate Z-score as a recession leading indicator.

- **Data:** yfinance balance sheet (total assets, working capital, retained earnings, market cap, total liabilities, EBIT, sales), income statement (net income, revenue, gross margin, SGA, depreciation), and cash flow (operating cash flow). All available via existing `yfinance_service.py`.
- **Why implementable:** Pure calculation service — all inputs are in yfinance's standard `.balance_sheet`, `.financials`, and `.cashflow` DataFrames. No new data sources needed. Z-score formula is public domain (Altman 1968). Piotroski and Beneish formulas are also public.

### P1 — Dividend Analysis (`/dividends`)

Dividend yield, 5Y/10Y dividend growth rate, payout ratio, and dividend sustainability score per
ticker. Dividend aristocrats screener (25+ years consecutive increases). Sector dividend yield
comparison. Dividend discount model (DDM) fair value estimation.

- **Data:** yfinance `.dividends` time series and `.financials` (net income, shares outstanding for per-share calculations). Finnhub earnings calendar already provides ex-dividend dates.
- **Why implementable:** Dividend history is a standard yfinance attribute. Payout ratio = dividends / net income (both available). DDM is a simple Gordon growth model. Needs a new router + frontend page.

### P1 — Banking & Financial Stability (`/stability`)

Bank NPL ratios, capital adequacy ratios, bank Z-scores, and domestic credit growth for ~200
countries. BIS credit-to-GDP gaps as early warning indicators (gaps >10% signal elevated systemic
risk per BIS methodology). FRED financial stress indices. Composite banking crisis early-warning
model with traffic-light output.

- **Data:** World Bank `FB.AST.NPER.ZS` (NPL ratio), `FB.BNK.CAPA.ZS` (bank capital/assets), `GFDD.SI.01` (bank Z-score), `FS.AST.DOMO.GD.ZS` (domestic credit). BIS credit gap data already downloaded via `WS_CREDIT_GAP_csv_flat.zip` in `source_bis.py` — never exposed via any router. FRED stress indices already in `credit_market.py`.
- **Why implementable:** BIS credit gaps and WB banking indicators only need new indicator mapping + router endpoints. FRED financial stress data is already wired via `get_credit_pulse()`. Most of the work is frontend.

### P2 — Cross-Border Finance (`/crossborder`)

BIS locational banking statistics — cross-border claims by nationality and residence, international
debt securities outstanding. Visualize global financial interconnectedness via a chord diagram or
network graph showing which countries hold claims on which other countries.

- **Data:** BIS locational banking statistics (separate ZIP from current `BIS_ZIPS`). International debt securities statistics. Both available via BIS bulk download portal.
- **Why implementable:** Same BIS ZIP→parquet pattern already proven in `source_bis.py` + `bulk_data_service.py`. Needs new BIS dataset URLs added. Chord diagram visualization is straightforward with D3 or a Recharts custom component.

---

## 2. 📊 New Macro Tabs (Expand `/macro`)

### ✅ P0 — Fiscal Sustainability Tab — **DONE (Phase 25)**

Government revenue, expenditure, tax revenue as % GDP, fiscal balance trends, and gross national
savings rates. Debt sustainability heatmap combining debt/GDP (already mapped) with fiscal balance
(already in `country_risk_service.py`) and effective interest costs. Identify countries with
adverse debt dynamics (interest rate > growth rate).

- **Data:** World Bank `GC.TAX.TOTL.GD.ZS` (tax revenue), `GC.XPN.TOTL.GD.ZS` (expenditure), `GC.REV.XGRT.GD.ZS` (revenue), `NY.GNS.ICTR.ZS` (gross savings). Fiscal balance already available via `GC.BAL.CASH.GD.ZS` (already in `country_risk_service.py`).
- **Why implementable:** 4 new WB indicator codes. The `r-g` comparison uses GDP growth (already mapped) vs effective interest rate (already in `policy_service.py` / `rates_service.py`). Router pattern is identical to existing macro tabs.

### P1 — Labor Market Deep Dive Tab

Expand beyond headline unemployment to include labor force participation rate, youth unemployment
(ages 15-24), employment-to-population ratio, vulnerable employment share, and informal employment
estimates. US wage growth via FRED average hourly earnings. Cross-country productivity comparison
(GDP per employed person).

- **Data:** World Bank `SL.TLF.CACT.ZS` (LFPR), `SL.UEM.1524.ZS` (youth unemployment), `SL.EMP.TOTL.SP.ZS` (employment/population), `SL.EMP.VULN.ZS` (vulnerable employment), `SL.GDP.PCAP.EM.KD` (GDP per employed person). FRED `AHETPI` (average hourly earnings) and `OPHNFB` (nonfarm productivity).
- **Why implementable:** 5 new WB codes + 2 FRED series IDs. Can be built as a new tab in the existing `/macro` page using the same `MacroTabShell` pattern (add entry to `TABS` array, lazy-load new component).

### P1 — Energy Transition & Climate Economics Tab

CO2 emissions per capita, renewable energy share of consumption, fossil fuel dependency, energy
imports as % of energy use, and oil/gas/coal rents as % of GDP. Compare climate vulnerability vs
fiscal capacity to respond. Track progress toward Paris Agreement implied targets.

- **Data:** World Bank `EN.ATM.CO2E.PC` (CO2 per capita), `EG.FEC.RNEW.ZS` (renewable share), `EG.IMP.CONS.ZS` (energy imports), `NY.GDP.PETR.RT.ZS` (oil rents), `NY.GDP.NGAS.RT.ZS` (gas rents), `NY.GDP.COAL.RT.ZS` (coal rents).
- **Why implementable:** 6 new WB codes. All are annual country-level data. Same pattern as existing macro tabs. Energy transition is a high-demand topic with no current coverage in the app.

### P1 — Inequality & Development Tab

Gini coefficient, income share held by top 10% / bottom 40%, poverty headcount ratios at $2.15,
$3.65, and $6.85/day (World Bank international poverty lines), and GDP per capita (already mapped).
Lorenz curve visualization per country with decade-over-decade comparison.

- **Data:** World Bank `SI.POV.GINI` (Gini), `SI.DST.10TH.10` / `SI.DST.FRST.10` (income decile shares), `SI.POV.DDAY` ($2.15 poverty), `SI.POV.LMIC` ($3.65), `SI.POV.UMIC` ($6.85). GDP per capita already mapped via `NY.GDP.PCAP.KD`.
- **Why implementable:** 5 new WB codes. Coverage is spottier than macro indicators (Gini may have gaps for some developing countries) but sufficient for major economies and aggregate trends. Lorenz curve is a straightforward cumulative distribution chart.

### P2 — Business Dynamism Tab

New business formation density (registrations per 1,000 working-age population), private sector
credit growth, and historical Doing Business scores (discontinued in 2021 but historical data
available). Track entrepreneurship as a leading indicator for employment growth.

- **Data:** World Bank `IC.BUS.NDNS.ZS` (new business density), `IC.REG.DURS` (time to start business). Historical Doing Business data can be loaded as static JSON (the World Bank still hosts historical CSV exports).
- **Why implementable:** 2 new WB codes + static JSON for Doing Business historical data. Coverage may be limited (new business density is not reported for all countries annually), so this is P2.

---

## 3. 🛠️ New Tools & Analytical Models

### P0 — Insider Trading Aggregator

EDGAR Form 4 data is already fetched per-ticker on the Markets page. Aggregate across the entire
market: compute insider buy/sell ratio, detect cluster buying (≥3 insiders buying the same stock
within 30 days), sector-level insider sentiment scores, and a "smart money" index tracking
aggregate insider behavior vs subsequent market returns.

- **Data:** Form 4 filings already fetched via `edgar_service.py` (`_fetch_form4_sync`). Existing endpoint at `GET /api/market/form4?ticker=`. Needs a new aggregation router.
- **Why implementable:** The per-ticker EDGAR pipeline is proven. Aggregation requires a new router endpoint that iterates over a universe (e.g., S&P 500) with rate limiting. The buy/sell ratio is a simple count. Cluster detection is a date-range join. This is a high-value feature with zero new data sources.

### P1 — Currency Crisis Early Warning System

Composite early warning model using: foreign reserves decline rate (already in country risk),
current account deficit (already mapped), real exchange rate overvaluation (BIS effective FX +
Frankfurter spot), inflation (already mapped), and short-term external debt. Output: traffic-light
warning (green/yellow/red) per country with contributing factor breakdown.

- **Data:** All inputs already in the pipeline — reserves via `FI.RES.TOTL.CD` (country risk), current account via `BN.CAB.XOKA.GD.ZS` (atlas/macro), effective FX via BIS (source_bis.py), inflation via `FP.CPI.TOTL.ZG` (atlas/macro). Short-term debt as % of total external debt via WB `DT.DOD.DSTC.ZS`.
- **Why implementable:** Pure model logic. Only one new WB code needed (short-term debt share). The methodology follows well-known academic early warning literature (Kaminsky, Lizondo & Reinhart 1998; IMF Vulnerability Exercises).

### P1 — Sector DuPont Analysis

Decompose ROE into three drivers — net profit margin × asset turnover × equity multiplier — for
every sector using aggregated yfinance financials. Visualize which sectors drive ROE through margin
efficiency vs leverage vs asset utilization. Spot leverage buildups before they become systemic.

- **Data:** yfinance financials for all S&P 500 constituents (constituent list already in `constituents.py`). Net income, revenue, total assets, and shareholder equity are all standard yfinance fields. Sector mapping already exists in `sector_service.py`.
- **Why implementable:** DuPont formula is trivial arithmetic. Aggregation by sector is a GROUP BY on existing screener data. The screener cache already warms fundamentals for the S&P 500 universe.

### P2 — Sovereign Default Probability Model

Logistic regression or probit model trained on historical sovereign default data (Reinhart &
Rogoff dataset, available as academic CSV). Predictors: debt/GDP, fiscal balance, current account,
inflation, reserves/imports ratio, and GDP growth. Output: implied 1-year and 5-year default
probability for each country with confidence bands.

- **Data:** Predictors all available from World Bank/IMF (already mapped). Training data from Reinhart & Rogoff "This Time Is Different" dataset (publicly available CSV from Carmen Reinhart's website, ~70KB). Model fitting uses scipy/numpy only (consistent with Econ Lab's no-statsmodels rule).
- **Why implementable:** True P2 because it needs a new static CSV file loaded and a nontrivial model fitting pipeline. But all predictor data is already in the system, the training dataset is tiny and freely available, and the Econ Lab already proves scipy-only regression works.

### P2 — M&A / Corporate Actions Tracker

Dashboard tracking announced M&A deals, deal values, acquisition premiums, and sector M&A activity
heatmap. Calendar of upcoming shareholder meetings and corporate actions.

- **Data:** Finnhub has some M&A news via `/news?category=merger` and corporate actions. The existing news feed on Markets page already pulls Finnhub general news.
- **Why implementable:** Extends existing Finnhub news pipeline. Coverage may be incomplete vs paid services (Bloomberg, FactSet) but sufficient for trending analysis. Finnhub M&A data quality is the main uncertainty, hence P2.

---

## 4. 🔧 Enhancements (Expand Existing Pages)

### ✅ P0 — BIS Property Prices → Housing Tab — **DONE (Phase 25)**

BIS residential property price data is already downloaded via `WS_SPP_csv_flat.zip` in
`source_bis.py`. Wire it to the existing Housing tab on `/macro` for global house price
comparison. Add nominal and real (CPI-deflated) house price indices for 50+ countries with
long-term trends and bubble detection (price-to-rent and price-to-income deviation from trend).

- **Data:** BIS property price data already in the pipeline but never exposed via any router. CPI data already mapped for deflation. FRED US housing data already in Housing tab.
- **Why implementable:** Pure wiring task. New `source_bis.get_property_prices()` function → router endpoint → Housing tab component. Zero new data downloads.

### ✅ P0 — BIS Credit Gaps → Financial Conditions Tab — **DONE (Phase 25)**

BIS credit-to-GDP gaps are already downloaded via `WS_CREDIT_GAP_csv_flat.zip` in `source_bis.py`.
Add a credit gap gauge to the Financial & Funding Conditions tab. BIS methodology flags gaps above
10 percentage points as elevated systemic risk. Show a country-by-country gap heatmap.

- **Data:** Credit gap data already in pipeline. Existing Financial Conditions tab already shows IG/HY OAS, funding spreads — credit gaps are the natural complement.
- **Why implementable:** Pure wiring. New `source_bis.get_credit_gaps()` function → endpoint → add panel to `FinancialConditions.tsx`.

### P1 — Government Bond Global Comparison → `/yield`

Expand `/yield` beyond US Treasuries to show 10Y government bond yields for 20+ countries. Build a
yield spread matrix (each country vs US, vs Germany, vs Japan). Show real yields (nominal minus
inflation) using already-mapped CPI data. Track yield curve slopes across countries.

- **Data:** FRED has G7 10Y yields (`IRLTLT01` OECD series, or country-specific series like `GBRTLT01`, `JPNTLT01`). BIS has broader government bond yield data. ECB has euro area yields via ecbdata. Frankfurter can provide FX context.
- **Why implementable:** ~10 new FRED series IDs. The existing `/yield` page already has US spot curve rendering — adding more countries is the same pattern with a country selector.

### P1 — Inflation Expectations → Inflation Tab

Add 5Y/5Y forward inflation swap rate, breakeven inflation rates (already partially in `/yield`),
University of Michigan survey inflation expectations, and NY Fed consumer expectations survey.
Compare market-implied vs survey-implied inflation for divergence signals (markets pricing
different inflation than consumers expect).

- **Data:** FRED `T5YIFR` (5Y/5Y forward), `T10YIE` (10Y breakeven), `MICH` (Michigan 5Y expectations), NY Fed survey data (available via FRED or direct CSV from NY Fed website).
- **Why implementable:** 3 new FRED series IDs. The existing Inflation tab already has CPI and PCE charts — adding expectations is a natural extension panel. Divergence analysis is a simple subtraction.

### P1 — Supply Chain Vulnerability → Atlas Overlay

Compute import concentration (Herfindahl index of import partners), food import dependency, and
energy import dependency per country. Add as a new Atlas map layer. Identify countries vulnerable
to trade disruptions based on concentrated import sources and essential goods dependency.

- **Data:** World Bank trade indicators (already partially mapped). Bilateral trade data from IMF Direction of Trade Statistics (DOTS) if available via imfp, or computed from WB merchandise trade data. Food import share via `TM.VAL.FOOD.ZS.UN` and fuel import share via `TM.VAL.FUEL.ZS.UN`.
- **Why implementable:** The Atlas already has 6 map layers with the year slider — adding a 7th is a straightforward extension. Trade concentration needs bilateral data which may require IMF DOTS exploration (the main P1 uncertainty), but the food/fuel import shares are direct WB indicators.

### P2 — Demographics Overlay → Atlas

Population growth (already mapped), age dependency ratio, urbanization rate, and life expectancy
as new Atlas map layers. Long-term pension sustainability heatmap combining old-age dependency
ratio with fiscal capacity. Population projection overlays for 2030/2050.

- **Data:** World Bank `SP.POP.DPND` (age dependency), `SP.URB.TOTL.IN.ZS` (urbanization), `SP.DYN.LE00.IN` (life expectancy), `SP.POP.GROW` (population growth — already mapped? Check). Population growth is `SP.POP.TOTL` (total population) which is already mapped in `INDICATOR_MAP`.
- **Why implementable:** 3 new WB codes. Atlas layer extension is proven pattern. Population projections could use UN World Population Prospects (free CSV download) as a one-time static data load.

### P2 — Short Interest Dashboard → Markets Panel

Show most-shorted stocks (highest % of float short), short squeeze candidates (high short interest
+ high borrow cost + small float), and sector aggregate short interest trends. Overlay with options
data for gamma squeeze detection.

- **Data:** Finnhub has short interest via `/stock/short-interest`. yfinance may provide short interest in `.info` dict. Borrow cost data is harder — may need Finnhub or be limited.
- **Why implementable:** Finnhub short interest endpoint is straightforward. Coverage quality is the main uncertainty (Finnhub free tier limitations), hence P2. Options data is already extensive in `/options` page.

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

## Summary Matrix

| # | Idea | Category | Priority | New Data Needed? | Effort | Status |
|---|------|----------|----------|------------------|--------|--------|
| 1 | Trade Flows & Globalization | New Page | P0 | No — 3 new WB codes | Medium | ✅ DONE Phase 26 |
| 2 | Corporate Health Monitor | New Page | P0 | No — yfinance financials | Medium | ✅ DONE Phase 27 |
| 3 | Dividend Analysis | New Page | P1 | No — yfinance dividends | Small | ✅ DONE Phase 27 |
|| 4 | Banking & Financial Stability | New Page | P1 | No — WB codes + BIS wiring | Large | ✅ DONE Phase 31 |
|| 5 | Cross-Border Finance | New Page | P2 | BIS LBS ZIP (fallback: WB trade) | Large | ✅ DONE Phase 31 |
| 6 | Fiscal Sustainability | Macro Tab | P0 | No — 4 new WB codes | Small | ✅ DONE Phase 25 |
| 7 | Labor Market Deep Dive | Macro Tab | P1 | 5 WB codes + 2 FRED | Medium | |
| 8 | Energy Transition & Climate | Macro Tab | P1 | 6 new WB codes | Medium | |
| 9 | Inequality & Development | Macro Tab | P1 | 5 new WB codes | Medium | |
| 10 | Business Dynamism | Macro Tab | P2 | 2 WB codes + static JSON | Small | ✅ DONE Phase 30 |
| 11 | Insider Trading Aggregator | Tool | P0 | No — aggregate existing data | Medium | ✅ DONE Phase 27 |
| 12 | Currency Crisis Early Warning | Tool | P1 | 1 new WB code | Medium | |
| 13 | Sector DuPont Analysis | Tool | P1 | No — existing screener data | Small | ✅ DONE Phase 27 |
|| 14 | Sovereign Default Model | Tool | P2 | Bundled RR data + scipy logit | Large | ✅ DONE Phase 31 |
| 15 | M&A / Corporate Actions | Tool | P2 | Finnhub endpoint check | Small | ✅ DONE Phase 30 |
| 16 | BIS Property → Housing Tab | Enhance | P0 | No — BIS data already downloaded | Small | ✅ DONE Phase 25 |
| 17 | BIS Credit Gaps → Financial Tab | Enhance | P0 | No — BIS data already downloaded | Small | ✅ DONE Phase 25 |
| 18 | Global Bond Yields → /yield | Enhance | P1 | ~10 FRED series IDs | Medium | |
| 19 | Inflation Expectations → Inflation Tab | Enhance | P1 | 3 FRED series IDs | Small | ✅ DONE Phase 27 |
| 20 | Supply Chain → Atlas Overlay | Enhance | P1 | 2 WB codes + bilateral data | Medium | |
| 21 | Demographics → Atlas Overlay | Enhance | P2 | 3 WB codes + UN projections | Medium | ✅ DONE Phase 30 |
| 22 | Short Interest → Markets Panel | Enhance | P2 | Finnhub endpoint | Small | ✅ DONE Phase 30 |

**Completed:** 16/22 · **Remaining:** 6 (1 P0 · 5 P1 · 0 P2)
