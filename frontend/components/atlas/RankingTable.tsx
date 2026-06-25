"use client";

import type { AtlasCountry } from "@/lib/types";
import { fmtNum, exportToCsv } from "@/lib/format";

interface Props {
  countries: AtlasCountry[];
  year: number;
  unit: string;
  indicatorLabel: string;
  region: string;
  members: Set<string>;
}

export function RankingTable({ countries, year, unit, indicatorLabel, region, members }: Props) {
  const yearStr = String(year);

  const visible = countries
    .filter((c) => region === "World" || members.has(c.iso3))
    .filter((c) => c.values[yearStr] !== null && c.values[yearStr] !== undefined)
    .map((c) => ({ ...c, value: c.values[yearStr] as number }))
    .sort((a, b) => b.value - a.value);

  const top10 = visible.slice(0, 10);
  const bottom10 = [...visible].reverse().slice(0, 10);

  function handleExport() {
    const rows = visible.map((c, i) => ({
      rank: i + 1,
      country: c.name,
      iso3: c.iso3,
      [`${indicatorLabel} (${unit})`]: c.value,
    }));
    exportToCsv(`atlas_${indicatorLabel}_${year}`, rows);
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm font-semibold text-text-secondary">
          Rankings — {indicatorLabel} ({year})
        </h3>
        <button
          onClick={handleExport}
          className="text-xs text-text-muted hover:text-text-primary border border-border rounded-md px-2 py-1 transition-colors"
        >
          Export CSV
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top 10 */}
        <div>
          <div className="text-xs font-semibold text-success mb-2">Top 10</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted border-b border-border">
                <th className="text-left pb-1 font-normal w-6">#</th>
                <th className="text-left pb-1 font-normal">Country</th>
                <th className="text-right pb-1 font-normal">{unit}</th>
              </tr>
            </thead>
            <tbody>
              {top10.map((c, i) => (
                <tr key={c.iso3} className="border-b border-border/40 hover:bg-surface-alt/40 transition-colors">
                  <td className="py-1.5 pr-2 text-text-muted">{i + 1}</td>
                  <td className="py-1.5 text-text-primary font-medium">{c.name}</td>
                  <td className="py-1.5 text-right font-mono text-success">{fmtNum(c.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Bottom 10 */}
        <div>
          <div className="text-xs font-semibold text-danger mb-2">Bottom 10</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted border-b border-border">
                <th className="text-left pb-1 font-normal w-6">#</th>
                <th className="text-left pb-1 font-normal">Country</th>
                <th className="text-right pb-1 font-normal">{unit}</th>
              </tr>
            </thead>
            <tbody>
              {bottom10.map((c, i) => (
                <tr key={c.iso3} className="border-b border-border/40 hover:bg-surface-alt/40 transition-colors">
                  <td className="py-1.5 pr-2 text-text-muted">{visible.length - i}</td>
                  <td className="py-1.5 text-text-primary font-medium">{c.name}</td>
                  <td className="py-1.5 text-right font-mono text-danger">{fmtNum(c.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
