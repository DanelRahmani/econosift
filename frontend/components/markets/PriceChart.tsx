"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { PricesResponse } from "@/lib/types";
import { CHART_COLORS } from "@/lib/format";
import { chartTooltipStyle } from "@/components/ui";

export function PriceChart({ data }: { data: PricesResponse }) {
  const { prices, benchmarks } = data;
  if (!prices.length) {
    return <div className="text-text-muted text-sm">No price data.</div>;
  }

  const cols = Object.keys(prices[0]).filter((k) => k !== "Date");

  // Normalise each series to 100 at first valid value.
  const base: Record<string, number> = {};
  for (const c of cols) {
    const first = prices.find((p) => typeof p[c] === "number" && p[c] !== null);
    if (first && typeof first[c] === "number") base[c] = first[c] as number;
  }

  const normalised = prices.map((p) => {
    const row: Record<string, string | number | null> = { Date: p.Date };
    for (const c of cols) {
      const v = p[c];
      row[c] = typeof v === "number" && base[c] ? (v / base[c]) * 100 : null;
    }
    return row;
  });

  return (
    <div className="h-96 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={normalised}>
          <CartesianGrid stroke="#2e3150" strokeDasharray="3 3" />
          <XAxis dataKey="Date" tick={{ fill: "#94a3b8", fontSize: 12 }} minTickGap={40} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} domain={["auto", "auto"]} />
          <Tooltip {...chartTooltipStyle()} formatter={(v: number) => v?.toFixed(2)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {cols.map((c, i) => (
            <Line
              key={c}
              type="monotone"
              dataKey={c}
              stroke={CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              strokeDasharray={benchmarks.includes(c) ? "5 4" : undefined}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
