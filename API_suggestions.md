# EconoSift – Free API & Datasource Suggestions (G20, Key Financial Hubs & Research Strategies)

This document lists free APIs and structured datasources (no HTML webscraping) that can support EconoSift’s goal of becoming a global hub for financial and economic metrics, from basic ratios to advanced macro models, econometrics, and research-based trading analytics.[cite:10][cite:37][cite:39]

## 1. G20 Central Bank & Monetary Policy Data

### 1.1 European Central Bank (ECB) – Euro Area (G20 Member: EU)

- **API / Portal**: ECB SDMX 2.1 RESTful web service via the ECB Data Portal.[cite:61]
- **Python access**: Generic SDMX libraries (`sdmx`, `pandasdmx`) or ECB-specific wrappers.[cite:91][cite:96]
- **What you get**:
  - Euro area monetary statistics (policy rates, reserves, money aggregates), yield curves, macro aggregates.[cite:61]
- **Use in EconoSift**:
  - Eurozone monetary policy and yield curve panels (Rates & Yields, Financial Conditions).[cite:10]
  - Carry trade inputs (EUR short rates, yield curve term structure).[cite:140]

### 1.2 De Nederlandsche Bank (DNB) – Netherlands (EU/G20)

- **API / Portal**: DNB Statistics API.[cite:49]
- **Access**: Free registration via My DNB; subscribe to “Public” and “DNB Statistics API”.[cite:49]
- **What you get**:
  - Dutch monetary aggregates, interest rates, payment statistics, financial sector data.
- **Use in EconoSift**:
  - Netherlands central bank dashboards (policy rates, banking metrics).
  - Inputs to Netherlands macro and financial hub panels.

### 1.3 Bank of England (BoE) – United Kingdom

- **API / Datasource**: BoE Interactive Statistical Database CSV endpoints.[cite:62]
- **Python package**: `bank-of-england` (PyPI) – wrapper for BoE IADB.[cite:88]
- **What you get**:
  - Bank Rate, SONIA, gilt yields, exchange rates, mortgage rates, credit and money supply.[cite:62]
- **Use in EconoSift**:
  - UK monetary policy, yield curve, and housing dashboards.
  - FX carry inputs (GBP short rates, curve) and risk-parity bond data.[cite:127][cite:134]

### 1.4 Bank of Japan (BoJ) – Japan

- **API / Portal**: BoJ Time-Series Data Search (CSV/flat files).[cite:57][cite:63]
- **What you get**:
  - Policy rates, price indices, Tankan survey, Flow of Funds, balance of payments.[cite:63]
- **Use in EconoSift**:
  - Japan macro tabs (Growth & Employment, Inflation, Financial Conditions).[cite:10]
  - FX carry inputs (JPY short rates) and macro modeling for IS-LM-PC.[cite:140]

### 1.5 Bank of Canada – Canada

- **API / Portal**: Bank of Canada Valet API.[cite:70][cite:76]
- **Python package**: `pyvalet` – pandas-integrated wrapper.[cite:89]
- **What you get**:
  - FX rates, economic statistics, yields, CPI, monetary aggregates.[cite:70]
- **Use in EconoSift**:
  - Canada macro & monetary dashboards.
  - Risk-parity bond data and FX carry inputs (CAD rates).[cite:127][cite:134]

### 1.6 Banco Central do Brasil (BCB) – Brazil

- **API / Portal**: BCData/SGS time series API and OLINDA expectations API.[cite:68][cite:74][cite:80]
- **Python packages**: `sgs`, `BacenAPI` – wrappers for SGS.[cite:90][cite:95][cite:100]
- **What you get**:
  - Interest rates, FX, credit, activity indices, inflation, expectations.[cite:68][cite:80]
- **Use in EconoSift**:
  - Brazil macro dashboards and expectations panels.
  - Carry trade and global macro strategy inputs (BRL rates, inflation).[cite:131][cite:134]

### 1.7 Reserve Bank of Australia (RBA) – Australia

