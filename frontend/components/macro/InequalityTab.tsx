"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { InequalityData } from "@/lib/types";
import { Card } from "@/components/ui";
import { shortCountryName } from "@/lib/format";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function signalColor(s: string): string {
  if (s === "red") return "text-danger";
  if (s === "yellow") return "text-warning";
  if (s === "green") return "text-success";
  return "text-text-muted";
}

function KpiCard({ label, value, unit = "", sub, sig }: {
  label: string; value: number | null; unit?: string; sub?: string; sig?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${sig ? signalColor(sig) : ""}`}>
        {value != null ? `${value.toFixed(1)}${unit}` : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function InequalityTab() {
  const [data, setData] = useState<InequalityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.macroInequality().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
    ))}</div>;
  }

  if (error || !data) {
    return <div className="text-text-secondary text-sm py-8 text-center">
      Inequality data unavailable — World Bank data may be temporarily inaccessible.
    </div>;
  }

  const { summary, countries } = data;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard label="Avg Gini" value={summary.avgGini}
          sig={summary.avgGini != null && summary.avgGini < 30 ? "green" : summary.avgGini != null && summary.avgGini < 45 ? "yellow" : "red"}
          sub={`${summary.totalCountries} countries`} />
        <KpiCard label="Avg Poverty ($2.15)" value={summary.avgPoverty215} unit="%"
          sig={summary.avgPoverty215 != null && summary.avgPoverty215 < 5 ? "green" : "yellow"} />
        <KpiCard label="High Inequality" value={summary.highGiniCount} unit=""
          sig={summary.highGiniCount > 3 ? "red" : "yellow"} sub="Gini >45" />
        <KpiCard label="Source" value={null} unit="" sub={data.source} />
      </div>

      {/* Gini Coefficient */}
      {countries.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Gini Coefficient (0=perfect equality, 100=perfect inequality)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;30 · Yellow 30–45 · Red &gt;45
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 22)}>
            <BarChart
              data={countries.filter(c => c.kpis.gini != null).map(c => ({
                name: c.name, value: c.kpis.gini ?? 0, sig: c.kpis.giniSignal,
              }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}`, "Gini"]} />
              <ReferenceLine x={30} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={45} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter(c => c.kpis.gini != null).map((c) => {
                  const color = c.kpis.giniSignal === "red" ? "#ef4444" : c.kpis.giniSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Income Share of Top 10% */}
      {countries.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Income Share Held by Top 10% (%)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;25% · Yellow 25–35% · Red &gt;35%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 22)}>
            <BarChart
              data={countries.filter(c => c.kpis.incomeTop10 != null).map(c => ({
                name: c.name, value: c.kpis.incomeTop10 ?? 0, sig: c.kpis.incomeTop10Signal,
              }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Top 10%"]} />
              <ReferenceLine x={25} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={35} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter(c => c.kpis.incomeTop10 != null).map((c) => {
                  const color = c.kpis.incomeTop10Signal === "red" ? "#ef4444" : c.kpis.incomeTop10Signal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Poverty Headcount Ratios */}
      {countries.filter(c => c.kpis.poverty215 != null).length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Poverty Headcount — $2.15/day (intl. poverty line, %)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;5% · Yellow 5–20% · Red &gt;20%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.filter(c => c.kpis.poverty215 != null).length * 22)}>
            <BarChart
              data={countries.filter(c => c.kpis.poverty215 != null).map(c => ({
                name: c.name, value: c.kpis.poverty215 ?? 0, sig: c.kpis.poverty215Signal,
              }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Poverty $2.15"]} />
              <ReferenceLine x={5} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={20} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter(c => c.kpis.poverty215 != null).map((c) => {
                  const color = c.kpis.poverty215Signal === "red" ? "#ef4444" : c.kpis.poverty215Signal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
