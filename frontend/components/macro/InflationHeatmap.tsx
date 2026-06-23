"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { MacroResponse, Country } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";

// Map a CPI inflation value to a colour: blue (low/deflation) → red (high).
function heatColor(v: number | null): string {
  if (v === null) return "transparent";
  if (v < 0) return "rgba(8,145,178,0.55)"; // deflation → cyan/blue
  const t = Math.max(0, Math.min(10, v)) / 10; // 0..1 across 0–10%
  // interpolate green(22,163,74) → amber(202,138,4) → red(196,57,74)
  let r: number, g: number, b: number;
  if (t < 0.5) {
    const k = t / 0.5;
    r = 22 + (202 - 22) * k; g = 163 + (138 - 163) * k; b = 74 + (4 - 74) * k;
  } else {
    const k = (t - 0.5) / 0.5;
    r = 202 + (196 - 202) * k; g = 138 + (57 - 138) * k; b = 4 + (74 - 4) * k;
  }
  return `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},0.75)`;
}

const SPAN = 15; // years of history to show

export function InflationHeatmap({ selected, countries }: { selected: string[]; countries: Country[] }) {
  const endYear = new Date().getFullYear();
  const startYear = endYear - SPAN + 1;
  const [data, setData] = useState<MacroResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const key = selected.join(",");

  useEffect(() => {
    if (!selected.length) { setData(null); return; }
    let live = true;
    setLoading(true);
    api.macroData(key, "inflation", startYear, endYear)
      .then((r) => live && setData(r))
      .catch(() => live && setData(null))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const years = useMemo(
    () => Array.from({ length: SPAN }, (_, i) => String(startYear + i)),
    [startYear],
  );

  const nameOf = (iso: string) => countries.find((c) => c.iso2 === iso)?.name ?? iso;

  // country -> year -> value
  const lookup = useMemo(() => {
    const m = new Map<string, Map<string, number>>();
    data?.series.forEach((s) => {
      const ym = new Map<string, number>();
      s.data.forEach((d) => ym.set(d.year, d.value));
      m.set(s.country, ym);
    });
    return m;
  }, [data]);

  return (
    <Card>
      <h2 className="text-sm font-semibold mb-1 text-text-secondary">Inflation Heatmap</h2>
      <p className="text-xs text-text-muted mb-4">
        Annual CPI inflation by country · blue = deflation, green = low, red = high.
      </p>
      {loading && !data ? (
        <Skeleton className="h-48" />
      ) : !data || !data.series.length ? (
        <div className="text-text-muted text-sm">No inflation data for this selection.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="text-xs border-separate" style={{ borderSpacing: "2px" }}>
            <thead>
              <tr>
                <th className="text-left px-2 py-1 text-text-secondary font-medium sticky left-0 bg-surface">Country</th>
                {years.map((y) => (
                  <th key={y} className="px-1 py-1 text-text-muted font-mono font-normal text-center min-w-[40px]">
                    {y.slice(2)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {selected.map((iso) => (
                <tr key={iso}>
                  <td className="px-2 py-1 text-text-primary whitespace-nowrap sticky left-0 bg-surface">{nameOf(iso)}</td>
                  {years.map((y) => {
                    const v = lookup.get(iso)?.get(y) ?? null;
                    return (
                      <td key={y} className="text-center rounded font-mono"
                        style={{ backgroundColor: heatColor(v), color: v !== null ? "#fff" : undefined }}
                        title={v !== null ? `${nameOf(iso)} ${y}: ${v.toFixed(1)}%` : "no data"}>
                        {v !== null ? v.toFixed(1) : "·"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
