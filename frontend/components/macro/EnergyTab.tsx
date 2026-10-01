"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EnergyData } from "@/lib/types";
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

export function EnergyTab() {
  const [data, setData] = useState<EnergyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    api.macroEnergy().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
    ))}</div>;
  }

  if (error || !data) {
    return <div className="text-text-secondary text-sm py-8 text-center">
      Energy data unavailable — World Bank data may be temporarily inaccessible.
    </div>;
  }

  const { summary, countries } = data;

  return (
    <div className="space-y-6" {...scope}>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard prov="summary" label="Avg CO₂/capita" value={summary.avgCo2PerCapita} unit=" t"
          sig={summary.avgCo2PerCapita != null && summary.avgCo2PerCapita < 5 ? "green" : summary.avgCo2PerCapita != null && summary.avgCo2PerCapita < 10 ? "yellow" : "red"}
          sub={`${summary.totalCountries} countries`} />
        <KpiCard prov="summary" label="Avg Renewable" value={summary.avgRenewableShare}
          sig={summary.avgRenewableShare != null && summary.avgRenewableShare > 30 ? "green" : summary.avgRenewableShare != null && summary.avgRenewableShare > 15 ? "yellow" : "red"} />
        <KpiCard prov="summary" label="High CO₂ (>10t)" value={summary.highCo2Count} unit=""
          sig={summary.highCo2Count > 3 ? "red" : "yellow"} sub="Countries" />
        <KpiCard label="Source" value={null} unit="" sub={data.source} />
      </div>

      {/* CO2 per capita */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.co2PerCapita" data-prov-ctx="CO2 emissions per capita">
          <h3 className="font-semibold mb-1">CO₂ Emissions per Capita (t CO₂e, excl. land use)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;5t · Yellow 5–10t · Red &gt;10t
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.co2PerCapita != null).map((c) => ({ name: c.name, value: c.kpis.co2PerCapita, sig: c.kpis.co2Signal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}t`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)} t`, "CO₂/capita"]} />
              <ReferenceLine x={5} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={10} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.co2PerCapita != null).map((c) => {
                  const color = c.kpis.co2Signal === "red" ? "#ef4444" : c.kpis.co2Signal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Renewable Energy Share */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.renewableShare" data-prov-ctx="Renewable energy share">
          <h3 className="font-semibold mb-1">Renewable Energy Share (% of total final energy consumption)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &gt;30% · Yellow 15–30% · Red &lt;15%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.renewableShare != null).map((c) => ({ name: c.name, value: c.kpis.renewableShare, sig: c.kpis.renewableSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Renewable"]} />
              <ReferenceLine x={30} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={15} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.renewableShare != null).map((c) => {
                  const color = c.kpis.renewableSignal === "red" ? "#ef4444" : c.kpis.renewableSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Energy Imports */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.energyImports" data-prov-ctx="Energy imports">
          <h3 className="font-semibold mb-1">Energy Imports (% of energy use)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;20% · Yellow 20–50% · Red &gt;50%. Negative = net exporter.
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.energyImports != null).map((c) => ({ name: c.name, value: c.kpis.energyImports, sig: c.kpis.energyImportsSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Energy Imports"]} />
              <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" />
              <ReferenceLine x={20} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={50} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.energyImports != null).map((c) => {
                  const color = c.kpis.energyImportsSignal === "red" ? "#ef4444" : c.kpis.energyImportsSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Fossil Fuel Rents */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.fossilRentsTotal" data-prov-ctx="Fossil fuel rents">
          <h3 className="font-semibold mb-1">Fossil Fuel Rents (% of GDP) — Oil + Gas + Coal</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;2% · Yellow 2–10% · Red &gt;10%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter((c) => c.kpis.fossilRentsTotal != null).map((c) => ({ name: c.name, value: c.kpis.fossilRentsTotal, sig: c.kpis.fossilRentsSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Fossil Rents"]} />
              <ReferenceLine x={2} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={10} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter((c) => c.kpis.fossilRentsTotal != null).map((c) => {
                  const color = c.kpis.fossilRentsSignal === "red" ? "#ef4444" : c.kpis.fossilRentsSignal === "yellow" ? "#f59e0b" : "#10b981";
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
