export interface PricePoint {
  Date: string;
  [ticker: string]: string | number | null;
}

export interface PricesResponse {
  prices: PricePoint[];
  benchmarks: string[];
  missing: string[];
}

export interface Quote {
  symbol: string;
  price: number | null;
  changePercent: number | null;
  currency: string;
  name: string;
}

export interface RiskMetric {
  ticker: string;
  benchmark: string;
  annVolatility: number | null;
  dailyMeanReturn: number | null;
  var95: number | null;
  cvar95: number | null;
  sharpe: number | null;
  sortino: number | null;
  beta: number | null;
  returns: (number | null)[];
}

export interface RiskResponse {
  metrics: RiskMetric[];
}

export interface Valuation {
  ticker: string;
  benchmark: string;
  beta: number | null;
  expectedReturn: number | null;
  trailingPE: number | null;
  spotPrice: number | null;
  dcfTarget: number | null;
  currency: string;
  signal: "BUY" | "OVERVALUED" | "FAIR VALUE" | "INCOMPLETE";
}

export interface ValuationResponse {
  valuations: Valuation[];
}

export interface RatioGroup {
  [key: string]: number | null;
}

export interface RatiosResponse {
  ticker: string;
  benchmark: string;
  beta: number | null;
  sharpe: number | null;
  sortino: number | null;
  zScore: number | null;
  liquidity: RatioGroup;
  leverage: RatioGroup;
  efficiency: RatioGroup;
  profitability: RatioGroup;
  valuation: RatioGroup;
}

export interface SearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

export interface Indicator {
  id: string;
  label: string;
  unit: string;
  availableSources: string[];
}

export interface Country {
  iso2: string;
  name: string;
  region: string;
}

export interface MacroDataPoint {
  year: string;
  value: number;
}

export interface MacroSeries {
  country: string;
  countryName: string;
  source_label: string;
  data: MacroDataPoint[];
}

export interface MacroResponse {
  indicator: string;
  unit: string;
  series: MacroSeries[];
}

export interface FxResponse {
  base: string;
  date: string | null;
  rates: Record<string, number>;
}

// --- Phase 0: Two-Stage DCF ---
export interface DcfScenario {
  scenario: "Bear" | "Base" | "Bull";
  fcfGrowth: number;
  wacc: number;
  intrinsicValue: number | null;
  upsidePct: number | null;
}
export interface DcfSensitivity {
  fcfGrowthAxis: number[];
  waccAxis: number[];
  grid: (number | null)[][];
}
export interface DcfResponse {
  ticker: string;
  currency: string;
  spotPrice: number | null;
  intrinsicValue: number | null;
  upsidePct: number | null;
  locked: boolean;
  reason?: string;
  inputs: {
    ttmFcf: number | null;
    shares: number | null;
    netDebt: number | null;
    fcfGrowth: number;
    terminalGrowth: number;
    wacc: number;
    stage1Years: number;
  };
  scenarios: DcfScenario[];
  sensitivity: DcfSensitivity | Record<string, never>;
  asOf: string;
}

// --- Phase 0: FX Rates panel ---
export interface FxPair {
  pair: string;
  quote: string;
  rate: number | null;
  change1d: number | null;
  change1w: number | null;
  change1m: number | null;
  change1y: number | null;
  sparkline: number[];
  inverted?: boolean;
}
export interface FxRatesResponse {
  base: string;
  asOf: string;
  pairs: FxPair[];
}

// --- Phase 0: Regime Classifier (Goldilocks 2x2) ---
export type RegimeQuadrant =
  | "Goldilocks" | "Overheating" | "Slowdown" | "Stagflation";
export interface RegimePoint {
  date: string;
  gdpGrowth: number | null;
  cpiInflation: number | null;
  quadrant: RegimeQuadrant | null;
}
export interface RegimeResponse {
  country: string;
  thresholds: { gdp: number; cpi: number };
  series: RegimePoint[];
  current: RegimePoint | null;
  source: string;
  asOf: string;
  note: string | null;
}

// --- Phase 1: Valuation Engine ---
export interface WaccInfo {
  wacc: number | null;
  costOfEquity: number | null;
  costOfDebt: number | null;
  taxRate: number | null;
  beta: number | null;
  country: string;
  riskFree: number | null;
  erp: number | null;
  weightEquity: number | null;
  weightDebt: number | null;
}
export interface ValModel {
  model: string;
  value: number | null;
  locked: boolean;
  reason: string | null;
  detail?: Record<string, unknown>;
}
export type ValVerdict =
  | "Significantly Undervalued" | "Undervalued" | "Fairly Valued"
  | "Overvalued" | "Significantly Overvalued" | "Insufficient Data";
export interface AxiomFairValue {
  value: number | null;
  upsidePct: number | null;
  verdict: ValVerdict;
  weightsUsed: Record<string, number>;
}
export interface ValuationCore {
  ticker: string;
  currency: string;
  spotPrice: number | null;
  wacc: WaccInfo;
  models: ValModel[];
  capmImplied: ValModel;
  axiomFairValue: AxiomFairValue;
  asOf: string;
}
export interface Fundamentals {
  roic: { roic: number | null; nopat: number | null; investedCapital: number | null } | null;
  dupont: {
    threeFactor: Record<string, number | null>;
    fiveFactor: Record<string, number | null>;
  } | null;
  piotroski: { score: number | null; maxScore: number | null; criteria: Record<string, boolean | null> } | null;
  beneish: { mScore: number | null; note?: string } | null;
  ohlson: { oScore: number | null; probDefault: number | null } | null;
  cashConversionCycle: { ccc: number | null; dso: number | null; dio: number | null; dpo: number | null } | null;
}
export interface AnalystData {
  ticker: string;
  currency: string;
  price: number | null;
  priceTarget: {
    meanPrice: number | null; highPrice: number | null; lowPrice: number | null;
    medianPrice: number | null; numberOfAnalysts: number | null; upsidePct: number | null;
  };
  consensus: {
    recommendationMean: number | null; recommendationKey: string | null;
    history: { period: string; strongBuy: number; buy: number; hold: number; sell: number; strongSell: number }[];
  };
  earningsSurprises: { date: string; epsEstimate: number | null; epsActual: number | null; surprisePct: number | null }[];
  estimates: Record<string, unknown>;
  growthEstimates: Record<string, Record<string, number | null>> | null;
  asOf: string;
}
export interface ValuationKpis {
  price: number | null;
  marketCap: number | null;
  trailingPE: number | null;
  forwardPE: number | null;
  trailingEps: number | null;
  forwardEps: number | null;
  dividendYield: number | null;
  fiftyTwoWeekHigh: number | null;
  fiftyTwoWeekLow: number | null;
  beta: number | null;
  averageVolume: number | null;
  bookValue: number | null;
  evToFcf: number | null;
  fcfYield: number | null;
  shortPercentOfFloat: number | null;
  shortRatio: number | null;
  sector: string | null;
  industry: string | null;
  currency: string;
}
export interface ValuationFullResponse {
  ticker: string;
  kpis: ValuationKpis;
  valuation: ValuationCore;
  fundamentals: Fundamentals;
  analyst: AnalystData;
}
export interface FactorResponse {
  ticker: string;
  model: string;
  alpha?: number | null;
  alphaDaily?: number | null;
  betas?: Record<string, number | null>;
  rSquared?: number | null;
  tStats?: Record<string, number | null>;
  nObs?: number;
  period?: string;
  asOf?: string;
  error?: string;
}

