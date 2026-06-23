"use client";

import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { PricesResponse } from "@/lib/types";
import { CHART_COLORS } from "@/lib/format";
import { chartTooltipStyle, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";

const SMA_WINDOWS = [20, 50, 200];

function rollingAvg(values: (number | null)[], window: number): (number | null)[] {
  return values.map((_, i) => {
    if (i < window - 1) return null;
    let sum = 0, count = 0;
    for (let j = i - window + 1; j <= i; j++) {
      const v = values[j];
      if (typeof v === "number") { sum += v; count++; }
    }
    return count === window ? sum / count : null;
  });
}

export function PriceChart({ data }: { data: PricesResponse }) {
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  const { prices, benchmarks } = data;
  const [activeSmas, setActiveSmas] = useState<number[]>([]);

  if (!prices.length) {
    return <div className="text-text-muted text-sm">No price data.</div>;
  }

  const cols = Object.keys(prices[0]).filter((k) => k !== "Date");
  const primaryCols = cols.filter((c) => !benchmarks.includes(c));

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

  // Compute SMAs and attach to chart data
  const chartData = normalised.map((row) => ({ ...row }));
  if (activeSmas.length) {
    for (const c of primaryCols) {
      const vals = normalised.map((r) => r[c] as number | null);
      for (const w of activeSmas) {
        const avgs = rollingAvg(vals, w);
        avgs.forEach((v, i) => { chartData[i][`${c}_SMA${w}`] = v; });
      }
    }
  }

  function toggleSma(w: number) {
    setActiveSmas((prev) => prev.includes(w) ? prev.filter((x) => x !== w) : [...prev, w]);
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-text-muted">SMA:</span>
        {SMA_WINDOWS.map((w) => (
          <button
            key={w}
            onClick={() => toggleSma(w)}
            className={`px-2 py-0.5 rounded text-xs font-mono transition-colors border ${
              activeSmas.includes(w)
                ? "bg-accent/20 text-accent border-accent/40"
                : "text-text-muted border-border hover:text-text-primary"
            }`}
          >
            {w}
          </button>
        ))}
      </div>
      <div className="h-96 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
            <XAxis dataKey="Date" tick={{ fill: pal.axis, fontSize: 12 }} minTickGap={40} />
            <YAxis tick={{ fill: pal.axis, fontSize: 12 }} domain={["auto", "auto"]} />
            <Tooltip {...chartTooltipStyle(theme)} formatter={(v: number) => v?.toFixed(2)} />
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
            {primaryCols.flatMap((c, i) =>
              activeSmas.map((w) => (
                <Line
                  key={`${c}_SMA${w}`}
                  type="monotone"
                  dataKey={`${c}_SMA${w}`}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={1.5}
                  strokeDasharray="4 3"
                  strokeOpacity={0.65}
                  dot={false}
                  connectNulls
                  legendType="none"
                  name={`${c} SMA${w}`}
                />
              ))
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
