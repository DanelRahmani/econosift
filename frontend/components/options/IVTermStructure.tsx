"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, Skeleton, chartPalette, chartTooltipStyle } from "@/components/ui";
import { fmtNum } from "@/lib/format";
import type { IVTermPoint } from "@/lib/types";

interface Props {
  data: IVTermPoint[];
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
      <div className="font-semibold text-text-primary">{label} DTE</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value !== null ? `${fmtNum(p.value, 2)}%` : "—"}
        </div>
      ))}
    </div>
  );
}

export function IVTermStructure({ data, loading, theme }: Props) {
  const p = chartPalette(theme as "light" | "dark");
  const tt = chartTooltipStyle(theme as "light" | "dark");

  if (loading) {
    return <Skeleton className="h-64 w-full rounded-xl" />;
  }

  if (!data.length) {
    return (
      <Card className="flex items-center justify-center h-64">
        <span className="text-text-muted text-sm">No term structure data</span>
      </Card>
    );
  }

  const chartData = data.map((d) => ({
    dte: d.dte,
    expiry: d.expiry,
    atmIV: d.atmIV,
    straddle: d.straddle,
  }));

  const hasStraddle = data.some((d) => d.straddle !== null);

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-4 text-text-primary">IV Term Structure</h3>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={p.grid} />
          <XAxis
            dataKey="dte"
            stroke={p.axis}
            tick={{ fontSize: 11, fill: p.axis }}
            label={{ value: "Days to Expiry", position: "insideBottom", offset: -12, fill: p.axis, fontSize: 11 }}
          />
          <YAxis
            stroke={p.axis}
            tick={{ fontSize: 11, fill: p.axis }}
            tickFormatter={(v) => `${v}%`}
            label={{ value: "ATM IV (%)", angle: -90, position: "insideLeft", offset: 10, fill: p.axis, fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} {...tt} />
          {hasStraddle && <Legend wrapperStyle={{ fontSize: 11, color: p.axis }} />}
          <Line
            type="monotone"
            dataKey="atmIV"
            name="ATM IV%"
            stroke="#c4394a"
            strokeWidth={2}
            dot={{ r: 3, fill: "#c4394a" }}
            connectNulls
          />
          {hasStraddle && (
            <Line
              type="monotone"
              dataKey="straddle"
              name="Straddle"
              stroke="#0065cb"
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={false}
              connectNulls
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
