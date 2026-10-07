"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { Holding, RollingData, DateValuePoint } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  holdings: Holding[];
  period: string;
}

const WINDOWS = [20, 60, 120, 252] as const;

export function RollingMetrics({ holdings, period }: Props) {
  const [window, setWindow] = useState<number>(60);
  const [data, setData] = useState<RollingData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    if (holdings.length === 0) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.portfolioRolling(holdings, period, window)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setError("Failed to load rolling metrics"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [holdings, period, window]);

  function thin(pts: DateValuePoint[], maxPts = 200): DateValuePoint[] {
    if (!pts || pts.length === 0) return [];
    const step = Math.max(1, Math.floor(pts.length / maxPts));
    return pts.filter((_, i) => i % step === 0);
  }

  function miniChart(
    pts: DateValuePoint[],
    label: string,
    color: string,
    formatter: (v: number) => string,
    provKey: string,
  ) {
    return (
      <div data-prov={provKey} className="rounded-lg border border-border bg-surface-alt p-3">
        <p className="text-xs text-text-muted font-medium mb-2">{label}</p>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={thin(pts)} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
            <XAxis
              dataKey="date"
              tickFormatter={(d) => d.slice(0, 7)}
              tick={{ fontSize: 10, fill: "rgb(var(--text-muted))" }}
              interval="preserveStartEnd"
              minTickGap={60}
            />
            <YAxis
              dataKey="value"
              tickFormatter={formatter}
              tick={{ fontSize: 10, fill: "rgb(var(--text-muted))" }}
              width={44}
            />
            <Tooltip
              formatter={(v: number) => [formatter(v), label]}
              labelFormatter={(l) => `Date: ${l}`}
              contentStyle={{
                backgroundColor: "rgb(var(--surface-alt))",
                border: "1px solid rgb(var(--border))",
                borderRadius: 8,
                fontSize: 11,
              }}
            />
            <Line type="monotone" dataKey="value" stroke={color} dot={false} strokeWidth={1.5} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-4" {...scope}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-semibold text-sm">Rolling Metrics</h3>
        <div className="flex gap-1 items-center">
          <span className="text-xs text-text-muted">Window:</span>
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
      </div>

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-lg border border-border bg-surface-alt h-40 animate-pulse" />
          ))}
        </div>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}

      {!loading && data && (
        <div className="space-y-3">
          {miniChart(data.sharpe, "Rolling Sharpe", "rgb(var(--primary))", (v) => v.toFixed(2), "sharpe")}
          {miniChart(data.volatility, "Rolling Volatility (ann.)", "#f59e0b", (v) => `${(v * 100).toFixed(1)}%`, "volatility")}
          {miniChart(data.beta, "Rolling Beta", "#6366f1", (v) => v.toFixed(2), "beta")}
        </div>
      )}
    </div>
  );
}