// --- Phase 2: Dashboard (breadth / indices / fear&greed / movers) ---
export interface BreadthResponse {
  index: string;
  asOf: string | null;
  total: number;
  advancing: number;
  declining: number;
  unchanged: number;
  newHighs: number;
  newLows: number;
  pctAboveSma50: number | null;
  pctAboveSma200: number | null;
  mcclellanOscillator: number | null;
  mcclellanSummation: number | null;
  cumulativeAdLine: { date: string; value: number }[];
  advDeclHistory: { date: string; adv: number; dec: number }[];
}

export interface IndexRow {
  symbol: string;
  name: string;
  region: string;
  price: number | null;
  change1d: number | null;
  spark: number[];
  change1m: number | null;
  changeYtd: number | null;
}
export interface IndicesResponse {
  asOf: string | null;
  regions: string[];
  indices: IndexRow[];
}

export interface FearGreedSignal {
  key: string;
  label: string;
  score: number | null;
  label_text: string | null;
}
export interface FearGreedResponse {
  index: number | null;
  label: string | null;
  asOf: string | null;
  signals: FearGreedSignal[];
  history: { date: string; value: number }[];
}

export interface MoverRow {
  ticker: string;
  name: string;
  price: number | null;
  changePercent: number | null;
  volume?: number;
  avgVolume?: number;
  volumeRatio?: number;
}
export interface MoversResponse {
  index: string;
  asOf: string | null;
  gainers: MoverRow[];
  losers: MoverRow[];
  unusualVolume: MoverRow[];
  newHighs: MoverRow[];
  newLows: MoverRow[];
}

export interface ConstituentsResponse {
  index: string;
  count: number;
  constituents: { symbol: string; name: string; sector: string | null }[];
}

// --- Portfolio ---
export interface PortfolioHolding {
  ticker: string;
  weight: number | null;
  totalReturn: number | null;
  contribution: number | null;
}

export interface PortfolioMetrics {
  totalReturn: number | null;
  annReturn: number | null;
  annVolatility: number | null;
  sharpe: number | null;
  sortino: number | null;
  maxDrawdown: number | null;
  var95: number | null;
  beta: number | null;
}

export interface PortfolioResponse {
  holdings: PortfolioHolding[];
  series: { date: string; value: number }[];
  metrics: PortfolioMetrics;
  missing: string[];
  benchmark?: string;
}

// --- Sector heatmap ---
export interface SectorPerf {
  ticker: string;
  sector: string;
  changePercent: number | null;
}
export interface SectorsResponse {
  period: string;
  sectors: SectorPerf[];
}

// --- Relative strength ---
export interface RelStrengthRow {
  ticker: string;
  benchmark: string;
  ret1m: number | null;
  ret1mRel: number | null;
  ret3m: number | null;
  ret3mRel: number | null;
  ret6m: number | null;
  ret6mRel: number | null;
}
export interface RelStrengthResponse {
  rankings: RelStrengthRow[];
}

// --- Screener ---
export interface ScreenerRow {
  ticker: string;
  name: string;
  sector: string | null;
  sharpe: number | null;
  beta: number | null;
  zScore: number | null;
  valuation: RatioGroup;
  leverage: RatioGroup;
  liquidity: RatioGroup;
  profitability: RatioGroup;
}
export interface ScreenerResponse {
  fields: string[];
  filters: { field: string; op: string; value: number }[];
  sort: string;
  count: number;
  screened: number;
  results: ScreenerRow[];
}

// --- News feed ---
export type Sentiment = "positive" | "neutral" | "negative";
export interface NewsItem {
  title: string;
  publisher: string;
  url: string;
  published: string | null;
  sentiment: Sentiment;
}
export interface NewsResponse {
  ticker: string;
  news: NewsItem[];
}

// --- Events overlay ---
export interface EventsResponse {
  ticker: string;
  earnings: string | null;
  dividends: { date: string; amount: number }[];
  splits: { date: string; ratio: number }[];
}

// --- Yield curve ---
export interface YieldPoint {
  tenor: string;
  years: number;
  yield: number | null;
}
export interface YieldCurveResponse {
  points: YieldPoint[];
  spread10y3m: number | null;
  spread10y5y: number | null;
  inverted: boolean;
}

// --- Country snapshot comparison ---
export interface SnapshotIndicator {
  id: string;
  unit: string;
  values: Record<string, { value: number; year: number }>;
}
export interface SnapshotResponse {
  countries: string[];
  indicators: SnapshotIndicator[];
}

// --- IMF forecast overlay ---
export interface ForecastResponse {
  indicator: string;
  unit: string;
  source: string;
  series: MacroSeries[];
}

// --- Phase 3: S&P 500 Treemap ---
export interface TreemapStock {
  symbol: string;
  name: string;
  sector: string;
  industry: string | null;
  price: number;
  changePercent: number;
  marketCap: number;
  high52: number;
  low52: number;
}
export interface TreemapResponse {
  index: string;
  period: string;
  asOf: string | null;
  stocks: TreemapStock[];
}

// --- Phase 4: Economic Calendar ---
export interface CalendarEvent {
  date: string;                 // YYYY-MM-DD
  category: "macro" | "earnings" | "dividend" | "ipo";
  title: string;
  ticker: string | null;
  country: string | null;
  impact: number | null;        // 1..3
  time: "bmo" | "amc" | null;
  epsEstimate: number | null;
  epsActual: number | null;
  revenueEstimate: number | null;
  surprisePct: number | null;
  beatMiss: "beat" | "miss" | "inline" | null;
  amount: number | null;
  exchange: string | null;
}
export interface CalendarResponse {
  index: string;
  start: string;
  end: string;
  macro: CalendarEvent[];
  earnings: CalendarEvent[];
  dividends: CalendarEvent[];
  ipos: CalendarEvent[];
  sources: { finnhub: boolean; fred: boolean; cbMeetings: boolean };
}

