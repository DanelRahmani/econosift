"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TabButton } from "@/components/ui";
import type { Holding } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  holdings: Holding[];
}

export function ScenarioTab({ holdings }: Props) {
  const [activeTab, setActiveTab] = useState<"Historical" | "Custom">("Historical");
  const [histEpisodes, setHistEpisodes] = useState<any[]>([]);
  const [stressResults, setStressResults] = useState<any>(null);
  const [stressData, setStressData] = useState<any>(null);
  const [loadingStress, setLoadingStress] = useState(false);
  const [shocks, setShocks] = useState({ equities: -10, rates: 50, credit: 100 });
  const [customResult, setCustomResult] = useState<any>(null);
  const [loadingCustom, setLoadingCustom] = useState(false);
  const stressScope = useSourceScope(provOf(stressData));
  const customScope = useSourceScope(provOf(customResult));

  useEffect(() => {
    api.scenarioHistorical().then(setHistEpisodes).catch(console.error);
  }, []);

  const runHistorical = async () => {
    setLoadingStress(true);
    try {
      const res = await api.scenarioStress(holdings);
      setStressData(res);
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
    <div className="space-y-6">
      <div className="flex gap-2 border-b border-border">
        {["Historical", "Custom"].map((t) => (
          <TabButton key={t} active={activeTab === t} onClick={() => setActiveTab(t as any)}>
            {t}
          </TabButton>
        ))}
      </div>

      {activeTab === "Historical" && (
        <div className="space-y-4">
          <button
            onClick={runHistorical}
            disabled={loadingStress}
            className="px-4 py-2 bg-accent text-white rounded text-sm disabled:opacity-50"
          >
            {loadingStress ? "Running..." : "🔴 Run Historical Stress Test"}
          </button>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" {...stressScope}>
            {stressResults ? (
              stressResults.map((r: any, i: number) => (
                <div key={i} data-prov={`episodes.${r.scenario}`} data-prov-ctx={r.label || r.scenario} className="p-4 bg-surface rounded-lg border border-border">
                  <h3 className="font-semibold">{r.label || r.scenario}</h3>
                  <div className="text-sm text-text-secondary mt-1">
                    Return: {r.totalReturn !== null ? (r.totalReturn * 100).toFixed(2) + "%" : "N/A"}
                    <br />
                    Max Drawdown: {r.maxDrawdown !== null ? (r.maxDrawdown * 100).toFixed(2) + "%" : "N/A"}
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-2 text-sm text-text-muted">
                Click run to see historical stress test results.
                Available episodes: {histEpisodes.map((e: any) => e.label).join(", ")}
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
              <input
                type="number"
                value={shocks.equities}
                onChange={(e) => setShocks({ ...shocks, equities: parseFloat(e.target.value) })}
                className="border p-1 rounded bg-surface mt-1"
              />
            </label>
            <label className="flex flex-col text-sm">
              Rates (bps Shock)
              <input
                type="number"
                value={shocks.rates}
                onChange={(e) => setShocks({ ...shocks, rates: parseFloat(e.target.value) })}
                className="border p-1 rounded bg-surface mt-1"
              />
            </label>
            <label className="flex flex-col text-sm">
              Credit (bps Shock)
              <input
                type="number"
                value={shocks.credit}
                onChange={(e) => setShocks({ ...shocks, credit: parseFloat(e.target.value) })}
                className="border p-1 rounded bg-surface mt-1"
              />
            </label>
          </div>
          <button
            onClick={runCustom}
            disabled={loadingCustom}
            className="px-4 py-2 bg-accent text-white rounded text-sm disabled:opacity-50"
          >
            {loadingCustom ? "Running..." : "🔴 Simulate Custom Shock"}
          </button>
          {customResult && (
            <div className="p-4 bg-surface rounded-lg border border-border" {...customScope}>
              <h3 data-prov="totalImpactPct" className="font-semibold">Estimated Impact: {(customResult.totalImpactPct * 100).toFixed(2)}%</h3>
              <ul className="mt-2 text-sm space-y-1">
                {customResult.impacts?.map((imp: any, i: number) => (
                  <li key={i} data-prov={`impacts.${imp.factor}`} data-prov-ctx={imp.factor}>
                    {imp.factor} Impact: {(imp.impact * 100).toFixed(2)}% (Beta: {imp.beta?.toFixed(2)})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
