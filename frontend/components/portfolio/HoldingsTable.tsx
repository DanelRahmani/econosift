"use client";

import type { PortfolioAnalysis } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  data: PortfolioAnalysis;
}

function fmtPct(v: number | null) {
  if (v === null) return "—";
  const pct = v * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

export function HoldingsTable({ data }: Props) {
  const scope = useSourceScope(provOf(data));
  return (
    <div className="rounded-xl border border-border bg-surface p-4" {...scope}>
      <h3 className="font-semibold text-sm mb-3">Holdings Breakdown</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-text-muted text-xs">
              <th className="text-left py-2 pr-4">Ticker</th>
              <th className="text-right py-2 pr-4">Weight</th>
              <th className="text-right py-2 pr-4">Total Return</th>
              <th className="text-right py-2">Contribution</th>
            </tr>
          </thead>
          <tbody>
            {data.holdings.map((h) => {
              const ret = h.totalReturn !== null ? h.totalReturn * 100 : null;
              const contrib = h.contribution !== null ? h.contribution * 100 : null;
              return (
                <tr key={h.ticker} data-prov-ctx={h.ticker} className="border-b border-border/50 hover:bg-surface-alt/50 transition-colors">
                  <td className="py-2 pr-4 font-mono font-medium text-text-primary">{h.ticker}</td>
                  <td data-prov={`holdings.${h.ticker}.weight`} className="py-2 pr-4 text-right text-text-secondary">
                    {h.weight !== null ? `${h.weight.toFixed(1)}%` : "—"}
                  </td>
                  <td data-prov={`holdings.${h.ticker}.totalReturn`} className={`py-2 pr-4 text-right font-medium ${ret !== null && ret >= 0 ? "text-green-500" : "text-red-500"}`}>
                    {fmtPct(h.totalReturn)}
                  </td>
                  <td data-prov={`holdings.${h.ticker}.contribution`} className={`py-2 text-right font-medium ${contrib !== null && contrib >= 0 ? "text-green-500" : "text-red-500"}`}>
                    {fmtPct(h.contribution)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {data.missing.length > 0 && (
        <p className="text-xs text-text-muted mt-2">
          Missing data for: {data.missing.join(", ")}
        </p>
      )}
    </div>
  );
}
