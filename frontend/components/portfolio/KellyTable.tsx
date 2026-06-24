"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Holding, KellyData } from "@/lib/types";

interface Props {
  holdings: Holding[];
  period: string;
}

export function KellyTable({ holdings, period }: Props) {
  const [data, setData] = useState<KellyData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function calculate() {
    setLoading(true);
    setError(null);
    try {
      const d = await api.portfolioKelly(holdings, period);
      setData(d);
    } catch {
      setError("Failed to calculate Kelly criterion");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Kelly Criterion</h3>
        <button
          onClick={calculate}
          disabled={loading || holdings.length === 0}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Calculating…" : "🟡 Calculate Kelly"}
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {data && data.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-xs">
                  <th className="text-left py-2 pr-4">Ticker</th>
                  <th className="text-right py-2 pr-4">Ann. Return</th>
                  <th className="text-right py-2 pr-4">Ann. Vol</th>
                  <th className="text-right py-2">Kelly Fraction</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => {
                  const kelly = r.kellyFraction !== null ? Math.min(r.kellyFraction * 100, 100) : null;
                  return (
                    <tr key={r.ticker} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-mono font-medium text-text-primary">{r.ticker}</td>
                      <td className={`py-2 pr-4 text-right ${r.annReturn !== null && r.annReturn >= 0 ? "text-green-500" : "text-red-500"}`}>
                        {r.annReturn !== null ? `${(r.annReturn * 100).toFixed(2)}%` : "—"}
                      </td>
                      <td className="py-2 pr-4 text-right text-text-secondary">
                        {r.annVolatility !== null ? `${(r.annVolatility * 100).toFixed(2)}%` : "—"}
                      </td>
                      <td className="py-2 text-right font-medium text-accent">
                        {kelly !== null ? `${kelly.toFixed(1)}%` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted italic">
            Kelly criterion is the theoretical maximum position size for geometric-growth maximization.
            In practice, use half-Kelly or less to manage drawdown risk.
          </p>
        </>
      )}
    </div>
  );
}
