// How long react-query treats a response as fresh, per data class. Within that
// window a tab switch or a remount reuses the cached answer instead of asking
// the backend again. The backend serves everything from econosift.db; the
// windows follow how often the fetcher writes each class (plan §2.2, §4).
// Kept free of imports so `node --test tests/unit` can load it directly.

export const STALE_MS = {
  live: 0, // admin status: show what the backend says right now
  snapshot: 60_000, // quotes, breadth, movers: the fetcher snapshots every ~15 min
  default: 5 * 60_000,
  fundamentals: 30 * 60_000, // SEC facts and Yahoo estimates change at most daily
  macro: 60 * 60_000, // macro, rates, atlas, reference data: daily or slower
} as const;

type StaleClass = keyof typeof STALE_MS;

// Keyed by the api.ts method name, which is also the first element of every
// query key built by apiQuery() (lib/queries.ts).
const CLASS_BY_NAME: Record<string, StaleClass> = {
  health: "live", prefetchStatus: "live", bulkDataStatus: "live", config: "live",
  adminErrors: "live", screenerStatus: "live", aiHistory: "live", fetchTransactions: "live",

  quote: "snapshot", prices: "snapshot", snapshot: "snapshot", breadth: "snapshot",
  indices: "snapshot", fearGreed: "snapshot", movers: "snapshot", treemap: "snapshot",
  screener: "snapshot", screenerUniverse: "snapshot", sectors: "snapshot",
  relativeStrength: "snapshot", sectorReturns: "snapshot", sectorRotation: "snapshot",
  sectorDrill: "snapshot", fetchTechnicals: "snapshot", optionsKPIs: "snapshot",
  optionsChain: "snapshot", optionsTermStructure: "snapshot", optionsSmile: "snapshot",
  optionsOIProfile: "snapshot", optionsExpiries: "snapshot",

  valuation: "fundamentals", valuationFull: "fundamentals", valuationFactors: "fundamentals",
  ratios: "fundamentals", dcf: "fundamentals", snowflake: "fundamentals",
  snowflakeBatch: "fundamentals", corporateHealth: "fundamentals",
  corporateEarningsQuality: "fundamentals", dividendAnalysis: "fundamentals",
  researchDupont: "fundamentals", sectorFundamentals: "fundamentals",
  market13f: "fundamentals", marketForm4: "fundamentals", marketShortInterest: "fundamentals",
  insiderAggregate: "fundamentals", events: "fundamentals", calendar: "fundamentals",
  mergers: "fundamentals", news: "fundamentals",

  constituents: "macro", search: "macro", indicators: "macro", countries: "macro",
  macroData: "macro", fx: "macro", fxRates: "macro", riskFreeRates: "macro", regime: "macro",
  yieldCurve: "macro", yieldCurves: "macro", yieldNoise: "macro", policyTracker: "macro",
  sovereignRisk: "macro", sovereignDefaultProb: "macro", creditPulse: "macro",
  factbookCountries: "macro", factbookCountry: "macro", crossborderClaims: "macro",
  wikiCategories: "macro", wikiTerms: "macro", screenerPresets: "macro",
  backtestSignals: "macro", carryTable: "macro",
};

export function staleTimeFor(name: string): number {
  const cls =
    CLASS_BY_NAME[name] ??
    (/^(macro|atlas|stability)/.test(name) ? "macro" : "default");
  return STALE_MS[cls];
}

/** One retry; up to six only while the desktop backend is still starting (BackendGate). */
export function retryFor(failureCount: number, backendStarting: boolean): boolean {
  return failureCount < (backendStarting ? 6 : 1);
}
