import type {
  PricesResponse, Quote, RiskResponse, ValuationResponse, RatiosResponse,
  SearchResult, Indicator, Country, MacroResponse, FxResponse,
  PortfolioResponse, SectorsResponse, RelStrengthResponse, ScreenerResponse,
  EventsResponse, YieldCurveResponse, HealthResponse, NewsResponse,
  SnapshotResponse, ForecastResponse,
  DcfResponse, FxRatesResponse, RegimeResponse,
  ValuationFullResponse, FactorResponse,
  BreadthResponse, IndicesResponse, FearGreedResponse, MoversResponse,
  ConstituentsResponse,
  TreemapResponse,
  CalendarResponse,
  ScreenerUniverseResponse, PresetDef, ScreenerStatus,
  RollingMetricsResponse, ExtendedRiskResponse, CorrelationResponse,
  GarchResult, HurstResult, OUResponse, CointegrationResult,
  MonteCarloResult, StressTestResponse,
  OptionsKPIs, OptionsChain, IVTermPoint, IVSmilePoint, OIProfile, MCOptionsResult,
  RatesData, InflationData, EmploymentData, HousingData, CommoditiesData,
  FxHeatmapData, FxPppData, LeadingData, FinancialConditionsData, CotData,
  Holders13FResponse, Form4Response,
  SnowflakeResponse, SnowflakeBatchResponse,
  SectorReturnsResponse, SectorFundamentalsResponse, SectorRotationResponse, SectorDrillResponse,
  Holding,
  PortfolioAnalysis, CorrelationData, RiskContribData, CAPMData, RollingData,
  KellyData, FFData, FrontierData, MCData, BLData, StressScenario,
  TechnicalsResponse,
  AtlasIndicator, AtlasRegion, AtlasTimelineResponse, AtlasSnapshotResponse,
} from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  prices: (tickers: string, period: string, benchmark?: string) =>
    get<PricesResponse>(`/market/prices?tickers=${encodeURIComponent(tickers)}&period=${period}` +
      (benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : "")),

  quote: (ticker: string) =>
    get<Quote>(`/market/quote/${encodeURIComponent(ticker)}`),

  risk: (tickers: string, period: string, riskFree: number, benchmark?: string) =>
    get<RiskResponse>(`/market/risk?tickers=${encodeURIComponent(tickers)}&period=${period}&risk_free=${riskFree}` +
      (benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : "")),

  valuation: (
    tickers: string, period: string,
    p: { risk_free: number; market_premium: number; fcf_growth: number; terminal_growth: number },
  ) =>
    get<ValuationResponse>(
      `/valuation/capm-dcf?tickers=${encodeURIComponent(tickers)}&period=${period}` +
      `&risk_free=${p.risk_free}&market_premium=${p.market_premium}` +
      `&fcf_growth=${p.fcf_growth}&terminal_growth=${p.terminal_growth}`),

  ratios: (ticker: string) =>
    get<RatiosResponse>(`/ratios/${encodeURIComponent(ticker)}`),

  search: (q: string) =>
    get<{ results: SearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),

  indicators: () =>
    get<{ indicators: Indicator[] }>(`/macro/indicators`),

  countries: () =>
    get<{ countries: Country[] }>(`/macro/countries`),

  macroData: (countries: string, indicator: string, start: number, end: number) =>
    get<MacroResponse>(`/macro/data?countries=${encodeURIComponent(countries)}&indicator=${indicator}&start=${start}&end=${end}`),

  fx: (base: string, targets: string) =>
    get<FxResponse>(`/macro/fx?base=${base}&targets=${encodeURIComponent(targets)}`),

  portfolio: (holdings: { ticker: string; weight: number }[], period: string, riskFree = 0.04) =>
    post<PortfolioResponse>(`/portfolio/analyze`, { holdings, period, risk_free: riskFree }),

  sectors: (period: string) =>
    get<SectorsResponse>(`/market/sectors?period=${period}`),

  relativeStrength: (tickers: string) =>
    get<RelStrengthResponse>(`/market/relative-strength?tickers=${encodeURIComponent(tickers)}`),

  screener: (universe: string, filters: string, sort: string, period: string) =>
    get<ScreenerResponse>(
      `/screener?universe=${encodeURIComponent(universe)}&filters=${encodeURIComponent(filters)}` +
      `&sort=${sort}&period=${period}`),

  events: (ticker: string) =>
    get<EventsResponse>(`/market/events/${encodeURIComponent(ticker)}`),

  news: (ticker: string) =>
    get<NewsResponse>(`/market/news/${encodeURIComponent(ticker)}`),

  yieldCurve: () =>
    get<YieldCurveResponse>(`/macro/yield-curve`),

  snapshot: (countries: string) =>
    get<SnapshotResponse>(`/macro/snapshot?countries=${encodeURIComponent(countries)}`),

  forecast: (countries: string, indicator: string, end: number) =>
    get<ForecastResponse>(`/macro/forecast?countries=${encodeURIComponent(countries)}&indicator=${indicator}&end=${end}`),

  health: () =>
    get<HealthResponse>(`/admin/health`),

  // --- Phase 0 ---
  dcf: (
    ticker: string,
    p: { fcf_growth: number; terminal_growth: number; wacc: number; stage1_years: number },
  ) =>
    get<DcfResponse>(
      `/valuation/dcf?ticker=${encodeURIComponent(ticker)}` +
      `&fcf_growth=${p.fcf_growth}&terminal_growth=${p.terminal_growth}` +
      `&wacc=${p.wacc}&stage1_years=${p.stage1_years}`),

  fxRates: (base: string) =>
    get<FxRatesResponse>(`/market/fx-rates?base=${encodeURIComponent(base)}`),

  regime: (country: string, start = 2000) =>
    get<RegimeResponse>(`/macro/regime?country=${encodeURIComponent(country)}&start=${start}`),

  // --- Phase 1 ---
  valuationFull: (ticker: string) =>
    get<ValuationFullResponse>(`/valuation/full?ticker=${encodeURIComponent(ticker)}`),

  valuationFactors: (ticker: string, model: "3" | "5" = "3") =>
    get<FactorResponse>(`/valuation/factors?ticker=${encodeURIComponent(ticker)}&model=${model}`),

  // --- Phase 2: Dashboard ---
  breadth: (index = "sp500") =>
    get<BreadthResponse>(`/dashboard/breadth?index=${index}`),

  indices: () =>
    get<IndicesResponse>(`/dashboard/indices`),

  fearGreed: () =>
    get<FearGreedResponse>(`/dashboard/fear-greed`),

  movers: (index = "sp500", limit = 10) =>
    get<MoversResponse>(`/dashboard/movers?index=${index}&limit=${limit}`),

  constituents: (index = "sp500") =>
    get<ConstituentsResponse>(`/dashboard/constituents?index=${index}`),

  // --- Phase 3: Treemap ---
  treemap: (index = "sp500", period = "1d") =>
    get<TreemapResponse>(`/treemap?index=${encodeURIComponent(index)}&period=${encodeURIComponent(period)}`),

  // --- Phase 4: Economic Calendar ---
  calendar: (index = "dow", start: string, end: string) =>
    get<CalendarResponse>(
      `/calendar?index=${encodeURIComponent(index)}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),

  // --- Phase 5: Screener Overhaul ---
  screenerUniverse: (
    index: string,
    presets: string,
    filters: string,
    sort: string,
    dir: "asc" | "desc",
    limit: number,
  ) =>
    get<ScreenerUniverseResponse>(
      `/screener/universe?index=${index}&presets=${encodeURIComponent(presets)}&filters=${encodeURIComponent(filters)}&sort=${sort}&dir=${dir}&limit=${limit}`
    ),

  screenerPresets: () =>
    get<{ presets: PresetDef[] }>(`/screener/presets`),

  screenerStatus: (index: string) =>
    get<ScreenerStatus>(`/screener/status?index=${index}`),

  screenerRefresh: (index: string) =>
    post<{ index: string; started: boolean }>(`/screener/refresh?index=${index}`, {}),

  // --- Phase 6: Risk & Rolling Metrics ---
  riskRolling: (tickers: string, period: string, window: number, benchmark?: string) =>
    get<RollingMetricsResponse>(
      `/risk/rolling?tickers=${encodeURIComponent(tickers)}&period=${period}&window=${window}` +
      (benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : "")
    ),

  riskExtended: (tickers: string, period: string, benchmark?: string) =>
    get<ExtendedRiskResponse>(
      `/risk/extended?tickers=${encodeURIComponent(tickers)}&period=${period}` +
      (benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : "")
    ),

  riskCorrelation: (tickers: string, period: string, window: number) =>
    get<CorrelationResponse>(
      `/risk/correlation?tickers=${encodeURIComponent(tickers)}&period=${period}&window=${window}`
    ),

  riskGarch: (ticker: string, period = "2y") =>
    post<GarchResult>(`/risk/garch?ticker=${encodeURIComponent(ticker)}&period=${period}`, {}),

  riskHurst: (ticker: string, period = "3y") =>
    post<HurstResult>(`/risk/hurst?ticker=${encodeURIComponent(ticker)}&period=${period}`, {}),

  riskOU: (tickers: string, period = "2y") =>
    post<OUResponse>(`/risk/ou?tickers=${encodeURIComponent(tickers)}&period=${period}`, {}),

  riskCointegration: (tickers: string, period = "3y") =>
    post<CointegrationResult>(`/risk/cointegration?tickers=${encodeURIComponent(tickers)}&period=${period}`, {}),

  riskMonteCarlo: (ticker: string, period = "2y", sims = 10000, horizon = 1) =>
    post<MonteCarloResult>(
      `/risk/montecarlo?ticker=${encodeURIComponent(ticker)}&period=${period}&sims=${sims}&horizon=${horizon}`, {}
    ),

  riskStress: (ticker: string, scenarios = "gfc,covid,rates,dotcom", benchmark?: string) =>
    post<StressTestResponse>(
      `/risk/stress?ticker=${encodeURIComponent(ticker)}&scenarios=${encodeURIComponent(scenarios)}` +
      (benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : ""), {}
    ),

  // --- Phase 7: Options & IV Module ---
  optionsExpiries: (ticker: string) =>
    get<string[]>(`/options/expiries?ticker=${encodeURIComponent(ticker)}`),

  optionsKPIs: (ticker: string) =>
    get<OptionsKPIs>(`/options/ivmetrics?ticker=${encodeURIComponent(ticker)}`),

  optionsChain: (ticker: string, expiry: string) =>
    get<OptionsChain>(`/options/chain?ticker=${encodeURIComponent(ticker)}&expiry=${encodeURIComponent(expiry)}`),

  optionsTermStructure: (ticker: string) =>
    get<IVTermPoint[]>(`/options/termstructure?ticker=${encodeURIComponent(ticker)}`),

  optionsSmile: (ticker: string, expiry: string) =>
    get<IVSmilePoint[]>(`/options/smile?ticker=${encodeURIComponent(ticker)}&expiry=${encodeURIComponent(expiry)}`),

  optionsOIProfile: (ticker: string, expiry: string) =>
    get<OIProfile>(`/options/oiprofile?ticker=${encodeURIComponent(ticker)}&expiry=${encodeURIComponent(expiry)}`),

  optionsMonteCarlo: (ticker: string, strike: number, expiry: string, optType: string, sims = 10000) =>
    post<MCOptionsResult>(
      `/options/montecarlo?ticker=${encodeURIComponent(ticker)}&strike=${strike}&expiry=${encodeURIComponent(expiry)}&opt_type=${optType}&sims=${sims}`,
      {}
    ),

  // --- Phase 8: Macro Expansion ---
  macroRates: () =>
    get<RatesData>(`/macro/rates`),

  macroInflation: () =>
    get<InflationData>(`/macro/inflation`),

  macroEmployment: () =>
    get<EmploymentData>(`/macro/employment`),

  macroHousing: () =>
    get<HousingData>(`/macro/housing`),

  macroCommodities: () =>
    get<CommoditiesData>(`/macro/commodities`),

  macroFxHeatmap: () =>
    get<FxHeatmapData>(`/macro/fx/heatmap`),

  macroFxPpp: () =>
    get<FxPppData>(`/macro/fx/ppp`),

  macroLeading: () =>
    get<LeadingData>(`/macro/leading`),

  macroFinancialConditions: () =>
    get<FinancialConditionsData>(`/macro/financial-conditions`),

  macroCot: () =>
    get<CotData>(`/macro/positioning`),

  market13f: (ticker: string) =>
    get<Holders13FResponse>(`/market/13f?ticker=${encodeURIComponent(ticker)}`),

  marketForm4: (ticker: string) =>
    get<Form4Response>(`/market/form4?ticker=${encodeURIComponent(ticker)}`),

  snowflake: (ticker: string) =>
    get<SnowflakeResponse>(`/snowflake?ticker=${encodeURIComponent(ticker)}`),

  snowflakeBatch: (tickers: string[]) =>
    get<SnowflakeBatchResponse>(`/snowflake/batch?tickers=${tickers.map(encodeURIComponent).join(",")}`),

  // --- Phase 10: Sector Performance ---
  sectorReturns: (): Promise<SectorReturnsResponse> => get("/sector/returns"),
  sectorFundamentals: (): Promise<SectorFundamentalsResponse> => get("/sector/fundamentals"),
  sectorRotation: (): Promise<SectorRotationResponse> => get("/sector/rotation"),
  sectorDrill: (sector: string): Promise<SectorDrillResponse> =>
    get(`/sector/drill?sector=${encodeURIComponent(sector)}`),

  // --- Phase 11: Portfolio Analytics ---
  portfolioAnalyze: (holdings: Holding[], period: string): Promise<PortfolioAnalysis> =>
    post("/portfolio/analyze", { holdings, period }),

  portfolioCorrelation: (holdings: Holding[], period: string): Promise<CorrelationData> =>
    post("/portfolio/correlation", { holdings, period }),

  portfolioRiskContribution: (holdings: Holding[], period: string): Promise<RiskContribData> =>
    post("/portfolio/risk-contribution", { holdings, period }),

  portfolioCAPM: (holdings: Holding[], period: string): Promise<CAPMData> =>
    post("/portfolio/capm", { holdings, period }),

  portfolioRolling: (holdings: Holding[], period: string, window: number): Promise<RollingData> =>
    post("/portfolio/rolling", { holdings, period, window }),

  portfolioKelly: (holdings: Holding[], period: string): Promise<KellyData> =>
    post("/portfolio/kelly", { holdings, period }),

  portfolioFF: (holdings: Holding[], period: string, model: "3" | "5"): Promise<FFData> =>
    post("/portfolio/ff", { holdings, period, model }),

  portfolioFrontier: (holdings: Holding[], period: string): Promise<FrontierData> =>
    post("/portfolio/frontier", { holdings, period }),

  portfolioMonteCarlo: (holdings: Holding[], period: string): Promise<MCData> =>
    post("/portfolio/montecarlo", { holdings, period }),

  portfolioBL: (holdings: Holding[], views: { ticker: string; expectedReturn: number }[], period: string): Promise<BLData> =>
    post("/portfolio/blacklitterman", { holdings, views, period }),

  portfolioStress: (holdings: Holding[], period: string): Promise<StressScenario[]> =>
    post("/portfolio/stress", { holdings, period }),

  fetchTechnicals: (ticker: string, period = "1y"): Promise<TechnicalsResponse> =>
    get(`/technicals?ticker=${encodeURIComponent(ticker)}&period=${period}`),

  // --- Phase 13: Global Macro Atlas ---
  atlasIndicators: (): Promise<{ indicators: AtlasIndicator[] }> =>
    get("/atlas/indicators"),

  atlasRegions: (): Promise<{ regions: AtlasRegion[] }> =>
    get("/atlas/regions"),

  atlasTimeline: (indicator: string, start = 2000, end = 2024): Promise<AtlasTimelineResponse> =>
    get(`/atlas/timeline?indicator=${encodeURIComponent(indicator)}&start=${start}&end=${end}`),

  atlasSnapshot: (indicator: string, year: number): Promise<AtlasSnapshotResponse> =>
    get(`/atlas/snapshot?indicator=${encodeURIComponent(indicator)}&year=${year}`),
};
