import type {
  CountryRate,
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
  OptionsKPIs, OptionsChain, OptionsExpiriesResponse, IVTermStructureResponse, IVSmileResponse, OIProfile, MCOptionsResult,
  RatesData, InflationData, EmploymentData, HousingData, CommoditiesData,
  FxHeatmapData, FxPppData, LeadingData, FinancialConditionsData, CotData,
  Holders13FResponse, Form4Response,
  SnowflakeResponse, SnowflakeBatchResponse,
  SectorReturnsResponse, SectorFundamentalsResponse, SectorRotationResponse, SectorDrillResponse,
  Holding,
  PortfolioAnalysis, CorrelationData, RiskContribData, CAPMData, RollingData,
  KellyData, FFData, FrontierData, MCData, BLData, StressData,
  TechnicalsResponse,
  AtlasIndicator, AtlasRegion, AtlasTimelineResponse, AtlasSnapshotResponse,
  RiskParityWeights, RiskParityBacktest, CarryTable, CarryBacktest, MomentumResponse,
  MomentsResponse, MomentsCrossSection, DupontResponse, CorporateHealthResponse, DividendAnalysisResponse, InsiderAggregateResponse,
  RegressResponse,
  CountryRiskData, CentralBanksData,
  PricePoint, RiskMetric,
  CreditPulseData, YieldCurvesData, PolicyTrackerData, SovereignRiskData, MacroRegimeData,
  WikiCategoriesResponse, WikiTermsResponse,
  PrefetchStatus,
  BulkDatasetStatus,
  ConfigResponse, ConfigUpdateRequest, ErrorLogResponse,
  GlobalHousingData, CreditGapsData, FiscalData, TradeData, LaborData, EnergyData,
  NetLiquidityData, RecessionProbabilityData, EarningsQualityData, EventStudyData, FactorRegimeData,
  CreditConditionsData, OilShocksData, TreasuryNoiseData,
  BacktestResponse, BacktestSignalDef, BacktestRequestBody,
  RiskDialData, RiskDialBacktest,
  CurrencyCrisisData, BankingStabilityData, InequalityData,
  BusinessData, ShortInterestData, MAData,
  FactbookCountry, FactbookProfile, CrossborderData,
  SovereignDefaultData,
  AiSummaryResponse, AiSummaryHistoryItem,
  Transaction, PnLSummary,
  CrossAssetCorrelation, FxMacroLinkResponse, MultiCountryPortfolio, MultiCountryHoldingInput,
} from "./types";

import { noteResponse, STALE_HEADER } from "./staleData";
import { REFRESH_HEADER, requestDone, requestStarted } from "./refresh";

// Relative by default (Docker/web hit /api via nginx); the Tauri desktop build
// sets NEXT_PUBLIC_API_URL=http://localhost:8000 in .env.production.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function get<T>(path: string): Promise<T> {
  const refreshing = requestStarted();
  let data: unknown;
  try {
    data = await getJson(path, refreshing);
    return data as T;
  } finally {
    requestDone(refreshing, data);
  }
}

async function getJson(path: string, refreshing: boolean): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    cache: "no-store",
    headers: refreshing ? { [REFRESH_HEADER]: "1" } : undefined,
  });
  if (!res.ok) {
    // Surface the server's reason (FastAPI `detail`) so a page can say *why*
    // data is missing instead of a bare status code.
    const detail = await res.json().then((b) => (typeof b?.detail === "string" ? b.detail : null)).catch(() => null);
    throw new Error(detail ?? `API ${path} failed: ${res.status}`);
  }
  const data = await res.json();
  noteResponse(path, res.headers.get(STALE_HEADER), data);
  return data;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
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

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const msg = (detail as Record<string, unknown>)?.detail || `${path} failed: ${res.status}`;
    throw new Error(String(msg));
  }
  return res.json() as Promise<T>;
}

