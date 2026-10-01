"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LaborData } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
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

function KpiCard({ label, value, unit = "%", sub, sig, prov }: {
  label: string; value: number | null; unit?: string; sub?: string; sig?: string; prov?: string;
}) {
  return (
    <Card className="p-4" data-prov={prov} data-prov-ctx={label}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${sig && value != null ? signalColor(sig) : ""}`}>
        {value != null ? `${value.toFixed(1)}${unit}` : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function LaborTab() {
  const [data, setData] = useState<LaborData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    api.macroLabor().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
    ))}</div>;
  }

  if (error || !data) {
    return <div className="text-text-secondary text-sm py-8 text-center">
      Labor data unavailable — World Bank data may be temporarily inaccessible.
    </div>;
  }

  const { summary, countries } = data;

  return (
    <div className="space-y-6" {...scope}>
      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard prov="summary" label="Avg LFPR" value={summary.avgLfpr}
          sig={summary.avgLfpr != null && summary.avgLfpr > 65 ? "green" : summary.avgLfpr != null && summary.avgLfpr > 55 ? "yellow" : "red"}
          sub={`${summary.totalCountries} countries`} />
        <KpiCard prov="summary" label="Avg Youth Unemp" value={summary.avgYouthUnemp}
          sig={summary.avgYouthUnemp != null && summary.avgYouthUnemp < 10 ? "green" : summary.avgYouthUnemp != null && summary.avgYouthUnemp < 20 ? "yellow" : "red"} />
        <KpiCard prov="summary" label="High Youth Unemp" value={summary.highYouthUnempCount} unit=""
          sig={summary.highYouthUnempCount > 3 ? "red" : summary.highYouthUnempCount > 0 ? "yellow" : "green"}
          sub="Countries >20%" />
        <KpiCard label="Source" value={null} unit="" sub={data.source} />
      </div>

      {/* Labor Force Participation Rate */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.lfpr" data-prov-ctx="Labor force participation rate">
          <h3 className="font-semibold mb-1">Labor Force Participation Rate (%)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &gt;65% · Yellow 55–65% · Red &lt;55%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.lfpr != null).map((c) => ({ name: c.name, value: c.kpis.lfpr, sig: c.kpis.lfprSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "LFPR"]} />
              <ReferenceLine x={65} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={55} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.lfpr != null).map((c) => {
                  const color = c.kpis.lfprSignal === "red" ? "#ef4444" : c.kpis.lfprSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Youth Unemployment */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.youthUnemp" data-prov-ctx="Youth unemployment rate">
          <h3 className="font-semibold mb-1">Youth Unemployment Rate (ages 15–24, %)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;10% · Yellow 10–20% · Red &gt;20%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.youthUnemp != null).map((c) => ({ name: c.name, value: c.kpis.youthUnemp, sig: c.kpis.youthUnempSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Youth Unemp"]} />
              <ReferenceLine x={10} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={20} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.youthUnemp != null).map((c) => {
                  const color = c.kpis.youthUnempSignal === "red" ? "#ef4444" : c.kpis.youthUnempSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Employment-to-Population Ratio */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.empPopRatio" data-prov-ctx="Employment-to-population ratio">
          <h3 className="font-semibold mb-1">Employment-to-Population Ratio (%)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &gt;60% · Yellow 50–60% · Red &lt;50%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.empPopRatio != null).map((c) => ({ name: c.name, value: c.kpis.empPopRatio, sig: c.kpis.empPopRatioSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Emp/Pop"]} />
              <ReferenceLine x={60} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={50} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.empPopRatio != null).map((c) => {
                  const color = c.kpis.empPopRatioSignal === "red" ? "#ef4444" : c.kpis.empPopRatioSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Vulnerable Employment */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.vulnerableEmp" data-prov-ctx="Vulnerable employment">
          <h3 className="font-semibold mb-1">Vulnerable Employment (% of total employment)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;10% · Yellow 10–30% · Red &gt;30%. Self-employed + unpaid family workers.
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.vulnerableEmp != null).map((c) => ({ name: c.name, value: c.kpis.vulnerableEmp, sig: c.kpis.vulnerableEmpSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Vulnerable Emp"]} />
              <ReferenceLine x={10} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={30} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.vulnerableEmp != null).map((c) => {
                  const color = c.kpis.vulnerableEmpSignal === "red" ? "#ef4444" : c.kpis.vulnerableEmpSignal === "yellow" ? "#f59e0b" : "#10b981";
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
