"use client";

import { useState, useEffect, Suspense, lazy } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { EventsResponse } from "@/lib/types";
import { SearchBar } from "@/components/SearchBar";
import { Card, Skeleton, ChartSkeleton, ScrollableTabBar, ExportPdfButton } from "@/components/ui";
import { PriceChart } from "@/components/markets/PriceChart";
import { QuoteCards } from "@/components/markets/QuoteCards";
import { NewsFeed } from "@/components/markets/NewsFeed";
import { InstitutionalHolders } from "@/components/markets/InstitutionalHolders";
import { InsiderActivity } from "@/components/markets/InsiderActivity";
import { Watchlist } from "@/components/Watchlist";
import { SnowflakeChart } from "@/components/markets/SnowflakeChart";
import { TabSkeleton } from "@/components/markets/TabSkeleton";
import { TreemapChart } from "@/components/markets/Treemap";
import { SectorReturnsChart } from "@/components/sectors/SectorReturnsChart";
import { SectorFundamentalsTable } from "@/components/sectors/SectorFundamentalsTable";
import { SectorRotationClock } from "@/components/sectors/SectorRotationClock";
import { SectorIndustryDrillDown } from "@/components/sectors/SectorIndustryDrillDown";
import type {
  TreemapResponse, SectorReturnsResponse,
  SectorFundamentalsResponse, SectorRotationResponse, SectorDrillResponse,
} from "@/lib/types";

