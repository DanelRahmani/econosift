"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { Skeleton } from "@/components/ui";
import { SearchBar } from "@/components/SearchBar";
import { RiskKPIRow } from "@/components/risk/RiskKPIRow";
import { RollingMetricsChart } from "@/components/risk/RollingMetricsChart";
import { ExtendedRiskTable } from "@/components/risk/ExtendedRiskTable";
import { CorrelationHeatmap } from "@/components/risk/CorrelationHeatmap";
import { OnDemandRisk } from "@/components/risk/OnDemandRisk";
import { MonteCarloPanel } from "@/components/risk/MonteCarloPanel";
import { StressTestPanel } from "@/components/risk/StressTestPanel";
import type {
  RiskMetric,
  ExtendedRiskTicker,
  RollingTickerMetrics,
  CorrelationResponse,
  RollingMetricsResponse,
  ExtendedRiskResponse,
} from "@/lib/types";

const PERIODS = ["1y", "2y", "3y"] as const;
type Period = (typeof PERIODS)[number];

const TABS = ["Rolling Metrics", "Extended", "Correlation", "On-Demand", "Stress & Monte Carlo"] as const;
type Tab = (typeof TABS)[number];

const WINDOWS = [20, 60, 120, 252] as const;
type Window = (typeof WINDOWS)[number];

function RiskPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { theme } = useTheme();

  const [tickersStr, setTickersStr] = useState<string>(searchParams.get("t") ?? "AAPL");
  const [period, setPeriod] = useState<Period>((searchParams.get("p") as Period) ?? "3y");
  const [window, setWindow] = useState<Window>(252);
  const [tab, setTab] = useState<Tab>("Rolling Metrics");

  // Data state
  const [baseMetrics, setBaseMetrics] = useState<RiskMetric[]>([]);
  const [extendedData, setExtendedData] = useState<ExtendedRiskTicker[]>([]);
  const [rollingData, setRollingData] = useState<RollingTickerMetrics[]>([]);
  const [corrData, setCorrData] = useState<CorrelationResponse | null>(null);

  const [baseLoading, setBaseLoading] = useState(false);
  const [rollingLoading, setRollingLoading] = useState(false);
  const [extendedLoading, setExtendedLoading] = useState(false);
  const [corrLoading, setCorrLoading] = useState(false);

  // URL sync
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("t", tickersStr);
    params.set("p", period);
    router.replace(`/risk?${params.toString()}`, { scroll: false });
  }, [tickersStr, period, router]);

  // Fetch base risk (for KPI row)
  const fetchBase = useCallback(async () => {
    if (!tickersStr.trim()) return;
    setBaseLoading(true);
    try {
      const res = await api.risk(tickersStr, "1y", 0.04);
      setBaseMetrics(res.metrics);
    } catch {
      setBaseMetrics([]);
    } finally {
      setBaseLoading(false);
    }
  }, [tickersStr]);

  // Fetch rolling
  const fetchRolling = useCallback(async () => {
    if (!tickersStr.trim()) return;
    setRollingLoading(true);
    try {
      const res: RollingMetricsResponse = await api.riskRolling(tickersStr, period, window);
      setRollingData(res.tickers ?? []);
    } catch {
      setRollingData([]);
    } finally {
      setRollingLoading(false);
    }
  }, [tickersStr, period, window]);

  // Fetch extended
  const fetchExtended = useCallback(async () => {
    if (!tickersStr.trim()) return;
    setExtendedLoading(true);
    try {
      const res: ExtendedRiskResponse = await api.riskExtended(tickersStr, period);
      setExtendedData(res.tickers ?? []);
    } catch {
      setExtendedData([]);
    } finally {
      setExtendedLoading(false);
    }
  }, [tickersStr, period]);

  // Fetch correlation
  const fetchCorr = useCallback(async () => {
    const tickers = tickersStr.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickers.length < 2) {
      setCorrData(null);
      return;
    }
    setCorrLoading(true);
    try {
      const res = await api.riskCorrelation(tickersStr, period, window);
      setCorrData(res);
    } catch {
      setCorrData(null);
    } finally {
      setCorrLoading(false);
    }
  }, [tickersStr, period, window]);

  useEffect(() => {
    fetchBase();
    fetchRolling();
    fetchExtended();
    fetchCorr();
  }, [fetchBase, fetchRolling, fetchExtended, fetchCorr]);

  const primaryTicker = tickersStr.split(",")[0].trim().toUpperCase() || "AAPL";
  const firstBase = baseMetrics[0] ?? null;
  const firstExtended = extendedData[0] ?? null;

  function handleSearch(sym: string) {
    const existing = tickersStr.split(",").map((t) => t.trim()).filter(Boolean);
    if (!existing.includes(sym.toUpperCase())) {
      setTickersStr([...existing, sym.toUpperCase()].join(","));
    } else {
      setTickersStr(sym.toUpperCase());
    }
  }

  function removeTicker(sym: string) {
    const remaining = tickersStr
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t && t !== sym);
    setTickersStr(remaining.join(",") || "AAPL");
  }

  const tickerList = tickersStr.split(",").map((t) => t.trim()).filter(Boolean);

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Risk & Rolling Metrics</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Rolling risk analytics, extended ratios, and compute-gated tail risk models
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Period */}
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  period === p
                    ? "bg-accent text-white"
                    : "bg-surface-alt text-text-secondary hover:text-text-primary"
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Ticker input */}
      <div className="space-y-2">
        <SearchBar onAdd={handleSearch} />
        {tickerList.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tickerList.map((t) => (
              <div
                key={t}
                className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-surface-alt border border-border text-xs font-mono"
              >
                <span>{t}</span>
                <button
                  onClick={() => removeTicker(t)}
                  className="text-text-muted hover:text-danger transition-colors leading-none"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* KPI Row */}
      {baseLoading ? (
        <Skeleton className="h-28 w-full rounded-xl" />
      ) : (
        <RiskKPIRow base={firstBase} extended={firstExtended} ticker={primaryTicker} />
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border overflow-x-auto pb-0.5">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
              tab === t
                ? "border-b-2 border-accent text-accent"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {tab === "Rolling Metrics" && (
          <div className="space-y-4">
            <div className="flex gap-2 items-center">
              <span className="text-xs text-text-muted">Rolling window:</span>
              {WINDOWS.map((w) => (
                <button
                  key={w}
                  onClick={() => setWindow(w)}
                  className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                    window === w
                      ? "bg-accent text-white"
                      : "bg-surface-alt text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {w}D
                </button>
              ))}
            </div>
            <RollingMetricsChart data={rollingData} theme={theme} loading={rollingLoading} />
          </div>
        )}

        {tab === "Extended" && (
          extendedLoading ? (
            <Skeleton className="h-64 w-full rounded-xl" />
          ) : (
            <ExtendedRiskTable tickers={extendedData} />
          )
        )}

        {tab === "Correlation" && (
          <CorrelationHeatmap data={corrData} loading={corrLoading} />
        )}

        {tab === "On-Demand" && (
          <div className="space-y-2">
            <div className="p-3 rounded-md bg-warning/10 border border-warning/30 text-xs text-warning">
              On-demand calculations · Click "Calculate" to run each model individually (~2–3s per model)
            </div>
            <OnDemandRisk ticker={primaryTicker} tickers={tickersStr} theme={theme} />
          </div>
        )}

        {tab === "Stress & Monte Carlo" && (
          <div className="space-y-4">
            <div className="p-3 rounded-md bg-danger/10 border border-danger/30 text-xs text-danger font-medium">
              Compute-intensive calculations — may take 15–60 seconds · Results are not cached
            </div>
            <MonteCarloPanel ticker={primaryTicker} theme={theme} />
            <StressTestPanel ticker={primaryTicker} theme={theme} />
          </div>
        )}
      </div>
    </main>
  );
}

export default function RiskPage() {
  return (
    <Suspense fallback={<div className="p-8 text-text-muted">Loading…</div>}>
      <RiskPageInner />
    </Suspense>
  );
}
