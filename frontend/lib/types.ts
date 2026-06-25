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
  config: { fredApiKey: boolean };
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
