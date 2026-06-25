"use client";

import type { AtlasCountry } from "@/lib/types";
import { fmtNum } from "@/lib/format";

interface Props {
  countries: AtlasCountry[];
  year: number;
  unit: string;
  region: string;
  members: Set<string>;
}

export function AtlasKPIs({ countries, year, unit, region, members }: Props) {
  const yearStr = String(year);

  const visible = countries.filter(
    (c) => region === "World" || members.has(c.iso3)
  );

  const reporting = visible.filter(
    (c) => c.values[yearStr] !== null && c.values[yearStr] !== undefined
  );

  const values = reporting.map((c) => c.values[yearStr] as number);
  const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

  let highest: AtlasCountry | null = null;
  let lowest: AtlasCountry | null = null;
  for (const c of reporting) {
    const v = c.values[yearStr] as number;
    if (highest === null || v > (highest.values[yearStr] as number)) highest = c;
    if (lowest === null || v < (lowest.values[yearStr] as number)) lowest = c;
  }

  const kpis = [
    {
      label: "Global Mean",
      value: avg !== null ? `${fmtNum(avg)} ${unit}` : "—",
      sub: `${reporting.length} countries`,
    },
    {
      label: "Highest",
      value: highest ? `${fmtNum(highest.values[yearStr] as number)} ${unit}` : "—",
      sub: highest?.name ?? "—",
      color: "text-success",
    },
    {
      label: "Lowest",
      value: lowest ? `${fmtNum(lowest.values[yearStr] as number)} ${unit}` : "—",
      sub: lowest?.name ?? "—",
      color: "text-danger",
    },
    {
      label: "Reporting",
      value: String(reporting.length),
      sub: `of ${visible.length} countries`,
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {kpis.map((k) => (
        <div key={k.label} className="rounded-xl bg-surface border border-border p-4 shadow-sm">
          <div className="text-xs text-text-muted mb-1">{k.label}</div>
          <div className={`text-lg font-mono font-bold ${k.color ?? "text-text-primary"}`}>{k.value}</div>
          <div className="text-xs text-text-secondary mt-0.5">{k.sub}</div>
        </div>
      ))}
    </div>
  );
}