// --- Phase 5: Screener Overhaul ---
export interface ScreenerCacheRow {
  symbol: string;
  name: string;
  sector: string | null;
  industry: string | null;
  price: number | null;
  changePercent: number | null;
  marketCap: number | null;
  volume: number | null;
  avgVolume20d: number | null;
  volumeRatio: number | null;
  pe: number | null;
  forwardPE: number | null;
  eps: number | null;
  dividendYield: number | null;
  beta: number | null;
  pb: number | null;
  evEbitda: number | null;
  evFcf: number | null;
  fcfYield: number | null;
  roic: number | null;
  psRatio: number | null;
  shortFloat: number | null;
  shortRatio: number | null;
  grossMargin: number | null;
  operatingMargin: number | null;
  netMargin: number | null;
  roe: number | null;
  roa: number | null;
  debtToEquity: number | null;
  currentRatio: number | null;
  revenueGrowth: number | null;
  epsGrowth: number | null;
  sma50: number | null;
  sma200: number | null;
  aboveSma200: boolean | null;
  goldenCross: boolean | null;
  rsi14: number | null;
  high52: number | null;
  low52: number | null;
  pctFromHigh: number | null;
  piotroski: number | null;
  altmanZ: number | null;
  esg: number | null;
  earningsRev30d: number | null;
  spark: number[];
  // Phase 12 fields
  macd: number | null;
  macdSignal: number | null;
  bbPctB: number | null;
  bbSqueeze: boolean | null;
  obv: number | null;
  cmf20: number | null;
  ichimokuBullish: boolean | null;
  obvDivergence: boolean | null;
}

export interface ScreenerUniverseResponse {
  index: string;
  asOf: string | null;
  count: number;
  screened: number;
  stale: boolean;
  presets: string[];
  results: ScreenerCacheRow[];
}

export interface PresetDef {
  id: string;
  label: string;
  description: string;
  category: string;
}

export interface ScreenerStatus {
  index: string;
  rowCount: number;
  lastRefresh: string | null;
  stale: boolean;
}

// --- Phase 6: Risk & Rolling Metrics ---
export interface RollingPoint {
  date: string;
  value: number | null;
}

export interface RollingTickerMetrics {
  ticker: string;
  benchmark: string;
  window: number;
  volatility: RollingPoint[];
  sharpe: RollingPoint[];
  sortino: RollingPoint[];
  maxDrawdown: RollingPoint[];
  var95: RollingPoint[];
  var99: RollingPoint[];
  beta: RollingPoint[];
}

export interface RollingMetricsResponse {
  tickers: RollingTickerMetrics[];
  period: string;
  window: number;
}

export interface ExtendedRiskTicker {
  ticker: string;
  benchmark: string;
  annReturn: number | null;
  annVolatility: number | null;
  maxDrawdown: number | null;
  calmar: number | null;
  omega: number | null;
  beta: number | null;
  alpha: number | null;
  treynor: number | null;
  systematicVar: number | null;
  idiosyncraticVar: number | null;
  rSquared: number | null;
  var95Historical: number | null;
  var99Historical: number | null;
  cvar95: number | null;
  cvar99: number | null;
}

export interface ExtendedRiskResponse {
  tickers: ExtendedRiskTicker[];
  period: string;
}

export interface CorrelationSnapshot {
  date: string;
  matrix: Record<string, Record<string, number | null>>;
}

export interface CorrelationResponse {
  snapshots: CorrelationSnapshot[];
  tickers: string[];
  window: number;
}

export interface GarchResult {
  omega: number | null;
  alpha: number | null;
  beta: number | null;
  forecastVol: number | null;
  annForecastVol: number | null;
  error?: string;
}

export interface HurstResult {
  hurst: number | null;
  interpretation: string;
}

export interface OUResult {
  ticker: string;
  theta: number | null;
  mu: number | null;
  sigma: number | null;
  halfLifeDays: number | null;
}

export interface OUResponse {
  results: OUResult[];
}

export interface CointegrationResult {
  ticker1: string;
  ticker2: string;
  pValue: number | null;
  isCointegrated: boolean | null;
  hedgeRatio: number | null;
  spread: RollingPoint[];
  error?: string;
}

export interface MonteCarloDistBin {
  bin: number | null;
  count: number;
}

export interface MonteCarloResult {
  var95: number | null;
  var99: number | null;
  expected: number | null;
  worstCase: number | null;
  distribution: MonteCarloDistBin[];
  sims: number;
  horizon: number;
  error?: string;
}

export interface StressScenarioResult {
  scenario: string;
  label: string;
  start: string;
  end: string;
  totalReturn: number | null;
  maxDrawdown: number | null;
  returnsTimeSeries: RollingPoint[];
  benchmark: RollingPoint[] | null;
  error?: string;
}

export interface StressTestResponse {
  ticker: string;
  benchmark: string;
  scenarios: StressScenarioResult[];
}

// ─── Phase 7: Options & IV Module ────────────────────────────────────────────

export interface OptionsKPIs {
  iv30: number | null;
  iv30Approximate: boolean;
  ivRank: number | null;
  ivRankApproximate: boolean;
  ivPercentile: number | null;
  pcOIRatio: number | null;
  maxPain: number | null;
  impliedMove: number | null;
  spot: number | null;
  error?: string;
}

export interface OptionRow {
  strike: number;
  bid: number | null;
  ask: number | null;
  mid: number | null;
  last: number | null;
  volume: number | null;
  openInterest: number | null;
  iv: number | null;       // already ×100 (e.g. 28.5 means 28.5%)
  delta: number | null;
  bsPrice: number | null;
  itm: boolean;
}

export interface OptionsChain {
  ticker: string;
  expiry: string;
  spot: number;
  calls: OptionRow[];
  puts: OptionRow[];
  error?: string;
}

export interface IVTermPoint {
  expiry: string;
  dte: number;
  atmIV: number | null;
  straddle: number | null;
}

export interface IVSmilePoint {
  strike: number;
  moneyness: number;
  callIV: number | null;
  putIV: number | null;
}

export interface OIProfile {
  strikes: number[];
  callOI: number[];
  putOI: number[];
  maxPain: number | null;
  spot: number;
  error?: string;
}

export interface MCOptionsResult {
  price: number | null;
  std: number | null;
  var95: number | null;
  var99: number | null;
  distribution: { bin: number; count: number }[];
  bsPrice: number | null;
  ticker?: string;
  strike?: number;
  expiry?: string;
  optType?: string;
  spot?: number;
  error?: string;
}

// ─── Phase 8: Macro Expansion ────────────────────────────────────────────────

