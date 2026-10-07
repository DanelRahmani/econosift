"use client";
import type { PolicyDivergenceEntry } from "@/lib/types";

const STANCE_COLORS: Record<string, string> = {
  tightening: "bg-red-500/20 text-red-400",
  easing: "bg-green-500/20 text-green-400",
  on_hold: "bg-yellow-500/20 text-yellow-400",
  unknown: "bg-gray-500/20 text-gray-400",
};

interface Props { entries: PolicyDivergenceEntry[] }

export function PolicyDivergenceTable({ entries }: Props) {
  const fmt = (v: number | null) => v != null ? `${v.toFixed(2)}%` : "N/A";
  const fmtChange = (v: number | null) => {
    if (v == null) return "N/A";
    const sign = v > 0 ? "+" : "";
    return `${sign}${v.toFixed(2)}%`;
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-text-muted text-left">
            <th className="pb-2 pr-4">Central Bank</th>
            <th className="pb-2 pr-4 text-right">Current Rate</th>
            <th className="pb-2 pr-4 text-right">3M Change</th>
            <th className="pb-2 pr-4 text-right">12M Change</th>
            <th className="pb-2">Stance</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.cb} className="border-b border-border/50 hover:bg-surface/50" data-prov={`divergence.${e.cb}`} data-prov-ctx={e.cb}>
              <td className="py-2 pr-4 font-medium">{e.cb}</td>
              <td className="py-2 pr-4 text-right">{fmt(e.current_rate)}</td>
              <td data-prov={`divergence.${e.cb}.change_3m`} className={`py-2 pr-4 text-right ${(e.change_3m ?? 0) >= 0 ? "text-red-400" : "text-green-400"}`}>
                {fmtChange(e.change_3m)}
              </td>
              <td data-prov={`divergence.${e.cb}.change_12m`} className={`py-2 pr-4 text-right ${(e.change_12m ?? 0) >= 0 ? "text-red-400" : "text-green-400"}`}>
                {fmtChange(e.change_12m)}
              </td>
              <td className="py-2" data-prov={`divergence.${e.cb}.stance`}>
                <span className={`px-2 py-0.5 rounded-full text-xs ${STANCE_COLORS[e.stance] ?? STANCE_COLORS.unknown}`}>
                  {e.stance.replace("_", " ")}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
