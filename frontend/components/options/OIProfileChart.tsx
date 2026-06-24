"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Card, Skeleton, chartPalette, chartTooltipStyle } from "@/components/ui";
import { fmtPrice } from "@/lib/format";
import type { OIProfile } from "@/lib/types";

interface Props {
  data: OIProfile | null;
  loading: boolean;
  theme: string;
}

function fmtOI(v: number) {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(abs / 1_000).toFixed(0)}K`;
  return String(abs);
}

interface TooltipPayloadEntry {
  dataKey: string;
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
      <div className="font-semibold text-text-primary">Strike {fmtPrice(Number(label))}</div>
      {payload.map((p) => {
        const isCall = p.dataKey === "callOI";
        const label2 = isCall ? "Call OI" : "Put OI";
        const val = p.value !== null ? fmtOI(Math.abs(p.value ?? 0)) : "—";
        return (
          <div key={p.dataKey} style={{ color: p.color }}>
            {label2}: {val}
          </div>
        );
      })}
    </div>
  );
}

export function OIProfileChart({ data, loading, theme }: Props) {
  const p = chartPalette(theme as "light" | "dark");
  const tt = chartTooltipStyle(theme as "light" | "dark");

  if (loading) {
    return <Skeleton className="h-80 w-full rounded-xl" />;
  }

  if (!data || data.error) {
    return (
      <Card className="flex items-center justify-center h-80">
        <span className="text-text-muted text-sm">
          {data?.error ?? "No OI profile data available"}
        </span>
      </Card>
    );
  }

  const chartData = data.strikes.map((strike, i) => ({
    strike,
    callOI: data.callOI[i] ?? 0,
    putOI: -(data.putOI[i] ?? 0),
  }));

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-primary">Open Interest Profile</h3>
        <div className="flex items-center gap-4 text-[10px] text-text-muted">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2 rounded-sm bg-green-600/70" /> Calls
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2 rounded-sm bg-red-600/70" /> Puts
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={chartData}
          margin={{ top: 4, right: 16, left: 40, bottom: 4 }}
          layout="vertical"
        >
          <CartesianGrid strokeDasharray="3 3" stroke={p.grid} horizontal={false} />
          <XAxis
            type="number"
            stroke={p.axis}
            tick={{ fontSize: 10, fill: p.axis }}
            tickFormatter={fmtOI}
          />
          <YAxis
            type="category"
            dataKey="strike"
            stroke={p.axis}
            tick={{ fontSize: 10, fill: p.axis }}
            tickFormatter={(v) => fmtPrice(v)}
            width={56}
          />
          <Tooltip content={<CustomTooltip />} {...tt} />

          {/* Max Pain line */}
          {data.maxPain !== null && (
            <ReferenceLine
              y={data.maxPain}
              stroke="#ca8a04"
              strokeWidth={1.5}
              strokeDasharray="4 2"
              label={{
                value: `Max Pain ${fmtPrice(data.maxPain)}`,
                position: "insideTopRight",
                fill: "#ca8a04",
                fontSize: 10,
              }}
            />
          )}

          {/* Spot line */}
          <ReferenceLine
            y={data.spot}
            stroke={p.axis}
            strokeWidth={1.5}
            strokeDasharray="3 3"
            label={{
              value: `Spot ${fmtPrice(data.spot)}`,
              position: "insideTopLeft",
              fill: p.axis,
              fontSize: 10,
            }}
          />

          <Bar dataKey="callOI" name="Call OI" fill="#16a34a" fillOpacity={0.7} radius={[0, 2, 2, 0]} />
          <Bar dataKey="putOI" name="Put OI" fill="#c4394a" fillOpacity={0.7} radius={[0, 2, 2, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
