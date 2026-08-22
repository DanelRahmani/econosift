"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { TreasuryNoiseData } from "@/lib/types";
import { Card, ChartSkeleton, chartPalette } from "@/components/ui";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

function fmt(v: number | null | undefined, decimals = 2, suffix = ""): string {
  return v != null ? `${v.toFixed(decimals)}${suffix}` : "—";
}

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      <div className="text-xs text-text-secondary mt-0.5">{sub}</div>
    </Card>
  );
}

export function CurveNoiseTab() {
  const [data, setData] = useState<TreasuryNoiseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [full, setFull] = useState(false);
  const pal = chartPalette("dark");

  useEffect(() => {
    api
      .yieldNoise()
      .then(setData)
      .catch(() => setData({ error: "unavailable" }))
      .finally(() => setLoading(false));
  }, []);

  const chart = useMemo(() => {
    const src = full ? data?.history ?? [] : data?.recent ?? [];
    // Thin the daily series so the chart stays responsive over 25 years.
    const step = Math.max(1, Math.floor(src.length / 1200));
    return src.filter((_, i) => i % step === 0).map((p) => ({ date: p.date, value: p.value }));
  }, [data, full]);

  if (loading) return <ChartSkeleton />;

  if (!data || data.error || !data.kpis) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-1">Treasury Curve-Fit Noise</h3>
        <p className="text-sm text-text-secondary">
          {data?.error === "FRED API key required"
            ? "A FRED API key is required for this measure. Add one in Admin → API Keys."
            : "Curve noise data is currently unavailable — the upstream source did not return data."}
        </p>
      </Card>
    );
  }

  const k = data.kpis;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-semibold text-lg">Treasury Curve-Fit Noise</h2>
        <p className="text-xs text-text-secondary mt-1">
          Hu, Pan &amp; Wang (2013) showed that the dispersion of Treasury yields around a
          smooth fitted curve gauges how much arbitrage capital is deployed in fixed income:
          well-capitalised relative-value desks iron the curve out, constrained ones cannot.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi label="Current noise" value={fmt(k.latest, 2, " bps")} sub={k.asOf ? `as of ${k.asOf}` : ""} />
        <Kpi label="20-day average" value={fmt(k.ma20, 2, " bps")} sub="Smooths daily fitting jitter" />
        <Kpi label="Percentile" value={fmt(k.percentile, 0, "%ile")} sub="Rank within history since 2000" />
        <Kpi label="Historical median" value={fmt(k.median, 2, " bps")} sub={`Peak ${fmt(k.max, 1, " bps")}`} />
      </div>

      <Card className="p-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-semibold">Noise (RMSE of Nelson-Siegel fit, bps)</h3>
          <button
            onClick={() => setFull(!full)}
            className={`px-2 py-1 text-xs rounded border transition-colors ${
              full ? "border-accent bg-accent/10 text-accent" : "border-border text-text-muted hover:text-text-primary"
            }`}
          >
            {full ? "Full history" : "Since 2020"}
          </button>
        </div>
        <p className="text-xs text-text-secondary mb-3">
          Higher = the curve is more dislocated relative to a smooth three-factor shape.
        </p>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={chart}>
            <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis tickFormatter={(v) => `${v}`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => [`${v?.toFixed(2)} bps`, "Curve noise"]} />
            {k.median != null && (
              <ReferenceLine y={k.median} stroke={pal.axis} strokeDasharray="4 4" label={{ value: "median", fontSize: 10, fill: pal.axis }} />
            )}
            <Area type="monotone" dataKey="value" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.2} strokeWidth={1.4} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <Card className="p-4 border-warning/40">
        <h4 className="text-sm font-semibold mb-1">Read this before using the level</h4>
        <p className="text-xs text-text-secondary">{data.limitation}</p>
        <p className="text-xs text-text-secondary mt-2">{data.method}</p>
        <p className="text-[11px] text-text-muted mt-2">Source: {data.sources}</p>
      </Card>
    </div>
  );
}
