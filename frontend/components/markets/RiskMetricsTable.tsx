"use client";

import type { RiskMetric } from "@/lib/types";
import { fmtNum, fmtPctFromFraction } from "@/lib/format";

export function RiskMetricsTable({ metrics }: { metrics: RiskMetric[] }) {
  if (!metrics.length) return <div className="text-text-muted text-sm">No risk data.</div>;
  const head = ["Ticker", "Ann. Vol", "VaR 95%", "CVaR 95%", "Sharpe", "Sortino", "Beta"];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-text-secondary border-b border-border">
            {head.map((h) => (
              <th key={h} className="text-left py-2 px-3 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.ticker} className="border-b border-border/50">
              <td className="py-2 px-3 font-mono">{m.ticker}</td>
              <td className="py-2 px-3">{fmtPctFromFraction(m.annVolatility)}</td>
              <td className="py-2 px-3 text-danger">{fmtPctFromFraction(m.var95)}</td>
              <td className="py-2 px-3 text-danger">{fmtPctFromFraction(m.cvar95)}</td>
              <td className="py-2 px-3">{fmtNum(m.sharpe)}</td>
              <td className="py-2 px-3">{fmtNum(m.sortino)}</td>
              <td className="py-2 px-3">{fmtNum(m.beta)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