- **API / Datasource**: RBA statistics tables and CSV data.[cite:69][cite:72][cite:75]
- **What you get**:
  - Policy rates, exchange rates, banking statistics, historical economic data.[cite:69][cite:75]
- **Use in EconoSift**:
  - Australia monetary & FX dashboards.
  - FX carry inputs (AUD short rates, curve) and risk-parity portfolios.[cite:134][cite:127]

### 1.8 People’s Bank of China (PBoC) / China NBS – China

- **API / Datasource**: NBS public data via data.stats.gov.cn (structured endpoints).[cite:52]
- **What you get**:
  - GDP, price indices, money supply, provincial and sectoral stats.[cite:52]
- **Use in EconoSift**:
  - China macro atlas and production function estimation.
  - Carry and macro regime analysis using Chinese policy and macro data.[cite:131][cite:140]

### 1.9 Reserve Bank of India (RBI) – India

- **API / Datasource**: RBI Database on Indian Economy (CSV/Excel).
- **What you get**:
  - Policy rates, monetary aggregates, credit, inflation, external sector.
- **Use in EconoSift**:
  - India macro dashboards and FX carry inputs (INR rates).[cite:134]

### 1.10 South African Reserve Bank (SARB) – South Africa

- **API / Datasource**: SARB statistics and quarterly bulletin data (CSV/Excel).
- **Use in EconoSift**:
  - South Africa macro & monetary panels.
  - EM risk-parity and carry strategy inputs.

### 1.11 Central Bank of the Russian Federation – Russia

- **API / Datasource**: CBR statistics via CSV/XML.
- **Use in EconoSift**:
  - Russia macro and monetary dashboards.
  - FX carry strategies and Russia-specific risk analysis.

### 1.12 Other G20 Members via Global APIs

- **World Bank REST API** – Global indicators (GDP, CPI, unemployment, debt/GDP, etc.) across all G20 countries.[cite:10][cite:58]
- **IMF Data & WEO** – Policy rates, macro aggregates, forecasts.[cite:10]
- **DB.Nomics REST API** – Aggregated series from central banks and NSOs.[cite:10]

These support broad carry trade, macro regime classification, and cross-country econometric analysis.

## 2. Key Financial Hubs – Central Banks & Financial Statistics

### 2.1 Switzerland – Swiss National Bank (SNB)

- **API / Portal**: SNB Data Portal API (`data.snb.ch`).[cite:103][cite:106][cite:109]
- **What you get**:
  - Exchange rates, SNB balance sheet, monetary aggregates, SARON rates, banking statistics, balance of payments.[cite:109]
- **Use in EconoSift**:
  - Switzerland financial hub dashboard (FX, reserves, banking stats).
  - Inputs for global risk-parity and cross-border funding/carry analysis.[cite:133]

### 2.2 Hong Kong – Hong Kong Monetary Authority (HKMA)

- **API / Portal**: HKMA Open API (`api.hkma.gov.hk`).[cite:104][cite:107][cite:116]
- **What you get**:
  - Monetary base, interbank liquidity (HIBOR, daily figures), FX reserves, economic statistics.[cite:107][cite:110][cite:113]
- **Use in EconoSift**:
  - Hong Kong hub dashboard (liquidity, FX, reserves).
  - Carry trade inputs (HKD rates) and hub-specific macro stress tests.[cite:134]

### 2.3 Singapore – Monetary Authority of Singapore (MAS)

- **API / Portal**: MAS statistics and Singapore’s open data portal (`data.gov.sg`) with MAS-sourced datasets.[cite:105][cite:108][cite:111]
- **What you get**:
  - Money supply, exchange rates, SORA, foreign reserves, banking statistics.[cite:105][cite:108]
- **Use in EconoSift**:
  - Singapore financial hub dashboard.
  - FX carry, risk-parity, and systemic risk panels for a key Asian hub.[cite:137]

### 2.4 Netherlands – CBS & DNB

