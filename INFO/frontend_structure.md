# Axiom Finance — Frontend File Structure

> **Last updated:** 2026-06-29 — reflects all phases through Phase 31.
> Pages: 24 · Components: 118 · Library files: 8

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
│   ├── markets/page.tsx        # /markets — stock analysis: price chart, sub-tabs (Overview/Technicals/
│   │                           #   Valuation/Ratios/News/Rankings/Sectors/Screener/FX/Risk/Portfolio)
│   ├── macro/page.tsx          # /macro — 16-tab hub: Overview, Inflation, Growth, Housing, Commodities,
│   │                           #   FX, Leading, Financial, Positioning, Country Risk, CB, Lab,
│   │                           #   Fiscal, Labor, Energy, Inequality
│   ├── screener/page.tsx       # /screener — multi-index screener with 20+ preset signals, 9 result tabs
│   ├── treemap/page.tsx        # /treemap — S&P 500 / NDX / Dow squarified treemap
│   ├── calendar/page.tsx       # /calendar — earnings, macro, IPO, dividend, CB meeting events
│   ├── risk/page.tsx           # /risk — rolling metrics, GARCH, Hurst, cointegration, stress, MC
│   ├── options/page.tsx        # /options — IV analytics, Greeks, term structure, smile, OI profile, MC
│   ├── sectors/page.tsx        # /sectors — SPDR ETF returns, fundamentals, rotation clock, drill-down
│   ├── portfolio/page.tsx      # /portfolio — performance, correlation, frontier, BL, stress
│   ├── research/page.tsx       # /research — Risk Parity, FX Carry, Momentum, Realized Moments, Econ Lab
│   ├── atlas/page.tsx          # /atlas — world choropleth: 6 indicators, year slider, regional blocs
│   ├── yield/page.tsx          # /yield — US spot curve, TIPS, breakevens, ACM term premium
│   ├── policy/page.tsx         # /policy — CB divergence, G10 carry, sovereign risk
│   ├── sovereign/page.tsx      # /sovereign — 6-KPI traffic-light risk rankings, ~200 countries
│   ├── scenario/page.tsx       # /scenario — stress scenario designer (Phase 18B stub)
│   ├── admin/page.tsx          # /admin — backend health, cache stats, API keys management
│   │
│   # --- IDEA_LIST pages (Phases 25–31) ---
│   ├── trade/page.tsx          # /trade — exports/imports %GDP, trade balances, openness indices, BIS FX
│   ├── corporate/page.tsx      # /corporate — Altman Z, Piotroski 9-pt, Beneish M, sector Z-score aggregate
│   ├── dividends/page.tsx      # /dividends — yield, growth, payout, aristocrats, DDM
│   ├── insider/page.tsx        # /insider — aggregate buy/sell ratio, cluster detection, smart money index
│   ├── mergers/page.tsx        # /mergers — M&A deals, deal values, acquisition premiums, sector heatmap
│   ├── country/page.tsx        # /country — country detail page with factbook data
│   │   └── [iso2]/page.tsx     # /country/{iso2} — dynamic country profile route
│   ├── stability/page.tsx      # /stability — Currency Crisis EWS + Banking Stability (tabbed)
│   └── crossborder/page.tsx    # /crossborder — BIS locational banking, debt securities, chord diagram
│
├── components/                 # Shared + feature React components (118 files across 17 dirs + root)
│   ├── Navbar.tsx              # Desktop top navigation bar (scroll-responsive)
│   ├── MobileNav.tsx           # Mobile bottom tab bar
│   ├── SearchBar.tsx           # Global ticker search with autocomplete
│   ├── TickerSearch.tsx        # Ticker search with recent picks
│   ├── ThemeProvider.tsx       # Dark/light theme context + localStorage persistence
│   ├── ThemeToggle.tsx         # Sun/moon toggle button
│   ├── Watchlist.tsx           # Pinned ticker watchlist with price alerts
│   ├── providers.tsx           # React Query client provider + theme provider wrapper
│   ├── ui.tsx                  # Shared primitives: Card, Badge, Spinner, Skeleton, etc.
│   ├── DataFreshnessBadge.tsx  # "Updated X ago" freshness indicator
│   ├── Footer.tsx              # App footer
│   │
│   ├── dashboard/              # BreadthBar, FearGreedGauge, GlobalIndices, TopMovers
│   ├── markets/                # 26 files: PriceChart, QuoteCards, ValuationTab/Engine/ModelsGrid/KpiPanel,
│   │                           #   DcfPanel, SnowflakeChart/Mini, AxiomGauge, TechnicalsTab, RatiosTab,
│   │                           #   RiskMetricsTable, CorrelationMatrix, FxRatesPanel, AnalystPanel,
│   │                           #   InstitutionalHolders, InsiderActivity, NewsFeed, SectorHeatmap,
│   │                           #   Treemap, RankingsTab, ScreenerTab, PortfolioTab, TabSkeleton,
│   │                           #   ShortInterestPanel
│   ├── macro/                  # 31 files: MacroTabShell, MacroDashboard, MacroOverview, MacroChart,
│   │                           #   CountrySelector, IndicatorSelector, CountryComparison, RegimeClock,
│   │                           #   RegimeDetector, RegimeOverlay, YieldCurve, FxWidget, FxTab,
│   │                           #   InflationHeatmap/InflationTab, GrowthEmployment, HousingTab,
│   │                           #   CommoditiesTab, LeadingIndicators, FinancialConditions,
│   │                           #   PositioningTab, SentimentTab, CentralBanksTab, CountryRiskTab,
│   │                           #   EconLabTab, TaylorRuleWidget, FiscalTab, LaborTab, EnergyTab,
│   │                           #   InequalityTab, BusinessTab, FundingLiquidityTab
│   ├── options/                # IVKPIRow, IVTermStructure, IVSmile, OIProfileChart, ChainTable, MonteCarloOptions
│   ├── risk/                   # RiskKPIRow, RollingMetricsChart, ExtendedRiskTable, CorrelationHeatmap,
│   │                           #   OnDemandRisk, MonteCarloPanel, StressTestPanel
│   ├── portfolio/              # 16 files: PortfolioInput, PortfolioKPIs, PerformanceChart, DrawdownChart,
│   │                           #   HoldingsTable, CorrelationHeatmap, RiskContribution, RollingMetrics,
│   │                           #   CAPMAttribution, KellyTable, FFAttribution, EfficientFrontier,
│   │                           #   MonteCarlo, BlackLitterman, ScenarioTab, StressTesting
│   ├── research/               # RiskParityTab, FxCarryTab, MomentumTab, RealizedMomentsTab, DupontTab
│   ├── screener/               # PresetPills, ScreenerTable, ResultTabs, Sparkline
│   ├── calendar/               # CalendarGrid, CalendarFilters, EventCard
│   ├── sectors/                # SectorReturnsChart, SectorFundamentalsTable, SectorRotationClock, SectorIndustryDrillDown
│   ├── atlas/                  # WorldMap, YearSlider, RegionFilter, ColorLegend, AtlasKPIs, RankingTable, IndicatorSelector
│   ├── policy/                 # PolicyDivergenceTable
│   ├── sovereign/              # SovereignSpreadTable
│   ├── yield/                  # MultiCountryYieldChart
│   ├── stability/              # CurrencyCrisisPanel, BankingStabilityPanel
│   ├── wiki/                   # WikiSearch, WikiTermCard, WikiCategoryNav
│   │
│   # --- Root-level component dirs ---
│   └── ... (new page component dirs created per-feature)
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
└── lib/                        # Shared utilities and types (8 files)
    ├── api.ts                  # All backend API calls (typed fetch wrappers, get/post/put helpers)
    ├── types.ts                # Shared TypeScript interfaces (~800+ lines: all response types)
    ├── format.ts               # Number/price/percentage/market-cap formatting + chart colors
    ├── queryClient.ts          # React Query client configuration (staleTime, gcTime, retry)
    ├── ratioGuide.ts           # Per-ratio explanations + Good/Average/Caution ranges
    ├── atlasScale.ts           # Atlas map color scaling utilities
    ├── useKeyboardShortcuts.ts # Keyboard shortcut hooks (Ctrl+K search, number keys, arrow keys)
    └── wikiData.ts             # Wiki/glossary data utilities
```
