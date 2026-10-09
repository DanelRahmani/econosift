"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { Skeleton, TabButton } from "@/components/ui";
import { SearchBar } from "@/components/SearchBar";
import { useUrlState } from "@/lib/useUrlState";
import { SourceScope } from "@/components/provenance/SourceScope";
import { provOf, type Provenance } from "@/lib/provenance";
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
import { useRefreshNonce } from "@/lib/refresh";
import { useKeyboardShortcuts, tabKeys, tabStepKeys, periodKeys } from "@/lib/useKeyboardShortcuts";

const PERIODS = ["1y", "2y", "3y"] as const;
type Period = (typeof PERIODS)[number];

const TABS = ["Rolling Metrics", "Extended", "Correlation", "On-Demand", "Stress & Monte Carlo"] as const;
type Tab = (typeof TABS)[number];

const WINDOWS = [20, 60, 120, 252] as const;
type Window = (typeof WINDOWS)[number];

const BENCHMARKS = [
  { value: "", label: "Auto" },
  { value: "^GSPC", label: "S&P 500" },
  { value: "^NDX", label: "Nasdaq 100" },
  { value: "^DJI", label: "Dow Jones" },
  { value: "^RUT", label: "Russell 2000" },
];

function RiskPageInner() {
  const { theme } = useTheme();

  const [urlState, setUrlState] = useUrlState({
    t: "AAPL",
    p: "3y",
    tab: "Rolling Metrics",
    w: "252",
    b: "",
  });

  const tickersStr = urlState.t;
  const period = (PERIODS as readonly string[]).includes(urlState.p) ? (urlState.p as Period) : "3y";
  const tab = (TABS as readonly string[]).includes(urlState.tab) ? (urlState.tab as Tab) : "Rolling Metrics";
  const window = (WINDOWS as readonly number[]).includes(Number(urlState.w)) ? (Number(urlState.w) as Window) : 252;
  const benchmark = urlState.b;
  // P2-07: 1–9 pick a tab, ←/→ step the period.
  useKeyboardShortcuts({
    onTabSwitch: tabKeys(TABS, (t) => setUrlState({ tab: t })),
    ...tabStepKeys(TABS, (t) => t === tab, (t) => setUrlState({ tab: t })),
    ...periodKeys(PERIODS, period, (p) => setUrlState({ p })),
  });

  // Data state
  const [baseMetrics, setBaseMetrics] = useState<RiskMetric[]>([]);
  const [extendedData, setExtendedData] = useState<ExtendedRiskTicker[]>([]);
  const [rollingData, setRollingData] = useState<RollingTickerMetrics[]>([]);
  const [corrData, setCorrData] = useState<CorrelationResponse | null>(null);
  // `provenance` maps of the responses whose arrays are unwrapped into the state above
  const [baseProv, setBaseProv] = useState<Provenance | undefined>();
  const [rollingProv, setRollingProv] = useState<Provenance | undefined>();
  const [extendedProv, setExtendedProv] = useState<Provenance | undefined>();

  const [baseLoading, setBaseLoading] = useState(false);
  const [rollingLoading, setRollingLoading] = useState(false);
  const [extendedLoading, setExtendedLoading] = useState(false);
  const [corrLoading, setCorrLoading] = useState(false);

  // Fetch base risk (for KPI row)
  const fetchBase = useCallback(async (signal: AbortSignal) => {
    if (!tickersStr.trim()) return;
    setBaseLoading(true);
    try {
      const res = await api.risk(tickersStr, "1y", 0.04, benchmark || undefined, signal);
      setBaseMetrics(res.metrics);
      setBaseProv(provOf(res));
    } catch {
      if (signal.aborted) return;
      setBaseMetrics([]);
      setBaseProv(undefined);
    } finally {
      if (!signal.aborted) setBaseLoading(false);
    }
  }, [tickersStr, benchmark]);

  // Fetch rolling
  const fetchRolling = useCallback(async (signal: AbortSignal) => {
    if (!tickersStr.trim()) return;
    setRollingLoading(true);
    try {
      const res: RollingMetricsResponse = await api.riskRolling(tickersStr, period, window, benchmark || undefined, signal);
      setRollingData(res.tickers ?? []);
      setRollingProv(provOf(res));
    } catch {
      if (signal.aborted) return;
      setRollingData([]);
      setRollingProv(undefined);
    } finally {
      if (!signal.aborted) setRollingLoading(false);
    }
  }, [tickersStr, period, window, benchmark]);

  // Fetch extended
  const fetchExtended = useCallback(async (signal: AbortSignal) => {
    if (!tickersStr.trim()) return;
    setExtendedLoading(true);
    try {
      const res: ExtendedRiskResponse = await api.riskExtended(tickersStr, period, benchmark || undefined, signal);
      setExtendedData(res.tickers ?? []);
      setExtendedProv(provOf(res));
    } catch {
      if (signal.aborted) return;
      setExtendedData([]);
      setExtendedProv(undefined);
    } finally {
      if (!signal.aborted) setExtendedLoading(false);
    }
  }, [tickersStr, period, benchmark]);

  // Fetch correlation
  const fetchCorr = useCallback(async (signal: AbortSignal) => {
    const tickers = tickersStr.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickers.length < 2) {
      setCorrData(null);
      return;
    }
    setCorrLoading(true);
    try {
      const res = await api.riskCorrelation(tickersStr, period, window, signal);
      setCorrData(res);
    } catch {
      if (signal.aborted) return;
      setCorrData(null);
    } finally {
      if (!signal.aborted) setCorrLoading(false);
    }
  }, [tickersStr, period, window]);

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    // Cancel the requests a new period/ticker/window supersedes: left running on a slow backend they
    // hold the browser's 6 connections to this origin and the next ?p= navigation never starts.
    const ctrl = new AbortController();
    fetchBase(ctrl.signal);
    fetchRolling(ctrl.signal);
    fetchExtended(ctrl.signal);
    fetchCorr(ctrl.signal);
    return () => ctrl.abort();
  }, [fetchBase, fetchRolling, fetchExtended, fetchCorr, refreshNonce]);

  const primaryTicker = tickersStr.split(",")[0].trim().toUpperCase() || "AAPL";
  const firstBase = baseMetrics[0] ?? null;
  const firstExtended = extendedData[0] ?? null;

  function handleSearch(sym: string) {
    const existing = tickerList;
    if (!existing.includes(sym.toUpperCase())) {
      setUrlState({ t: [...existing, sym.toUpperCase()].join(",") });
    } else {
      setUrlState({ t: sym.toUpperCase() });
    }
  }

  function removeTicker(sym: string) {
    const remaining = tickerList.filter((t) => t !== sym);
    setUrlState({ t: remaining.join(",") || "AAPL" });
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
          {/* Benchmark */}
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
          {/* Period */}
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setUrlState({ p })}
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
        <RiskKPIRow
          base={firstBase}
          extended={firstExtended}
          ticker={primaryTicker}
          period={period}
          baseProv={baseProv}
          extendedProv={extendedProv}
        />
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border overflow-x-auto pb-0.5 sticky top-14 z-20 bg-background/95 backdrop-blur">
        {TABS.map((t) => (
          <TabButton key={t} active={tab === t} onClick={() => setUrlState({ tab: t })}>
            {t}
          </TabButton>
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
                  onClick={() => setUrlState({ w: String(w) })}
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
            <SourceScope prov={rollingProv}>
              <RollingMetricsChart data={rollingData} theme={theme} loading={rollingLoading} />
            </SourceScope>
          </div>
        )}

        {tab === "Extended" && (
          extendedLoading ? (
            <Skeleton className="h-64 w-full rounded-xl" />
          ) : (
            <SourceScope prov={extendedProv}>
              <ExtendedRiskTable tickers={extendedData} />
            </SourceScope>
          )
        )}

        {tab === "Correlation" && (
          <CorrelationHeatmap data={corrData} loading={corrLoading} />
        )}

        {tab === "On-Demand" && (
          <div className="space-y-2">
            <div className="p-3 rounded-md bg-warning/10 border border-warning/30 text-xs text-warning">
              On-demand calculations · Click &quot;Calculate&quot; to run each model individually (~2–3s per model)
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
