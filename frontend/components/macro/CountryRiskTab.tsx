"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CountryRiskData, TrafficLight } from "@/lib/types";

const KPI_LABELS: Record<string, string> = {
  debt_gdp:        "Debt / GDP",
  current_account: "Curr. Account",
  inflation:       "Inflation",
  fiscal_balance:  "Fiscal Bal.",
  reserves_growth: "Reserves Grwth",
  unemployment:    "Unemployment",
};
const KPI_KEYS = Object.keys(KPI_LABELS);

function trafficBg(sig: TrafficLight): string {
  if (sig === "green")  return "bg-success/20 text-success";
  if (sig === "yellow") return "bg-warning/20 text-warning";
  if (sig === "red")    return "bg-danger/20 text-danger";
  return "bg-surface-alt text-text-muted";
}

function fmt(v: number | null | undefined, key: string): string {
  if (v === null || v === undefined) return "—";
  if (key === "reserves_growth") return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
  return `${v.toFixed(1)}%`;
}

export function CountryRiskTab() {
  const [data, setData] = useState<CountryRiskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.macroCountryRisk()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-16 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Country risk data unavailable.
      </div>
    );
  }

  const sorted = [...data.countries].sort((a, b) => a.name.localeCompare(b.name));

  const filtered = sorted.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.iso3.toLowerCase().includes(search.toLowerCase())
  );

  const averages: Record<string, number | null> = {};
  for (const key of KPI_KEYS) {
    const vals = data.countries
      .map(c => (c.indicators as unknown as Record<string, number | null>)[key])
      .filter((v): v is number => v !== null && v !== undefined);
    averages[key] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }

  return (
    <div className="space-y-6">
      {/* KPI summary strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {KPI_KEYS.map(key => (
          <div key={key} className="card p-3">
            <div className="text-xs text-text-secondary mb-1">{KPI_LABELS[key]}</div>
            <div className="text-lg font-semibold text-text-primary">{fmt(averages[key], key)}</div>
            <div className="text-[10px] text-text-muted mt-1">
              {data.thresholds[key]?.green} = <span className="text-success">good</span>
            </div>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search country…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="input w-full max-w-xs text-sm"
        />
        <span className="text-xs text-text-muted">{filtered.length} countries</span>
      </div>

      {/* Traffic-light table */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-alt">
              <th className="text-left px-3 py-2 text-text-secondary font-medium sticky left-0 bg-surface-alt min-w-[140px]">Country</th>
              {KPI_KEYS.map(key => (
                <th key={key} className="text-center px-2 py-2 text-text-secondary font-medium min-w-[90px]">
                  {KPI_LABELS[key]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, i) => (
              <tr key={c.iso3} className={`border-b border-border ${i % 2 === 0 ? "" : "bg-surface-alt/40"}`}>
                <td className="px-3 py-1.5 sticky left-0 bg-surface font-medium">
                  <span className="text-text-primary">{c.name}</span>
                  <span className="ml-1.5 text-[10px] text-text-muted">{c.iso3}</span>
                </td>
                {KPI_KEYS.map(key => {
                  const val = (c.indicators as unknown as Record<string, number | null>)[key];
                  const sig = (c.signals as Record<string, TrafficLight>)[key];
                  return (
                    <td key={key} className={`text-center px-2 py-1.5 ${trafficBg(sig)}`}>
                      <span className="text-xs font-mono">{fmt(val, key)}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
