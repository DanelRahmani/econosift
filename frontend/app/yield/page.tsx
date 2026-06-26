"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MultiCountryYieldChart } from "@/components/yield/MultiCountryYieldChart";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from "recharts";

const TABS = ["US Curve", "Foreign Spreads", "Real & Breakeven"] as const;

function KpiCard({ label, value, badge }: { label: string; value: string; badge?: string }) {
  return (
    <div className="bg-surface rounded-lg p-4 border border-border">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
      {badge && (
        <span className="text-xs mt-1 px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">{badge}</span>
      )}
    </div>
  );
}

export default function YieldPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("US Curve");
  const { data, isLoading, error } = useQuery({
    queryKey: ["yieldCurves"],
    queryFn: api.yieldCurves,
  });

  if (isLoading) return <div className="p-8 text-muted">Loading yield curve data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load yield data.</div>;

  const { us_curve, foreign_10y, real_yields, breakevens, term_premium } = data;
  const fmt = (v: number | null, decimals = 2) => v != null ? `${v.toFixed(decimals)}%` : "N/A";

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Yield Curves &amp; Term Structure</h1>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="US 10Y Yield" value={fmt(us_curve.points.find(p => p.tenor === "10y")?.yield ?? null)} />
        <KpiCard
          label="2Y–10Y Spread"
          value={fmt(us_curve.spread_2y10y)}
          badge={us_curve.inverted ? "INVERTED" : undefined}
        />
        <KpiCard label="10Y Breakeven" value={fmt(breakevens["10y"] ?? null)} />
        <KpiCard label="Term Premium (ACM)" value={fmt(term_premium.current)} />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 -mb-px transition-colors ${
              tab === t ? "border-accent text-accent" : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "US Curve" && (
        <div className="bg-surface rounded-lg p-4 border border-border">
          <h2 className="text-sm font-medium mb-4 text-muted">US Treasury Spot Curve</h2>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={us_curve.points.filter(p => p.yield !== null)}>
              <XAxis dataKey="tenor" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${v.toFixed(1)}%`} domain={["auto", "auto"]} />
              <Tooltip formatter={(v: number) => [`${v.toFixed(3)}%`, "Yield"]} />
              <Line type="monotone" dataKey="yield" stroke="#3b82f6" dot={{ r: 4 }} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {tab === "Foreign Spreads" && (
        <div className="bg-surface rounded-lg p-4 border border-border">
          <h2 className="text-sm font-medium mb-4 text-muted">10Y Sovereign Spread vs US Treasury</h2>
          <MultiCountryYieldChart data={foreign_10y} />
        </div>
      )}

      {tab === "Real & Breakeven" && (
        <div className="bg-surface rounded-lg p-4 border border-border">
          <h2 className="text-sm font-medium mb-4 text-muted">TIPS Real Yields by Tenor</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={real_yields.filter(p => p.yield !== null)}>
              <XAxis dataKey="tenor" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${v.toFixed(1)}%`} />
              <Tooltip formatter={(v: number) => [`${v.toFixed(3)}%`, "Real Yield"]} />
              <Bar dataKey="yield" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-4 grid grid-cols-3 gap-3">
            {Object.entries(breakevens).map(([tenor, val]) => (
              <KpiCard key={tenor} label={`${tenor} Breakeven`} value={fmt(val)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
