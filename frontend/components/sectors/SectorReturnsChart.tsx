"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, LabelList, ResponsiveContainer,
} from "recharts";
import type { SectorReturn } from "@/lib/types";

interface Props {
  data: SectorReturn[];
  onSectorClick?: (sector: string) => void;
}

export function SectorReturnsChart({ data, onSectorClick }: Props) {
  const sorted = [...data]
    .filter((r) => r.changePercent !== null)
    .sort((a, b) => (b.changePercent ?? 0) - (a.changePercent ?? 0));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <BarChart
        data={sorted}
        layout="vertical"
        margin={{ top: 4, right: 80, left: 8, bottom: 4 }}
        onClick={(e) => {
          if (e?.activePayload?.[0]?.payload && onSectorClick) {
            onSectorClick(e.activePayload[0].payload.sector as string);
          }
        }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(128,128,128,0.15)" />
        <XAxis
          type="number"
          tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`}
          tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
          stroke="var(--color-border)"
        />
        <YAxis
          type="category"
          dataKey="sector"
          width={140}
          tick={{ fontSize: 12, fill: "var(--color-text-muted)" }}
          stroke="var(--color-border)"
        />
        <Tooltip
          formatter={(v: number) => [`${v > 0 ? "+" : ""}${v.toFixed(2)}%`, "Return"]}
          contentStyle={{ fontSize: 12 }}
        />
        <Bar dataKey="changePercent" radius={[0, 3, 3, 0]} cursor={onSectorClick ? "pointer" : undefined}>
          {sorted.map((row, i) => (
            <Cell
              key={i}
              fill={(row.changePercent ?? 0) >= 0 ? "#16a34a" : "#c4394a"}
              fillOpacity={0.85}
            />
          ))}
          <LabelList
            dataKey="changePercent"
            position="right"
            formatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`}
            style={{ fontSize: 11, fill: "currentColor" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
