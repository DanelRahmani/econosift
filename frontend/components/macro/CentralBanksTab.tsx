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

const CB_FULL_NAMES: Record<string, string> = {
  Fed: "US Federal Reserve",
  ECB: "European Central Bank",
  BoE: "Bank of England",
  BoJ: "Bank of Japan",
  BoC: "Bank of Canada",
  RBA: "Reserve Bank of Australia",
  SNB: "Swiss National Bank",
};

const TIME_SPANS = [
  { label: "1Y", months: 12 },
  { label: "5Y", months: 60 },
  { label: "10Y", months: 120 },
  { label: "All", months: 0 },
] as const;

export function CentralBanksTab() {
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  const tooltipStyle = chartTooltipStyle(theme);

  const [data, setData] = useState<CentralBanksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [timeSpan, setTimeSpan] = useState<number>(120); // default 10Y

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

  // Filter history by actual date range, not index count
  const allHistory = data.history;
  const today = new Date();
  let cutoffDate: Date | null = null;
  if (timeSpan > 0) {
    cutoffDate = new Date(today);
    cutoffDate.setMonth(cutoffDate.getMonth() - timeSpan);
  }
  const filteredHistory = cutoffDate
    ? allHistory.filter((p: any) => new Date(p.date) >= cutoffDate!)
    : allHistory;
  const chartData = filteredHistory;
  // Tick strategy: 1Y=monthly marks, 5Y=quarterly, 10Y/All=year-start only
  const showMonths = timeSpan > 0 && timeSpan <= 12;
  const showQuarters = timeSpan > 12 && timeSpan <= 60;
  const xInterval = showMonths ? 0 : showQuarters ? Math.max(1, Math.floor(filteredHistory.length / 20)) : Math.max(1, Math.floor(filteredHistory.length / 12));
  const tickFmt = (v: string) => {
    if (showMonths) return v.slice(0, 7);       // "2026-06"
    if (showQuarters) { const m = parseInt(v.slice(5,7)); const q = Math.ceil(m/3); return `${v.slice(0,4)} Q${q}`; }
    return v.slice(0, 4);                        // "2026"
  };

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
              <div className="text-[10px] text-text-muted mt-0.5" title={CB_FULL_NAMES[cb]}>
                {CB_FULL_NAMES[cb]}
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
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-text-secondary">Policy Rate History</h3>
          <div className="flex gap-1">
            {TIME_SPANS.map(ts => (
              <button key={ts.label} onClick={() => setTimeSpan(ts.months)}
                className={`px-2.5 py-1 text-xs rounded border transition-colors ${
                  timeSpan === ts.months
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border text-text-muted hover:text-text-primary"
                }`}>{ts.label}</button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
            <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 10 }}
                   tickFormatter={tickFmt}
                   interval={xInterval} />
            <YAxis tick={{ fill: pal.axis, fontSize: 11 }}
                   tickFormatter={(v: number) => `${v}%`} domain={["auto", "auto"]} />
            <Tooltip
              {...tooltipStyle}
              labelFormatter={(v: string) => v.slice(0, 7)}
              formatter={(v: number, name: string) => [`${v?.toFixed(2)}%`, CB_FULL_NAMES[name] ?? name]}
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
          <h3 className="text-sm font-medium text-text-secondary mb-4">US Federal Reserve Balance Sheet (Total Assets, $T)</h3>
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
