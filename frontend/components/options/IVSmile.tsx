"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
import { Card, Skeleton, chartPalette, chartTooltipStyle } from "@/components/ui";
import { fmtNum } from "@/lib/format";
import type { IVSmilePoint } from "@/lib/types";

interface Props {
  data: IVSmilePoint[];
  loading: boolean;
  theme: string;
}

interface TooltipPayloadEntry {
  name: string;
  value: number | null;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string | number;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg space-y-1">
      <div className="font-semibold text-text-primary">
        Moneyness: {typeof label === "number" ? fmtNum(label, 3) : label}
      </div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value !== null ? `${fmtNum(p.value, 2)}%` : "—"}
        </div>
      ))}
    </div>
  );
}

export function IVSmile({ data, loading, theme }: Props) {
  const p = chartPalette(theme as "light" | "dark");
  const tt = chartTooltipStyle(theme as "light" | "dark");

  if (loading) {
    return <Skeleton className="h-64 w-full rounded-xl" />;
  }

  if (!data.length) {
    return (
      <Card className="flex items-center justify-center h-64">
        <span className="text-text-muted text-sm">No smile data</span>
      </Card>
    );
  }

  const chartData = data
    .slice()
    .sort((a, b) => a.moneyness - b.moneyness)
    .map((d) => ({
      moneyness: d.moneyness,
      strike: d.strike,
      callIV: d.callIV,
      putIV: d.putIV,
    }));

  const TICKS = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3];

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-4 text-text-primary">IV Smile</h3>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={p.grid} />
          <XAxis
            dataKey="moneyness"
            type="number"
            domain={["auto", "auto"]}
            ticks={TICKS}
            tickFormatter={(v) => v.toFixed(1)}
            stroke={p.axis}
            tick={{ fontSize: 11, fill: p.axis }}
            label={{ value: "Moneyness (K/S)", position: "insideBottom", offset: -12, fill: p.axis, fontSize: 11 }}
          />
          <YAxis
            stroke={p.axis}
            tick={{ fontSize: 11, fill: p.axis }}
            tickFormatter={(v) => `${v}%`}
            label={{ value: "IV (%)", angle: -90, position: "insideLeft", offset: 10, fill: p.axis, fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} {...tt} />
          <Legend wrapperStyle={{ fontSize: 11, color: p.axis }} />
          <ReferenceLine
            x={1.0}
            stroke={p.axis}
            strokeDasharray="4 2"
            label={{ value: "ATM", position: "top", fill: p.axis, fontSize: 10 }}
          />
          <Line
            type="monotone"
            dataKey="callIV"
            name="Call IV%"
            stroke="#16a34a"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="putIV"
            name="Put IV%"
            stroke="#c4394a"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
