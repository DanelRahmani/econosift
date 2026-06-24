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
