"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { PortfolioResponse } from "@/lib/types";
import { Card, Skeleton, chartTooltipStyle, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { fmtNum, fmtPctFromFraction } from "@/lib/format";

export function PortfolioTab({ tickers, period }: { tickers: string[]; period: string }) {
  const { theme } = useTheme();
  const pal = chartPalette(theme);

  // Weights keyed by ticker; default to equal weight whenever the basket changes.
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setWeights((prev) => {
      const next: Record<string, number> = {};
      for (const t of tickers) next[t] = prev[t] ?? Math.round((100 / tickers.length));
      return next;
    });
  }, [tickers]);

  const totalWeight = useMemo(
    () => tickers.reduce((s, t) => s + (weights[t] || 0), 0),
    [weights, tickers],
  );

  useEffect(() => {
    if (!tickers.length) { setData(null); return; }
    const holdings = tickers.map((t) => ({ ticker: t, weight: weights[t] || 0 }));
    if (holdings.every((h) => h.weight === 0)) return;
    const id = setTimeout(async () => {
      setLoading(true);
      try {
        setData(await api.portfolio(holdings, period));
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    }, 500);
    return () => clearTimeout(id);
  }, [tickers, weights, period]);

  if (!tickers.length) {
    return <Card><div className="text-text-muted text-sm">Add tickers to build a portfolio.</div></Card>;
  }

  const m = data?.metrics;
  const metricCards: { label: string; value: string; tone?: "pos" | "neg" }[] = m ? [
    { label: "Total Return", value: fmtPctFromFraction(m.totalReturn), tone: (m.totalReturn ?? 0) >= 0 ? "pos" : "neg" },
    { label: "Ann. Return", value: fmtPctFromFraction(m.annReturn), tone: (m.annReturn ?? 0) >= 0 ? "pos" : "neg" },
    { label: "Ann. Volatility", value: fmtPctFromFraction(m.annVolatility) },
    { label: "Sharpe", value: fmtNum(m.sharpe), tone: (m.sharpe ?? 0) >= 0 ? "pos" : "neg" },
    { label: "Sortino", value: fmtNum(m.sortino) },
    { label: "Max Drawdown", value: fmtPctFromFraction(m.maxDrawdown), tone: "neg" },
    { label: "VaR 95% (daily)", value: fmtPctFromFraction(m.var95), tone: "neg" },
    { label: "Beta", value: fmtNum(m.beta) },
  ] : [];

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-text-secondary">Allocation</h2>
          <button
            onClick={() => {
              const eq = Math.round(100 / tickers.length);
              setWeights(Object.fromEntries(tickers.map((t) => [t, eq])));
            }}
            className="px-2.5 py-1 rounded-md text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
          >
            Equal weight
          </button>
        </div>
        <div className="space-y-3">
          {tickers.map((t) => (
            <div key={t} className="flex items-center gap-3">
              <span className="font-mono text-sm w-16">{t}</span>
              <input
                type="range" min={0} max={100} step={1}
                value={weights[t] ?? 0}
                onChange={(e) => setWeights((w) => ({ ...w, [t]: parseInt(e.target.value, 10) }))}
                className="flex-1 accent-accent"
              />
              <span className="font-mono text-sm w-12 text-right">
                {totalWeight ? Math.round(((weights[t] || 0) / totalWeight) * 100) : 0}%
              </span>
            </div>
          ))}
        </div>
        <p className="text-xs text-text-muted mt-3">Weights are normalised automatically.</p>
      </Card>

      {loading && !data ? (
        <Skeleton className="h-40" />
      ) : data ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {metricCards.map((c) => (
              <Card key={c.label}>
                <div className="text-xs text-text-muted mb-1">{c.label}</div>
                <div className={`text-lg font-mono ${
                  c.tone === "pos" ? "text-success" : c.tone === "neg" ? "text-danger" : "text-text-primary"
                }`}>{c.value}</div>
              </Card>
            ))}
          </div>

          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">
              Portfolio Value (base 100) · benchmark {data.benchmark}
            </h2>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.series}>
                  <defs>
                    <linearGradient id="portFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#c4394a" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#c4394a" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 12 }} minTickGap={40} />
                  <YAxis tick={{ fill: pal.axis, fontSize: 12 }} domain={["auto", "auto"]} />
                  <Tooltip {...chartTooltipStyle(theme)} formatter={(v: number) => v?.toFixed(2)} />
                  <Area type="monotone" dataKey="value" stroke="#c4394a" strokeWidth={2} fill="url(#portFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Holdings Contribution</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text-secondary border-b border-border">
                    <th className="text-left py-2 px-3 font-medium">Ticker</th>
                    <th className="text-right py-2 px-3 font-medium">Weight</th>
                    <th className="text-right py-2 px-3 font-medium">Return</th>
                    <th className="text-right py-2 px-3 font-medium">Contribution</th>
                  </tr>
                </thead>
                <tbody>
                  {data.holdings.map((h) => (
                    <tr key={h.ticker} className="border-b border-border/50">
                      <td className="py-2 px-3 font-mono">{h.ticker}</td>
                      <td className="py-2 px-3 text-right font-mono">{fmtPctFromFraction(h.weight)}</td>
                      <td className={`py-2 px-3 text-right font-mono ${(h.totalReturn ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                        {fmtPctFromFraction(h.totalReturn)}
                      </td>
                      <td className={`py-2 px-3 text-right font-mono ${(h.contribution ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                        {fmtPctFromFraction(h.contribution)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.missing.length > 0 && (
              <p className="text-xs text-warning mt-3">No data for: {data.missing.join(", ")}</p>
            )}
          </Card>
        </>
      ) : (
        <Card><div className="text-text-muted text-sm">No portfolio data.</div></Card>
      )}
    </div>
  );
}
