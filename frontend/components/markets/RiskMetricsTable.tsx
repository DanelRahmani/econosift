"use client";

import type { RiskMetric } from "@/lib/types";
import { fmtNum, fmtPctFromFraction, exportToCsv } from "@/lib/format";

export function RiskMetricsTable({ metrics }: { metrics: RiskMetric[] }) {
  if (!metrics.length) return <div className="text-text-muted text-sm">No risk data.</div>;
  const head = ["Ticker", "Ann. Vol", "VaR 95%", "CVaR 95%", "Sharpe", "Sortino", "Beta"];

  function handleExport() {
    const rows = metrics.map((m) => ({
      Ticker: m.ticker,
      Benchmark: m.benchmark,
      "Ann. Volatility": m.annVolatility != null ? (m.annVolatility * 100).toFixed(2) + "%" : "",
      "VaR 95%": m.var95 != null ? (m.var95 * 100).toFixed(2) + "%" : "",
      "CVaR 95%": m.cvar95 != null ? (m.cvar95 * 100).toFixed(2) + "%" : "",
      Sharpe: m.sharpe?.toFixed(2) ?? "",
      Sortino: m.sortino?.toFixed(2) ?? "",
      Beta: m.beta?.toFixed(2) ?? "",
    }));
    exportToCsv("risk-metrics", rows);
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button
          onClick={handleExport}
          className="px-3 py-1 rounded-md text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
        >
          Export CSV
        </button>
      </div>
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
              <tr key={m.ticker} className="border-b border-border/50" data-prov={`metrics.${m.ticker}`} data-prov-ctx={m.ticker}>
                <td className="py-2 px-3 font-mono">{m.ticker}</td>
                <td className="py-2 px-3" data-prov={`metrics.${m.ticker}.annVolatility`}>{fmtPctFromFraction(m.annVolatility)}</td>
                <td className="py-2 px-3 text-danger" data-prov={`metrics.${m.ticker}.var95`}>{fmtPctFromFraction(m.var95)}</td>
                <td className="py-2 px-3 text-danger" data-prov={`metrics.${m.ticker}.cvar95`}>{fmtPctFromFraction(m.cvar95)}</td>
                <td className="py-2 px-3" data-prov={`metrics.${m.ticker}.sharpe`}>{fmtNum(m.sharpe)}</td>
                <td className="py-2 px-3" data-prov={`metrics.${m.ticker}.sortino`}>{fmtNum(m.sortino)}</td>
                <td className="py-2 px-3" data-prov={`metrics.${m.ticker}.beta`}>{fmtNum(m.beta)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
