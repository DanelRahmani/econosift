"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BankingStabilityData } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { shortCountryName } from "@/lib/format";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { useRefreshNonce } from "@/lib/refresh";

const GRID = "rgba(255,255,255,0.08)";

function signalColor(s: string): string {
  if (s === "red") return "text-danger";
  if (s === "yellow") return "text-warning";
  if (s === "green") return "text-success";
  return "text-text-muted";
}

export function BankingStabilityPanel() {
  const [data, setData] = useState<BankingStabilityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api.stabilityBanking().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, [refreshNonce]);

  if (loading) return <div className="py-8 text-center text-muted">Loading banking stability data…</div>;
  if (error || !data) return <div className="py-8 text-center text-red-400">Failed to load data.</div>;

  const { summary, countries, source } = data;

  return (
    <div className="space-y-6" {...scope}>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Red Alerts</div>
          <div className="text-2xl font-bold text-danger">{summary.redCount}</div>
        </Card>
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Yellow Warnings</div>
          <div className="text-2xl font-bold text-warning">{summary.yellowCount}</div>
        </Card>
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Green / Stable</div>
          <div className="text-2xl font-bold text-success">{summary.greenCount}</div>
        </Card>
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Countries</div>
          <div className="text-2xl font-bold">{summary.totalCountries}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Source</div>
          <div className="text-sm mt-1">{source}</div>
        </Card>
      </div>

      {/* NPL Ratio Bar Chart */}
      {countries.length > 0 && (
        <Card className="p-4" data-prov={`countries.${countries[0].iso2}.kpis.nplRatio`} data-prov-ctx="Bank NPL ratio, all countries (source shown for the first country; period varies)">
          <h3 className="font-semibold mb-1">Bank Non-Performing Loans (% of total)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Green &lt;5% · Yellow 5–10% · Red &gt;10%
          </p>
          <ResponsiveContainer width="100%" height={Math.max(300, countries.length * 24)}>
            <BarChart
              data={countries.filter(c => c.kpis.nplRatio != null).map(c => ({
                name: c.name, value: c.kpis.nplRatio ?? 0,
                color: (c.kpis.nplRatio ?? 0) > 10 ? "#ef4444" : (c.kpis.nplRatio ?? 0) > 5 ? "#f59e0b" : "#10b981",
              }))}
              layout="vertical" margin={{ left: 100, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={95} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "NPL Ratio"]} />
              <ReferenceLine x={5} stroke="#10b981" strokeDasharray="4 4" />
              <ReferenceLine x={10} stroke="#ef4444" strokeDasharray="4 4" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {(countries.filter(c => c.kpis.nplRatio != null).map((c) => (
                  <Cell key={c.iso2} fill={(c.kpis.nplRatio ?? 0) > 10 ? "#ef4444" : (c.kpis.nplRatio ?? 0) > 5 ? "#f59e0b" : "#10b981"} fillOpacity={0.8} />
                )) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Capital Adequacy + Z-Score Grid */}
      <div className="grid md:grid-cols-2 gap-4">
        {countries.length > 0 && (
          <Card className="p-4" data-prov={`countries.${countries[0].iso2}.kpis.capitalAdequacy`} data-prov-ctx="Bank capital to assets, all countries (source shown for the first country; period varies)">
            <h3 className="font-semibold mb-1">Bank Capital to Assets Ratio (%)</h3>
            <p className="text-xs text-text-secondary mb-3">Green &gt;8% · Yellow 6–8% · Red &lt;6%</p>
            <ResponsiveContainer width="100%" height={Math.max(280, countries.length * 22)}>
              <BarChart
                data={countries.filter(c => c.kpis.capitalAdequacy != null).map(c => ({
                  name: c.name, value: c.kpis.capitalAdequacy ?? 0,
                }))}
                layout="vertical" margin={{ left: 100, right: 40 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10 }} />
                <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 10 }} width={95} tickFormatter={shortCountryName} />
                <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Capital/Assets"]} />
                <ReferenceLine x={8} stroke="#10b981" strokeDasharray="4 4" />
                <ReferenceLine x={6} stroke="#f59e0b" strokeDasharray="4 4" />
                <Bar dataKey="value" fill="#3b82f6" radius={[0, 3, 3, 0]} fillOpacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}

        {countries.length > 0 && (
          <Card className="p-4" data-prov={`countries.${countries[0].iso2}.kpis.bankZscore`} data-prov-ctx="Bank Z-score, all countries (source shown for the first country; period varies)">
            <h3 className="font-semibold mb-1">Bank Z-Score (higher = more stable)</h3>
            <p className="text-xs text-text-secondary mb-3">
              Green &gt;20 · Yellow 10–20 · Red &lt;10
              {data.zscoreYear != null && ` · latest published: ${data.zscoreYear} (World Bank GFDD)`}
            </p>
            <ResponsiveContainer width="100%" height={Math.max(280, countries.length * 22)}>
              <BarChart
                data={countries.filter(c => c.kpis.bankZscore != null).map(c => ({
                  name: c.name, value: c.kpis.bankZscore ?? 0,
                }))}
                layout="vertical" margin={{ left: 100, right: 40 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis type="number" tickFormatter={(v) => `${v}`} tick={{ fontSize: 10 }} />
                <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 10 }} width={95} tickFormatter={shortCountryName} />
                <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}`, "Z-Score"]} />
                <ReferenceLine x={20} stroke="#10b981" strokeDasharray="4 4" />
                <ReferenceLine x={10} stroke="#f59e0b" strokeDasharray="4 4" />
                <Bar dataKey="value" fill="#8b5cf6" radius={[0, 3, 3, 0]} fillOpacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}
      </div>

      {/* Credit Gap Alerts */}
      {countries.filter(c => c.kpis.creditGap != null && c.kpis.creditGap > 2).length > 0 && (
        <Card className="p-4 border-warning/30 bg-warning/5">
          <h3 className="font-semibold mb-1 text-warning">⚠ Elevated BIS Credit-to-GDP Gaps</h3>
          <p className="text-xs text-text-secondary mb-3">
            Gaps &gt;10pp signal elevated systemic risk (BIS methodology). Showing countries with gap &gt;2pp.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
            {countries.filter(c => c.kpis.creditGap != null && c.kpis.creditGap > 2)
              .sort((a, b) => (b.kpis.creditGap || 0) - (a.kpis.creditGap || 0))
              .map(c => (
                <div key={c.iso2} data-prov={`countries.${c.iso2}.kpis.creditGap`} data-prov-ctx={c.name} className={c.kpis.creditGap != null && c.kpis.creditGap > 10 ? "text-danger" : "text-warning"}>
                  <span className="font-medium">{c.name}</span>
                  <span className="text-xs ml-1">{c.kpis.creditGap?.toFixed(1)}pp</span>
                </div>
              ))}
          </div>
        </Card>
      )}
    </div>
  );
}
