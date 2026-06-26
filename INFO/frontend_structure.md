# Axiom Finance — Frontend File Structure (Phases 0–19)

Root: `frontend/`

```
frontend/
├── Dockerfile                  # Multi-stage build: npm install → next build → next start
├── next.config.js              # Next.js config (API rewrites /api/* → backend:8000)
├── tailwind.config.ts          # Tailwind theme + dark mode config + custom brand palette
├── tsconfig.json               # TypeScript 5.5 strict mode
├── postcss.config.js           # PostCSS pipeline (Tailwind + Autoprefixer)
├── playwright.config.ts        # E2E test config (base URL, browser options)
├── package.json                # Dependencies (next 14.2, react 18.3, recharts, @tanstack/react-query 5, d3)
│
├── app/                        # Next.js 14 App Router — one folder = one page
│   ├── layout.tsx              # Root layout: ThemeProvider, Navbar, MobileNav, providers
│   ├── globals.css             # Tailwind base imports + CSS custom properties (dark/light)
│   ├── page.tsx                # Root redirect (→ /dashboard)
│   │
│   ├── dashboard/page.tsx      # /dashboard — market breadth, global indices, Fear & Greed, top movers
│   ├── markets/page.tsx        # /markets — stock analysis: price chart, tabs (Overview/Risk/
│   │                           #   Technicals/Valuation/Ratios/Portfolio/Rankings/Sectors/Screener/FX)
│   ├── macro/page.tsx          # /macro — 12-tab macroeconomic intelligence hub (+ Lab, Country Risk, CB)
│   ├── screener/page.tsx       # /screener — multi-index stock screener with 20+ preset signals
│   ├── treemap/page.tsx        # /treemap — S&P 500 / NDX / Dow squarified treemap with sector drill-down
│   ├── calendar/page.tsx       # /calendar — earnings, macro, IPO, dividend events
│   ├── risk/page.tsx           # /risk — rolling metrics, GARCH, Hurst, cointegration, stress, MC
│   ├── options/page.tsx        # /options — IV analytics, Greeks, term structure, smile, OI profile
│   ├── sectors/page.tsx        # /sectors — SPDR ETF returns, fundamentals, rotation clock, drill-down
│   ├── portfolio/page.tsx      # /portfolio — performance, correlation, frontier, BL, stress
│   ├── research/page.tsx       # /research — Risk Parity, FX Carry, Momentum, Realized Moments (4 tabs)
│   ├── atlas/page.tsx          # /atlas — world choropleth: 6 macro indicators, year slider, regional blocs
│   ├── yield/page.tsx          # /yield — US spot curve, TIPS real yields, breakevens, ACM term premium
│   ├── policy/page.tsx         # /policy — central bank divergence, G10 carry, policy surprises
│   ├── sovereign/page.tsx      # /sovereign — 6-KPI traffic-light risk rankings, ~200 countries
│   ├── scenario/page.tsx       # /scenario — stress scenario designer (Phase 18B, basic stub)
│   └── admin/page.tsx          # /admin — backend health: cache stats, source health, latency, performance
│
├── components/                 # Shared + feature React components
│   ├── Navbar.tsx              # Desktop top navigation bar (scroll-responsive)
│   ├── MobileNav.tsx           # Mobile bottom tab bar (9 items, scrollable)
│   ├── SearchBar.tsx           # Global ticker search with autocomplete + add-to-watchlist
│   ├── ThemeProvider.tsx       # Dark/light theme context + localStorage persistence
│   ├── ThemeToggle.tsx         # Sun/moon toggle button
│   ├── Watchlist.tsx           # Pinned ticker watchlist with price alerts + remove
│   ├── providers.tsx           # React Query client provider + theme provider wrapper
│   ├── ui.tsx                  # Shared primitives: Card, Badge, Spinner, Skeleton, etc.
│   │
│   ├── dashboard/              # /dashboard page components
│   │   ├── BreadthBar.tsx      # Market breadth: advance/decline, new highs/lows, McClellan
│   │   ├── FearGreedGauge.tsx  # 7-signal Fear & Greed composite index (needle gauge)
│   │   ├── GlobalIndices.tsx   # ~25 global indices table (price, change, YTD)
│   │   └── TopMovers.tsx       # Top gainers / losers cards from screener cache
│   │
│   ├── markets/                # /markets page components
│   │   ├── PriceChart.tsx      # Line chart with period selector + normalised (base 100) toggle
│   │   ├── QuoteCards.tsx      # KPI strip cards (price, name, change%) per ticker
│   │   ├── TabSkeleton.tsx     # Lazy-loading suspense fallback for tabs
│   │   ├── ValuationTab.tsx        # Valuation tab shell (lazy-loaded)
│   │   ├── ValuationEngine.tsx     # 8-model valuation grid
│   │   ├── ValuationModelsGrid.tsx # Individual model cards (DCF, DDM, EPV, etc.)
│   │   ├── ValuationKpiPanel.tsx   # KPI strip: Price, Market Cap, P/E, EPS, Div Yield, 52W, Beta
│   │   ├── DcfPanel.tsx        # Two-stage DCF detail: inputs, scenarios, sensitivity heatmap
│   │   ├── SnowflakeChart.tsx      # 5-axis pentagon radar (Value/Growth/Performance/Health/Dividend)
│   │   ├── SnowflakeMini.tsx   # Compact 100×100 radar for screener cards
│   │   ├── AxiomGauge.tsx      # Composite fair-value gauge (significantly over/undervalued)
│   │   ├── TechnicalsTab.tsx   # Technicals tab (lazy-loaded): SMA, MACD, RSI, BB, Ichimoku, Fib, Pivots
│   │   ├── RatiosTab.tsx       # 23 financial ratios with colour-coding + guide popover
│   │   ├── RiskMetricsTable.tsx    # VaR, Sharpe, Beta, Sortino, Volatility display
│   │   ├── CorrelationMatrix.tsx   # Pairwise correlation heatmap
│   │   ├── FxRatesPanel.tsx    # FX rates relative to selected base currency
│   │   ├── AnalystPanel.tsx    # Analyst ratings + price target band + consensus history
│   │   ├── InstitutionalHolders.tsx # Top 13F institutional holders table
│   │   ├── InsiderActivity.tsx      # Form 4 insider buy/sell transactions table
│   │   ├── NewsFeed.tsx        # Ticker news cards with keyword sentiment (positive/negative/neutral)
│   │   ├── SectorHeatmap.tsx   # Intraday sector ETF performance heatmap (lazy-loaded)
│   │   ├── Treemap.tsx         # Embedded d3-hierarchy treemap with sector colouring
│   │   ├── RankingsTab.tsx     # Relative strength rankings (lazy-loaded)
│   │   ├── ScreenerTab.tsx     # Inline screener with preset filters (lazy-loaded)
│   │   └── PortfolioTab.tsx    # Quick portfolio analysis (lazy-loaded)
│   │
│   ├── macro/                  # /macro page components (12 sub-tabs)
│   │   ├── MacroTabShell.tsx   # Tab shell + sub-tab routing + progressive loading
│   │   ├── MacroDashboard.tsx  # Main macro page orchestrator
│   │   ├── MacroOverview.tsx   # Overview sub-tab: key indicators KPI strip
│   │   ├── MacroChart.tsx      # Generic Recharts time-series (line/area with date range picker)
│   │   ├── CountrySelector.tsx # Multi-select country picker dropdown
│   │   ├── IndicatorSelector.tsx   # Indicator category/series picker
│   │   ├── CountryComparison.tsx   # Side-by-side country KPI cards
│   │   ├── RegimeClock.tsx     # Macro regime clock visualisation (2×2 quadrant)
│   │   ├── RegimeDetector.tsx  # Rules-engine regime badge (expansion/slowdown/stagflation/recession)
│   │   ├── YieldCurve.tsx      # Full yield curve chart + inversion badge
│   │   ├── FxWidget.tsx        # FX rates widget (base/target, live rate, change)
│   │   ├── FxTab.tsx           # FX heatmap + PPP valuation sub-tab
│   │   ├── InflationHeatmap.tsx     # Country × year CPI heatmap
│   │   ├── InflationTab.tsx    # CPI/PCE/PPI/M2 + Quantity Theory sub-tab
│   │   ├── GrowthEmployment.tsx     # Sahm Rule, JOLTS, industrial production, capacity utilisation
│   │   ├── HousingTab.tsx      # Case-Shiller, housing starts, mortgage rates, NAHB
│   │   ├── CommoditiesTab.tsx  # ~25 futures + Bitcoin table with KPIs
│   │   ├── RatesYields.tsx     # Rates & Yields sub-tab
│   │   ├── LeadingIndicators.tsx   # LEI/CLI/CFNAI/PMI + IS-LM-PC panels
│   │   ├── FinancialConditions.tsx # NFCI/STLFSI4/Fed balance sheet
│   │   ├── PositioningTab.tsx  # CFTC COT report — 6 key contracts, speculator positioning
│   │   ├── CountryRiskTab.tsx  # 6-KPI traffic-light sovereign risk panel (Phase 16)
│   │   ├── CentralBanksTab.tsx # Policy rate history + CB meetings timeline (Phase 16)
│   │   └── LabTab.tsx          # Econometric Lab: pool OLS regression UI (Phase 15)
│   │
│   ├── screener/               # /screener page components
│   │   ├── PresetPills.tsx     # 20+ signal preset pill buttons (Chapter 7, unusual volume, etc.)
│   │   ├── ScreenerTable.tsx   # Results data table with sortable columns
│   │   ├── ResultTabs.tsx      # 9 result view tabs (Top Picks, Undervalued, etc.)
│   │   └── Sparkline.tsx       # Canvas 200×120 sparkline gallery for screener cards
│   │
│   ├── calendar/               # /calendar page components
│   │   ├── CalendarGrid.tsx    # Weekly Mon–Sun event grid
│   │   ├── CalendarFilters.tsx # Category, impact, country, timezone filter pills
│   │   └── EventCard.tsx       # Individual event card with countdown + impact colour
│   │
│   ├── risk/                   # /risk page components
│   │   ├── RiskKPIRow.tsx      # KPI summary strip (Vol, VaR, Sharpe, Beta, MaxDD)
│   │   ├── RollingMetricsChart.tsx  # Rolling Sharpe/Vol/Beta/etc. time series
│   │   ├── ExtendedRiskTable.tsx    # Calmar, Omega, Treynor, Jensen's Alpha, etc.
│   │   ├── CorrelationHeatmap.tsx   # Rolling pairwise heatmap + date scrubber
│   │   ├── OnDemandRisk.tsx    # GARCH / Hurst / OU / cointegration panel (🔴 buttons)
│   │   ├── MonteCarloPanel.tsx # GBM Monte Carlo VaR histogram
│   │   └── StressTestPanel.tsx # Historical stress test scenarios (2008, 2020, 2022, etc.)
│   │
│   ├── options/                # /options page components
│   │   ├── IVKPIRow.tsx        # IV30, IV Rank, IV Percentile, Max Pain KPI strip
│   │   ├── IVTermStructure.tsx # IV vs DTE term structure chart
│   │   ├── IVSmile.tsx         # IV smile (moneyness 0.70–1.30) chart
│   │   ├── OIProfileChart.tsx  # Open interest profile + Max Pain line chart
│   │   ├── ChainTable.tsx      # Option chain: Calls | Strikes | Puts data table
│   │   └── MonteCarloOptions.tsx   # 10k GBM path options pricing histogram
│   │
│   ├── sectors/                # /sectors page components
│   │   ├── SectorReturnsChart.tsx      # Sorted horizontal bar chart by period
│   │   ├── SectorFundamentalsTable.tsx # P/E, P/B, yield, beta, vol table
│   │   ├── SectorRotationClock.tsx     # Stovall 4-phase rotation bubble chart
│   │   └── SectorIndustryDrillDown.tsx # Top-3 stocks per GICS industry
│   │
│   ├── portfolio/              # /portfolio page components
│   │   ├── PortfolioInput.tsx  # Holdings entry form (ticker + weight/shares)
│   │   ├── PortfolioKPIs.tsx   # Return, Sharpe, max drawdown KPI strip
│   │   ├── PerformanceChart.tsx     # Cumulative return vs SPY + AGG
│   │   ├── DrawdownChart.tsx   # Underwater drawdown curve
│   │   ├── HoldingsTable.tsx   # Weight / return / contribution table
│   │   ├── CorrelationHeatmap.tsx   # NxN correlation heatmap
│   │   ├── RiskContribution.tsx     # Variance risk-contribution bars
│   │   ├── RollingMetrics.tsx  # Rolling Sharpe/Vol/Beta with window selector
│   │   ├── CAPMAttribution.tsx # Alpha, beta, R², systematic vs idiosyncratic
│   │   ├── KellyTable.tsx      # Kelly criterion position sizing table
│   │   ├── FFAttribution.tsx   # Fama-French FF3/FF5 factor loadings
│   │   ├── EfficientFrontier.tsx    # SLSQP frontier + max-Sharpe star
│   │   ├── MonteCarlo.tsx      # 10k Dirichlet random-weight cloud
│   │   ├── BlackLitterman.tsx  # BL posterior returns + optimal weights form
│   │   └── StressTesting.tsx   # Portfolio stress test across 4 scenarios
│   │
│   ├── research/               # /research page components
│   │   ├── RiskParityPanel.tsx # Risk parity weights + ERC + backtest chart
│   │   ├── CarryPanel.tsx      # G10 FX carry table + backtest + DXY vs carry
│   │   ├── MomentumPanel.tsx   # Cross-sectional momentum decile table + return chart
│   │   └── RealizedMomentsPanel.tsx  # Realized skew/kurtosis + tail-return cross-section
│   │
│   ├── atlas/                  # /atlas page components
│   │   ├── AtlasMap.tsx        # react-simple-maps choropleth world map
│   │   ├── YearSlider.tsx      # Year range slider (2000–2024)
│   │   ├── RegionSelector.tsx  # Regional bloc filter (G7/G20/Eurozone/EM)
│   │   ├── ColorLegend.tsx     # Indicator colour scale legend
│   │   └── KpiStrip.tsx        # Top/Bottom-10 rankings + KPI summary
│   │
│   ├── yield/                  # /yield page components
│   │   ├── YieldCurveChart.tsx # US spot curve (3M–30Y) interactive chart
│   │   ├── BreakevenChart.tsx  # TIPS breakeven inflation chart
│   │   └── RealYieldChart.tsx  # TIPS real yield chart
│   │
│   ├── policy/                 # /policy page components
│   │   ├── PolicyKpiRow.tsx    # CB divergence, G10 carry, policy surprise KPIs
│   │   ├── DivergenceChart.tsx # Central bank policy rate divergence chart
│   │   └── CarryDifferentialChart.tsx # G10 carry differentials chart
│   │
│   └── sovereign/              # /sovereign page components
│       ├── RiskTable.tsx       # 6-KPI traffic-light risk ranking table
│       └── RiskGauge.tsx       # Sovereign risk gauge visualisation
│
└── lib/                        # Shared utilities and types
    ├── api.ts                  # All backend API calls (typed fetch wrappers, get/post helpers)
    ├── types.ts                # Shared TypeScript interfaces (~800+ lines: all response types)
    ├── ratioGuide.ts           # Per-ratio explanations + Good/Average/Caution ranges
    └── format.ts               # Number/price/percentage/market-cap formatting + chart colors
```
