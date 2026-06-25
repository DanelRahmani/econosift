# Axiom Finance – Project Ideas

This file lists high-impact feature ideas for evolving Axiom Finance into a global hub for financial and economic metrics, from beginner-friendly ratios to advanced macroeconomic and econometric models.[cite:10][cite:37][cite:39]

## Feature Ideas

### High-Impact / Core Enhancements

1. **Portfolio Builder & Tracker**
   Allow users to create a named portfolio by adding multiple tickers with share counts or weights. Show aggregate performance, total P&L, weighted risk metrics, and a portfolio-level Sharpe ratio. Persist portfolios in localStorage or a lightweight SQLite backend.

2. **Earnings Calendar & Event Overlay**
   Surface upcoming earnings dates, dividend ex-dates, and stock splits directly on the price chart as vertical event markers. yfinance already provides this data via `ticker.calendar` and `ticker.dividends`.

3. **Sector & Industry Heatmap**
   A color-coded grid (red/green) showing intraday or weekly performance by S&P 500 sector, similar to Finviz. Use yfinance sector ETFs (XLK, XLF, XLE, etc.) as proxies. Gives users an instant macro-to-micro view.

4. **Watchlist with Price Alerts**
   A persistent watchlist panel where users can pin tickers and set price-level or percentage-change alerts. Alerts could trigger browser notifications (Notifications API) or write to a local log.

5. **Technical Indicators on Price Chart**
   Add toggleable overlays: SMA (20/50/200), EMA, Bollinger Bands, RSI (sub-chart), MACD. All computable from existing OHLCV data without new dependencies (or add `pandas-ta`).

---

### Analytics & Intelligence

6. **AI-Powered Company Summary**
   On the Markets page, add a "Summarize" button that calls the Claude API (claude-sonnet-4-6) with the company's financial ratios, valuation signals, and risk metrics and returns a plain-English analyst-style paragraph. Great for non-technical users.

7. **Multi-Factor Screening**
   A stock screener where users set filters (P/E < 15, Debt/Equity < 0.5, Sharpe > 1, etc.) against a user-defined universe of tickers. Returns a ranked table. Runs entirely on the existing `/api/ratios` and `/api/market/risk` endpoints.

8. **Macro Regime Detector**
   Classify the current macro environment (expansion, slowdown, stagflation, recession) using a simple rules engine over GDP growth, CPI, and unemployment for a selected country. Display a color-coded "regime badge" on the Macro page.

9. **Relative Strength Rankings**
   Rank a basket of tickers by rolling 1/3/6-month returns, normalized vs. their benchmark. Useful for momentum-based screening. Extend the `/api/market/prices` endpoint to accept multiple tickers and return a sorted ranking.

10. **News Feed Integration**
    Pull recent news headlines per ticker from a free source (Yahoo Finance RSS via yfinance `ticker.news`, or GNews free tier). Display as a sidebar panel on the Markets page with sentiment scoring (positive/neutral/negative) using a lightweight keyword classifier.

---

### Macro Enhancements

11. **Country Comparison Cards**
    A side-by-side snapshot card view for any two selected countries showing all 9 macro indicators at once, with traffic-light coloring (green = healthy, yellow = watch, red = warning) based on configurable thresholds.

12. **Yield Curve Visualizer**
    Plot the full government bond yield curve (2Y, 5Y, 10Y, 30Y) for US, EU, and UK using FRED and ECB data. Show inversion detection (2Y > 10Y) as a warning badge — historically a recession signal.

13. **Macro Indicator Forecasts**
    Pull IMF World Economic Outlook projections (already partially available via imfp) and overlay forecast lines on existing historical charts with a dashed style.

14. **Global Inflation Comparison Heatmap**
    A year-by-year heatmap grid (countries × years) for CPI inflation, color-coded from low (blue) to high (red). Instantly surfaces which countries have chronic inflation problems.

---

### UX / Developer Experience

15. **Shareable URLs / Deep Linking**
    Encode the current dashboard state (selected tickers, time period, active tab) in the URL query string. Users can bookmark or share a specific view without re-entering inputs.

16. **Export to CSV / PDF**
    Add an export button on the Risk Metrics and Ratios tabs. CSV for data; PDF using browser `window.print()` with a print-optimized stylesheet. No additional dependencies needed.

17. **Dark/Light Theme Persistence**
    Currently the theme toggle likely resets on page reload. Persist the preference in `localStorage` so the chosen theme survives refreshes.

18. **Backend Health Dashboard**
    An `/admin` page showing cache hit rates, data-source success/failure counts per macro source, and API response time percentiles. Useful for debugging which fallback sources are actually firing.

19. **Configurable Benchmark Override**
    Let users manually override the auto-detected benchmark (e.g., compare AAPL to ^NDX instead of ^GSPC) via a UI dropdown on the Markets page. The backend already supports arbitrary benchmark tickers.

20. **Mobile Bottom Navigation**
    Replace the top navbar with a fixed bottom tab bar on small screens (Markets | Macro | Watchlist) for better mobile ergonomics. Tailwind's responsive utilities make this straightforward.