export interface MacroTimeSeries {
  date: string;
  value: number | null;
}

// Rates & Yields
export interface RatesData {
  asOf: string | null;
  yields: Record<string, number | null>;
  spread_2y10y: number | null;
  spread_3m10y: number | null;
  inverted: boolean;
  history: Record<string, MacroTimeSeries[]>;
  taylor_rule: {
    implied: MacroTimeSeries[];
    actual: MacroTimeSeries[];
  };
  acm: {
    expectations: MacroTimeSeries[];
    term_premium: MacroTimeSeries[];
    source: string;
  };
}

// Inflation
export interface InflationData {
  asOf: string | null;
  kpis: {
    cpiYoY: number | null;
    coreCpiYoY: number | null;
    pceYoY: number | null;
    corePceYoY: number | null;
    breakeven5y: number | null;
    michigan5y: number | null;
  };
  history: {
    cpiYoY: MacroTimeSeries[];
    coreCpiYoY: MacroTimeSeries[];
    pceYoY: MacroTimeSeries[];
    corePceYoY: MacroTimeSeries[];
    ppiYoY: MacroTimeSeries[];
    breakeven5y: MacroTimeSeries[];
    breakeven10y: MacroTimeSeries[];
    forward5y5y: MacroTimeSeries[];
    michigan5y: MacroTimeSeries[];
    m2: MacroTimeSeries[];
    m2Yoy: MacroTimeSeries[];
  };
  quantityTheory: {
    nominalGdp: MacroTimeSeries[];
    m2: MacroTimeSeries[];
  };
}

// Employment
export interface EmploymentData {
  asOf: string | null;
  kpis: {
    gdpYoY: number | null;
    unemploymentRate: number | null;
    nfpLatest: number | null;
    joblessClaims: number | null;
    laborParticipation: number | null;
  };
  history: {
    gdpYoY: MacroTimeSeries[];
    unemploymentRate: MacroTimeSeries[];
    nfp: MacroTimeSeries[];
    joblessClaims: MacroTimeSeries[];
    sahmRule: MacroTimeSeries[];
    joltsOpenings: MacroTimeSeries[];
    joltsQuits: MacroTimeSeries[];
    indProd: MacroTimeSeries[];
    capUtil: MacroTimeSeries[];
  };
  recessionPeriods: { start: string; end: string }[];
}

// Housing
export interface HousingData {
  asOf: string | null;
  kpis: {
    caseShillerYoY: number | null;
    housingStarts: number | null;
    mortgageRate: number | null;
    existingHomeSales: number | null;
  };
  history: {
    caseShillerYoY: MacroTimeSeries[];
    housingStarts: MacroTimeSeries[];
    mortgageRate: MacroTimeSeries[];
    existingHomeSales: MacroTimeSeries[];
  };
  recessionPeriods: { start: string; end: string }[];
}

// BIS Global Housing (Phase 25)
export interface GlobalHousingCountry {
  iso2: string;
  name: string;
  latestIndex: number | null;
  latestDate: string | null;
  yoyChange: number | null;
  history: MacroTimeSeries[];
}
export interface GlobalHousingData {
  asOf: string | null;
  source: string;
  note: string;
  countries: GlobalHousingCountry[];
}

// Commodities
export interface CommodityRow {
  ticker: string;
  name: string;
  price: number | null;
  change1d: number | null;
  change1w: number | null;
  change1m: number | null;
  changeYtd: number | null;
}
export interface CommoditiesData {
  asOf: string | null;
  kpis: {
    wti: number | null;
    gold: number | null;
    natGas: number | null;
    copper: number | null;
    wheat: number | null;
    wtiChange1d: number | null;
    goldChange1d: number | null;
  };
  table: CommodityRow[];
  ratios: {
    goldOilRatio: MacroTimeSeries[];
  };
  axiomIndex: MacroTimeSeries[];
}

// FX
export interface FxCross {
  pair: string;
  change1d: number | null;
}
export interface FxHeatmapData {
  crosses: FxCross[];
  asOf: string | null;
}
export interface FxPppPair {
  pair: string;
  spot: number | null;
  ppp: number | null;
  overvaluation: number | null;
}
export interface FxPppData {
  pairs: FxPppPair[];
}

// Leading Indicators
export interface LeadingData {
  asOf: string | null;
  kpis: {
    lei: number | null;
    cfnai: number | null;
    ismPmi: number | null;
    gscpi: number | null;
  };
  history: {
    lei: MacroTimeSeries[];
    cfnai: MacroTimeSeries[];
    ismPmi: MacroTimeSeries[];
    gscpi: MacroTimeSeries[];
  };
  islmpc: {
    gdp: MacroTimeSeries[];
    gdpPot: MacroTimeSeries[];
    fedFunds: MacroTimeSeries[];
    m2: MacroTimeSeries[];
    unrate: MacroTimeSeries[];
    cpi: MacroTimeSeries[];
  };
}

// Financial Conditions
export interface FinancialConditionsData {
  asOf: string | null;
  kpis: {
    nfci: number | null;
    stlfsi: number | null;
    fedBalanceSheet: number | null;
    ciLoans: number | null;
  };
  history: {
    nfci: MacroTimeSeries[];
    stlfsi: MacroTimeSeries[];
    fedBalanceSheet: MacroTimeSeries[];
    creditCardDelinquency: MacroTimeSeries[];
    ciLoans: MacroTimeSeries[];
    economicPolicyUncertainty: MacroTimeSeries[];
  };
}

// BIS Credit-to-GDP Gaps (Phase 25)
export interface CreditGapCountry {
  iso2: string;
  name: string;
  latestGap: number | null;
  latestDate: string | null;
  signal: "green" | "yellow" | "red" | "unknown";
  history: MacroTimeSeries[];
}
export interface CreditGapsData {
  asOf: string | null;
  source: string;
  note: string;
  countries: CreditGapCountry[];
}

// Fiscal Sustainability (Phase 25)
export interface FiscalCountryKpis {
  debtGdp: number | null;
  debtGdpSignal: "green" | "yellow" | "red" | "unknown";
  fiscalBalance: number | null;
  fiscalBalanceSignal: "green" | "yellow" | "red" | "unknown";
  taxRevenue: number | null;
  taxRevenueSignal: "green" | "yellow" | "red" | "unknown";
  govtRevenue: number | null;
  govtExpenditure: number | null;
  grossSavings: number | null;
  gdpGrowth: number | null;
  primaryBalance: number | null;
  adverseDynamics: boolean;
}
export interface FiscalCountry {
  iso2: string;
  iso3: string;
  name: string;
  latestYear: number;
  kpis: FiscalCountryKpis;
  history: {
    debtGdp: MacroTimeSeries[];
    fiscalBalance: MacroTimeSeries[];
    taxRevenue: MacroTimeSeries[];
    gdpGrowth: MacroTimeSeries[];
    govtRevenue: MacroTimeSeries[];
    govtExpenditure: MacroTimeSeries[];
    grossSavings: MacroTimeSeries[];
  };
}
export interface FiscalData {
  asOf: string | null;
  source: string;
  countries: FiscalCountry[];
  summary: {
    avgDebtGdp: number | null;
    avgFiscalBalance: number | null;
    adverseDynamicsCount: number;
    totalCountries: number;
  };
}

