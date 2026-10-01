"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";
import type { PortfolioAnalysis } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  data: PortfolioAnalysis;
}

interface MergedPoint {
  date: string;
  portfolio: number | null;
  gspc: number | null;
  agg: number | null;
}

function mergeByDate(data: PortfolioAnalysis): MergedPoint[] {
  const map = new Map<string, MergedPoint>();

  for (const p of data.series) {
    map.set(p.date, { date: p.date, portfolio: p.value - 100, gspc: null, agg: null });
  }
  for (const p of data.benchmarkSeries.gspc) {
    const existing = map.get(p.date);
    if (existing) existing.gspc = p.value - 100;
    else map.set(p.date, { date: p.date, portfolio: null, gspc: p.value - 100, agg: null });
  }
  for (const p of data.benchmarkSeries.agg) {
    const existing = map.get(p.date);
    if (existing) existing.agg = p.value - 100;
    else map.set(p.date, { date: p.date, portfolio: null, gspc: null, agg: p.value - 100 });
  }

  return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function formatDate(d: string) {
  return d.slice(0, 7); // YYYY-MM
}

function formatPct(v: number | null) {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function PerformanceChart({ data }: Props) {
  const scope = useSourceScope(provOf(data));
  const merged = mergeByDate(data);
  // Thin to ~200 points for performance
  const step = Math.max(1, Math.floor(merged.length / 200));
  const pts = merged.filter((_, i) => i % step === 0 || i === merged.length - 1);

  return (
    <div className="rounded-xl border border-border bg-surface p-4" {...scope}>
      <h3 className="font-semibold text-sm mb-3">Cumulative Return</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={pts} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
            interval="preserveStartEnd"
            minTickGap={60}
          />
          <YAxis
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
            width={52}
          />
          <Tooltip
            formatter={(value: number, name: string) => [formatPct(value), name]}
            labelFormatter={(label: string) => `Date: ${label}`}
            contentStyle={{
              backgroundColor: "var(--color-surface-alt)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone"
            dataKey="portfolio"
            name="Portfolio"
            stroke="var(--color-accent)"
            dot={false}
            strokeWidth={2}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="gspc"
            name="S&P 500"
            stroke="#9ca3af"
            dot={false}
            strokeWidth={1.5}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="agg"
            name="AGG (Bonds)"
            stroke="#f59e0b"
            dot={false}
            strokeWidth={1.5}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
