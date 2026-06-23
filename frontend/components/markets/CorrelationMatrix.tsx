"use client";

import type { RiskMetric } from "@/lib/types";

function pearson(a: number[], b: number[]): number {
  const n = Math.min(a.length, b.length);
  if (n < 2) return NaN;
  const xa = a.slice(-n);
  const xb = b.slice(-n);
  const ma = xa.reduce((s, v) => s + v, 0) / n;
  const mb = xb.reduce((s, v) => s + v, 0) / n;
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) {
    const x = xa[i] - ma;
    const y = xb[i] - mb;
    num += x * y;
    da += x * x;
    db += y * y;
  }
  const den = Math.sqrt(da * db);
  return den === 0 ? NaN : num / den;
}

function color(c: number): string {
  if (Number.isNaN(c)) return "#252840";
  // red (-1) -> surface (0) -> green (+1)
  if (c >= 0) {
    const g = Math.round(40 + c * (197 - 40));
    return `rgba(34, ${g}, 94, ${0.25 + c * 0.55})`;
  }
  const r = Math.round(40 + -c * (239 - 40));
  return `rgba(${r}, 68, 68, ${0.25 + -c * 0.55})`;
}

export function CorrelationMatrix({ metrics }: { metrics: RiskMetric[] }) {
  const series = metrics
    .map((m) => ({
      ticker: m.ticker,
      returns: (m.returns || []).filter((v): v is number => typeof v === "number"),
    }))
    .filter((s) => s.returns.length > 1);

  if (series.length < 2) {
    return <div className="text-text-muted text-sm">Add 2+ tickers to see correlations.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="text-sm border-collapse">
        <thead>
          <tr>
            <th className="p-2"></th>
            {series.map((s) => (
              <th key={s.ticker} className="p-2 font-mono text-text-secondary">{s.ticker}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {series.map((row) => (
            <tr key={row.ticker}>
              <td className="p-2 font-mono text-text-secondary">{row.ticker}</td>
              {series.map((col) => {
                const c = pearson(row.returns, col.returns);
                return (
                  <td
                    key={col.ticker}
                    className="p-2 text-center font-mono w-16"
                    style={{ backgroundColor: color(c) }}
                  >
                    {Number.isNaN(c) ? "—" : c.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