---

## 1. Global Macro Atlas

- **Interactive world map macro dashboard**: Choropleth map where users can select indicators (GDP growth, CPI inflation, unemployment, policy rate, debt/GDP, current account, FX regimes) and view them by country, with tooltips showing trends and distributions.[cite:10][cite:37]
- **Multi-layer indicator overlays**: Ability to overlay two indicators (e.g., GDP growth and inflation) on the map, with bivariate color schemes to show stagflation vs Goldilocks regimes.
- **Temporal slider for macro series**: Time slider to animate macro indicators on the map over years or quarters, showing business cycle evolution.
- **Regional aggregation**: Region toggles (G7, Eurozone, EM Asia, LatAm, Africa) that compute regional averages or medians on the fly.[cite:10]

## 2. Macro Modeling & IS-LM-PC Suite

- **IS-LM-PC interactive tri-panel**: Visual IS curve, LM curve, and Phillips curve with sliders for fiscal stance, monetary stance, and expectations, backed by FRED/OECD data rather than toy numbers.[cite:10]
- **Scenario builder for macro shocks**: User interface to apply shocks (e.g., fiscal expansion, monetary tightening, supply shock) and see how equilibrium output, interest rates, and inflation paths change over time.
- **Automatic regime classification**: Use GDP growth and inflation data to classify regimes (Goldilocks, Overheating, Stagflation, Recession) across countries and overlay them on the world map.[cite:10]
- **Macro policy analysis tools**: Simple calculators for Taylor rule implied rates, output gap estimates, and fiscal impulse, with visual comparisons to actual policy paths.[cite:10]

## 3. Econometric Lab

- **One-click regression workspace**: Panel where users can choose a dependent variable (e.g., unemployment rate, GDP per capita, equity returns) and regress it on selected explanatory variables (inflation, policy rate, debt, demographics) using OLS, with options for log transforms and lag structures.[cite:10][cite:42]
- **Model comparison dashboard**: Side-by-side metrics (R², adjusted R², AIC/BIC, residual diagnostics) for several candidate models, to teach users trade-offs between parsimonious and complex specifications.
- **Nation production function estimator**: Cobb-Douglas or CES production function estimation for selected countries, using capital stock proxies, labor force data, and TFP, with visual decomposition of growth contributions.
- **Panel data tools**: Fixed effects and random effects models for multi-country, multi-period datasets (e.g., growth regressions, debt and growth relationships).

## 4. Cross-Asset & Factor Analytics

- **Global factor explorer**: Integrate Fama-French and other factor libraries to show factor premia across time and geographies, with country and sector breakdowns.[cite:10]
- **Custom factor construction**: Allow users to define their own factors (e.g., quality, low volatility, momentum) and backtest them across universes, with automated portfolio formation and performance visualization.[cite:10][cite:135]
- **FX and commodity macro-link panel**: Explore relationships between FX pairs, commodity prices (oil, gold, copper, wheat), and macro indicators (inflation, growth, terms of trade).[cite:10]
- **Cross-asset correlation heatmaps**: Dynamic correlation matrices between equities, bonds, FX, commodities, and crypto over adjustable rolling windows.[cite:10]

## 5. Multi-Scale Portfolio Intelligence

- **Multi-country portfolio builder**: Let users allocate across equities, bonds, FX, and commodities with country weights, then compute portfolio risk and return metrics, including currency-adjusted results.[cite:10]
- **Macro-tilted portfolio analysis**: Tools to show how portfolios perform under different macro scenarios (e.g., rising rates, high inflation, growth slowdown) using historical episodes and scenario simulations.[cite:10]
- **Factor attribution for portfolios**: Attribute portfolio returns to systematic factors (value, size, momentum, quality) and macro drivers (GDP growth, inflation surprises).[cite:10][cite:124]

## 6. Learning Layers – From Beginner to Expert

- **Beginner-friendly views**: Simple toggles that switch each panel between starter and advanced views, with explanations and tooltips (e.g., P/E, dividend yield, basic macro definitions).[cite:37]
- **Narrative walkthroughs**: Guided tours explaining what each metric means, why it matters, and how it connects to broader macro and market dynamics.
- **Academic-style notebooks**: Embedded notebooks or report exports showing step-by-step calculations for complex models (IS-LM-PC, production function estimation, factor models) using real data.[cite:10]

## 7. Advanced Risk & Stress Testing Extensions

- **Macro-linked stress tests**: Scenario generator where users can construct stress tests based on historical macro episodes (e.g., 1970s inflation, 2008 crisis, COVID shock) and apply them to portfolios.[cite:10]
- **Country risk dashboards**: Country-specific panels showing sovereign risk metrics (debt/GDP, fiscal deficit, current account, reserves, CDS spreads) and early-warning indicators.[cite:10]
- **Multi-horizon risk metrics**: Expand VaR/CVaR to multiple horizons (1-day to 1-year) and tie them to macro conditions (e.g., volatility regimes, monetary stance).[cite:10]

