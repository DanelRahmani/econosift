"use client";
import { useEffect, useState } from "react";
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { CentralBanksData } from "@/lib/types";

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
const GRID = "rgba(255,255,255,0.08)";

export function CentralBanksTab() {
  const [data, setData] = useState<CentralBanksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.macroCentralBanks()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-white/40">Loading central bank data…</div>
  );
  if (error || !data) return (
    <div className="flex items-center justify-center h-64 text-red-400">Failed to load central bank data.</div>
  );

  const chartData = data.history.filter((_, i) => i % 3 === 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {CB_NAMES.map(cb => {
          const cur = data.current[cb];
          if (!cur) return null;
          return (
            <div key={cb} className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: CB_COLORS[cb] }} />
                <span className="text-xs text-white/60 font-medium">{cb}</span>
              </div>
              <div className="text-lg font-semibold text-white">
                {cur.rate !== null ? `${cur.rate.toFixed(2)}%` : "—"}
              </div>
              {cur.next_meeting && (
                <div className="text-[10px] text-white/40 mt-1">
                  Next: {cur.next_meeting.slice(5)}{cur.days_until !== null ? ` (${cur.days_until}d)` : ""}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-white/5 rounded-lg border border-white/10 p-4">
        <h3 className="text-sm font-medium text-white/80 mb-4">Policy Rate History (2005–present)</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="date" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
                   tickFormatter={(v: string) => v.slice(0, 7)} interval={23} />
            <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                   tickFormatter={(v: number) => `${v}%`} domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={{ background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 6 }}
              labelStyle={{ color: "rgba(255,255,255,0.6)", fontSize: 12 }}
              labelFormatter={(v: string) => v.slice(0, 7)}
              formatter={(v: number, name: string) => [`${v?.toFixed(2)}%`, name]}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: "rgba(255,255,255,0.6)" }} />
            {CB_NAMES.map(cb => (
              <Line key={cb} type="monotone" dataKey={cb} stroke={CB_COLORS[cb]}
                    dot={false} strokeWidth={1.5} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {data.balance_sheet.length > 0 && (
        <div className="bg-white/5 rounded-lg border border-white/10 p-4">
          <h3 className="text-sm font-medium text-white/80 mb-4">Fed Balance Sheet (Total Assets, $T)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.balance_sheet.filter((_, i) => i % 4 === 0)}
                       margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
                     tickFormatter={(v: string) => v.slice(0, 7)} interval={35} />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                     tickFormatter={(v: number) => `$${v.toFixed(1)}T`} />
              <Tooltip
                contentStyle={{ background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 6 }}
                formatter={(v: number) => [`$${v.toFixed(2)}T`, "Balance Sheet"]}
                labelFormatter={(v: string) => v.slice(0, 7)}
              />
              <Area type="monotone" dataKey="value" stroke="#3b82f6"
                    fill="rgba(59,130,246,0.15)" strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
