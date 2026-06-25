"use client";
import { useEffect, useState } from "react";
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { CentralBanksData } from "@/lib/types";
import { chartPalette, chartTooltipStyle } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";

const CB_COLORS: Record<string, string> = {
  Fed: "#3b82f6",
  ECB: "#eab308",
  BoE: "#ef4444",
  BoJ: "#a855f7",
  BoC: "#14b8a6",
  RBA: "#f97316",
  SNB: "#ec4899",
};
const CB_NAMES = Object.keys(CB_COLORS);

export function CentralBanksTab() {
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  const tooltipStyle = chartTooltipStyle(theme);

  const [data, setData] = useState<CentralBanksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.macroCentralBanks()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Central bank data unavailable.
      </div>
    );
  }

  const chartData = data.history.filter((_, i) => i % 3 === 0);

  return (
    <div className="space-y-6">
      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {CB_NAMES.map(cb => {
          const cur = data.current[cb];
          if (!cur) return null;
          return (
            <div key={cb} className="card p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: CB_COLORS[cb] }} />
                <span className="text-xs text-text-secondary font-medium">{cb}</span>
              </div>
              <div className="text-lg font-semibold text-text-primary">
                {cur.rate !== null ? `${cur.rate.toFixed(2)}%` : "—"}
              </div>
              {cur.next_meeting && (
                <div className="text-[10px] text-text-muted mt-1">
                  Next: {cur.next_meeting.slice(5)}{cur.days_until !== null ? ` (${cur.days_until}d)` : ""}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Policy rate history chart */}
      <div className="card p-4">
        <h3 className="text-sm font-medium text-text-secondary mb-4">Policy Rate History (2005–present)</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
            <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 10 }}
                   tickFormatter={(v: string) => v.slice(0, 7)} interval={23} />
            <YAxis tick={{ fill: pal.axis, fontSize: 11 }}
                   tickFormatter={(v: number) => `${v}%`} domain={["auto", "auto"]} />
            <Tooltip
              {...tooltipStyle}
              labelFormatter={(v: string) => v.slice(0, 7)}
              formatter={(v: number, name: string) => [`${v?.toFixed(2)}%`, name]}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: pal.axis }} />
            {CB_NAMES.map(cb => (
              <Line key={cb} type="monotone" dataKey={cb} stroke={CB_COLORS[cb]}
                    dot={false} strokeWidth={1.5} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Fed balance sheet */}
      {data.balance_sheet.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-medium text-text-secondary mb-4">Fed Balance Sheet (Total Assets, $T)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.balance_sheet.filter((_, i) => i % 4 === 0)}
                       margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 10 }}
                     tickFormatter={(v: string) => v.slice(0, 7)} interval={35} />
              <YAxis tick={{ fill: pal.axis, fontSize: 11 }}
                     tickFormatter={(v: number) => `$${v.toFixed(1)}T`} />
              <Tooltip
                {...tooltipStyle}
                formatter={(v: number) => [`$${v.toFixed(2)}T`, "Balance Sheet"]}
                labelFormatter={(v: string) => v.slice(0, 7)}
              />
              <Area type="monotone" dataKey="value" stroke={CB_COLORS.Fed}
                    fill={`${CB_COLORS.Fed}26`} strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
