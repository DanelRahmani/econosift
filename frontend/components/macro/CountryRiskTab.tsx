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
  if (sig === "green")  return "bg-green-900/40 text-green-300";
  if (sig === "yellow") return "bg-yellow-900/40 text-yellow-300";
  if (sig === "red")    return "bg-red-900/40 text-red-300";
  return "bg-white/5 text-white/40";
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

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-white/40">Loading country risk data…</div>
  );
  if (error || !data) return (
    <div className="flex items-center justify-center h-64 text-red-400">Failed to load country risk data.</div>
  );

  const filtered = data.countries.filter(c =>
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
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {KPI_KEYS.map(key => (
          <div key={key} className="bg-white/5 rounded-lg p-3 border border-white/10">
            <div className="text-xs text-white/50 mb-1">{KPI_LABELS[key]}</div>
            <div className="text-lg font-semibold text-white">{fmt(averages[key], key)}</div>
            <div className="text-[10px] text-white/30 mt-1">
              {data.thresholds[key]?.green} = <span className="text-green-400">good</span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search country…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full max-w-xs bg-white/10 border border-white/20 rounded px-3 py-1.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <span className="text-xs text-white/40">{filtered.length} countries</span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-white/10">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 bg-white/5">
              <th className="text-left px-3 py-2 text-white/60 font-medium sticky left-0 bg-zinc-900 min-w-[140px]">Country</th>
              {KPI_KEYS.map(key => (
                <th key={key} className="text-center px-2 py-2 text-white/60 font-medium min-w-[90px]">
                  {KPI_LABELS[key]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, i) => (
              <tr key={c.iso3} className={`border-b border-white/5 ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                <td className="px-3 py-1.5 sticky left-0 bg-zinc-900 font-medium">
                  <span className="text-white/90">{c.name}</span>
                  <span className="ml-1.5 text-[10px] text-white/30">{c.iso3}</span>
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