// Trade Flows (Phase 26)
export interface TradeCountryKpis {
  exportsGdp: number | null;
  importsGdp: number | null;
  tradeBalance: number | null;
  tradeOpenness: number | null;
  merchandiseTrade: number | null;
}
export interface TradeCountry {
  iso2: string;
  iso3: string;
  name: string;
  latestYear: number;
  kpis: TradeCountryKpis;
  history: {
    exportsGdp: MacroTimeSeries[];
    importsGdp: MacroTimeSeries[];
    tradeBalance: MacroTimeSeries[];
    merchandiseTrade: MacroTimeSeries[];
  };
}
export interface TradeData {
  asOf: string | null;
  source: string;
  countries: TradeCountry[];
  summary: {
    avgExportsGdp: number | null;
    avgImportsGdp: number | null;
    avgTradeBalance: number | null;
    topSurplusCountry: string | null;
    topSurplusValue: number | null;
    totalCountries: number;
  };
}

// Business Dynamism (Phase 30)
export interface BusinessCountryKpis {
  newBusinessDensity: number | null;
  newBusinessDensitySignal: string;
  startupTime: number | null;
  startupTimeSignal: string;
  doingBusinessScore: number | null;
}
export interface BusinessCountry {
  iso2: string;
  iso3: string;
  name: string;
  latestYear: number;
  kpis: BusinessCountryKpis;
  history: {
    newBusinessDensity: MacroTimeSeries[];
    startupTime: MacroTimeSeries[];
    doingBusinessScore: MacroTimeSeries[];
  };
}
export interface BusinessData {
  asOf: string | null;
  source: string;
  countries: BusinessCountry[];
  summary: {
    avgBusinessDensity: number | null;
    avgStartupDays: number | null;
    avgDoingBusinessScore: number | null;
    totalCountries: number;
  };
}

// Labor Market (Phase 28 stub)
export interface LaborData {
  asOf: string | null;
  source: string;
  countries: any[];
  summary: Record<string, any>;
  methodology?: string;
}
// Energy & Climate (Phase 28 stub)
export interface EnergyData {
  asOf: string | null;
  source: string;
  countries: any[];
  summary: Record<string, any>;
  methodology?: string;
}
// Inequality (Phase 29 stub)
export interface InequalityData {
  asOf: string | null;
  source: string;
  countries: any[];
  summary: Record<string, any>;
  methodology?: string;
}
// Currency Crisis (Phase 28 stub)
export interface CurrencyCrisisData {
  asOf: string | null;
  source: string;
  countries: any[];
  summary: Record<string, any>;
  methodology?: string;
}
// Banking Stability (Phase 28 stub)
export interface BankingStabilityData {
  asOf: string | null;
  source: string;
  countries: any[];
  summary: Record<string, any>;
  methodology?: string;
}

// COT Positioning
export interface CotContract {
  name: string;
  code: string;
  net_speculator: number | null;
  net_commercial: number | null;
  cot_index: number | null;
  open_interest: number | null;
  history: { date: string; net_spec: number }[];
}
export interface CotData {
  asOf: string | null;
  contracts: CotContract[];
  source: string;
  error?: string | null;
}

// EDGAR (for Markets page)
export interface Holder13F {
  name: string;
  shares: number | null;
  value: number | null;
  pctFloat: number | null;
  changeShares: number | null;
  changePct: number | null;
}
export interface Holders13FResponse {
  ticker: string;
  asOf: string | null;
  reportingLag: string;
  holders: Holder13F[];
  error?: string | null;
}
export interface InsiderTransaction {
  insiderName: string;
  title: string | null;
  transactionType: "Buy" | "Sell";
  shares: number;
  pricePerShare: number | null;
  totalValue: number | null;
  date: string;
}
export interface Form4Response {
  ticker: string;
  transactions: InsiderTransaction[];
  error?: string | null;
}

// --- Snowflake Composite Score (Phase 9) ---
export interface SnowflakeScores {
  value: number | null;
  growth: number | null;
  performance: number | null;
  health: number | null;
  dividend: number | null;
}
export interface SnowflakeComponent {
  label: string;
  score: number | null;
  value?: number | null;
  percentile?: number | null;
  detail?: string | null;
  weight?: number;
}
export interface SnowflakeAxisDetail {
  score: number | null;
  components: SnowflakeComponent[];
}
export interface SnowflakeReward {
  axis: string;
  label: string;
  score: number;
}
export interface SnowflakeResponse {
  ticker: string;
  sector: string | null;
  industry: string | null;
  sectorPeers: number;
  overallScore: number | null;
  verdict: string;
  scores: SnowflakeScores;
  rewards: SnowflakeReward[];
  risks: SnowflakeReward[];
  axisDetails: Record<string, SnowflakeAxisDetail>;
}
export interface SnowflakeBatchResponse {
  [ticker: string]: {
    overallScore: number | null;
    scores: SnowflakeScores;
  };
}

// --- Phase 10: Sector Performance ---
export interface SectorReturn {
  ticker: string;
  sector: string;
  changePercent: number | null;
  vsSpy: number | null;
}
export interface SectorReturnsResponse {
  periods: {
    "1d": SectorReturn[];
    "1w": SectorReturn[];
    "1m": SectorReturn[];
    "3m": SectorReturn[];
    "ytd": SectorReturn[];
    "1y": SectorReturn[];
  };
}
export interface SectorFundamentals {
  ticker: string;
  sector: string;
  price: number | null;
  aum: number | null;
  trailingPE: number | null;
  priceToBook: number | null;
  dividendYield: number | null;
  beta: number | null;
  vol30d: number | null;
  maxDrawdown: number | null;
  return1m: number | null;
  return3m: number | null;
  return6m: number | null;
  return1y: number | null;
}
export type SectorFundamentalsResponse = SectorFundamentals[];
export interface SectorBubble {
  ticker: string;
  sector: string;
  return3m: number | null;
  vsSpy: number | null;
  aum: number | null;
  phaseRank: number | null;
}
export interface SectorRotationResponse {
  phase: "Early" | "Mid" | "Late" | "Recession";
  confidence: number;
  regimePhase: string | null;
  regimeQuadrant: string | null;
  sectors: SectorBubble[];
}
export interface IndustryGroup {
  industry: string;
  stocks: Array<{ symbol: string; name: string; change1d: number | null }>;
}
export type SectorDrillResponse = IndustryGroup[];