- **CBS Open Data API** – Dutch regional and national statistics.[cite:55]
- **DNB Statistics API** – Central bank monetary and financial sector data (see 1.2).[cite:49]
- **Use in EconoSift**:
  - Detailed Netherlands hub view combining macro, regional, and central bank metrics.

## 3. National Statistical Offices & Global Macro APIs (Non-Central Bank)

These complement central bank data and are critical for econometric lab and macro modeling:

- **Statistics Netherlands (CBS Open Data API)** – Regional/national stats (GDP, income, housing, demographics).[cite:55]
- **World Bank REST API** – Global indicators across many themes.[cite:10][cite:58]
- **OECD.Stat Web Services** – Composite leading indicators, productivity, employment.
- **IMF Data & WEO** – Global macro forecasts and historical aggregates.[cite:10]
- **DB.Nomics REST API** – Unified access to datasets from NSOs, central banks, and international bodies.[cite:10]

## 4. Market Data APIs (Equities, FX, Commodities)

These are the backbone for momentum, realized moments, risk parity, and cross-asset analytics.

- **yfinance** (already implemented) – Yahoo Finance-based data.[cite:5][cite:37]
  - Daily (and some intraday) OHLCV, fundamentals, options, FX, futures.
  - Use for price histories, realized moments (variance/skew/kurtosis), momentum signals, sector performance, and cross-sectional analytics.[cite:135][cite:138]

- **Alpha Vantage** – Free stock/FX/crypto API.[cite:53][cite:59]
  - Intraday and daily OHLCV, technical indicators.
  - Use for higher-frequency realized volatility and realized moment estimates; alternative price source for robustness.[cite:135]

- **IEX Cloud (free tier)** – US equity price and fundamentals.[cite:60]
  - Detailed US market data (including some depth and intraday information) with message-based rate limits.[cite:60]
  - Use for US-centric momentum, cross-sectional factor studies, and robustness checks.[cite:124]

- **Crypto exchanges (e.g., Binance REST API)** – Free REST APIs for crypto OHLCV.
  - Use to extend cross-asset momentum, carry, and risk-parity analyses to digital assets.

## 5. Options, Risk & Factor Data

Essential for risk-parity, volatility, and factor/momentum research.

- **FRED API** (already implemented) – Yields, spreads, macro risk indicators.[cite:5][cite:10]
  - Use for term structure, credit spreads, macro risk variables in carry trade and risk-parity modules.[cite:133][cite:140]

- **Ken French Data Library** (already used) – Factor CSVs (Fama-French 3F/5F).[cite:10]
  - Use for multi-factor labs, risk-adjusted performance evaluation, and momentum/factor interactions.[cite:124][cite:125]

- **CFTC COT ZIP** – Positioning data.[cite:10]
  - Use for positioning overlays on carry trades and macro strategies.

- **BIS, NY Fed datasets** – International banking stats, GSCPI, ACM yield decomposition.[cite:10][cite:140]
  - Use for global systemic risk, financial conditions, and macro-linked stress tests.

## 6. Country-Specific Economic APIs for Research Modules

- **China & Hong Kong** – NBS and HKMA Open API as above.[cite:52][cite:104][cite:107]
- **Singapore** – MAS/data.gov.sg (money/banking and finance & insurance data).[cite:105][cite:108][cite:114]
- **Additional NSOs** – Japan Statistics Bureau, UK ONS, US BEA/BLS via their REST APIs and CSV downloads.

These provide granular inputs for production function estimation, panel data regressions, and cross-country econometric studies.

## 7. APIs Directly Supporting New Research-Based Strategy Modules

The following sources are particularly important for the new project ideas around trading and analytics strategies:

### 7.1 Momentum & Cross-Sectional Signals

- **Daily/intraday OHLCV** via `yfinance`, Alpha Vantage, and IEX Cloud.[cite:5][cite:53][cite:59][cite:60]
  - Required for constructing time-series and cross-sectional momentum signals, realized moments, extreme return metrics (MAX/MIN), and volatility-managed strategies.[cite:124][cite:129][cite:135][cite:138]

