"use client";

import { Card } from "@/components/ui";
import type { ExtendedRiskTicker } from "@/lib/types";
import { fmtNum, fmtPct, exportToCsv } from "@/lib/format";

interface Props {
  tickers: ExtendedRiskTicker[];
}

function pct(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return fmtPct(v * 100);
}

function ratioColor(v: number | null, good: (n: number) => boolean) {
  if (v === null) return "";
  return good(v) ? "text-success" : "text-danger";
}

export function ExtendedRiskTable({ tickers }: Props) {
  if (!tickers.length) return <div className="text-text-muted text-sm">No extended data.</div>;

  function handleExport() {
    const rows = tickers.map((t) => ({
      Ticker: t.ticker,
      Benchmark: t.benchmark,
      "Ann. Return": pct(t.annReturn),
      "Ann. Volatility": pct(t.annVolatility),
      "Max Drawdown": pct(t.maxDrawdown),
      "Calmar Ratio": fmtNum(t.calmar),
      "Omega Ratio": fmtNum(t.omega),
      Beta: fmtNum(t.beta),
      "Jensen Alpha": pct(t.alpha),
      "Treynor Ratio": fmtNum(t.treynor),
      "R-Squared": fmtNum(t.rSquared),
      "VaR 95% (Hist.)": pct(t.var95Historical),
      "VaR 99% (Hist.)": pct(t.var99Historical),
      "CVaR 95%": pct(t.cvar95),
      "CVaR 99%": pct(t.cvar99),
    }));
    exportToCsv("extended-risk", rows);
  }

  const multi = tickers.length > 1;

  return (
    <div className="space-y-4">
      {/* CAPM Decomposition */}
      {tickers.map((t) => {
        const sysVar = t.systematicVar;
        const idioVar = t.idiosyncraticVar;
        const total = (sysVar ?? 0) + (idioVar ?? 0);
        const sysPct = total > 0 && sysVar !== null ? (sysVar / total) * 100 : null;
        const idioPct = total > 0 && idioVar !== null ? (idioVar / total) * 100 : null;

        return (
          <Card key={t.ticker} className="p-4" data-prov={`tickers.${t.ticker}.systematicVar`} data-prov-ctx={t.ticker}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">
                {multi ? `${t.ticker} — ` : ""}CAPM Variance Decomposition
              </h3>
              {t.rSquared !== null && (
                <span data-prov={`tickers.${t.ticker}.rSquared`} className="text-xs text-text-muted">R² = {fmtNum(t.rSquared)}</span>
              )}
            </div>
            {sysPct !== null && idioPct !== null ? (
              <div>
                <div className="flex rounded-full overflow-hidden h-3 mb-2">
                  <div className="bg-accent" style={{ width: `${sysPct}%` }} title={`Systematic ${sysPct.toFixed(1)}%`} />
                  <div className="bg-surface-alt" style={{ width: `${idioPct}%` }} title={`Idiosyncratic ${idioPct.toFixed(1)}%`} />
                </div>
                <div className="flex gap-4 text-xs text-text-muted">
                  <span><span className="inline-block w-2 h-2 rounded-full bg-accent mr-1" />Systematic {sysPct.toFixed(1)}%</span>
                  <span><span className="inline-block w-2 h-2 rounded-full bg-surface-alt border border-border mr-1" />Idiosyncratic {idioPct.toFixed(1)}%</span>
                </div>
              </div>
            ) : (
              <div className="text-text-muted text-xs">Decomposition unavailable</div>
            )}
          </Card>
        );
      })}

      {/* Metrics table */}
      <Card className="p-4">
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
                {multi && <th className="text-left py-2 px-3 font-medium">Ticker</th>}
                <th className="text-left py-2 px-3 font-medium">Ann. Return</th>
                <th className="text-left py-2 px-3 font-medium">Ann. Vol</th>
                <th className="text-left py-2 px-3 font-medium">Max DD</th>
                <th className="text-left py-2 px-3 font-medium">Calmar</th>
                <th className="text-left py-2 px-3 font-medium">Omega</th>
                <th className="text-left py-2 px-3 font-medium">Beta</th>
                <th className="text-left py-2 px-3 font-medium">Alpha</th>
                <th className="text-left py-2 px-3 font-medium">Treynor</th>
                <th className="text-left py-2 px-3 font-medium">VaR 99%</th>
                <th className="text-left py-2 px-3 font-medium">CVaR 95%</th>
              </tr>
            </thead>
            <tbody>
              {tickers.map((t) => (
                <tr key={t.ticker} data-prov-ctx={t.ticker} className="border-b border-border/50">
                  {multi && <td className="py-2 px-3 font-mono font-semibold">{t.ticker}</td>}
                  <td data-prov={`tickers.${t.ticker}.annReturn`} className={`py-2 px-3 ${ratioColor(t.annReturn, (v) => v > 0)}`}>{pct(t.annReturn)}</td>
                  <td data-prov={`tickers.${t.ticker}.annVolatility`} className="py-2 px-3">{pct(t.annVolatility)}</td>
                  <td data-prov={`tickers.${t.ticker}.maxDrawdown`} className={`py-2 px-3 ${ratioColor(t.maxDrawdown, (v) => v > -0.1)}`}>{pct(t.maxDrawdown)}</td>
                  <td data-prov={`tickers.${t.ticker}.calmar`} className={`py-2 px-3 ${ratioColor(t.calmar, (v) => v > 1)}`}>{fmtNum(t.calmar)}</td>
                  <td data-prov={`tickers.${t.ticker}.omega`} className={`py-2 px-3 ${ratioColor(t.omega, (v) => v > 1)}`}>{fmtNum(t.omega)}</td>
                  <td data-prov={`tickers.${t.ticker}.beta`} className="py-2 px-3">{fmtNum(t.beta)}</td>
                  <td data-prov={`tickers.${t.ticker}.alpha`} className={`py-2 px-3 ${ratioColor(t.alpha, (v) => v > 0)}`}>{pct(t.alpha)}</td>
                  <td data-prov={`tickers.${t.ticker}.treynor`} className={`py-2 px-3 ${ratioColor(t.treynor, (v) => v > 0)}`}>{fmtNum(t.treynor)}</td>
                  <td data-prov={`tickers.${t.ticker}.var99Historical`} className="py-2 px-3 text-danger">{pct(t.var99Historical)}</td>
                  <td data-prov={`tickers.${t.ticker}.cvar95`} className="py-2 px-3 text-danger">{pct(t.cvar95)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
