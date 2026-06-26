"use client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, Cell, ResponsiveContainer } from "recharts";
import type { YieldCurvesData } from "@/lib/types";

interface Props { data: YieldCurvesData["foreign_10y"] }

export function MultiCountryYieldChart({ data }: Props) {
  const rows = Object.entries(data)
    .filter(([, v]) => v.spread_vs_us !== null)
    .map(([name, v]) => ({ name, spread: v.spread_vs_us as number }))
    .sort((a, b) => b.spread - a.spread);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v) => `${v.toFixed(1)}%`} />
        <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`, "Spread vs US 10Y"]} />
        <ReferenceLine y={0} stroke="#6b7280" />
        <Bar dataKey="spread" radius={[3, 3, 0, 0]}>
          {rows.map((r, i) => (
            <Cell key={i} fill={r.spread > 1 ? "#ef4444" : r.spread < -0.5 ? "#22c55e" : "#3b82f6"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
