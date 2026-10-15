"use client";

import { useEffect, useState, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiQuery } from "@/lib/queries";
import { PageSkeleton, TabButton } from "@/components/ui";
import { useUrlState } from "@/lib/useUrlState";
import type { Holding, CorrelationData, RiskContribData } from "@/lib/types";
// RiskContribData is RiskContribItem[] (flat list), CorrelationData has matrix as number[][]

import { PortfolioInput } from "@/components/portfolio/PortfolioInput";
import { PortfolioKPIs } from "@/components/portfolio/PortfolioKPIs";
import { PerformanceChart } from "@/components/portfolio/PerformanceChart";
import { DrawdownChart } from "@/components/portfolio/DrawdownChart";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { WalkthroughBanner } from "@/components/WalkthroughBanner";
import { PORTFOLIO_TABS } from "@/lib/pageTabs";
import { useKeyboardShortcuts, tabKeys, tabStepKeys, periodKeys } from "@/lib/useKeyboardShortcuts";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import dynamic from "next/dynamic";

// Tabs load on first open, so the page ships only the tab it shows (Phase 69).
const CorrelationHeatmap = dynamic(() => import("@/components/portfolio/CorrelationHeatmap").then((m) => ({ default: m.CorrelationHeatmap })));
const RiskContribution = dynamic(() => import("@/components/portfolio/RiskContribution").then((m) => ({ default: m.RiskContribution })));
const RollingMetrics = dynamic(() => import("@/components/portfolio/RollingMetrics").then((m) => ({ default: m.RollingMetrics })));
const CAPMAttribution = dynamic(() => import("@/components/portfolio/CAPMAttribution").then((m) => ({ default: m.CAPMAttribution })));
const KellyTable = dynamic(() => import("@/components/portfolio/KellyTable").then((m) => ({ default: m.KellyTable })));
const FFAttribution = dynamic(() => import("@/components/portfolio/FFAttribution").then((m) => ({ default: m.FFAttribution })));
const EfficientFrontier = dynamic(() => import("@/components/portfolio/EfficientFrontier").then((m) => ({ default: m.EfficientFrontier })));
const MonteCarlo = dynamic(() => import("@/components/portfolio/MonteCarlo").then((m) => ({ default: m.MonteCarlo })));
const BlackLitterman = dynamic(() => import("@/components/portfolio/BlackLitterman").then((m) => ({ default: m.BlackLitterman })));
const StressTesting = dynamic(() => import("@/components/portfolio/StressTesting").then((m) => ({ default: m.StressTesting })));
const ScenarioTab = dynamic(() => import("@/components/portfolio/ScenarioTab").then((m) => ({ default: m.ScenarioTab })));
const TransactionLog = dynamic(() => import("@/components/portfolio/TransactionLog").then((m) => ({ default: m.TransactionLog })));

const LS_KEY = "econosift_portfolio";
const LEGACY_LS_KEY = "axiom_portfolio";

const DEFAULT_HOLDINGS: Holding[] = [
  { ticker: "AAPL", weight: 40 },
  { ticker: "MSFT", weight: 30 },
  { ticker: "GOOGL", weight: 20 },
  { ticker: "BRK-B", weight: 10 },
];

const PERIODS = ["1y", "2y", "3y"] as const;
type Period = (typeof PERIODS)[number];

const TABS = PORTFOLIO_TABS;
type Tab = (typeof TABS)[number];

function loadFromStorage(): Holding[] {
  try {
    const raw = localStorage.getItem(LS_KEY) ?? localStorage.getItem(LEGACY_LS_KEY);
    if (!raw) return DEFAULT_HOLDINGS;
    const parsed = JSON.parse(raw) as Holding[];
    if (Array.isArray(parsed) && parsed.length > 0) {
      if (!localStorage.getItem(LS_KEY)) localStorage.setItem(LS_KEY, JSON.stringify(parsed));
      return parsed;
    }
  } catch {
    // ignore
  }
  return DEFAULT_HOLDINGS;
}

function saveToStorage(holdings: Holding[]) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(holdings));
  } catch {
    // ignore
  }
}

