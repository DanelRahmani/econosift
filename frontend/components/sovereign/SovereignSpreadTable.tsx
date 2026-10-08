"use client";
import type { SovereignCountry } from "@/lib/types";

const SIGNAL_COLORS = {
  green: "bg-green-500/20 text-green-400",
  yellow: "bg-yellow-500/20 text-yellow-400",
  red: "bg-red-500/20 text-red-400",
};

interface Props { countries: SovereignCountry[] }

export function SovereignSpreadTable({ countries }: Props) {
  const fmt = (v: number | null, d = 2) => v != null ? `${v.toFixed(d)}%` : "N/A";
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-text-muted text-left">
            <th className="pb-2 pr-4">Country</th>
            <th className="pb-2 pr-4 text-right">10Y Yield</th>
            <th className="pb-2 pr-4 text-right">Spread vs US</th>
            <th className="pb-2 pr-4 text-right">Risk Score</th>
            <th className="pb-2">Signal</th>
          </tr>
        </thead>
        <tbody>
          {countries.map((c) => (
            <tr key={c.iso3} className="border-b border-border/50 hover:bg-surface/50" data-prov={`countries.${c.iso3}`} data-prov-ctx={c.name}>
              <td className="py-2 pr-4 font-medium">{c.name}</td>
              <td className="py-2 pr-4 text-right" data-prov={`countries.${c.iso3}.yield_10y`}>{fmt(c.yield_10y)}</td>
              <td data-prov={`countries.${c.iso3}.spread_vs_us`} className={`py-2 pr-4 text-right ${(c.spread_vs_us ?? 0) > 1 ? "text-red-400" : "text-green-400"}`}>
                {fmt(c.spread_vs_us)}
              </td>
              <td className="py-2 pr-4 text-right">{c.composite_score.toFixed(1)}</td>
              <td className="py-2">
                <span className={`px-2 py-0.5 rounded-full text-xs ${SIGNAL_COLORS[c.signal]}`}>
                  {c.signal}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
