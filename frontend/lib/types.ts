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
