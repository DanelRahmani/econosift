"use client";

import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui";
import { chartTooltipStyle, chartPalette } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import type { RollingTickerMetrics, RollingPoint } from "@/lib/types";

const WINDOWS = [20, 60, 120, 252] as const;
type Window = (typeof WINDOWS)[number];

const METRICS = [
  { key: "sharpe", label: "Sharpe Ratio", unit: "", decimals: 2, zeroLine: true },
  { key: "volatility", label: "Volatility (Ann.)", unit: "%", decimals: 1, scale: 100, zeroLine: false },
  { key: "beta", label: "Beta", unit: "", decimals: 2, zeroLine: false, refLine: 1 },
  { key: "sortino", label: "Sortino Ratio", unit: "", decimals: 2, zeroLine: true },
  { key: "maxDrawdown", label: "Max Drawdown", unit: "%", decimals: 1, scale: 100, zeroLine: true },
  { key: "var95", label: "VaR 95%", unit: "%", decimals: 2, scale: 100, zeroLine: false },
] as const;

type MetricKey = (typeof METRICS)[number]["key"];
type ViewMode = "overlay" | "grid";

interface Props {
  data: RollingTickerMetrics[];
  theme: "light" | "dark";
  loading?: boolean;
}

function thinSeries(pts: RollingPoint[], maxPoints = 500): RollingPoint[] {
  if (pts.length <= maxPoints) return pts;
  const step = Math.ceil(pts.length / maxPoints);
  return pts.filter((_, i) => i % step === 0 || i === pts.length - 1);
}

function SingleChart({
  data, metricKey, tickers, theme, height = 260,
}: {
  data: RollingTickerMetrics[];
  metricKey: MetricKey;
  tickers: string[];
  theme: "light" | "dark";
  height?: number;
}) {
  const meta = METRICS.find((m) => m.key === metricKey)!;
  const palette = chartPalette(theme);
  const tooltip = chartTooltipStyle(theme);

  // Merge all tickers' series into a date-keyed map
  const dateMap = new Map<string, Record<string, number | null>>();
  data.forEach((td, i) => {
    const pts = thinSeries((td[metricKey] as RollingPoint[]) ?? []);
    pts.forEach(({ date, value }) => {
      if (!dateMap.has(date)) dateMap.set(date, { date: date as unknown as number });
      const entry = dateMap.get(date)!;
      const scale = (meta as { scale?: number }).scale ?? 1;
      entry[td.ticker] = value !== null ? value * scale : null;
    });
  });

  const chartData = Array.from(dateMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([, v]) => v);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 4, right: 12, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: palette.axis }}
          tickFormatter={(v) => v?.slice(0, 7) ?? ""}
          interval="preserveStartEnd"
        />
        <YAxis tick={{ fontSize: 10, fill: palette.axis }} tickFormatter={(v) => `${v}${meta.unit}`} />
        <Tooltip
          {...tooltip}
          formatter={(v: number, name: string) => [`${v?.toFixed(meta.decimals)}${meta.unit}`, name]}
          labelFormatter={(l) => String(l)}
        />
        {(meta as { zeroLine?: boolean }).zeroLine && (
          <ReferenceLine y={0} stroke={palette.axis} strokeDasharray="4 2" />
        )}
        {(meta as { refLine?: number }).refLine !== undefined && (
          <ReferenceLine y={(meta as { refLine?: number }).refLine} stroke={palette.axis} strokeDasharray="4 2" />
        )}
        {tickers.map((t, i) => (
          <Line
            key={t}
            dataKey={t}
            stroke={CHART_COLORS[i % CHART_COLORS.length]}
            dot={false}
            strokeWidth={1.5}
            connectNulls={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function RollingMetricsChart({ data, theme, loading }: Props) {
  const [window, setWindow] = useState<Window>(252);
  const [metric, setMetric] = useState<MetricKey>("sharpe");
  const [view, setView] = useState<ViewMode>("overlay");

  if (loading) {
    return (
      <Card className="p-4">
        <div className="h-64 flex items-center justify-center text-text-muted text-sm">
          Loading rolling metrics…
        </div>
      </Card>
    );
  }
  if (!data.length) {
    return (
      <Card className="p-4">
        <div className="text-text-muted text-sm">No rolling data available.</div>
      </Card>
    );
  }

  const tickers = data.map((d) => d.ticker);

  return (
    <Card className="p-4 space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
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

        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value as MetricKey)}
          className="px-2 py-1 rounded text-xs bg-surface-alt border border-border text-text-primary"
        >
          {METRICS.map((m) => (
            <option key={m.key} value={m.key}>{m.label}</option>
          ))}
        </select>

        <div className="flex gap-1 ml-auto">
          {(["overlay", "grid"] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-2 py-1 rounded text-xs font-medium capitalize transition-colors ${
                view === v
                  ? "bg-accent text-white"
                  : "bg-surface-alt text-text-secondary hover:text-text-primary"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Charts */}
      {view === "overlay" ? (
        <div>
          <p className="text-xs text-text-muted mb-2">
            {METRICS.find((m) => m.key === metric)?.label} · {window}D rolling window
          </p>
          <SingleChart data={data} metricKey={metric} tickers={tickers} theme={theme} height={280} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {METRICS.map((m) => (
            <div key={m.key}>
              <p className="text-xs text-text-muted mb-1">{m.label}</p>
              <SingleChart data={data} metricKey={m.key} tickers={tickers} theme={theme} height={180} />
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-3 pt-1">
        {tickers.map((t, i) => (
          <div key={t} className="flex items-center gap-1.5">
            <div
              className="w-3 h-0.5 rounded"
              style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
            />
            <span className="text-xs font-mono text-text-secondary">{t}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