const ValuationTab = lazy(() =>
  import("@/components/markets/ValuationTab").then((m) => ({ default: m.ValuationTab }))
);
const TechnicalsTab = lazy(() =>
  import("@/components/markets/TechnicalsTab").then((m) => ({ default: m.TechnicalsTab }))
);
const RatiosTab = lazy(() =>
  import("@/components/markets/RatiosTab").then((m) => ({ default: m.RatiosTab }))
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
const TABS = ["Overview", "Technicals", "Valuation", "Ratios", "News & Events", "Sectors", "Treemap"] as const;
type Tab = (typeof TABS)[number];

function MarketsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [tickers, setTickers] = useState<string[]>(() => {
    const t = searchParams.get("t");
    return t ? t.split(",").filter(Boolean) : ["AAPL", "MSFT"];
  });
  const [period, setPeriod] = useState<string>(() => searchParams.get("p") ?? "1y");
  const [tab, setTab] = useState<Tab>(() => {
    const v = searchParams.get("tab") ?? "";
    return (TABS as readonly string[]).includes(v) ? (v as Tab) : "Overview";
  });
  const [showWatchlist, setShowWatchlist] = useState(false);
  const [benchmark, setBenchmark] = useState<string>(() => searchParams.get("b") ?? "");

  // Sector state
  const [secReturns, setSecReturns] = useState<SectorReturnsResponse | null>(null);
  const [secFundamentals, setSecFundamentals] = useState<SectorFundamentalsResponse | null>(null);
  const [secRotation, setSecRotation] = useState<SectorRotationResponse | null>(null);
  const [secLoading, setSecLoading] = useState(false);
  const [secPeriod, setSecPeriod] = useState<keyof SectorReturnsResponse["periods"]>("1d");
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [drillData, setDrillData] = useState<SectorDrillResponse | null>(null);
  const [drillLoading, setDrillLoading] = useState(false);

  useEffect(() => {
    if (tab !== "Sectors") return;
    let alive = true;
    setSecLoading(true);
    Promise.all([api.sectorReturns(), api.sectorFundamentals(), api.sectorRotation()])
      .then(([r, f, rot]) => { if (alive) { setSecReturns(r); setSecFundamentals(f); setSecRotation(rot); } })
      .catch(() => {})
      .finally(() => { if (alive) setSecLoading(false); });
    return () => { alive = false; };
  }, [tab]);

  useEffect(() => {
    if (!selectedSector) { setDrillData(null); return; }
    let alive = true;
    setDrillLoading(true);
    api.sectorDrill(selectedSector)
      .then((d) => { if (alive) setDrillData(d); })
      .catch(() => { if (alive) setDrillData(null); })
      .finally(() => { if (alive) setDrillLoading(false); });
    return () => { alive = false; };
  }, [selectedSector]);

  // Treemap state
  const [tmIndex, setTmIndex] = useState<"sp500" | "ndx" | "dow">("sp500");
  const [tmPeriod, setTmPeriod] = useState<string>("1d");
  const [tmData, setTmData] = useState<TreemapResponse | null>(null);
  const [tmLoading, setTmLoading] = useState(false);

  useEffect(() => {
    if (tab !== "Treemap") return;
    let alive = true;
    setTmLoading(true);
    api.treemap(tmIndex, tmPeriod)
      .then((r) => { if (alive) setTmData(r); })
      .catch(() => {})
      .finally(() => { if (alive) setTmLoading(false); });
    return () => { alive = false; };
  }, [tab, tmIndex, tmPeriod]);

  const tickersKey = tickers.join(",");

  // Redirect old deprecated tabs
  useEffect(() => {
    const oldTab = searchParams.get("tab");
    const redirectMap: Record<string, string> = {
      Risk: `/risk${tickers.length ? `?t=${tickersKey}` : ""}`,
      Portfolio: `/portfolio${tickers.length ? `?t=${tickersKey}` : ""}`,
      Rankings: "/screener",
      Screener: "/screener",
      FX: "/macro?tab=FX",
    };
    if (oldTab && redirectMap[oldTab]) {
      router.replace(redirectMap[oldTab]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep URL in sync with current state so it can be bookmarked / shared
  useEffect(() => {
    const params = new URLSearchParams();
    if (tickers.length) params.set("t", tickers.join(","));
    params.set("p", period);
    params.set("tab", tab);
    if (benchmark) params.set("b", benchmark);
    router.replace(`/markets?${params.toString()}`, { scroll: false });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickersKey, period, tab, benchmark]);

  const { data: prices, isLoading: pricesLoading } = useQuery({
    queryKey: ["market-prices", tickersKey, period, benchmark ?? ""],
    queryFn: () => api.prices(tickersKey, period, benchmark || undefined),
    staleTime: 5 * 60 * 1000,
    enabled: tickers.length > 0,
  });

  const { data: risk, isLoading: riskLoading } = useQuery({
    queryKey: ["market-risk", tickersKey, period, benchmark ?? ""],
    queryFn: () => api.risk(tickersKey, period, 0.04, benchmark || undefined),
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

  function addTicker(sym: string) {
    setTickers((prev) => (prev.includes(sym) ? prev : [...prev, sym]));
  }
  function removeTicker(sym: string) {
    setTickers((prev) => prev.filter((t) => t !== sym));
  }

  function handleSnowflakeClick(t: string) {
    if (t === "Valuation" || t === "Ratios" || t === "Sectors") {
      setTab(t as Tab);
    } else {
      const redirects: Record<string, string> = {
        Portfolio: `/portfolio?t=${tickersKey}`,
        Screener: "/screener",
        FX: "/macro?tab=FX",
      };
      const dest = redirects[t];
      if (dest) router.push(dest);
    }
  }

  return (
    <div className="space-y-6">
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
            {tab === "Overview" && (
              <label className="flex items-center gap-1.5 text-xs text-text-muted">
                <span>Benchmark</span>
                <select
                  value={benchmark}
                  onChange={(e) => setBenchmark(e.target.value)}
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
                  onClick={() => setPeriod(p)}
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
            <div className="grid grid-cols-3 gap-4">
              <Card className="p-4">
                <div className="text-xs text-text-secondary">VaR 95%</div>
                <div className="text-xl font-bold mt-1">
                  {risk.metrics?.[0]?.var95 != null ? `${(risk.metrics[0].var95 * 100).toFixed(1)}%` : "—"}
                </div>
              </Card>
              <Card className="p-4">
                <div className="text-xs text-text-secondary">Sharpe Ratio</div>
                <div className="text-xl font-bold mt-1">
                  {risk.metrics?.[0]?.sharpe != null ? risk.metrics[0].sharpe.toFixed(2) : "—"}
                </div>
              </Card>
              <Card className="p-4">
                <div className="text-xs text-text-secondary">Beta</div>
                <div className="text-xl font-bold mt-1">
                  {risk.metrics?.[0]?.beta != null ? risk.metrics[0].beta.toFixed(2) : "—"}
                </div>
              </Card>
            </div>
          )}
          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Normalised Price (base 100)</h2>
            {pricesLoading ? <Skeleton className="h-96" /> : prices && <PriceChart data={prices} events={events} />}
          </Card>
          <SnowflakeChart ticker={tickers[0]} onAxisClick={handleSnowflakeClick} />
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
          <Card>
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
          <Card>
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
          <Card>
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
          <Card className="p-4">
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
