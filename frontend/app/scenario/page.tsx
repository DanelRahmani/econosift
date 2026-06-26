"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Holding } from "@/lib/types";
import { PortfolioInput } from "@/components/portfolio/PortfolioInput";

const DEFAULT_HOLDINGS: Holding[] = [
  { ticker: "AAPL", weight: 40 },
  { ticker: "MSFT", weight: 30 },
  { ticker: "GOOGL", weight: 20 },
  { ticker: "BRK-B", weight: 10 },
];

export default function ScenarioPage() {
  const [holdings, setHoldings] = useState<Holding[]>(DEFAULT_HOLDINGS);
  const [activeTab, setActiveTab] = useState<"Historical" | "Custom">("Historical");
  
  // Historical
  const [histEpisodes, setHistEpisodes] = useState<any[]>([]);
  const [stressResults, setStressResults] = useState<any>(null);
  const [loadingStress, setLoadingStress] = useState(false);

  // Custom
  const [shocks, setShocks] = useState({ equities: -10, rates: 50, credit: 100 });
  const [customResult, setCustomResult] = useState<any>(null);
  const [loadingCustom, setLoadingCustom] = useState(false);

  useEffect(() => {
    api.scenarioHistorical().then(setHistEpisodes).catch(console.error);
  }, []);

  const runHistorical = async () => {
    setLoadingStress(true);
    try {
      const res = await api.scenarioStress(holdings);
      setStressResults(res.episodes || []);
    } catch (e) {
      console.error(e);
    }
    setLoadingStress(false);
  };

  const runCustom = async () => {
    setLoadingCustom(true);
    try {
      const res = await api.scenarioCustom(holdings, shocks);
      setCustomResult(res);
    } catch (e) {
      console.error(e);
    }
    setLoadingCustom(false);
  };

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Scenario Lab</h1>
        <p className="text-sm text-text-muted mt-0.5">
          Stress test portfolios against historical episodes and custom macro shocks
        </p>
      </div>

      <PortfolioInput
        holdings={holdings}
        onChange={setHoldings}
        onAnalyze={() => {}}
        loading={false}
      />

      <div className="flex gap-2 border-b border-border">
        {["Historical", "Custom"].map(t => (
          <button
            key={t}
            onClick={() => setActiveTab(t as any)}
            className={`px-4 py-2 text-sm font-medium ${activeTab === t ? "border-b-2 border-accent text-accent" : "text-text-secondary"}`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="min-h-[400px]">
        {activeTab === "Historical" && (
          <div className="space-y-4">
            <button
              onClick={runHistorical}
              disabled={loadingStress}
              className="px-4 py-2 bg-accent text-white rounded text-sm disabled:opacity-50"
            >
              {loadingStress ? "Running..." : "Run Historical Stress Test"}
            </button>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {stressResults ? stressResults.map((r: any, i: number) => (
                <div key={i} className="p-4 bg-surface rounded-lg border border-border">
                  <h3 className="font-semibold">{r.label || r.scenario}</h3>
                  <div className="text-sm text-text-secondary mt-1">
                    Return: {r.totalReturn !== null ? (r.totalReturn * 100).toFixed(2) + "%" : "N/A"} <br/>
                    Max Drawdown: {r.maxDrawdown !== null ? (r.maxDrawdown * 100).toFixed(2) + "%" : "N/A"}
                  </div>
                </div>
              )) : (
                <div className="col-span-2 text-sm text-text-muted">
                  Click run to see historical stress test results. Available episodes: {histEpisodes.map(e => e.label).join(", ")}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "Custom" && (
          <div className="space-y-4">
            <div className="flex gap-4">
              <label className="flex flex-col text-sm">
                Equities (% Shock)
                <input type="number" value={shocks.equities} onChange={e => setShocks({...shocks, equities: parseFloat(e.target.value)})} className="border p-1 rounded bg-surface" />
              </label>
              <label className="flex flex-col text-sm">
                Rates (bps Shock)
                <input type="number" value={shocks.rates} onChange={e => setShocks({...shocks, rates: parseFloat(e.target.value)})} className="border p-1 rounded bg-surface" />
              </label>
              <label className="flex flex-col text-sm">
                Credit (bps Shock)
                <input type="number" value={shocks.credit} onChange={e => setShocks({...shocks, credit: parseFloat(e.target.value)})} className="border p-1 rounded bg-surface" />
              </label>
            </div>
            <button
              onClick={runCustom}
              disabled={loadingCustom}
              className="px-4 py-2 bg-accent text-white rounded text-sm disabled:opacity-50"
            >
              {loadingCustom ? "Running..." : "Simulate Custom Shock"}
            </button>

            {customResult && (
              <div className="p-4 bg-surface rounded-lg border border-border">
                <h3 className="font-semibold">Estimated Impact: {(customResult.totalImpactPct * 100).toFixed(2)}%</h3>
                <ul className="mt-2 text-sm space-y-1">
                  {customResult.impacts.map((imp: any, i: number) => (
                    <li key={i}>{imp.factor} Impact: {(imp.impact * 100).toFixed(2)}% (Beta: {imp.beta?.toFixed(2)})</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
