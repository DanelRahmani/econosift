"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from "recharts";
import type { RiskContribData } from "@/lib/types";

const COLORS = [
  "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#3b82f6",
  "#a855f7", "#ec4899", "#14b8a6", "#f97316", "#84cc16",
];

interface Props {
  data: RiskContribData | null;
  loading: boolean;
}

export function RiskContribution({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 animate-pulse">
        <div className="h-4 w-40 bg-border rounded mb-4" />
        <div className="h-48 bg-surface-alt rounded" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 text-sm text-text-muted">
        Risk contribution data not available.
      </div>
    );
  }

  const pts = data
    .filter((c) => c.pctContrib !== null)
    .map((c) => ({ ticker: c.ticker, value: (c.pctContrib ?? 0) * 100 }));

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h3 className="font-semibold text-sm mb-3">Variance Contribution (%)</h3>
      <ResponsiveContainer width="100%" height={Math.max(180, pts.length * 36)}>
        <BarChart
          data={pts}
          layout="vertical"
          margin={{ top: 4, right: 24, bottom: 0, left: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-border)" />
          <XAxis
            type="number"
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
          />
          <YAxis
            type="category"
            dataKey="ticker"
            tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "monospace" }}
            width={52}
          />
          <Tooltip
            formatter={(v: number) => [`${v.toFixed(2)}%`, "Variance Contribution"]}
            contentStyle={{
              backgroundColor: "var(--color-surface-alt)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {pts.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
