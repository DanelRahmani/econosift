"use client";

import { useState, useEffect, Suspense, lazy, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useUrlState } from "@/lib/useUrlState";
import type { EventsResponse } from "@/lib/types";
import { SearchBar } from "@/components/SearchBar";
import { Card, Skeleton, ChartSkeleton, ScrollableTabBar, ExportPdfButton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { PriceChart } from "@/components/markets/PriceChart";
import { QuoteCards } from "@/components/markets/QuoteCards";
import { NewsFeed } from "@/components/markets/NewsFeed";
import { InstitutionalHolders } from "@/components/markets/InstitutionalHolders";
import { InsiderActivity } from "@/components/markets/InsiderActivity";
import { Watchlist } from "@/components/Watchlist";
import { AiSummaryPanel } from "@/components/AiSummaryPanel";
import { WalkthroughBanner } from "@/components/WalkthroughBanner";
import { SnowflakeChart } from "@/components/markets/SnowflakeChart";
import { TabSkeleton } from "@/components/markets/TabSkeleton";
import { TreemapChart } from "@/components/markets/Treemap";
import { SectorReturnsChart } from "@/components/sectors/SectorReturnsChart";
import { SectorFundamentalsTable } from "@/components/sectors/SectorFundamentalsTable";
import { SectorRotationClock } from "@/components/sectors/SectorRotationClock";
import { SectorIndustryDrillDown } from "@/components/sectors/SectorIndustryDrillDown";
import { MARKETS_TABS } from "@/lib/pageTabs";
import type {
  TreemapResponse, SectorReturnsResponse,
  SectorFundamentalsResponse, SectorRotationResponse, SectorDrillResponse,
} from "@/lib/types";
import { useRefreshNonce } from "@/lib/refresh";

const ValuationTab = lazy(() =>
  import("@/components/markets/ValuationTab").then((m) => ({ default: m.ValuationTab }))
);
const TechnicalsTab = lazy(() =>
  import("@/components/markets/TechnicalsTab").then((m) => ({ default: m.TechnicalsTab }))
);
const RatiosTab = lazy(() =>
  import("@/components/markets/RatiosTab").then((m) => ({ default: m.RatiosTab }))
);
const ShortInterestPanel = lazy(() =>
  import("@/components/markets/ShortInterestPanel").then((m) => ({ default: m.ShortInterestPanel }))
);
const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"];
const BENCHMARKS = [
  { value: "", label: "Auto" },
  { value: "^GSPC", label: "S&P 500" },
  { value: "^NDX", label: "Nasdaq 100" },
  { value: "^DJI", label: "Dow Jones" },
  { value: "^RUT", label: "Russell 2000" },
];
const SEC_PERIODS = ["1d", "1w", "1m", "3m", "ytd", "1y"] as const;
const TABS = MARKETS_TABS;
type Tab = (typeof TABS)[number];

function MarketsPageInner() {
  const router = useRouter();

  const [urlState, setUrlState] = useUrlState({
    t: "AAPL,MSFT",
    p: "1y",
    tab: "Overview",
    b: "",
  });

  // Derive typed helpers from URL string state.
  const tickers = useMemo(
    () => urlState.t.split(",").filter(Boolean),
    [urlState.t],
  );
  const tickersKey = urlState.t;
  const period = urlState.p;
  const tab = (TABS as readonly string[]).includes(urlState.tab) ? (urlState.tab as Tab) : "Overview";
  const benchmark = urlState.b;

  const [showWatchlist, setShowWatchlist] = useState(false);

  // Sector state
  const [secReturns, setSecReturns] = useState<SectorReturnsResponse | null>(null);
  const [secFundamentals, setSecFundamentals] = useState<SectorFundamentalsResponse | null>(null);
  const [secRotation, setSecRotation] = useState<SectorRotationResponse | null>(null);
  const [secLoading, setSecLoading] = useState(false);
  const [secPeriod, setSecPeriod] = useState<keyof SectorReturnsResponse["periods"]>("1d");
  // One scope per card: the returns response feeds two cards.
  const secKpiScope = useSourceScope(provOf(secReturns));
  const secChartScope = useSourceScope(provOf(secReturns));
  const secRotationScope = useSourceScope(provOf(secRotation));
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [drillData, setDrillData] = useState<SectorDrillResponse | null>(null);
  const [drillLoading, setDrillLoading] = useState(false);

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (tab !== "Sectors") return;
    let alive = true;
    setSecLoading(true);
    Promise.all([api.sectorReturns(), api.sectorFundamentals(), api.sectorRotation()])
      .then(([r, f, rot]) => { if (alive) { setSecReturns(r); setSecFundamentals(f); setSecRotation(rot); } })
      .catch(() => {})
      .finally(() => { if (alive) setSecLoading(false); });
    return () => { alive = false; };
  }, [tab, refreshNonce]);

  useEffect(() => {
    if (!selectedSector) { setDrillData(null); return; }
    let alive = true;
    setDrillLoading(true);
    api.sectorDrill(selectedSector)
      .then((d) => { if (alive) setDrillData(d); })
      .catch(() => { if (alive) setDrillData(null); })
      .finally(() => { if (alive) setDrillLoading(false); });
    return () => { alive = false; };
  }, [selectedSector, refreshNonce]);

  // Treemap state
  const [tmIndex, setTmIndex] = useState<"sp500" | "ndx" | "dow">("sp500");
  const [tmPeriod, setTmPeriod] = useState<string>("1d");
  const [tmData, setTmData] = useState<TreemapResponse | null>(null);
  const [tmLoading, setTmLoading] = useState(false);
  const tmScope = useSourceScope(provOf(tmData));

  useEffect(() => {
    if (tab !== "Treemap") return;
    let alive = true;
    setTmLoading(true);
    api.treemap(tmIndex, tmPeriod)
      .then((r) => { if (alive) setTmData(r); })
      .catch(() => {})
      .finally(() => { if (alive) setTmLoading(false); });
    return () => { alive = false; };
  }, [tab, tmIndex, tmPeriod, refreshNonce]);

  // Redirect old deprecated tabs
  useEffect(() => {
    const redirectMap: Record<string, string> = {
      Risk: `/risk${tickers.length ? `?t=${tickersKey}` : ""}`,
      Portfolio: `/portfolio${tickers.length ? `?t=${tickersKey}` : ""}`,
      Rankings: "/screener",
      Screener: "/screener",
      FX: "/macro?tab=fx",
    };
    if (urlState.tab && redirectMap[urlState.tab]) {
      router.replace(redirectMap[urlState.tab]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { data: prices, isLoading: pricesLoading } = useQuery({
    queryKey: ["market-prices", tickersKey, period, benchmark ?? ""],
    queryFn: () => api.prices(tickersKey, period, benchmark || undefined),
    staleTime: 5 * 60 * 1000,
    enabled: tickers.length > 0,
  });

  const { data: risk, isLoading: riskLoading } = useQuery({
    queryKey: ["market-risk", tickersKey, period, benchmark ?? ""],
    queryFn: () => api.risk(tickersKey, period, undefined, benchmark || undefined),
    staleTime: 5 * 60 * 1000,
    enabled: tickers.length > 0,
  });

  const { data: eventsData } = useQuery({
    queryKey: ["market-events", tickersKey],
    queryFn: async () => {
      const results = await Promise.all(
        tickers.slice(0, 6).map((t) => api.events(t).catch(() => null))
      );
      return results.filter((e): e is EventsResponse => e !== null);
    },
    staleTime: 30 * 60 * 1000,
    enabled: tickers.length > 0,
  });

  const events = eventsData ?? [];
  const riskScope = useSourceScope(provOf(risk));

  function addTicker(sym: string) {
    const next = tickers.includes(sym) ? tickers : [...tickers, sym];
    setUrlState({ t: next.join(",") });
  }
  function removeTicker(sym: string) {
    const next = tickers.filter((t) => t !== sym);
    setUrlState({ t: next.join(",") });
  }

  function handleSnowflakeClick(t: string) {
    if (t === "Valuation" || t === "Ratios" || t === "Sectors") {
      setUrlState({ tab: t });
    } else {
      const redirects: Record<string, string> = {
        Portfolio: `/portfolio?t=${tickersKey}`,
        Screener: "/screener",
        FX: "/macro?tab=fx",
      };
      const dest = redirects[t];
      if (dest) router.push(dest);
    }
  }

  function setTab(t: Tab) {
    setUrlState({ tab: t });
  }

  return (
    <div className="space-y-6">
      <WalkthroughBanner pageKey="markets" />
      <div className="flex flex-wrap items-center gap-4" data-hide-print>
        <SearchBar onAdd={addTicker} />
        <div className="flex flex-wrap gap-2">
          {tickers.map((t) => (
            <span key={t} className="chip">
              {t}
              <button onClick={() => removeTicker(t)} className="text-text-muted hover:text-danger">×</button>
            </span>
          ))}
        </div>
        <button
          onClick={() => setShowWatchlist((v) => !v)}
          className={`ml-auto px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
            showWatchlist
              ? "bg-accent/10 border-accent/40 text-accent"
              : "border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt"
          }`}
        >
          Watchlist
        </button>
        <ExportPdfButton />
      </div>

      {showWatchlist && (
        <Watchlist onSelect={addTicker} />
      )}

      <div className="flex flex-wrap items-center justify-between gap-4" data-hide-print>
        <ScrollableTabBar className="sticky top-14 z-20 bg-background/95 backdrop-blur py-1">
          {TABS.map((t) => (
            <button
              key={t}
              data-active={tab === t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                tab === t ? "bg-accent text-white" : "text-text-secondary hover:bg-surface-alt"
              }`}
            >
              {t}
            </button>
          ))}
        </ScrollableTabBar>
        {(tab === "Overview" || tab === "Technicals" || tab === "Valuation") && (
          <div className="flex items-center gap-3">
            {(tab === "Overview" || tab === "Technicals") && (
              <label className="flex items-center gap-1.5 text-xs text-text-muted">
                <span>Benchmark</span>
                <select
                  value={benchmark}
                  onChange={(e) => setUrlState({ b: e.target.value })}
                  className="rounded-md bg-surface-alt border border-border px-2 py-1 text-xs text-text-primary"
                >
                  {BENCHMARKS.map((b) => (
                    <option key={b.value} value={b.value}>{b.label}</option>
                  ))}
                </select>
              </label>
            )}
            <div className="flex gap-1">
              {PERIODS.map((p) => (
                <button
                  key={p}
                  onClick={() => setUrlState({ p })}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
                    period === p ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {!tickers.length && tab !== "Technicals" && tab !== "News & Events" && tab !== "Sectors" && tab !== "Treemap" && (
        <Card><div className="text-text-muted">Search and add a ticker to begin.</div></Card>
      )}

      {tab === "Overview" && tickers.length > 0 && (
        <div className="space-y-6">
          <QuoteCards tickers={tickers} />
          {risk && (
            <div className="space-y-4" {...riskScope}>
              {(risk.metrics ?? []).map((m) => {
                const n = m.nObs ?? m.returns?.length ?? null;
                const rfStr = risk.riskFree != null
                  ? `rf ${(risk.riskFree * 100).toFixed(2)}%${risk.riskFreeSource ? ` (${risk.riskFreeSource})` : ""}`
                  : null;
                return (
                  <div key={m.ticker} data-prov-ctx={m.ticker}>
                    <div className="flex flex-wrap items-baseline gap-x-3 mb-2">
                      <span className="text-sm font-semibold font-mono">{m.ticker}</span>
                      <span className="text-xs text-text-muted">
                        {period} window · {n != null ? `${n} daily returns` : "sample size n/a"}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      <Card className="p-4" data-prov={`metrics.${m.ticker}.var95`}>
                        <div className="text-xs text-text-secondary">1-day VaR 95%</div>
                        <div className="text-xl font-bold mt-1">
                          {m.var95 != null ? `${(m.var95 * 100).toFixed(1)}%` : "—"}
                        </div>
                        <div className="text-[11px] text-text-muted mt-1">historical, 5th percentile of daily returns</div>
                      </Card>
                      <Card className="p-4" data-prov={`metrics.${m.ticker}.sharpe`}>
                        <div className="text-xs text-text-secondary">Sharpe Ratio</div>
                        <div className="text-xl font-bold mt-1">
                          {m.sharpe != null ? m.sharpe.toFixed(2) : "—"}
                        </div>
                        <div className="text-[11px] text-text-muted mt-1">{rfStr ?? "risk-free rate not reported"}</div>
                      </Card>
                      <Card className="p-4" data-prov={`metrics.${m.ticker}.beta`}>
                        <div className="text-xs text-text-secondary">Beta</div>
                        <div className="text-xl font-bold mt-1">
                          {m.beta != null ? m.beta.toFixed(2) : "—"}
                        </div>
                        <div className="text-[11px] text-text-muted mt-1">
                          {period} daily vs {m.benchmark || "benchmark"}
                        </div>
                      </Card>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Normalised Price (base 100)</h2>
            {pricesLoading ? <Skeleton className="h-96" /> : prices && <PriceChart data={prices} events={events} />}
          </Card>
          <SnowflakeChart ticker={tickers[0]} onAxisClick={handleSnowflakeClick} />
          <AiSummaryPanel
            summaryType="company"
            title="AI Analysis"
            options={tickers.map((t) => ({ key: t, label: t }))}
            onGenerate={(model, force, selected) => api.aiCompany(selected.join(",") || tickers[0], model, force)}
          />
          <NewsFeed tickers={tickers} />
        </div>
      )}

      {tab === "Technicals" && tickers.length > 0 && (
        <Suspense fallback={<TabSkeleton />}>
          <TechnicalsTab ticker={tickers[0]} />
        </Suspense>
      )}

      {!tickers.length && tab === "Technicals" && (
        <Card><div className="text-text-muted">Search and add a ticker to begin.</div></Card>
      )}

      {tab === "Valuation" && tickers.length > 0 && (
        <Suspense fallback={<TabSkeleton />}>
          <ValuationTab tickers={tickers} period={period} onNavigateTab={(t) => setTab(t as Tab)} />
        </Suspense>
      )}

      {tab === "Ratios" && tickers.length > 0 && (
        <Suspense fallback={<TabSkeleton />}>
          <RatiosTab tickers={tickers} />
        </Suspense>
      )}

      {tab === "News & Events" && (
        <div className="space-y-6">
          {tickers.length > 0 ? (
            <>
              <InstitutionalHolders ticker={tickers[0]} />
              <InsiderActivity ticker={tickers[0]} />
              <NewsFeed tickers={tickers} />
            </>
          ) : (
            <Card><div className="text-text-muted">Search and add a ticker to begin.</div></Card>
          )}
        </div>
      )}

      {tab === "Sectors" && (
        <div className="space-y-6">
          <h2 className="text-sm font-semibold text-text-secondary">Sector Performance</h2>
          {/* KPI strip */}
          <Card {...secKpiScope} data-prov="periods.1d">
            <h3 className="text-sm font-semibold text-text-secondary mb-3">Today&apos;s Returns</h3>
            {secLoading ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {Array.from({ length: 11 }).map((_, i) => (
                  <div key={i} className="animate-pulse bg-surface-alt rounded-lg h-14" />
                ))}
              </div>
            ) : secReturns ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {[...(secReturns.periods["1d"] ?? [])]
                  .sort((a, b) => (b.changePercent ?? 0) - (a.changePercent ?? 0))
                  .map((s) => (
                    <button key={s.ticker} onClick={() => setSelectedSector(s.sector === selectedSector ? null : s.sector)}
                      data-prov-ctx={s.sector}
                      className={`rounded-lg p-2.5 border text-left transition-colors ${
                        selectedSector === s.sector ? "border-accent bg-accent/10" : "border-border/60 hover:border-border"
                      }`}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-mono text-text-muted">{s.ticker}</span>
                      </div>
                      <div className="text-xs text-text-secondary leading-tight mb-1">{s.sector}</div>
                      <div className={`text-sm font-mono font-semibold ${(s.changePercent ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                        {s.changePercent !== null ? `${s.changePercent >= 0 ? "+" : ""}${s.changePercent.toFixed(2)}%` : "—"}
                      </div>
                    </button>
                  ))}
              </div>
            ) : null}
          </Card>
          {/* Returns chart */}
          <Card {...secChartScope} data-prov={`periods.${secPeriod}`}>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <h3 className="text-sm font-semibold text-text-secondary">Sector Returns by Period</h3>
              <div className="flex gap-1">
                {SEC_PERIODS.map((p) => (
                  <button key={p} onClick={() => setSecPeriod(p)}
                    className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
                      secPeriod === p ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"
                    }`}
                  >
                    {p.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            {secLoading ? <ChartSkeleton height="h-80" />
              : secReturns ? <SectorReturnsChart data={secReturns.periods[secPeriod as keyof typeof secReturns.periods] ?? []}
                  onSectorClick={(s) => setSelectedSector(s === selectedSector ? null : s)} /> : null}
          </Card>
          {/* Fundamentals */}
          <Card>
            <h3 className="text-sm font-semibold text-text-secondary mb-4">Sector ETF Fundamentals</h3>
            {secLoading || !secFundamentals ? (
              <ChartSkeleton height="h-48" />
            ) : <SectorFundamentalsTable data={secFundamentals} />}
          </Card>
          {/* Rotation clock */}
          <Card {...secRotationScope}>
            <h3 className="text-sm font-semibold text-text-secondary mb-4">Sector Rotation Clock</h3>
            <p className="text-xs text-text-muted mb-4">
              Sam Stovall 4-phase model. Bubbles sized by AUM. Click a dot to explore an industry.
            </p>
            {secLoading || !secRotation ? (
              <ChartSkeleton height="h-96" />
            ) : <SectorRotationClock data={secRotation} onSectorClick={(s) => setSelectedSector(s === selectedSector ? null : s)} />}
          </Card>
          {/* Industry drill-down */}
          {selectedSector && (
            <Card>
              <SectorIndustryDrillDown sector={selectedSector} data={drillData} loading={drillLoading} />
            </Card>
          )}
        </div>
      )}

      {tab === "Treemap" && (
        <div className="space-y-6">
          <h2 className="text-sm font-semibold text-text-secondary">Market Treemap</h2>
          <Card className="p-4" {...tmScope}>
            <div className="flex flex-wrap gap-3 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">Index</span>
                {[["sp500","S&P 500"],["ndx","Nasdaq-100"],["dow","Dow 30"]].map(([key, label]) => (
                  <button key={key} onClick={() => setTmIndex(key as any)}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                      tmIndex === key ? "bg-accent text-white" : "text-text-muted hover:bg-surface-alt"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">Period</span>
                {SEC_PERIODS.map((p) => (
                  <button key={p} onClick={() => setTmPeriod(p)}
                    className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
                      tmPeriod === p ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"
                    }`}
                  >
                    {p.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            {tmLoading ? (
              <Skeleton className="h-80" />
            ) : tmData && tmData.stocks ? (
              <TreemapChart stocks={tmData.stocks} groupBy="sector" period={tmPeriod} />
            ) : (
              <div className="h-80 flex items-center justify-center text-text-muted text-sm">No treemap data</div>
            )}
          </Card>
        </div>
      )}

      {tab === "Short Interest" && (
        <Suspense fallback={<div className="h-40 animate-pulse bg-surface-alt rounded" />}>
          <ShortInterestPanel />
        </Suspense>
      )}
    </div>
  );
}

export default function MarketsPage() {
  return (
    <Suspense fallback={null}>
      <MarketsPageInner />
    </Suspense>
  );
}
