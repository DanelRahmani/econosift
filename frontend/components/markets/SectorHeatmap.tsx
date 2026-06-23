"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SectorsResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { fmtPct } from "@/lib/format";

const PERIODS = ["1mo", "3mo", "6mo", "1y"];

// Map a percent change to a red→green background. Clamped at ±8% for saturation.
function heatColor(pct: number | null): string {
  if (pct === null) return "rgba(120,120,120,0.15)";
  const clamp = Math.max(-8, Math.min(8, pct)) / 8; // -1..1
  if (clamp >= 0) return `rgba(22,163,74,${0.12 + clamp * 0.45})`;
  return `rgba(196,57,74,${0.12 + Math.abs(clamp) * 0.45})`;
}

export function SectorHeatmap() {
  const [period, setPeriod] = useState("1mo");
  const [data, setData] = useState<SectorsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.sectors(period)
      .then((r) => active && setData(r))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [period]);

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-sm font-semibold text-text-secondary">S&amp;P 500 Sector Performance</h2>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
                period === p ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"
              }`}
            >{p}</button>
          ))}
        </div>
      </div>
      {loading && !data ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {data?.sectors.map((s) => (
            <div
              key={s.ticker}
              className="rounded-lg p-3 border border-border/60 flex flex-col justify-between min-h-[84px]"
              style={{ backgroundColor: heatColor(s.changePercent) }}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text-primary">{s.sector}</span>
                <span className="font-mono text-xs text-text-muted">{s.ticker}</span>
              </div>
              <div className={`text-lg font-mono font-semibold ${
                (s.changePercent ?? 0) >= 0 ? "text-success" : "text-danger"
              }`}>
                {s.changePercent !== null && s.changePercent >= 0 ? "+" : ""}{fmtPct(s.changePercent)}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
