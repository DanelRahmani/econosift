"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Holding, BLData } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  holdings: Holding[];
  period: string;
}

export function BlackLitterman({ holdings, period }: Props) {
  // views keyed by ticker → string % input
  const [viewInputs, setViewInputs] = useState<Record<string, string>>({});
  const [data, setData] = useState<BLData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  function updateView(ticker: string, val: string) {
    setViewInputs((prev) => ({ ...prev, [ticker]: val }));
  }

  async function run() {
    setLoading(true);
    setError(null);
    // Build views list (only non-empty inputs)
    const views: { ticker: string; expectedReturn: number }[] = [];
    for (const [ticker, val] of Object.entries(viewInputs)) {
      const n = parseFloat(val);
      if (!isNaN(n)) views.push({ ticker, expectedReturn: n / 100 }); // convert % to decimal
    }
    try {
      const d = await api.portfolioBL(holdings, views, period);
      if (d.error) {
        setError(d.error);
        setData(null);
      } else {
        setData(d);
      }
    } catch {
      setError("Failed to run Black-Litterman optimization");
    } finally {
      setLoading(false);
    }
  }

  // Build optimal weight lookup for display
  const optWeightMap = new Map(
    (data?.optimalWeights ?? []).map((w) => [w.ticker, w.weight])
  );

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-4" {...scope}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Black-Litterman Optimization</h3>
        <button
          onClick={run}
          disabled={loading || holdings.length === 0}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Running…" : "🔴 Run Black-Litterman"}
        </button>
      </div>

      <div>
        <p className="text-xs text-text-muted mb-2">
          Optionally enter your expected return views (%) for each holding. Leave blank to use market equilibrium.
        </p>
        <div className="space-y-2">
          {holdings.map((h) => (
            <div key={h.ticker} className="flex items-center gap-3">
              <span className="font-mono text-sm text-text-primary w-16">{h.ticker}</span>
              <input
                type="number"
                value={viewInputs[h.ticker] ?? ""}
                onChange={(e) => updateView(h.ticker, e.target.value)}
                placeholder="Expected return %"
                className="w-44 px-2 py-1.5 rounded-md border border-border bg-surface-alt text-text-primary text-sm focus:outline-none focus:border-accent"
              />
              <span className="text-text-muted text-sm">%</span>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-500">{error}</div>
      )}

      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted text-xs">
                <th className="text-left py-2 pr-4">Ticker</th>
                <th className="text-right py-2 pr-4">Equilibrium Return</th>
                <th className="text-right py-2 pr-4">BL Return</th>
                <th className="text-right py-2">Optimal Weight</th>
              </tr>
            </thead>
            <tbody>
              {(data.blReturns ?? []).map((row) => {
                const optW = optWeightMap.get(row.ticker) ?? null;
                return (
                  <tr key={row.ticker} data-prov-ctx={row.ticker} className="border-b border-border/50">
                    <td className="py-2 pr-4 font-mono font-medium text-text-primary">{row.ticker}</td>
                    <td data-prov={`blReturns.${row.ticker}.equilibriumReturn`} className="py-2 pr-4 text-right text-text-secondary">
                      {row.equilibriumReturn !== null ? `${(row.equilibriumReturn * 100).toFixed(2)}%` : "—"}
                    </td>
                    <td data-prov={`blReturns.${row.ticker}.blReturn`} className={`py-2 pr-4 text-right font-medium ${row.blReturn !== null && row.blReturn >= 0 ? "text-green-500" : "text-red-500"}`}>
                      {row.blReturn !== null ? `${(row.blReturn * 100).toFixed(2)}%` : "—"}
                    </td>
                    <td data-prov="optimalWeights" className="py-2 text-right font-medium text-accent">
                      {optW !== null ? `${(optW * 100).toFixed(2)}%` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
