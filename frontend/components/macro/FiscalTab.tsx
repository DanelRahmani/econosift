"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FiscalData } from "@/lib/types";
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

function KpiCard({ label, value, unit = "%", sub, sig }: {
  label: string; value: number | null; unit?: string; sub?: string; sig?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${sig ? signalColor(sig) : ""}`}>
        {value != null ? `${value > 0 ? "+" : ""}${value.toFixed(1)}${unit}` : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function FiscalTab() {
  const [data, setData] = useState<FiscalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.macroFiscal().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
    ))}</div>;
  }

  if (error || !data) {
    return <div className="text-text-secondary text-sm py-8 text-center">
      Fiscal data unavailable — World Bank data may be temporarily inaccessible.
    </div>;
  }

  const { summary, countries } = data;

  return (
    <div className="space-y-6">
      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard label="Avg Debt/GDP" value={summary.avgDebtGdp}
          sig={summary.avgDebtGdp != null && summary.avgDebtGdp > 90 ? "red" : summary.avgDebtGdp != null && summary.avgDebtGdp > 60 ? "yellow" : "green"}
          sub={`${summary.totalCountries} countries`} />
        <KpiCard label="Avg Fiscal Balance" value={summary.avgFiscalBalance}
          sig={summary.avgFiscalBalance != null && summary.avgFiscalBalance < -3 ? "red" : summary.avgFiscalBalance != null && summary.avgFiscalBalance < 0 ? "yellow" : "green"} />
        <KpiCard label="Adverse r-g Dynamics" value={summary.adverseDynamicsCount} unit=""
          sig={summary.adverseDynamicsCount > 3 ? "red" : summary.adverseDynamicsCount > 0 ? "yellow" : "green"}
          sub="Debt &gt;90% &amp; growth &lt;2%" />
        <KpiCard label="Source" value={null} unit="" sub={data.source} />
      </div>

      {/* Debt-to-GDP Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Government Debt (% of GDP)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;60% · Yellow 60–90% · Red &gt;90%
          </p>
          <ResponsiveContainer width="100%" height={380}>
            <BarChart
              data={countries.map((c) => ({ name: c.name, value: c.kpis.debtGdp ?? 0, sig: c.kpis.debtGdpSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Debt/GDP"]} />
              <ReferenceLine x={60} stroke="#f59e0b" strokeDasharray="4 4" />
              <ReferenceLine x={90} stroke="#ef4444" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.map((c) => {
                  const color = c.kpis.debtGdpSignal === "red" ? "#ef4444" : c.kpis.debtGdpSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Fiscal Balance Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Fiscal Balance (% of GDP)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &gt;-3% · Yellow -3% to -6% · Red &lt;-6%. Positive = surplus.
          </p>
          <ResponsiveContainer width="100%" height={380}>
            <BarChart
              data={countries.map((c) => ({ name: c.name, value: c.kpis.fiscalBalance ?? 0, sig: c.kpis.fiscalBalanceSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Fiscal Balance"]} />
              <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" />
              <ReferenceLine x={-3} stroke="#f59e0b" strokeDasharray="4 4" label="Maastricht" />
              <ReferenceLine x={-6} stroke="#ef4444" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.map((c) => {
                  const color = c.kpis.fiscalBalanceSignal === "red" ? "#ef4444" : c.kpis.fiscalBalanceSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Tax Revenue Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Tax Revenue (% of GDP)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &gt;25% · Yellow 15–25% · Red &lt;15%
          </p>
          <ResponsiveContainer width="100%" height={380}>
            <BarChart
              data={countries.map((c) => ({ name: c.name, value: c.kpis.taxRevenue ?? 0, sig: c.kpis.taxRevenueSignal }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Tax Revenue"]} />
              <ReferenceLine x={15} stroke="#f59e0b" strokeDasharray="4 4" />
              <ReferenceLine x={25} stroke="#10b981" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.map((c) => {
                  const color = c.kpis.taxRevenueSignal === "red" ? "#ef4444" : c.kpis.taxRevenueSignal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Adverse Dynamics Warning */}
      {countries.filter(c => c.kpis.adverseDynamics).length > 0 && (
        <Card className="p-4 border-danger/30 bg-danger/5">
          <h3 className="font-semibold mb-1 text-danger">⚠ Adverse Debt Dynamics</h3>
          <p className="text-xs text-text-secondary mb-3">
            Countries with debt &gt;90% GDP AND growth &lt;2% — debt ratio likely to rise even without new borrowing.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {countries.filter(c => c.kpis.adverseDynamics).map((c) => (
              <div key={c.iso2} className="text-sm">
                <span className="text-text-primary">{c.name}</span>
                <span className="text-text-secondary text-xs ml-1">
                  Debt: {c.kpis.debtGdp?.toFixed(0)}% · Growth: {c.kpis.gdpGrowth?.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
