"use client";

import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { Holding, StressData, StressScenario } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  holdings: Holding[];
  period: string;
}

function ScenarioCard({ scenario }: { scenario: StressScenario }) {
  const ret = scenario.totalReturn !== null ? scenario.totalReturn * 100 : null;
  const dd = scenario.maxDrawdown !== null ? scenario.maxDrawdown * 100 : null;

  const pts = scenario.returnsTimeSeries.map((p) => ({
    date: p.date,
    value: (p.value ?? 0) * 100,
  }));

  return (
    <div className="rounded-lg border border-border bg-surface-alt p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-sm text-text-primary">{scenario.label}</h4>
        <div className="flex gap-3 text-xs">
          <span className={`font-bold ${ret !== null && ret >= 0 ? "text-green-500" : "text-red-500"}`}>
            {ret !== null ? `${ret >= 0 ? "+" : ""}${ret.toFixed(2)}%` : "—"}
          </span>
          <span className="text-red-500 font-medium">
            DD: {dd !== null ? `${dd.toFixed(2)}%` : "—"}
          </span>
        </div>
      </div>

      {scenario.error && (
        <p className="text-xs text-text-muted italic">{scenario.error}</p>
      )}

      {pts.length > 2 && (
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={pts} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis
              dataKey="date"
              tickFormatter={(d) => d.slice(2, 7)}
              tick={{ fontSize: 9, fill: "var(--color-text-muted)" }}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v) => `${v.toFixed(0)}%`}
              tick={{ fontSize: 9, fill: "var(--color-text-muted)" }}
              width={36}
            />
            <Tooltip
              formatter={(v: number) => [`${v.toFixed(2)}%`, "Return"]}
              contentStyle={{
                backgroundColor: "var(--color-surface-alt)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                fontSize: 11,
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={(ret ?? 0) >= 0 ? "#16a34a" : "#ef4444"}
              dot={false}
              strokeWidth={1.5}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export function StressTesting({ holdings, period }: Props) {
  const [data, setData] = useState<StressData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));
  const scenarios = data?.scenarios;

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const d = await api.portfolioStress(holdings, period);
      setData(d);
    } catch {
      setError("Failed to run stress tests");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-4" {...scope}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Historical Stress Testing</h3>
        <button
          onClick={run}
          disabled={loading || holdings.length === 0}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Running…" : "🔴 Run Stress Tests"}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-500">{error}</div>
      )}

      {scenarios && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {scenarios.map((s) => (
            <ScenarioCard key={s.scenario} scenario={s} />
          ))}
        </div>
      )}
    </div>
  );
}
