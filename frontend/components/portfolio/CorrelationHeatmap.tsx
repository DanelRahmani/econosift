"use client";

import { useState } from "react";
import type { CorrelationData } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  data: CorrelationData | null;
  loading: boolean;
}

// -1 = red, 0 = neutral, +1 = green
function corrColor(v: number): string {
  if (v >= 0) {
    return `rgba(22, 163, 74, ${v * 0.7})`;
  } else {
    return `rgba(239, 68, 68, ${Math.abs(v) * 0.7})`;
  }
}

export function CorrelationHeatmap({ data, loading }: Props) {
  const [hover, setHover] = useState<{ r: number; c: number; v: number } | null>(null);
  const scope = useSourceScope(provOf(data));

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 animate-pulse">
        <div className="h-4 w-32 bg-border rounded mb-4" />
        <div className="h-48 bg-surface-alt rounded" />
      </div>
    );
  }

  if (!data || data.tickers.length < 2) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 text-sm text-text-muted">
        Correlation data not available. Requires 2+ holdings.
      </div>
    );
  }

  const { tickers, matrix } = data;

  return (
    <div className="rounded-xl border border-border bg-surface p-4" {...scope}>
      <h3 className="font-semibold text-sm mb-3">Correlation Matrix</h3>
      <div className="overflow-x-auto">
        <table className="border-collapse text-xs">
          <thead>
            <tr>
              <th className="w-12" />
              {tickers.map((t) => (
                <th key={t} className="px-2 py-1 text-center font-mono text-text-secondary w-16">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickers.map((row, ri) => (
              <tr key={row}>
                <td className="pr-2 font-mono text-text-secondary text-right py-1">{row}</td>
                {tickers.map((_, ci) => {
                  const v = matrix[ri]?.[ci] ?? null;
                  const isHovered = hover?.r === ri && hover?.c === ci;
                  return (
                    <td
                      key={ci}
                      data-prov-ctx={`${row} ↔ ${tickers[ci]}`}
                      className="w-16 h-10 text-center rounded cursor-default transition-opacity"
                      style={{
                        backgroundColor: v !== null ? corrColor(v) : undefined,
                        outline: isHovered ? "2px solid rgb(var(--primary))" : undefined,
                      }}
                      onMouseEnter={() => v !== null && setHover({ r: ri, c: ci, v })}
                      onMouseLeave={() => setHover(null)}
                    >
                      <span className="text-text-primary font-medium">
                        {v !== null ? v.toFixed(2) : "—"}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hover !== null && (
        <div className="mt-2 text-xs text-text-muted">
          {tickers[hover.r]} ↔ {tickers[hover.c]}:{" "}
          <span className="font-medium text-text-primary">{hover.v.toFixed(4)}</span>
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-text-muted">
        <span>-1 (red)</span>
        <div className="flex h-3 w-32 rounded overflow-hidden">
          {Array.from({ length: 20 }, (_, i) => (i - 10) / 10).map((v, i) => (
            <div key={i} className="flex-1" style={{ backgroundColor: corrColor(v) }} />
          ))}
        </div>
        <span>+1 (green)</span>
      </div>
    </div>
  );
}
