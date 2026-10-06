"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TradeData } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";
import { shortCountryName, categoryBarHeight } from "@/lib/format";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { useRefreshNonce } from "@/lib/refresh";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({ label, value, unit = "%", sub, prov }: {
  label: string; value: number | null; unit?: string; sub?: string; prov?: string;
}) {
  return (
    <Card className="p-4" data-prov={prov}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="text-2xl font-bold mt-1">
        {value != null ? `${value > 0 ? "+" : ""}${value.toFixed(1)}${unit}` : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export default function TradePage() {
  const [data, setData] = useState<TradeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api.macroTrade().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, [refreshNonce]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Trade Flows & Globalization</h1>
          <p className="text-sm text-text-secondary mt-1">International trade metrics for major economies</p>
        </div>
        <PageSkeleton text="Loading trade data…" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-text-primary">Trade Flows & Globalization</h1>
        <p className="text-sm text-text-secondary mt-1">International trade metrics for major economies</p>
        <div className="text-text-secondary text-sm py-8 text-center">
          Trade data unavailable — World Bank data may be temporarily inaccessible.
        </div>
      </div>
    );
  }

  const { summary, countries } = data;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6" {...scope}>
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Trade Flows & Globalization</h1>
        <p className="text-sm text-text-secondary mt-1">
          Exports, imports, and trade balances as % of GDP. Source: {data.source}
          {data.asOf && ` · ${data.asOf}`}
        </p>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard
          prov="summary"
          label="Avg Exports/GDP"
          value={summary.avgExportsGdp}
          sub={`${summary.totalCountries} countries`}
        />
        <KpiCard
          prov="summary"
          label="Avg Imports/GDP"
          value={summary.avgImportsGdp}
        />
        <KpiCard
          prov="summary"
          label="Avg Trade Balance"
          value={summary.avgTradeBalance}
        />
        <KpiCard
          prov="summary"
          label="Top Surplus"
          value={summary.topSurplusValue}
          sub={summary.topSurplusCountry ?? undefined}
        />
      </div>

      {/* Exports % GDP Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.exportsGdp">
          <h3 className="font-semibold mb-1">Exports of Goods & Services (% of GDP)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Higher values indicate more export-oriented economies
          </p>
          <ResponsiveContainer width="100%" height={categoryBarHeight(countries.filter((c) => c.kpis.exportsGdp != null).length)}>
            <BarChart
              data={countries.filter((c) => c.kpis.exportsGdp != null).map((c) => ({ name: c.name, value: c.kpis.exportsGdp }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Exports/GDP"]} />
              <ReferenceLine x={summary.avgExportsGdp ?? 0} stroke="#6366f1" strokeDasharray="4 4" label="Avg" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} fill="#6366f1" fillOpacity={0.8}>
                {countries.map((c) => (
                  <Cell key={c.iso2} fill="#6366f1" fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Imports % GDP Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.importsGdp">
          <h3 className="font-semibold mb-1">Imports of Goods & Services (% of GDP)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Higher values indicate greater reliance on foreign goods and services
          </p>
          <ResponsiveContainer width="100%" height={categoryBarHeight(countries.filter((c) => c.kpis.importsGdp != null).length)}>
            <BarChart
              data={countries.filter((c) => c.kpis.importsGdp != null).map((c) => ({ name: c.name, value: c.kpis.importsGdp }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Imports/GDP"]} />
              <ReferenceLine x={summary.avgImportsGdp ?? 0} stroke="#f59e0b" strokeDasharray="4 4" label="Avg" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} fill="#f59e0b" fillOpacity={0.8}>
                {countries.map((c) => (
                  <Cell key={c.iso2} fill="#f59e0b" fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Trade Balance % GDP Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.tradeBalance">
          <h3 className="font-semibold mb-1">Trade Balance (% of GDP)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green = surplus · Red = deficit. Surplus countries export more than they import.
          </p>
          <ResponsiveContainer width="100%" height={categoryBarHeight(countries.filter((c) => c.kpis.tradeBalance != null).length)}>
            <BarChart
              data={countries.filter((c) => c.kpis.tradeBalance != null).map((c) => ({
                name: c.name,
                value: c.kpis.tradeBalance,
                isSurplus: (c.kpis.tradeBalance ?? 0) >= 0,
              }))}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v > 0 ? "+" : ""}${v?.toFixed(1)}%`, "Trade Balance"]} />
              <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {countries.filter((c) => c.kpis.tradeBalance != null).map((c) => {
                  const isSurplus = (c.kpis.tradeBalance ?? 0) >= 0;
                  return <Cell key={c.iso2} fill={isSurplus ? "#10b981" : "#ef4444"} fillOpacity={0.8} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Trade Openness Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov="kpis.tradeOpenness">
          <h3 className="font-semibold mb-1">Trade Openness (Exports + Imports, % of GDP)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Measures total trade relative to economic size. Higher = more globally integrated.
          </p>
          <ResponsiveContainer width="100%" height={categoryBarHeight(countries.filter((c) => c.kpis.tradeOpenness != null).length)}>
            <BarChart
              data={countries
                .filter((c) => c.kpis.tradeOpenness != null)
                .map((c) => ({ name: c.name, value: c.kpis.tradeOpenness as number }))
                .sort((a, b) => b.value - a.value)}
              layout="vertical" margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Trade Openness"]} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} fill="#8b5cf6" fillOpacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Data table */}
      {countries.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Trade Data Summary</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-secondary border-b border-border">
                  <th className="text-left py-2 px-3">Country</th>
                  <th className="text-right py-2 px-3">Exports/GDP</th>
                  <th className="text-right py-2 px-3">Imports/GDP</th>
                  <th className="text-right py-2 px-3">Balance</th>
                  <th className="text-right py-2 px-3">Openness</th>
                </tr>
              </thead>
              <tbody>
                {countries.map((c) => (
                  <tr key={c.iso2} className="border-b border-border/50 hover:bg-surface-alt/50" data-prov-ctx={c.name}>
                    <td className="py-2 px-3 font-medium">{c.name}</td>
                    <td className="py-2 px-3 text-right" data-prov="kpis.exportsGdp">{c.kpis.exportsGdp != null ? `${c.kpis.exportsGdp.toFixed(1)}%` : "—"}</td>
                    <td className="py-2 px-3 text-right" data-prov="kpis.importsGdp">{c.kpis.importsGdp != null ? `${c.kpis.importsGdp.toFixed(1)}%` : "—"}</td>
                    <td data-prov="kpis.tradeBalance" className={`py-2 px-3 text-right ${(c.kpis.tradeBalance ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                      {c.kpis.tradeBalance != null ? `${c.kpis.tradeBalance > 0 ? "+" : ""}${c.kpis.tradeBalance.toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2 px-3 text-right text-text-secondary" data-prov="kpis.tradeOpenness">
                      {c.kpis.tradeOpenness != null ? `${c.kpis.tradeOpenness.toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
