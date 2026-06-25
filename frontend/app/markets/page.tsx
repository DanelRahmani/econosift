"use client";

import { useState, useEffect, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { EventsResponse } from "@/lib/types";
import { SearchBar } from "@/components/SearchBar";
import { Card, Skeleton } from "@/components/ui";
import { PriceChart } from "@/components/markets/PriceChart";
import { QuoteCards } from "@/components/markets/QuoteCards";
import { RiskMetricsTable } from "@/components/markets/RiskMetricsTable";
import { CorrelationMatrix } from "@/components/markets/CorrelationMatrix";
import { ValuationTab } from "@/components/markets/ValuationTab";
import { RatiosTab } from "@/components/markets/RatiosTab";
import { PortfolioTab } from "@/components/markets/PortfolioTab";
import { RankingsTab } from "@/components/markets/RankingsTab";
import { SectorHeatmap } from "@/components/markets/SectorHeatmap";
import { ScreenerTab } from "@/components/markets/ScreenerTab";
import { FxRatesPanel } from "@/components/markets/FxRatesPanel";
import { NewsFeed } from "@/components/markets/NewsFeed";
import { Watchlist } from "@/components/Watchlist";
import { SnowflakeChart } from "@/components/markets/SnowflakeChart";
import { TechnicalsTab } from "@/components/markets/TechnicalsTab";

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"];
const BENCHMARKS = [
  { value: "", label: "Auto" },
  { value: "^GSPC", label: "S&P 500" },
  { value: "^NDX", label: "Nasdaq 100" },
  { value: "^DJI", label: "Dow Jones" },
  { value: "^RUT", label: "Russell 2000" },
];
const TABS = ["Overview", "Risk", "Technicals", "Valuation", "Ratios", "Portfolio", "Rankings", "Sectors", "Screener", "FX"] as const;
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

  const tickersKey = tickers.join(",");

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
      </div>

      {showWatchlist && (
        <Watchlist onSelect={addTicker} />
      )}

      <div className="flex flex-wrap items-center justify-between gap-4" data-hide-print>
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === t ? "bg-accent text-white" : "text-text-secondary hover:bg-surface-alt"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        {(tab === "Overview" || tab === "Risk" || tab === "Portfolio") && (
          <div className="flex items-center gap-3">
            {(tab === "Overview" || tab === "Risk") && (
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

      {!tickers.length && tab !== "Sectors" && tab !== "Screener" && tab !== "FX" && tab !== "Technicals" && (
        <Card><div className="text-text-muted">Search and add a ticker to begin.</div></Card>
      )}

      {tab === "Overview" && tickers.length > 0 && (
        <div className="space-y-6">
          <QuoteCards tickers={tickers} />
          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Normalised Price (base 100)</h2>
            {pricesLoading
              ? <Skeleton className="h-96" />
              : prices && <PriceChart data={prices} events={events} />}
          </Card>
          <SnowflakeChart
            ticker={tickers[0]}
            onAxisClick={(t) => setTab(t as Tab)}
          />
          <NewsFeed tickers={tickers} />
        </div>
      )}

      {tab === "Risk" && tickers.length > 0 && (
        <div className="space-y-6">
          <div className="flex justify-end" data-hide-print>
            <button
              onClick={() => {
                document.body.classList.add("print-mode");
                window.print();
                document.body.classList.remove("print-mode");
              }}
              className="px-3 py-1 rounded-md text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
            >
              Export PDF
            </button>
          </div>
          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Risk Metrics</h2>
            {riskLoading ? <Skeleton className="h-40" /> : risk && <RiskMetricsTable metrics={risk.metrics} />}
          </Card>
          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Return Correlation</h2>
            {risk && <CorrelationMatrix metrics={risk.metrics} />}
          </Card>
        </div>
      )}

      {tab === "Technicals" && tickers.length > 0 && (
        <TechnicalsTab ticker={tickers[0]} />
      )}

      {!tickers.length && tab === "Technicals" && (
        <Card><div className="text-text-muted">Search and add a ticker to begin.</div></Card>
      )}

      {tab === "Valuation" && tickers.length > 0 && (
        <ValuationTab tickers={tickers} period={period} onNavigateTab={(t) => setTab(t as Tab)} />
      )}

      {tab === "Ratios" && tickers.length > 0 && (
        <RatiosTab tickers={tickers} />
      )}

      {tab === "Portfolio" && (
        <PortfolioTab tickers={tickers} period={period} />
      )}

      {tab === "Rankings" && (
        <RankingsTab tickers={tickers} />
      )}

      {tab === "Sectors" && (
        <SectorHeatmap />
      )}

      {tab === "Screener" && (
        <ScreenerTab />
      )}

      {tab === "FX" && (
        <FxRatesPanel />
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
