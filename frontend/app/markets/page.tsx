"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { PricesResponse, RiskResponse } from "@/lib/types";
import { SearchBar } from "@/components/SearchBar";
import { Card, Skeleton } from "@/components/ui";
import { PriceChart } from "@/components/markets/PriceChart";
import { QuoteCards } from "@/components/markets/QuoteCards";
import { RiskMetricsTable } from "@/components/markets/RiskMetricsTable";
import { CorrelationMatrix } from "@/components/markets/CorrelationMatrix";
import { ValuationTab } from "@/components/markets/ValuationTab";
import { RatiosTab } from "@/components/markets/RatiosTab";
import { Watchlist } from "@/components/Watchlist";

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"];
const TABS = ["Overview", "Risk", "Valuation", "Ratios"] as const;
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

  const [prices, setPrices] = useState<PricesResponse | null>(null);
  const [risk, setRisk] = useState<RiskResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const tickersKey = tickers.join(",");

  // Keep URL in sync with current state so it can be bookmarked / shared
  useEffect(() => {
    const params = new URLSearchParams();
    if (tickers.length) params.set("t", tickers.join(","));
    params.set("p", period);
    params.set("tab", tab);
    router.replace(`/markets?${params.toString()}`, { scroll: false });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickersKey, period, tab]);

  useEffect(() => {
    if (!tickers.length) {
      setPrices(null);
      setRisk(null);
      return;
    }
    let active = true;
    setLoading(true);
    Promise.all([
      api.prices(tickersKey, period),
      api.risk(tickersKey, period, 0.04),
    ])
      .then(([p, r]) => {
        if (!active) return;
        setPrices(p);
        setRisk(r);
      })
      .catch(() => active && (setPrices(null), setRisk(null)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [tickersKey, period]);

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
        {(tab === "Overview" || tab === "Risk") && (
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
        )}
      </div>

      {!tickers.length && (
        <Card><div className="text-text-muted">Search and add a ticker to begin.</div></Card>
      )}

      {tab === "Overview" && tickers.length > 0 && (
        <div className="space-y-6">
          <QuoteCards tickers={tickers} />
          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Normalised Price (base 100)</h2>
            {loading && !prices ? <Skeleton className="h-96" /> : prices && <PriceChart data={prices} />}
          </Card>
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
            {loading && !risk ? <Skeleton className="h-40" /> : risk && <RiskMetricsTable metrics={risk.metrics} />}
          </Card>
          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Return Correlation</h2>
            {risk && <CorrelationMatrix metrics={risk.metrics} />}
          </Card>
        </div>
      )}

      {tab === "Valuation" && tickers.length > 0 && (
        <ValuationTab tickers={tickers} period={period} />
      )}

      {tab === "Ratios" && tickers.length > 0 && (
        <RatiosTab tickers={tickers} />
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