function PortfolioPageInner() {
  const [urlState, setUrlState] = useUrlState({ p: "3y", tab: "Overview" });

  const period = (PERIODS as readonly string[]).includes(urlState.p) ? (urlState.p as Period) : "3y";
  const tab = (TABS as readonly string[]).includes(urlState.tab) ? (urlState.tab as Tab) : "Overview";
  // P2-07: 1–9 pick a tab, ←/→ step the period.
  useKeyboardShortcuts({
    onTabSwitch: tabKeys(TABS, (t) => setUrlState({ tab: t })),
    ...tabStepKeys(TABS, (t) => t === tab, (t) => setUrlState({ tab: t })),
    ...periodKeys(PERIODS, period, (p) => setUrlState({ p })),
  });

  const [holdings, setHoldings] = useState<Holding[]>(DEFAULT_HOLDINGS);

  // The holdings + period the last analysis ran on: set from localStorage on mount and by
  // the Analyze button. Every tab's query keys off it, so a tab you return to is cached.
  const [analyzed, setAnalyzed] = useState<{ holdings: Holding[]; period: Period } | null>(null);
  const ready = !!analyzed && analyzed.holdings.length > 0;
  const aH = analyzed?.holdings ?? [];
  const aP = analyzed?.period ?? period;

  // Overview data
  const analyzeQ = useQuery({ ...apiQuery("portfolioAnalyze", aH, aP), enabled: !!analyzed });
  const analyzeData = analyzeQ.data ?? null;
  const analyzeLoading = analyzeQ.isFetching;
  const analyzeError = analyzeQ.isError ? "Failed to analyze portfolio. Check tickers and try again." : null;

  // Risk tab data, fetched when the tab is first shown
  const corrQ = useQuery({ ...apiQuery("portfolioCorrelation", aH, aP), enabled: ready && tab === "Risk" });
  const riskContribQ = useQuery({ ...apiQuery("portfolioRiskContribution", aH, aP), enabled: ready && tab === "Risk" });
  const corrData = corrQ.data ?? null;
  const corrLoading = corrQ.isLoading;
  const riskContribData = riskContribQ.data ?? null;
  const riskContribLoading = riskContribQ.isLoading;

  // Attribution tab data
  const capmQ = useQuery({ ...apiQuery("portfolioCAPM", aH, aP), enabled: ready && tab === "Attribution" });
  const capmData = capmQ.data ?? null;
  const capmLoading = capmQ.isLoading;

  // Load from localStorage on mount and analyze it
  useEffect(() => {
    const stored = loadFromStorage();
    setHoldings(stored);
    setAnalyzed({ holdings: stored, period });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleAnalyze() {
    saveToStorage(holdings);
    const same = analyzed && analyzed.period === period && JSON.stringify(analyzed.holdings) === JSON.stringify(holdings);
    if (same) void analyzeQ.refetch();
    else setAnalyzed({ holdings, period });
  }

  const validHoldings = holdings.filter((h) => h.ticker.trim() !== "" && h.weight > 0);

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <WalkthroughBanner pageKey="portfolio" />
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Portfolio Analytics</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Build, analyze, and optimize your custom portfolio
          </p>
        </div>
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

      {/* Portfolio Input */}
      <PortfolioInput
        holdings={holdings}
        onChange={setHoldings}
        onAnalyze={handleAnalyze}
        loading={analyzeLoading}
      />

      {/* Error */}
      {analyzeError && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-sm text-red-500">
          {analyzeError}
        </div>
      )}

      {/* KPI Strip */}
      <PortfolioKPIs data={analyzeData} loading={analyzeLoading} />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border overflow-x-auto pb-0.5 sticky top-14 z-20 bg-background/95 backdrop-blur">
        {TABS.map((t) => (
          <TabButton key={t} active={tab === t} onClick={() => setUrlState({ tab: t })}>
            {t}
          </TabButton>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px] space-y-4">
        <ErrorBoundary key={tab}>
        {/* ── Overview ── */}
        {tab === "Overview" && (
          <>
            {analyzeLoading && <PageSkeleton text="Loading portfolio data…" />}
            {!analyzeLoading && analyzeData && (
              <>
                <PerformanceChart data={analyzeData} />
                <DrawdownChart data={analyzeData} />
                <HoldingsTable data={analyzeData} />
              </>
            )}
            {!analyzeLoading && !analyzeData && !analyzeError && (
              <div className="flex items-center justify-center h-64 text-text-muted text-sm">
                Click &quot;Analyze Portfolio&quot; to get started.
              </div>
            )}
          </>
        )}

        {/* ── Risk ── */}
        {tab === "Risk" && (
          <>
            <CorrelationHeatmap data={corrData} loading={corrLoading} />
            <RiskContribution data={riskContribData} loading={riskContribLoading} />
            <RollingMetrics holdings={validHoldings} period={period} />
          </>
        )}

        {/* ── Attribution ── */}
        {tab === "Attribution" && (
          <>
            <CAPMAttribution data={capmData} loading={capmLoading} />
            <KellyTable holdings={validHoldings} period={period} />
            <FFAttribution holdings={validHoldings} period={period} />
          </>
        )}

        {/* ── Optimize ── */}
        {tab === "Optimize" && (
          <>
            <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-500 font-medium">
              Compute-intensive calculations — may take 15–60 seconds · Results are not cached
            </div>
            <EfficientFrontier holdings={validHoldings} period={period} />
            <MonteCarlo holdings={validHoldings} period={period} />
            <BlackLitterman holdings={validHoldings} period={period} />
            <StressTesting holdings={validHoldings} period={period} />
          </>
        )}

        {/* ── Scenario ── */}
        {tab === "Scenario" && (
          <ScenarioTab holdings={validHoldings} />
        )}

        {/* ── Transactions ── */}
        {tab === "Transactions" && (
          <TransactionLog />
        )}
        </ErrorBoundary>
      </div>
    </main>
  );
}

export default function PortfolioPage() {
  return (
    <Suspense fallback={<PageSkeleton text="Loading portfolio…" />}>
      <PortfolioPageInner />
    </Suspense>
  );
}