// --- Phase 11: Portfolio Analytics ---
export interface Holding {
  ticker: string;
  weight: number;
}

export interface PortfolioAnalysis {
  holdings: { ticker: string; weight: number; totalReturn: number | null; contribution: number | null }[];
  series: { date: string; value: number }[];
  drawdownSeries: { date: string; value: number }[];
  benchmarkSeries: {
    gspc: { date: string; value: number }[];
    agg: { date: string; value: number }[];
  };
  metrics: {
    totalReturn: number | null;
    annReturn: number | null;
    annVolatility: number | null;
    sharpe: number | null;
    sortino: number | null;
    maxDrawdown: number | null;
    var95: number | null;
    beta: number | null;
  };
  benchmark: string;
  missing: string[];
}

// correlation matrix is a 2D array (tickers x tickers)
export interface CorrelationData {
  tickers: string[];
  matrix: (number | null)[][];
}

// risk contribution returned as a flat list from backend
export interface RiskContribItem {
  ticker: string;
  weight: number | null;
  marginalContrib: number | null;
  pctContrib: number | null;
}
export type RiskContribData = RiskContribItem[];

export interface CAPMData {
  alpha: number | null;         // daily alpha
  annAlpha: number | null;      // annualised alpha
  beta: number | null;
  rSquared: number | null;
  systematicVarPct: number | null;
  idiosyncraticVarPct: number | null;
  nObs?: number;
  error?: string;
}

export interface DateValuePoint {
  date: string;
  value: number | null;
}
export interface RollingData {
  window: number;
  sharpe: DateValuePoint[];
  volatility: DateValuePoint[];
  beta: DateValuePoint[];
}

// Kelly returns a list (one per holding)
export interface KellyRow {
  ticker: string;
  annReturn: number | null;
  annVolatility: number | null;
  kellyFraction: number | null;
}
export type KellyData = KellyRow[];

export interface FFFactorRow {
  factor: string;
  loading: number | null;
  tStat: number | null;
}
export interface FFData {
  model: string;
  alpha: number | null;
  annAlpha: number | null;
  rSquared: number | null;
  factors: FFFactorRow[];
  nObs?: number;
  error?: string;
}

export interface FrontierPoint {
  vol: number | null;
  ret: number | null;
  sharpe: number | null;
}
export interface FrontierData {
  frontier: FrontierPoint[];
  currentPortfolio: FrontierPoint | null;
  maxSharpe: (FrontierPoint & { weights?: { ticker: string; weight: number }[] }) | null;
  error?: string;
  warning?: string;
}

export interface MCPortfolioPoint {
  vol: number | null;
  ret: number | null;
  sharpe: number | null;
}
export interface MCData {
  // backend returns 'points' key
  points: MCPortfolioPoint[];
  maxSharpe: (MCPortfolioPoint & { weights?: { ticker: string; weight: number }[] }) | null;
  error?: string;
}

export interface BLReturnRow {
  ticker: string;
  equilibriumReturn: number | null;
  blReturn: number | null;
}
export interface BLWeightRow {
  ticker: string;
  weight: number | null;
}
export interface BLData {
  blReturns: BLReturnRow[];
  optimalWeights: BLWeightRow[];
  currentWeights: BLWeightRow[];
  error?: string;
}

// Stress test returns a list of scenario objects
export interface StressScenario {
  scenario: string;
  label: string;
  start: string;
  end: string;
  totalReturn: number | null;
  maxDrawdown: number | null;
  returnsTimeSeries: DateValuePoint[];
  benchmark: DateValuePoint[];
  error?: string;
}
export type StressData = StressScenario[];

// --- Phase 12 Technicals ---
export interface TechnicalSummary {
  trend: 'Bullish' | 'Bearish' | 'Neutral' | 'N/A';
  rsi: number | null;
  macdSignal: 'Bullish' | 'Bearish' | 'Neutral' | 'N/A';
  volumeVs20d: number | null;
  week52Position: number | null;
  week52High: number | null;
  week52Low: number | null;
  bbSqueeze: boolean;
}

export interface BollingerPoint {
  date: string;
  upper: number;
  mid: number;
  lower: number;
  pctB: number | null;
  bandwidth: number | null;
}

export interface IchimokuPoint {
  date: string;
  tenkan: number | null;
  kijun: number | null;
  senkouA: number | null;
  senkouB: number | null;
  chikou: number | null;
}

export interface FibLevel {
  level: number;
  label: string;
  price: number;
}

export interface PivotSet {
  p: number;
  r1: number;
  r2: number;
  s1: number;
  s2: number;
}

export interface MACDPoint {
  date: string;
  macd: number | null;
  signal: number | null;
  hist: number | null;
}

export interface SubChartPoint {
  date: string;
  value: number | null;
}

export interface StochRsiPoint {
  date: string;
  k: number | null;
  d: number | null;
}