export const api = {
  prices: (tickers: string, period: string, benchmark?: string) =>
    get<PricesResponse>(`/market/prices?tickers=${encodeURIComponent(tickers)}&period=${period}` +
      (benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : "")),

  quote: (ticker: string) =>
    get<Quote>(`/market/quote/${encodeURIComponent(ticker)}`),

  risk: (tickers: string, period: string, riskFree?: number, benchmark?: string) =>
    get<RiskResponse>(`/market/risk?tickers=${encodeURIComponent(tickers)}&period=${period}` +
      (riskFree != null ? `&risk_free=${riskFree}` : "") +
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

  prefetchStart: () =>
    post<{ status: string; progress: PrefetchStatus }>(`/admin/prefetch`, {}),

  prefetchStatus: () =>
    get<PrefetchStatus>(`/admin/prefetch/status`),

  bulkDataStatus: () =>
    get<{ datasets: Record<string, BulkDatasetStatus>; running: boolean }>(`/admin/bulk-data/status`),

  bulkDataRefresh: () =>
    post<{ status: string; datasets: Record<string, { rows: number; error: string | null }> }>(`/admin/bulk-data/refresh`, {}),

  clearCache: () =>
    post<{ status: string; cleared: { entries: number; memory_caches: number } }>(`/admin/cache/clear`, {}),

  config: () =>
    get<ConfigResponse>(`/admin/config`),

  updateConfig: (body: ConfigUpdateRequest) =>
    put<ConfigResponse>(`/admin/config`, body),

  // --- Phase 41: live-ops error feed ---
  adminErrors: (limit = 100) =>
    get<ErrorLogResponse>(`/admin/errors?limit=${limit}`),

  clearAdminErrors: () =>
    post<{ status: string }>(`/admin/errors/clear`, {}),

  // --- Phase 0 ---
  dcf: (
    ticker: string,
    p: { fcf_growth: number; terminal_growth: number; wacc: number; stage1_years: number },
  ) =>
    get<DcfResponse>(
      `/valuation/dcf?ticker=${encodeURIComponent(ticker)}` +
      `&fcf_growth=${p.fcf_growth}&terminal_growth=${p.terminal_growth}` +
      `&wacc=${p.wacc}&stage1_years=${p.stage1_years}`),

  riskFreeRates: () =>
    get<{ rates: CountryRate[] }>("/valuation/risk-free-rates"),

  fxRates: (base: string) =>
    get<FxRatesResponse>(`/market/fx-rates?base=${encodeURIComponent(base)}`),

  regime: (country: string, start = 2000) =>
    get<RegimeResponse>(`/macro/regime-series?country=${encodeURIComponent(country)}&start=${start}`),

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
    get<OptionsExpiriesResponse>(`/options/expiries?ticker=${encodeURIComponent(ticker)}`),

  optionsKPIs: (ticker: string) =>
    get<OptionsKPIs>(`/options/ivmetrics?ticker=${encodeURIComponent(ticker)}`),

  optionsChain: (ticker: string, expiry: string) =>
    get<OptionsChain>(`/options/chain?ticker=${encodeURIComponent(ticker)}&expiry=${encodeURIComponent(expiry)}`),

  optionsTermStructure: (ticker: string) =>
    get<IVTermStructureResponse>(`/options/termstructure?ticker=${encodeURIComponent(ticker)}`),

  optionsSmile: (ticker: string, expiry: string) =>
    get<IVSmileResponse>(`/options/smile?ticker=${encodeURIComponent(ticker)}&expiry=${encodeURIComponent(expiry)}`),

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

  macroHousingGlobal: () =>
    get<GlobalHousingData>(`/macro/housing/global`),

  macroCommodities: () =>
    get<CommoditiesData>(`/macro/commodities`),

  macroFxHeatmap: () =>
    get<FxHeatmapData>(`/macro/fx/heatmap`),

  macroFxPpp: () =>
    get<FxPppData>(`/macro/fx/ppp`),

  macroLeading: (baseYear = 2020) =>
    get<LeadingData>(`/macro/leading?base_year=${baseYear}`),

  macroFinancialConditions: () =>
    get<FinancialConditionsData>(`/macro/financial-conditions`),

  macroCreditGaps: () =>
    get<CreditGapsData>(`/macro/credit-gaps`),

  macroFiscal: () =>
    get<FiscalData>(`/macro/fiscal`),

  macroTrade: () =>
    get<TradeData>(`/macro/trade`),

  macroBusiness: () =>
    get<BusinessData>(`/macro/business`),

  macroLabor: () =>
    get<LaborData>(`/macro/labor`),

  macroEnergy: () =>
    get<EnergyData>(`/macro/energy`),

  macroInequality: () =>
    get<InequalityData>(`/macro/inequality`),

  macroCot: () =>
    get<CotData>(`/macro/positioning`),

  market13f: (ticker: string) =>
    get<Holders13FResponse>(`/market/13f?ticker=${encodeURIComponent(ticker)}`),

  marketForm4: (ticker: string) =>
    get<Form4Response>(`/market/form4?ticker=${encodeURIComponent(ticker)}`),

  marketShortInterest: (tickerOrUniverse: string) =>
    get<ShortInterestData>(`/market/short-interest?${tickerOrUniverse === "sp500" ? "universe=sp500" : `ticker=${encodeURIComponent(tickerOrUniverse)}`}`),

  mergers: () =>
    get<MAData>(`/mergers`),

  factbookCountries: () =>
    get<FactbookCountry[]>(`/countries`),

  factbookCountry: (iso2: string) =>
    get<FactbookProfile>(`/countries/${encodeURIComponent(iso2)}`),

  crossborderClaims: () =>
    get<CrossborderData>(`/crossborder/claims`),

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

  portfolioStress: (holdings: Holding[], period: string): Promise<StressData> =>
    post("/portfolio/stress", { holdings, period }),

  fetchTechnicals: (ticker: string, period = "1y"): Promise<TechnicalsResponse> =>
    get(`/technicals?ticker=${encodeURIComponent(ticker)}&period=${period}`),

  // --- Phase 13: Global Macro Atlas ---
  atlasIndicators: (): Promise<{ indicators: AtlasIndicator[] }> =>
    get("/atlas/indicators"),

  atlasRegions: (): Promise<{ regions: AtlasRegion[] }> =>
    get("/atlas/regions"),

  atlasTimeline: (indicator: string, start = 2000, end = new Date().getFullYear() - 1): Promise<AtlasTimelineResponse> =>
    get(`/atlas/timeline?indicator=${encodeURIComponent(indicator)}&start=${start}&end=${end}`),

  atlasSnapshot: (indicator: string, year: number): Promise<AtlasSnapshotResponse> =>
    get(`/atlas/snapshot?indicator=${encodeURIComponent(indicator)}&year=${year}`),

  // --- Phase 14: Research Hub ---
  riskParity: (tickers: string[], period: string, mode: "erc" | "invvol"): Promise<RiskParityWeights> =>
    post("/research/riskparity", { tickers, period, mode }),

  riskParityBacktest: (tickers: string[], period: string, mode: "erc" | "invvol"): Promise<RiskParityBacktest> =>
    post("/research/riskparity", { tickers, period, mode, backtest: true }),

  carryTable: (period = "3y"): Promise<CarryTable> =>
    get(`/research/carry?period=${encodeURIComponent(period)}`),

  carryBacktest: (period = "3y"): Promise<CarryBacktest> =>
    get(`/research/carry?period=${encodeURIComponent(period)}&backtest=true`),

  momentum: (universe = "dow", signal = "12m1m"): Promise<MomentumResponse> =>
    get(`/research/momentum?universe=${encodeURIComponent(universe)}&signal=${encodeURIComponent(signal)}`),

  // --- Phase 15: Realized Moments ---
  moments: (ticker: string, period = "3y"): Promise<MomentsResponse> =>
    get(`/research/moments?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`),

  momentsCrosssection: (universe = "dow", window = 21): Promise<MomentsCrossSection> =>
    get(`/research/moments/crosssection?universe=${encodeURIComponent(universe)}&window=${window}`),

  // --- Phase 27: Sector DuPont ---
  researchDupont: (): Promise<DupontResponse> =>
    get("/research/dupont"),

  // --- Phase 27: Corporate Health ---
  corporateHealth: (ticker: string): Promise<CorporateHealthResponse> =>
    get(`/corporate/health?ticker=${encodeURIComponent(ticker)}`),

  // --- Phase 27: Dividend Analysis ---
  dividendAnalysis: (ticker: string): Promise<DividendAnalysisResponse> =>
    get(`/dividend/analysis?ticker=${encodeURIComponent(ticker)}`),

  // --- Phase 27: Insider Trading Aggregator ---
  insiderAggregate: (): Promise<InsiderAggregateResponse> =>
    get("/insider/aggregate"),

  // --- Phase 15: Econometric Lab ---
  macroRegress: (dep: string, indep: string[], countries: string[], start: number, end: number): Promise<RegressResponse> =>
    post("/macro/regress", { dep, indep, countries, start, end }),

  // --- Phase 16: Country Risk + Central Banks ---
  macroCountryRisk: (countries?: string) =>
    get<CountryRiskData>(`/macro/country-risk${countries ? `?countries=${countries}` : ""}`),
  macroCentralBanks: () =>
    get<CentralBanksData>(`/macro/centralbanks`),

  // --- Phase 18A: Credit, Yield, Policy, Sovereign, Regime ---
  creditPulse: () => get<CreditPulseData>("/credit/pulse"),
  yieldCurves: () => get<YieldCurvesData>("/yield/curves"),
  policyTracker: () => get<PolicyTrackerData>("/policy/tracker"),
  sovereignRisk: () => get<SovereignRiskData>("/sovereign/risk"),
  sovereignDefaultProb: () => get<SovereignDefaultData>("/sovereign/default-prob"),
  macroRegime: () => get<MacroRegimeData>("/macro/regime"),
  macroTaylorRule: () => get<any>("/macro/taylor-rule"),
  macroSentiment: () => get<any>("/macro/sentiment"),

  // --- Phase 28: Stability ---
  stabilityCurrencyCrisis: () => get<CurrencyCrisisData>("/stability/currency-crisis"),
  stabilityBanking: () => get<BankingStabilityData>("/stability/banking"),

  // --- Phase 18B: Scenario Lab ---
  macroFunding: () => get<any>("/macro/funding"),
  macroNetLiquidity: () => get<NetLiquidityData>("/macro/net-liquidity"),
  macroRecessionProbability: () => get<RecessionProbabilityData>("/macro/recession-probability"),

  // --- Phase 39: high-evidence credit / oil / rates indicators ---
  macroCreditConditions: () => get<CreditConditionsData>("/macro/credit-conditions"),
  macroOilShocks: () => get<OilShocksData>("/macro/oil-shocks"),
  macroRiskDial: () => get<RiskDialData>("/macro/risk-dial"),
  macroRiskDialBacktest: () => get<RiskDialBacktest>("/macro/risk-dial/backtest"),
  yieldNoise: () => get<TreasuryNoiseData>("/yield/noise"),
  corporateEarningsQuality: (universe: string) =>
    get<EarningsQualityData>(`/corporate/earnings-quality?universe=${encodeURIComponent(universe)}`),
  researchEventStudy: (p: { ticker: string; eventType: string; window: number }) =>
    post<EventStudyData>("/research/event-study", p),
  researchFactorRegime: () => get<FactorRegimeData>("/research/factor-regime"),
  backtestSignals: () => get<{ signals: BacktestSignalDef[] }>("/research/backtest/signals"),
  runBacktest: (body: BacktestRequestBody) => post<BacktestResponse>("/research/backtest", body),
  scenarioHistorical: () => get<any>("/scenario/historical"),
  scenarioStress: (holdings: Holding[]) => post<any>("/scenario/historical/stress", { holdings }),
  scenarioCustom: (holdings: Holding[], shocks: Record<string, number>) =>
    post<any>("/scenario/custom", { holdings, shocks }),

  // --- Wiki ---
  wikiCategories: () => get<WikiCategoriesResponse>("/wiki/categories"),
  wikiTerms: (search?: string, category?: string) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (category) params.set("category", category);
    return get<WikiTermsResponse>(`/wiki/terms?${params}`);
  },

  // --- AI Summaries (Gemini) ---
  aiCompany: (ticker: string, model: string, forceRegenerate: boolean) =>
    post<AiSummaryResponse>("/ai/company", { ticker, model, force_regenerate: forceRegenerate }),

  aiMacro: (countries: string[], model: string, forceRegenerate: boolean) =>
    post<AiSummaryResponse>("/ai/macro", { countries, model, force_regenerate: forceRegenerate }),

  aiDashboard: (model: string, forceRegenerate: boolean) =>
    post<AiSummaryResponse>("/ai/dashboard", { model, force_regenerate: forceRegenerate }),

  aiHistory: (summaryType: string, contextKey: string) =>
    get<{ items: AiSummaryHistoryItem[] }>(`/ai/history/${summaryType}/${encodeURIComponent(contextKey)}`),

  // --- Phase 37: Portfolio Transaction Log ---
  syncTransactions: (transactions: Transaction[]) =>
    post<{ saved: number }>("/portfolio/transactions/sync", { transactions }),

  fetchTransactions: () =>
    get<{ transactions: Transaction[] }>("/portfolio/transactions"),

  computePnL: (transactions: Transaction[], currentPrices: Record<string, number>) =>
    post<PnLSummary>("/portfolio/transactions/pnl", { transactions, current_prices: currentPrices }),

  // --- Phase 39: Cross-Asset & Factor Analytics ---
  crossAssetCorrelation: (tickers: string[], period = "3y") =>
    post<CrossAssetCorrelation>("/research/cross-asset-correlation", { tickers, period }),

  fxMacroLink: () =>
    get<FxMacroLinkResponse>("/research/fx-macro-link"),

  multiCountryPortfolio: (holdings: MultiCountryHoldingInput[], period = "3y") =>
    post<MultiCountryPortfolio>("/research/multi-country-portfolio", { holdings, period }),
};

// --- Phase 17.E: React Query ---
export const marketComposite = (
  tickers: string,
  period: string,
  benchmark?: string
): Promise<{ prices: PricePoint[]; risk: RiskMetric[]; quotes: Quote[] }> => {
  const params = new URLSearchParams({ tickers, period });
  if (benchmark) params.set('benchmark', benchmark);
  return get(`/market/composite?${params}`);
};