## 8. Global Policy & Institutional Monitoring

- **Central bank tracker**: Integrated view of policy rates, balance sheet size, and meeting calendars for major central banks, with commentary timelines.[cite:10]
- **Fiscal policy monitor**: Dashboard showing budget balances, debt trajectories, and fiscal impulses across countries, with sustainability indicators.[cite:10]
- **Regulation and institutional events timeline**: Timeline of major regulatory changes, trade agreements, and institutional shocks, linked to economic and market indicators.[cite:10]

## 9. Data Provenance & Meta Analytics

- **Data source explorer**: Interactive catalog of all data series used, with source, frequency, last update, and licensing notes, helping users understand the backbone of the platform.[cite:10]
- **Quality and coverage diagnostics**: Panels that show missing data, coverage gaps, and reliability scores for each country or asset class.[cite:10]
- **Versioned datasets and snapshots**: Ability to freeze datasets at particular dates for reproducible studies and to compare current vs historical views.[cite:10]

## 10. Workflow & Collaboration Features

- **Saved macro and market views**: Let users save custom dashboards (selected indicators, time ranges, countries) and recall them later.[cite:10]
- **Exportable analysis notebooks**: Generate markdown or PDF reports from chosen panels, charts, and models, supporting consulting workflows.[cite:10]
- **Collaboration and sharing**: Allow sharing of dashboard configurations or analysis sessions with colleagues, with embedded explanations.[cite:10]

## 11. Research-Based Trading & Analytics Strategies (New)

### 11.1 Momentum and Cross-Sectional Signal Modules

- **Cross-sectional momentum explorer**: Build tools to sort stocks on prior returns and analyze cross-sectional momentum patterns across universes and horizons, based on asset pricing research.[cite:124][cite:129]
- **Time-series vs cross-sectional momentum comparison**: Implement both time-series momentum (trend following on each asset) and cross-sectional momentum (relative winners vs losers) and compare performance, drawdowns, and regime sensitivity.[cite:129]
- **Left-tail risk and momentum analytics**: Incorporate realized skewness and kurtosis, left-tail risk, and extreme return metrics (MAX/MIN effects) to study how tail risk correlates with future returns, using realized moments literature.[cite:135][cite:122][cite:123]

### 11.2 Risk Parity & Risk-Based Allocation Tools

- **Risk parity portfolio builder**: Module to construct portfolios where risk contributions (rather than capital weights) are balanced across asset classes, using inverse volatility and full covariance-based formulations.[cite:127][cite:133][cite:136]
- **Risk contribution heatmaps**: Visualize per-asset risk contributions in risk parity portfolios and compare to traditional 60/40 allocations, highlighting concentration of equity risk.[cite:127][cite:139]
- **Dynamic risk parity backtester**: Evaluate out-of-sample performance of risk-parity strategies across regimes, including rebalancing effects and leverage, using historical macro and market data.[cite:127][cite:136]

### 11.3 FX Carry & Global Macro Strategies

- **FX carry trade analytics**: Tools to construct and backtest currency carry portfolios (long high-yielding currencies, short low-yielding) using interest rate differentials and forward premia.[cite:131][cite:134][cite:137][cite:140]
- **Carry and risk dashboards**: Panels showing carry returns, drawdowns, and volatility, plus systemic risk indicators and macro conditions that affect carry strategies.[cite:134][cite:140]
- **Multi-asset carry explorer**: Extend carry analysis to fixed income curves, commodities, and volatility products, showing how carry trades behave across assets.

### 11.4 Realized Moments & Volatility Structure

- **Realized moment forecast module**: Use realized variance, skewness, and kurtosis to forecast cross-sectional returns at short horizons, leveraging high-frequency or daily data.[cite:135][cite:138]
- **Volatility and momentum interaction panel**: Combine realized volatility metrics with momentum signals to investigate volatility-managed momentum strategies.[cite:138][cite:129]

### 11.5 Causal Momentum & Network-Based Signals

- **Causal momentum graph analytics**: Build causal graphs (e.g., via Granger causality or transfer entropy) across stocks or macro variables, then compute causal momentum features that aggregate lagged returns of causal drivers.[cite:120]
- **Network-based signal dashboards**: Visualize networks of causally linked assets, highlight hubs, and assess how causal momentum signals compare to traditional momentum in backtests.[cite:120]

### 11.6 Multi-Factor and Machine Learning Models

- **Extended factor model lab**: Beyond Fama-French, include profitability, investment, quality, and other factors, and allow users to estimate multi-factor models for universes and portfolios.[cite:124][cite:125]
- **Cross-sectional ML predictors**: Integrate simple machine learning models (e.g., gradient-boosted trees, random forests) using fundamental, macro, and realized moment features to predict cross-sectional returns and evaluate information coefficients.[cite:124][cite:135]

These research-based modules focus on **analysis and signal exploration**, not direct trading execution, and fit well with Axiom Finance’s role as an advanced analytics and research environment.
