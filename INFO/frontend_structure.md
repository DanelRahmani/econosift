# Axiom Finance — Frontend File Structure

Root: `frontend/`

```
frontend/
├── Dockerfile                  # Multi-stage build: npm install → next build → next start
├── next.config.js              # Next.js config (API rewrites to backend)
├── tailwind.config.ts          # Tailwind theme + dark mode config
├── tsconfig.json               # TypeScript compiler options
├── postcss.config.js           # PostCSS pipeline (Tailwind + Autoprefixer)
├── playwright.config.ts        # E2E test config (base URL, browser)
├── package.json                # Dependencies and npm scripts
│
├── app/                        # Next.js 14 App Router — one folder = one page
│   ├── layout.tsx              # Root layout: ThemeProvider, Navbar, MobileNav
│   ├── globals.css             # Tailwind base imports + global CSS vars
│   ├── page.tsx                # Root redirect (→ /dashboard)
│   ├── dashboard/page.tsx      # /dashboard — market overview landing page
│   ├── markets/page.tsx        # /markets — stock analysis (price, valuation, risk, ratios…)
│   ├── macro/page.tsx          # /macro — 10-tab macroeconomic intelligence hub
│   ├── screener/page.tsx       # /screener — stock screener with preset signals
│   ├── treemap/page.tsx        # /treemap — S&P 500 / NDX / Dow squarified treemap
│   ├── calendar/page.tsx       # /calendar — earnings, macro, IPO, dividend calendar
│   ├── risk/page.tsx           # /risk — rolling metrics, GARCH, stress tests, Monte Carlo
│   ├── options/page.tsx        # /options — IV analytics, Greeks, option chain
│   ├── sectors/page.tsx        # /sectors — sector performance, rotation clock, drill-down
│   ├── portfolio/page.tsx      # /portfolio — portfolio analytics, optimisation, attribution
│   └── admin/page.tsx          # /admin — backend health dashboard (cache, sources, latency)
│
├── components/                 # Shared + feature React components
│   ├── Navbar.tsx              # Desktop top navigation bar
│   ├── MobileNav.tsx           # Mobile bottom tab bar
│   ├── SearchBar.tsx           # Global ticker search with autocomplete
│   ├── ThemeProvider.tsx       # Dark/light theme context + localStorage persistence
│   ├── ThemeToggle.tsx         # Sun/moon toggle button
│   ├── Watchlist.tsx           # Pinned ticker watchlist with price alerts
│   ├── ui.tsx                  # Shared primitive components (Card, Badge, Spinner…)
│   │
│   ├── dashboard/              # /dashboard page components
│   │   ├── BreadthBar.tsx      # Market breadth visualisation (advance/decline)
│   │   ├── FearGreedGauge.tsx  # 7-signal Fear & Greed index gauge
│   │   ├── GlobalIndices.tsx   # ~25 global indices table
│   │   └── TopMovers.tsx       # Top gainers / losers cards
│   │
│   ├── markets/                # /markets page components
│   │   ├── PriceChart.tsx      # OHLCV candlestick / line chart with SMA overlays
│   │   ├── QuoteCards.tsx      # KPI strip (price, change, volume, 52W range)
│   │   ├── ValuationTab.tsx    # Valuation tab shell (DCF, CAPM, composite)
│   │   ├── ValuationEngine.tsx # 8-model valuation grid
│   │   ├── ValuationModelsGrid.tsx  # Individual model cards
│   │   ├── ValuationKpiPanel.tsx    # Valuation KPI summary strip
│   │   ├── DcfPanel.tsx        # Two-stage DCF detail panel
│   │   ├── SnowflakeChart.tsx  # Pentagon radar (Value/Growth/Performance/Health/Dividend)
│   │   ├── SnowflakeMini.tsx   # Compact 100×100 radar for screener cards
│   │   ├── AxiomGauge.tsx      # Composite score dial
│   │   ├── RatiosTab.tsx       # 23 financial ratios with colour-coding + guide
│   │   ├── RiskMetricsTable.tsx     # VaR, Sharpe, Beta, Sortino display
│   │   ├── CorrelationMatrix.tsx    # Pairwise correlation heatmap
│   │   ├── FxRatesPanel.tsx    # FX rates relative to selected base currency
│   │   ├── AnalystPanel.tsx    # Analyst ratings + price targets
│   │   ├── InstitutionalHolders.tsx # Top 13F institutional holders
│   │   ├── InsiderActivity.tsx      # Form 4 insider buy/sell transactions
│   │   ├── NewsFeed.tsx        # Ticker news with keyword sentiment scoring
│   │   ├── SectorHeatmap.tsx   # Intraday sector ETF heatmap
│   │   ├── Treemap.tsx         # Embedded treemap for markets context
│   │   ├── RankingsTab.tsx     # Relative strength rankings tab
│   │   ├── ScreenerTab.tsx     # Inline screener tab
│   │   └── PortfolioTab.tsx    # Quick portfolio view tab
│   │
│   ├── macro/                  # /macro page components (10 sub-tabs)
│   │   ├── MacroTabShell.tsx   # Tab shell + sub-tab routing
│   │   ├── MacroDashboard.tsx  # Main macro page orchestrator
│   │   ├── MacroOverview.tsx   # Overview sub-tab
│   │   ├── MacroChart.tsx      # Generic macro time-series chart
│   │   ├── CountrySelector.tsx # Country picker dropdown
│   │   ├── IndicatorSelector.tsx    # Indicator picker
│   │   ├── CountryComparison.tsx    # Side-by-side country cards
│   │   ├── RegimeClock.tsx     # Macro regime clock visualisation
│   │   ├── RegimeDetector.tsx  # Rules-engine regime badge
│   │   ├── YieldCurve.tsx      # Full yield curve + inversion badge
│   │   ├── FxWidget.tsx        # FX rates widget
│   │   ├── FxTab.tsx           # FX heatmap + PPP valuation sub-tab
│   │   ├── InflationHeatmap.tsx     # Country × year CPI heatmap
│   │   ├── InflationTab.tsx    # CPI/PCE/PPI/M2 sub-tab
│   │   ├── GrowthEmployment.tsx     # Sahm Rule, JOLTS, industrial production
│   │   ├── HousingTab.tsx      # Case-Shiller, starts, mortgage sub-tab
│   │   ├── CommoditiesTab.tsx  # ~25 futures + Bitcoin table
│   │   ├── RatesYields.tsx     # Rates & Yields sub-tab
│   │   ├── LeadingIndicators.tsx    # LEI/CLI/CFNAI/PMI + IS-LM-PC panels
│   │   ├── FinancialConditions.tsx  # NFCI/STLFSI4/Fed balance sheet
│   │   └── PositioningTab.tsx  # COT report — speculator positioning
│   │
│   ├── screener/               # /screener page components
│   │   ├── PresetPills.tsx     # 20+ signal preset pill buttons
│   │   ├── ScreenerTable.tsx   # Results data table
│   │   ├── ResultTabs.tsx      # 9 result view tabs
│   │   └── Sparkline.tsx       # Canvas 200×120 sparkline gallery
│   │
│   ├── calendar/               # /calendar page components
│   │   ├── CalendarGrid.tsx    # Weekly Mon–Sun event grid
│   │   ├── CalendarFilters.tsx # Category, impact, country, timezone filters
│   │   └── EventCard.tsx       # Individual event card with countdown
│   │
│   ├── risk/                   # /risk page components
│   │   ├── RiskKPIRow.tsx      # KPI summary strip
│   │   ├── RollingMetricsChart.tsx  # Rolling Sharpe/Vol/Beta/etc. time series
│   │   ├── ExtendedRiskTable.tsx    # Calmar, Omega, Treynor, Jensen's Alpha…
│   │   ├── CorrelationHeatmap.tsx   # Rolling pairwise heatmap + date scrubber
│   │   ├── OnDemandRisk.tsx    # GARCH / Hurst / OU / cointegration panel
│   │   ├── MonteCarloPanel.tsx # GBM Monte Carlo VaR histogram
│   │   └── StressTestPanel.tsx # Historical stress test scenarios
│   │
│   ├── options/                # /options page components
│   │   ├── IVKPIRow.tsx        # IV30, IV Rank, IV Pct, Max Pain KPI strip
│   │   ├── IVTermStructure.tsx # IV vs DTE term structure chart
│   │   ├── IVSmile.tsx         # IV smile (moneyness 0.70–1.30)
│   │   ├── OIProfileChart.tsx  # Open interest profile + Max Pain line
│   │   ├── ChainTable.tsx      # Option chain: Calls | Strikes | Puts
│   │   └── MonteCarloOptions.tsx    # 10k GBM path options pricing histogram
│   │
│   ├── sectors/                # /sectors page components
│   │   ├── SectorReturnsChart.tsx   # Sorted horizontal bar chart by period
│   │   ├── SectorFundamentalsTable.tsx  # P/E, P/B, yield, beta, vol table
│   │   ├── SectorRotationClock.tsx  # Stovall 4-phase rotation bubble chart
│   │   └── SectorIndustryDrillDown.tsx  # Top-3 stocks per GICS industry
│   │
│   └── portfolio/              # /portfolio page components
│       ├── PortfolioInput.tsx  # Holdings entry form (ticker + weight/shares)
│       ├── PortfolioKPIs.tsx   # Return, Sharpe, max drawdown KPI strip
│       ├── PerformanceChart.tsx     # Cumulative return vs SPY + AGG
│       ├── DrawdownChart.tsx   # Underwater drawdown curve
│       ├── HoldingsTable.tsx   # Weight / return / contribution table
│       ├── CorrelationHeatmap.tsx   # NxN correlation heatmap
│       ├── RiskContribution.tsx     # Variance risk-contribution bars
│       ├── RollingMetrics.tsx  # Rolling Sharpe/Vol/Beta with window selector
│       ├── CAPMAttribution.tsx # Alpha, beta, R², systematic vs idiosyncratic
│       ├── KellyTable.tsx      # Kelly criterion position sizing table
│       ├── FFAttribution.tsx   # Fama-French FF3/FF5 factor loadings
│       ├── EfficientFrontier.tsx    # SLSQP frontier + max-Sharpe star
│       ├── MonteCarlo.tsx      # 10k Dirichlet random-weight cloud
│       ├── BlackLitterman.tsx  # BL posterior returns + optimal weights form
│       └── StressTesting.tsx   # Portfolio stress test across 4 scenarios
│
└── lib/                        # Shared utilities and types
    ├── api.ts                  # All backend API calls (typed fetch wrappers)
    ├── types.ts                # Shared TypeScript interfaces and types
    ├── ratioGuide.ts           # Per-ratio explanations + Good/Average/Caution ranges
    └── format.ts               # Number and date formatting helpers
```
