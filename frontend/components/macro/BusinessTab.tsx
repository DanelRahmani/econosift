"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BusinessData } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { shortCountryName, categoryBarHeight } from "@/lib/format";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine, LineChart, Line,
} from "recharts";
import { useRefreshNonce } from "@/lib/refresh";

const GRID = "rgba(255,255,255,0.08)";

function signalColor(s: string): string {
  if (s === "red") return "text-danger";
  if (s === "yellow") return "text-warning";
  if (s === "green") return "text-success";
  return "text-text-muted";
}

function KpiCard({ label, value, unit = "", sub, sig, prov }: {
  label: string; value: number | null; unit?: string; sub?: string; sig?: string; prov?: string;
}) {
  return (
    <Card className="p-4" data-prov={prov} data-prov-ctx={label}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${sig && value != null ? signalColor(sig) : ""}`}>
        {value != null
          ? unit === "%" ? `${value.toFixed(2)}${unit}` : `${value.toFixed(1)}${unit}`
          : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function BusinessTab() {
  const [data, setData] = useState<BusinessData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api.macroBusiness().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, [refreshNonce]);

  if (loading) {
    return <div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
    ))}</div>;
  }

  if (error || !data) {
    return <div className="text-text-secondary text-sm py-8 text-center">
      Business dynamism data unavailable — World Bank data may be temporarily inaccessible.
    </div>;
  }

  const { summary, countries } = data;

  return (
    <div className="space-y-6" {...scope}>
      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard prov="summary" label="Avg New Business Density" value={summary.avgBusinessDensity}
          unit=" per 1,000"
          sig={summary.avgBusinessDensity != null && summary.avgBusinessDensity >= 5 ? "green" : summary.avgBusinessDensity != null && summary.avgBusinessDensity >= 2 ? "yellow" : "red"}
          sub={`${summary.totalCountries} countries`} />
        <KpiCard prov="summary" label="Avg Days to Start Business" value={summary.avgStartupDays}
          unit=" days"
          sig={summary.avgStartupDays != null && summary.avgStartupDays < 5 ? "green" : summary.avgStartupDays != null && summary.avgStartupDays < 20 ? "yellow" : "red"}
          sub={summary.avgStartupDays == null ? data.unavailable?.startupTime : undefined} />
        <KpiCard prov="summary" label="Avg Doing Business Score" value={summary.avgDoingBusinessScore}
          unit="/100"
          sig={summary.avgDoingBusinessScore != null && summary.avgDoingBusinessScore >= 75 ? "green" : summary.avgDoingBusinessScore != null && summary.avgDoingBusinessScore >= 60 ? "yellow" : "red"}
          sub="Historical (2015–2019)" />
        <KpiCard label="Source" value={null} unit="" sub={data.source} />
      </div>

      {/* New Business Density Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.newBusinessDensity" data-prov-ctx="New business density">
          <h3 className="font-semibold mb-1">New Business Density (registrations per 1,000 working-age people)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &gt;5 · Yellow 2–5 · Red &lt;2
          </p>
          <ResponsiveContainer width="100%" height={categoryBarHeight(countries.filter((c) => c.kpis.newBusinessDensity != null).length)}>
            <BarChart
              data={countries.filter((c) => c.kpis.newBusinessDensity != null).map((c) => ({ name: c.name, value: c.kpis.newBusinessDensity, sig: c.kpis.newBusinessDensitySignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}`, "Density"]} />
              <ReferenceLine x={2} stroke="#ef4444" strokeDasharray="4 4" />
              <ReferenceLine x={5} stroke="#10b981" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.newBusinessDensity != null).map((c) => {
                  const color = c.kpis.newBusinessDensitySignal === "red" ? "#ef4444" : c.kpis.newBusinessDensitySignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Startup Time Bar Chart */}
      {countries.some((c) => c.kpis.startupTime != null) && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Time to Start a Business (days)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;5 days · Yellow 5–20 days · Red &gt;20 days
          </p>
          <ResponsiveContainer width="100%" height={categoryBarHeight(countries.filter((c) => c.kpis.startupTime != null).length)}>
            <BarChart
              data={countries.filter((c) => c.kpis.startupTime != null).map((c) => ({ name: c.name, value: c.kpis.startupTime, sig: c.kpis.startupTimeSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}d`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)} days`, "Startup Time"]} />
              <ReferenceLine x={5} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={20} stroke="#ef4444" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.startupTime != null).map((c) => {
                  const color = c.kpis.startupTimeSignal === "red" ? "#ef4444" : c.kpis.startupTimeSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Doing Business Score Historical Line Chart */}
      {countries.length > 0 && countries.some(c => c.history.doingBusinessScore.length > 0) && (
        <Card className="p-4" data-prov="history.doingBusinessScore" data-prov-ctx="Doing Business score">
          <h3 className="font-semibold mb-1">Doing Business Score (0–100, 2015–2019)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Historical ease of doing business scores. Discontinued by World Bank in 2021.
          </p>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart margin={{ left: 10, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" type="category" allowDuplicatedCategory={false} tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}`, "Score"]} />
              {countries.filter(c => c.history.doingBusinessScore.length > 0).slice(0, 8).map((c) => (
                <Line
                  key={c.iso2}
                  data={c.history.doingBusinessScore}
                  dataKey="value"
                  name={c.name}
                  stroke={
                    c.iso2 === "US" ? "#3b82f6" :
                    c.iso2 === "CN" ? "#ef4444" :
                    c.iso2 === "IN" ? "#f59e0b" :
                    c.iso2 === "DE" ? "#10b981" :
                    c.iso2 === "JP" ? "#8b5cf6" :
                    c.iso2 === "GB" ? "#ec4899" :
                    c.iso2 === "KR" ? "#06b6d4" :
                    c.iso2 === "BR" ? "#84cc16" : "#6b7280"
                  }
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
