"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { PortfolioAnalysis } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  data: PortfolioAnalysis;
}

export function DrawdownChart({ data }: Props) {
  const scope = useSourceScope(provOf(data));
  const step = Math.max(1, Math.floor(data.drawdownSeries.length / 200));
  const pts = data.drawdownSeries
    .filter((_, i) => i % step === 0 || i === data.drawdownSeries.length - 1)
    .map((p) => ({ date: p.date, drawdown: p.value * 100 }));

  return (
    <div className="rounded-xl border border-border bg-surface p-4" data-prov="drawdownSeries" {...scope}>
      <h3 className="font-semibold text-sm mb-3">Drawdown</h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={pts} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => d.slice(0, 7)}
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
            formatter={(value: number) => [`${value.toFixed(2)}%`, "Drawdown"]}
            labelFormatter={(label: string) => `Date: ${label}`}
            contentStyle={{
              backgroundColor: "var(--color-surface-alt)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.2}
            strokeWidth={1.5}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