- **Factor returns** via Ken French Library.[cite:10]
  - Needed to evaluate factor-adjusted momentum strategies and multi-factor models.[cite:124]

### 7.2 Risk Parity & Risk-Based Allocation

- **Multi-asset price series** via yfinance/Alpha Vantage (equities, bonds via ETFs, commodities, FX).[cite:5][cite:53]
  - Inputs for covariance matrix estimation, per-asset risk contributions, and risk-parity portfolio construction.[cite:127][cite:133]

- **Yield curves & spreads** via FRED, ECB, BoE, SNB, etc.[cite:5][cite:61][cite:109]
  - Enhance bond risk modeling and term-structure-aware risk parity.

### 7.3 FX Carry & Global Macro Strategies

- **FX spot rates and interest differentials** via FRED, central bank APIs (ECB, BoE, BoJ, RBA, BCB, BoC, MAS, HKMA, RBI, SARB, etc.).[cite:61][cite:62][cite:63][cite:68][cite:69][cite:70][cite:105][cite:107]
  - Core inputs to carry trade analytics: forward premia approximations, short rates, yield differentials.[cite:131][cite:134][cite:140]

### 7.4 Realized Moments & Volatility Structure

- **High-frequency or fine-grained OHLCV** via Alpha Vantage and IEX free tiers.[cite:53][cite:59][cite:60]
  - Enables realized variance, skewness, kurtosis and realized moment forecasting modules.[cite:135][cite:138]

### 7.5 Causal Momentum & Network-Based Signals

- **Cross-asset price histories and macro series** via yfinance, FRED, World Bank, ECB, etc.[cite:5][cite:10][cite:61]
  - Necessary to construct Granger causality/transfer entropy graphs and causal momentum signals across stocks and macro variables.[cite:120]

### 7.6 Multi-Factor & Machine Learning Labs

- **Combined datasets** from market data (yfinance/Alpha Vantage/IEX) and macro/factor sources (FRED, World Bank, Ken French, NSOs).[cite:5][cite:10][cite:53][cite:58]
  - Provide feature sets (returns, vol, fundamentals, macro variables, realized moments) for cross-sectional ML predictors and extended factor models.[cite:124][cite:135]

## 8. Already Implemented in EconoSift (Further Suggestions)

These data sources are already part of EconoSift’s current or planned architecture, but can be expanded using some of the ideas in this document:[cite:5][cite:10][cite:37]

- **FRED (Federal Reserve Economic Data)** – US macro series and yields (`FRED_API_KEY` in `.env`).[cite:5][cite:34]
- **World Bank Open Data API** – Global indicators (macro, development).[cite:10]
- **ECB Data** – Euro area statistics (via `ecbdata` and SDMX).[cite:5][cite:61]
- **Finnhub API** – Economic calendar and selected macro/earnings data (`FINNHUB_API_KEY`).[cite:5][cite:34]
- **FinanceDatabase** – Static equity universes and sector classifications.[cite:5][cite:10]
- **Wikipedia MediaWiki API** – Index constituents (S&P 500, Nasdaq 100, Dow 30).[cite:5][cite:10]
- **SEC EDGAR via `edgartools`** – 13F, Form 4, and other filings.[cite:5][cite:10]
- **CFTC and NY Fed datasets** – Positioning and GSCPI/ACM yield curve.[cite:10]
- **Ken French and Damodaran datasets** – Factor returns and ERP/multiples.[cite:10]
- **yfinance** – Market data across equities, ETFs, FX, and commodities.[cite:5][cite:37]

These “already implemented” sources form the backbone of EconoSift. The additional APIs and structured datasets above are sufficient to support the new research-based strategy modules (momentum, risk parity, carry, realized moments, causal momentum, and ML factor labs) while respecting the project’s constraints of **free access and no webscraping**.[cite:10][cite:127][cite:129][cite:134][cite:135][cite:140]