"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { api } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { useUrlState } from "@/lib/useUrlState";
import type { Holding, PortfolioAnalysis, CorrelationData, RiskContribData, CAPMData } from "@/lib/types";
// RiskContribData is RiskContribItem[] (flat list), CorrelationData has matrix as number[][]

import { PortfolioInput } from "@/components/portfolio/PortfolioInput";
import { PortfolioKPIs } from "@/components/portfolio/PortfolioKPIs";
import { PerformanceChart } from "@/components/portfolio/PerformanceChart";
import { DrawdownChart } from "@/components/portfolio/DrawdownChart";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { CorrelationHeatmap } from "@/components/portfolio/CorrelationHeatmap";
import { RiskContribution } from "@/components/portfolio/RiskContribution";
import { RollingMetrics } from "@/components/portfolio/RollingMetrics";
import { CAPMAttribution } from "@/components/portfolio/CAPMAttribution";
import { KellyTable } from "@/components/portfolio/KellyTable";
import { FFAttribution } from "@/components/portfolio/FFAttribution";
import { EfficientFrontier } from "@/components/portfolio/EfficientFrontier";
import { MonteCarlo } from "@/components/portfolio/MonteCarlo";
import { BlackLitterman } from "@/components/portfolio/BlackLitterman";
import { StressTesting } from "@/components/portfolio/StressTesting";
import { ScenarioTab } from "@/components/portfolio/ScenarioTab";

const LS_KEY = "axiom_portfolio";

const DEFAULT_HOLDINGS: Holding[] = [
  { ticker: "AAPL", weight: 40 },
  { ticker: "MSFT", weight: 30 },
  { ticker: "GOOGL", weight: 20 },
  { ticker: "BRK-B", weight: 10 },
];

const PERIODS = ["1y", "2y", "3y"] as const;
type Period = (typeof PERIODS)[number];

const TABS = ["Overview", "Risk", "Attribution", "Optimize", "Scenario"] as const;
type Tab = (typeof TABS)[number];

function loadFromStorage(): Holding[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return DEFAULT_HOLDINGS;
    const parsed = JSON.parse(raw) as Holding[];
    if (Array.isArray(parsed) && parsed.length > 0) return parsed;
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

  const [holdings, setHoldings] = useState<Holding[]>(DEFAULT_HOLDINGS);

  // Overview data
  const [analyzeData, setAnalyzeData] = useState<PortfolioAnalysis | null>(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  // Risk tab data
  const [corrData, setCorrData] = useState<CorrelationData | null>(null);
  const [corrLoading, setCorrLoading] = useState(false);
  const [riskContribData, setRiskContribData] = useState<RiskContribData | null>(null);
  const [riskContribLoading, setRiskContribLoading] = useState(false);
  const [riskTabFetched, setRiskTabFetched] = useState(false);

  // Attribution tab data
  const [capmData, setCAPMData] = useState<CAPMData | null>(null);
  const [capmLoading, setCAPMLoading] = useState(false);
  const [attrTabFetched, setAttrTabFetched] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const stored = loadFromStorage();
    setHoldings(stored);
  }, []);

  const doAnalyze = useCallback(async (h: Holding[], p: Period) => {
    setAnalyzeLoading(true);
    setAnalyzeError(null);
    try {
      const d = await api.portfolioAnalyze(h, p);
      setAnalyzeData(d);
      // Reset tab-specific data when re-analyzing
      setCorrData(null);
      setRiskContribData(null);
      setCAPMData(null);
      setRiskTabFetched(false);
      setAttrTabFetched(false);
    } catch (e) {
      setAnalyzeError("Failed to analyze portfolio. Check tickers and try again.");
    } finally {
      setAnalyzeLoading(false);
    }
  }, []);

  // Auto-fetch on mount after loading from localStorage
  useEffect(() => {
    const stored = loadFromStorage();
    setHoldings(stored);
    doAnalyze(stored, period);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleAnalyze() {
    saveToStorage(holdings);
    doAnalyze(holdings, period);
  }

  // Fetch Risk tab data when tab becomes active
  useEffect(() => {
    if (tab !== "Risk" || riskTabFetched || holdings.length === 0) return;
    setRiskTabFetched(true);

    setCorrLoading(true);
    api.portfolioCorrelation(holdings, period)
      .then(setCorrData)
      .catch(() => setCorrData(null))
      .finally(() => setCorrLoading(false));

    setRiskContribLoading(true);
    api.portfolioRiskContribution(holdings, period)
      .then(setRiskContribData)
      .catch(() => setRiskContribData(null))
      .finally(() => setRiskContribLoading(false));
  }, [tab, riskTabFetched, holdings, period]);

  // Fetch Attribution tab data when tab becomes active
  useEffect(() => {
    if (tab !== "Attribution" || attrTabFetched || holdings.length === 0) return;
    setAttrTabFetched(true);

    setCAPMLoading(true);
    api.portfolioCAPM(holdings, period)
      .then(setCAPMData)
      .catch(() => setCAPMData(null))
      .finally(() => setCAPMLoading(false));
  }, [tab, attrTabFetched, holdings, period]);

  const validHoldings = holdings.filter((h) => h.ticker.trim() !== "" && h.weight > 0);

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
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
          <button
            key={t}
            onClick={() => setUrlState({ tab: t })}
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
      <div className="min-h-[400px] space-y-4">
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
                Click "Analyze Portfolio" to get started.
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
