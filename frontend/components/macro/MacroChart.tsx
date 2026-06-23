"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { MacroResponse } from "@/lib/types";
import { CHART_COLORS } from "@/lib/format";
import { chartTooltipStyle } from "@/components/ui";

export function MacroChart({ data }: { data: MacroResponse }) {
  const { series } = data;
  if (!series.length || series.every((s) => s.data.length === 0)) {
    return <div className="text-text-muted text-sm">No data for this selection.</div>;
  }

  // Merge series by year into wide rows.
  const years = new Set<string>();
  series.forEach((s) => s.data.forEach((d) => years.add(d.year)));
  const sorted = Array.from(years).sort();

  const rows = sorted.map((year) => {
    const row: Record<string, string | number | null> = { year };
    series.forEach((s) => {
      const pt = s.data.find((d) => d.year === year);
      row[s.country] = pt ? pt.value : null;
    });
    return row;
  });

  return (
    <div>
      <div className="h-96 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows}>
            <CartesianGrid stroke="#2e3150" strokeDasharray="3 3" />
            <XAxis dataKey="year" tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }}
              tickFormatter={(v) => `${v}${data.unit === "%" ? "%" : ""}`} />
            <Tooltip {...chartTooltipStyle()} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {series.map((s, i) => (
              <Line
                key={s.country}
                type="monotone"
                dataKey={s.country}
                name={s.countryName}
                stroke={CHART_COLORS[i % CHART_COLORS.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 text-xs text-text-muted">
        Sources: {Array.from(new Set(series.map((s) => s.source_label))).join(", ")}
      </div>
    </div>
  );
}
