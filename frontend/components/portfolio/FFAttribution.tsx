"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Holding, FFData } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  holdings: Holding[];
  period: string;
}

export function FFAttribution({ holdings, period }: Props) {
  const [model, setModel] = useState<"3" | "5">("3");
  const [data, setData] = useState<FFData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  async function calculate() {
    setLoading(true);
    setError(null);
    try {
      const d = await api.portfolioFF(holdings, period, model);
      if (d.error) {
        setError(d.error);
        setData(null);
      } else {
        setData(d);
      }
    } catch {
      setError("Failed to compute Fama-French attribution");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3" {...scope}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-semibold text-sm">Fama-French Attribution</h3>
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {(["3", "5"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setModel(m)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  model === m
                    ? "bg-accent text-white"
                    : "bg-surface-alt text-text-secondary hover:text-text-primary"
                }`}
              >
                FF{m}
              </button>
            ))}
          </div>
          <button
            onClick={calculate}
            disabled={loading || holdings.length === 0}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Calculating…" : "🟡 Calculate"}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-500">
          {error}
        </div>
      )}

      {data && (
        <>
          <div className="flex gap-4 flex-wrap">
            <div data-prov="annAlpha" className="bg-surface-alt rounded-lg p-3">
              <p className="text-xs text-text-muted">Alpha (ann.)</p>
              <p className={`text-lg font-bold mt-1 ${data.annAlpha !== null && (data.annAlpha ?? 0) >= 0 ? "text-green-500" : "text-red-500"}`}>
                {data.annAlpha !== null ? `${((data.annAlpha ?? 0) * 100).toFixed(2)}%` : "—"}
              </p>
            </div>
            <div data-prov="rSquared" className="bg-surface-alt rounded-lg p-3">
              <p className="text-xs text-text-muted">R²</p>
              <p className="text-lg font-bold mt-1 text-text-primary">
                {data.rSquared !== null ? data.rSquared.toFixed(3) : "—"}
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-xs">
                  <th className="text-left py-2 pr-4">Factor</th>
                  <th className="text-right py-2 pr-4">Loading</th>
                  <th className="text-right py-2">T-Statistic</th>
                </tr>
              </thead>
              <tbody>
                {(data.factors ?? []).map((row) => (
                  <tr key={row.factor} data-prov-ctx={row.factor} className="border-b border-border/50">
                    <td className="py-2 pr-4 font-medium text-text-primary">{row.factor}</td>
                    <td data-prov={`factors.${row.factor}.loading`} className={`py-2 pr-4 text-right ${row.loading !== null && row.loading >= 0 ? "text-green-500" : "text-red-500"}`}>
                      {row.loading !== null ? row.loading.toFixed(4) : "—"}
                    </td>
                    <td data-prov={`factors.${row.factor}.tStat`} className={`py-2 text-right ${row.tStat !== null && Math.abs(row.tStat) >= 2 ? "text-accent font-medium" : "text-text-secondary"}`}>
                      {row.tStat !== null ? row.tStat.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted">|t| ≥ 2 highlighted in accent (statistically significant at ~5% level)</p>
        </>
      )}
    </div>
  );
}
