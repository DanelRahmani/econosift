import type {
  PricesResponse, Quote, RiskResponse, ValuationResponse, RatiosResponse,
  SearchResult, Indicator, Country, MacroResponse, FxResponse,
  PortfolioResponse, SectorsResponse, RelStrengthResponse, ScreenerResponse,
  EventsResponse, YieldCurveResponse, HealthResponse, NewsResponse,
  SnapshotResponse, ForecastResponse,
  DcfResponse, FxRatesResponse, RegimeResponse,
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
};
