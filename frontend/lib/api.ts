import type {
  PricesResponse, Quote, RiskResponse, ValuationResponse, RatiosResponse,
  SearchResult, Indicator, Country, MacroResponse, FxResponse,
} from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  prices: (tickers: string, period: string) =>
    get<PricesResponse>(`/market/prices?tickers=${encodeURIComponent(tickers)}&period=${period}`),

  quote: (ticker: string) =>
    get<Quote>(`/market/quote/${encodeURIComponent(ticker)}`),

  risk: (tickers: string, period: string, riskFree: number) =>
    get<RiskResponse>(`/market/risk?tickers=${encodeURIComponent(tickers)}&period=${period}&risk_free=${riskFree}`),

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
};