export interface PriceOHLCV {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface TechnicalsResponse {
  ticker: string;
  period: string;
  asOf: string | null;
  summary: TechnicalSummary;
  prices: PriceOHLCV[];
  bollinger: BollingerPoint[];
  ichimoku: IchimokuPoint[];
  macd: MACDPoint[];
  rsi: SubChartPoint[];
  stochRsi: StochRsiPoint[];
  williamsR: SubChartPoint[];
  obv: SubChartPoint[];
  cmf: SubChartPoint[];
  atr: SubChartPoint[];
  fibLevels: FibLevel[];
  pivotPoints: Record<'daily' | 'weekly' | 'monthly', PivotSet>;
}

// --- Phase 13: Global Macro Atlas ---
export interface AtlasIndicator {
  id: string;
  label: string;
  unit: string;
  goodDirection: "high" | "low" | "neutral";
}

export interface AtlasRegion {
  id: string;
  label: string;
  members: string[]; // ISO3 codes
}

export interface AtlasCountry {
  iso3: string;
  id: string | null; // ISO numeric (matches TopoJSON geo.id)
  name: string;
  regions: string[];
  values: Record<string, number | null>;
}

export interface AtlasTimelineResponse {
  indicator: string;
  label: string;
  unit: string;
  goodDirection: "high" | "low" | "neutral";
  start: number;
  end: number;
  countries: AtlasCountry[];
}

export interface AtlasSnapshotCountry {
  iso3: string;
  id: string | null;
  name: string;
  regions: string[];
  value: number | null;
}

export interface AtlasSnapshotResponse {
  indicator: string;
  unit: string;
  year: number;
  countries: AtlasSnapshotCountry[];
  stats: {
    avg: number | null;
    count_reporting: number;
    top: Array<{ iso3: string; name: string; value: number }>;
    bottom: Array<{ iso3: string; name: string; value: number }>;
  };
}

// --- Admin health ---
export interface CacheStat {
  hits: number;
  misses: number;
  hitRate: number | null;
  size: number;
}
export interface DbHealth {
  daily_price?: number;
  daily_quote?: number;
  daily_macro?: number;
  daily_fx?: number;
  job_execution?: number;
  cache_entries?: number;
  cache_size_kb?: number;
  error?: string;
}
export interface HealthResponse {
  status: string;
  uptimeSeconds: number;
  cache: {
    byName: Record<string, CacheStat>;
    totalHits: number;
    totalMisses: number;
    overallHitRate: number | null;
    ttlSeconds: number;
  };
  config: { fredApiKey: boolean; finnhubApiKey: boolean };
  database: DbHealth;
}

export interface BulkDatasetStatus {
  last_ok: string | null;
  last_attempt: string | null;
  error: string | null;
  rows: number | null;
  size_kb: number | null;
}

export interface ConfigResponse {
  fredApiKey: string | null;
  finnhubApiKey: string | null;
  restartRequired?: boolean;
}

export interface ConfigUpdateRequest {
  fredApiKey?: string;
  finnhubApiKey?: string;
}

export interface PrefetchStatus {
  running: boolean;
  started_at: string | null;
  completed_at: string | null;
  total: number;
  done: number;
  ok: number;
  failed: number;
  current: string | null;
  errors: { label: string; error: string }[];
}

// --- Phase 14: Research Hub ---
export interface WeightRow { ticker: string; weight: number | null; }
export interface RiskContribRow { ticker: string; weight: number | null; pctContrib: number | null; }
export interface RiskParityWeights {
  weights: WeightRow[];
  riskContrib: RiskContribRow[];
  missing: string[];
  error?: string;
}
export interface BacktestPoint { date: string; strategy: number | null; benchmark: number | null; }
export interface BacktestMetrics {
  cagr: number | null; vol: number | null; sharpe: number | null; maxDrawdown: number | null;
}
export interface RiskParityBacktest {
  series: BacktestPoint[];
  finalWeights: WeightRow[];
  metrics: { strategy: BacktestMetrics; benchmark: BacktestMetrics };
  missing: string[];
  error?: string;
}

export interface CarryRow {
  ccy: string;
  pair: string;
  spot: number | null;
  foreignRate: number | null;
  carry: number | null;
  fxVol: number | null;
  volAdjCarry: number | null;
  rateSource: string;
}
export interface CarryTable {
  asOf: string;
  usdRate: number | null;
  rows: CarryRow[];
  error?: string;
}
export interface CarryBacktest {
  series: BacktestPoint[];
  legs: { long: string[]; short: string[] };
  metrics: BacktestMetrics;
  error?: string;
}

export interface MomentumDecile { decile: number; avgReturn: number | null; count: number; }
export interface MomentumRank { ticker: string; momentum: number | null; }
export interface MomentumResponse {
  universe: string;
  signal: string;
  asOf: string;
  deciles: MomentumDecile[];
  top: MomentumRank[];
  bottom: MomentumRank[];
  missing: string[];
  error?: string;
}

// --- Phase 15: Realized Moments ---
export interface MomentSeriesPoint {
  date: string;
  rvol21: number | null;
  rvol63: number | null;
  rvol252: number | null;
  skew21: number | null;
  skew63: number | null;
  skew252: number | null;
  kurt21: number | null;
  kurt63: number | null;
  kurt252: number | null;
}
export interface MomentsLatest {
  rvol21: number | null;
  skew21: number | null;
  kurt21: number | null;
}
export interface MomentsResponse {
  ticker: string;
  period: string;
  asOf: string;
  series: MomentSeriesPoint[];
  latest: MomentsLatest | null;
  error?: string;
}
export interface MomentsCrossDecile {
  decile: number;
  avgSkew: number | null;
  avgFwdReturn: number | null;
  count: number;
}
export interface MomentsNameRow {
  ticker: string;
  priorSkew: number | null;
  fwdReturn: number | null;
}
export interface MomentsCrossSection {
  universe: string;
  window: number;
  asOf: string;
  deciles: MomentsCrossDecile[];
  names: MomentsNameRow[];
  missing: string[];
  error?: string;
}

// --- Phase 27: Sector DuPont ---
export interface DupontSectorRow {
  sector: string;
  netMargin: number | null;
  assetTurnover: number | null;
  equityMultiplier: number | null;
  roe: number | null;
  tickerCount: number;
}
export interface DupontResponse {
  sectors: DupontSectorRow[];
  asOf: string | null;
  tickerCount: number;
  note?: string;
  error?: string;
}

// --- Phase 27: Corporate Health ---
export interface ZScoreDetail {
  zScore: number | null;
  zone: "Safe" | "Grey" | "Distress" | "unknown";
  components: {
    x1_workingCapitalToAssets: number | null;
    x2_retainedEarningsToAssets: number | null;
    x3_ebitToAssets: number | null;
    x4_marketValueToLiabilities: number | null;
    x5_salesToAssets: number | null;
  };
  isFinancial: boolean;
  note?: string;
}
export interface PiotroskiDetail {
  score: number;
  maxScore: number;
  interpretation: "Strong" | "Average" | "Weak";
  criteria: Record<string, boolean | null>;
}
export interface BeneishDetail {
  mScore: number | null;
  manipulationLikely: boolean | null;
  interpretation: string;
  indexes: Record<string, number | null>;
  mComponents: Record<string, number | null>;
  validComponents: number;
  totalComponents: number;
}
export interface CorporateHealthResponse {
  ticker: string;
  name: string;
  sector: string | null;
  industry: string | null;
  price: number | null;
  altmanZ: ZScoreDetail;
  piotroski: PiotroskiDetail;
  beneish: BeneishDetail;
  asOf: string | null;
  error?: string;
}

// --- Phase 27: Dividend Analysis ---
export interface DividendAnalysisResponse {
  ticker: string;
  name: string;
  sector: string | null;
  price: number | null;
  dividendYield: number | null;
  latestAnnualDividend: number | null;
  latestYear: number | null;
  cagr5y: number | null;
  cagr10y: number | null;
  consecutiveGrowthYears: number;
  payoutRatio: number | null;
  fcfPayoutRatio: number | null;
  sustainabilityScore: number;
  sustainabilityLabel: "Strong" | "Adequate" | "Weak";
  ddmFairValue: number | null;
  ddmGrowthRate: number | null;
  ddmUpsidePct: number | null;
  annualDividends: Record<string, number>;
  asOf: string | null;
  error?: string;
}

// --- Phase 27: Insider Trading Aggregator ---
export interface InsiderClusterBuy {
  ticker: string;
  insiderCount: number;
  transactionCount: number;
  totalValue: number;
  dateRange: string;
}
export interface InsiderSectorSentiment {
  sector: string;
  buys: number;
  sells: number;
  netBuyRatio: number;
  totalBuyValue: number;
  totalSellValue: number;
}
export interface InsiderTopTrade {
  ticker: string;
  insiderName: string;
  title: string | null;
  transactionType: string;
  shares: number | null;
  pricePerShare: number | null;
  totalValue: number | null;
  date: string | null;
  sector: string;
}
export interface InsiderAggregateResponse {
  asOf: string | null;
  tickersChecked: number;
  tickersWithData: number;
  totalTransactions: number;
  buyCount: number;
  sellCount: number;
  buySellRatio: number | null;
  totalBuyValue: number;
  totalSellValue: number;
  valueRatio: number | null;
  clusterBuys: InsiderClusterBuy[];
  sectorSentiment: InsiderSectorSentiment[];
  topTrades: InsiderTopTrade[];
  error?: string;
}

// --- Phase 15: Econometric Lab ---
export interface RegressCoefficient {
  name: string;
  coef: number | null;
  stdErr: number | null;
  tStat: number | null;
  pValue: number | null;
  stars: string;
}
export interface RegressResidual {
  country: string;
  year: number;
  fitted: number | null;
  residual: number | null;
}
export interface RegressResponse {
  dep: string;
  indep: string[];
  countries: string[];
  start: number;
  end: number;
  asOf?: string;
  nObs: number;
  rSquared?: number | null;
  adjRSquared?: number | null;
  aic?: number | null;
  bic?: number | null;
  coefficients: RegressCoefficient[];
  residuals: RegressResidual[];
  warning?: string | null;
  error?: string;
}

// Phase 16 — Country Risk
export interface CountryRiskIndicators {
  debt_gdp: number | null;
  current_account: number | null;
  inflation: number | null;
  fiscal_balance: number | null;
  reserves_growth: number | null;
  unemployment: number | null;
}
export type TrafficLight = "green" | "yellow" | "red" | null;
export interface CountryRiskEntry {
  iso3: string;
  name: string;
  year: number;
  indicators: CountryRiskIndicators;
  signals: Record<keyof CountryRiskIndicators, TrafficLight>;
}
export interface CountryRiskData {
  countries: CountryRiskEntry[];
  thresholds: Record<string, { green: string; yellow: string; red: string }>;
}

// Phase 16 — Central Banks
export interface CbCurrent {
  rate: number | null;
  series: string;
  next_meeting: string | null;
  days_until: number | null;
}
export interface CentralBanksData {
  history: Array<{
    date: string;
    Fed?: number; ECB?: number; BoE?: number; BoJ?: number;
    BoC?: number; RBA?: number; SNB?: number;
  }>;
  current: Record<string, CbCurrent>;
  balance_sheet: Array<{ date: string; value: number }>;
}

// ── Phase 18A ──────────────────────────────────────────────────

export interface CreditPulseData {
  current: {
    ig_oas: number | null;
    hy_oas: number | null;
    bbb_spread: number | null;
    funding_spread: number | null;
    hy_ig_ratio: number | null;
  };
  history: {
    ig_oas: MacroTimeSeries[];
    hy_oas: MacroTimeSeries[];
    bbb_spread: MacroTimeSeries[];
    funding_spread: MacroTimeSeries[];
  };
  signals: { ig_oas: string; hy_oas: string; stress: boolean };
}

export interface YieldCurvePoint { tenor: string; years: number; yield: number | null; }
export interface GlobalYieldCountry {
  iso2: string;
  name: string;
  yield_10y: number | null;
  spread_vs_us: number | null;
  spread_vs_de: number | null;
  spread_vs_jp: number | null;
  real_yield: number | null;
  inflation: number | null;
}
export interface YieldCurvesData {
  us_curve: {
    points: YieldCurvePoint[];
    spread_2y10y: number | null;
    spread_3m10y: number | null;
    inverted: boolean;
  };
  real_yields: YieldCurvePoint[];
  breakevens: Record<string, number | null>;
  term_premium: { current: number | null; history: MacroTimeSeries[] };
  foreign_10y: Record<string, { yield_10y: number | null; spread_vs_us: number | null }>;
  global_yields?: GlobalYieldCountry[];
}

export interface PolicyDivergenceEntry {
  cb: string;
  current_rate: number | null;
  change_3m: number | null;
  change_12m: number | null;
  stance: "tightening" | "easing" | "on_hold" | "unknown";
  divergence_rank: number;
}
export interface PolicyTrackerData {
  divergence: PolicyDivergenceEntry[];
  carry_differentials: Record<string, number | null>;
}

export interface SovereignCountry {
  iso3: string;
  name: string;
  yield_10y: number | null;
  spread_vs_us: number | null;
  composite_score: number;
  signal: "green" | "yellow" | "red";
  wb_indicators: Record<string, number | null>;
  wb_signals: Record<string, string>;
}
export interface SovereignRiskData {
  countries: SovereignCountry[];
  top_risk: SovereignCountry[];
  bottom_risk: SovereignCountry[];
}

// ─── Wiki ──────────────────────────────────────────────────────
export interface WikiTerm {
  slug: string;
  term: string;
  category: string;
  definition: string;
  related: string[];
}
export interface WikiCategory {
  key: string;
  label: string;
  icon: string;
  count: number;
}
export interface WikiCategoriesResponse {
  categories: WikiCategory[];
  total: number;
}
export interface WikiTermsResponse {
  terms: WikiTerm[];
  total: number;
  query: string;
  category: string;
}

export interface MacroRegimeData {
  regime: "Goldilocks" | "Reflationary" | "Stagflation" | "Deflationary";
  quadrant: 1 | 2 | 3 | 4;
  growth_z: number | null;
  inflation_z: number | null;
  growth_signal: "rising" | "falling";
  inflation_signal: "above" | "below";
  metrics: {
    lei_current: number | null;
    lei_change_3m: number | null;
    cpi_yoy: number | null;
    fed_funds: number | null;
    yield_spread_2y10y: number | null;
  };
  asset_signals: Record<string, "overweight" | "underweight" | "neutral">;
  allocation: Record<string, number>;
}
