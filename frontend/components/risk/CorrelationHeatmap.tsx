"use client";

import { useState } from "react";
import { Card } from "@/components/ui";
import type { CorrelationResponse } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  data: CorrelationResponse | null;
  loading?: boolean;
}

function corrColor(v: number | null): string {
  if (v === null) return "bg-surface-alt";
  if (v >= 0.8) return "bg-red-600/80 text-white";
  if (v >= 0.6) return "bg-red-400/60 text-white";
  if (v >= 0.4) return "bg-orange-300/60 text-text-primary";
  if (v >= 0.2) return "bg-yellow-200/60 text-text-primary";
  if (v >= -0.2) return "bg-surface-alt text-text-secondary";
  if (v >= -0.4) return "bg-blue-200/60 text-text-primary";
  if (v >= -0.6) return "bg-blue-400/60 text-white";
  return "bg-blue-600/80 text-white";
}

export function CorrelationHeatmap({ data, loading }: Props) {
  const [snapshotIdx, setSnapshotIdx] = useState<number | null>(null);
  const scope = useSourceScope(provOf(data));

  if (loading) {
    return (
      <Card className="p-4">
        <div className="h-48 flex items-center justify-center text-text-muted text-sm">
          Loading correlation data…
        </div>
      </Card>
    );
  }
  if (!data || !data.snapshots.length) {
    return (
      <Card className="p-4">
        <div className="text-text-muted text-sm">
          Add at least 2 tickers to see correlation analysis.
        </div>
      </Card>
    );
  }

  const tickers = data.tickers;
  const idx = snapshotIdx ?? data.snapshots.length - 1;
  const snapshot = data.snapshots[idx];

  return (
    <Card className="p-4 space-y-4" {...scope}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Rolling Pairwise Correlation</h3>
        <span className="text-xs text-text-muted">as of {snapshot.date}</span>
      </div>

      {/* Period scrubber */}
      {data.snapshots.length > 1 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">{data.snapshots[0].date}</span>
          <input
            type="range"
            min={0}
            max={data.snapshots.length - 1}
            value={idx}
            onChange={(e) => setSnapshotIdx(Number(e.target.value))}
            className="flex-1 h-1 accent-accent"
          />
          <span className="text-xs text-text-muted">{data.snapshots[data.snapshots.length - 1].date}</span>
        </div>
      )}

      {/* Heatmap grid */}
      <div className="overflow-x-auto">
        <table className="text-xs border-collapse">
          <thead>
            <tr>
              <th className="w-16" />
              {tickers.map((t) => (
                <th key={t} className="px-2 py-1 font-mono font-semibold text-text-secondary">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickers.map((row) => (
              <tr key={row}>
                <td className="px-2 py-1 font-mono font-semibold text-text-secondary text-right pr-3">{row}</td>
                {tickers.map((col) => {
                  const v = snapshot.matrix[row]?.[col] ?? null;
                  const isDiag = row === col;
                  return (
                    <td
                      key={col}
                      data-prov-ctx={`${row} × ${col}`}
                      className={`px-3 py-2 text-center rounded-sm ${isDiag ? "bg-accent/20 font-bold" : corrColor(v)}`}
                      title={v !== null ? `${row} × ${col}: ${v.toFixed(3)}` : "—"}
                    >
                      {isDiag ? "1.00" : v !== null ? v.toFixed(2) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2 text-xs text-text-muted">
        <span className="px-2 py-0.5 rounded bg-red-600/80 text-white">≥ 0.8</span>
        <span className="px-2 py-0.5 rounded bg-orange-300/60">0.4–0.8</span>
        <span className="px-2 py-0.5 rounded bg-surface-alt border border-border">-0.2–0.4</span>
        <span className="px-2 py-0.5 rounded bg-blue-400/60 text-white">≤ -0.2</span>
        <span className="ml-2 text-text-muted">Window: {data.window}D</span>
      </div>
    </Card>
  );
}
