"use client";

import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui";
import { chartTooltipStyle, chartPalette } from "@/components/ui";
import { fmtPct, fmtNum } from "@/lib/format";
import { api } from "@/lib/api";
import type { MonteCarloResult } from "@/lib/types";

interface Props {
  ticker: string;
  theme: "light" | "dark";
}

export function MonteCarloPanel({ ticker, theme }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MonteCarloResult | null>(null);
  const [sims, setSims] = useState(10000);
  const [horizon, setHorizon] = useState(1);

  const palette = chartPalette(theme);
  const tooltip = chartTooltipStyle(theme);

  async function runMonteCarlo() {
    setLoading(true);
    try {
      const res = await api.riskMonteCarlo(ticker, "2y", sims, horizon);
      setResult(res);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Monte Carlo VaR</h3>
          <span className="px-1.5 py-0.5 rounded text-xs bg-danger/20 text-danger font-medium">
            Run Analysis
          </span>
        </div>
      </div>

      <p className="text-xs text-text-muted">
        GBM simulation of {ticker}&apos;s 1-day P&L distribution. Parameterised from 2 years of
        historical returns. Each run draws N random paths.
      </p>

      <div className="flex flex-wrap gap-4 text-xs items-center">
        <div className="flex items-center gap-2">
          <span className="text-text-muted">Simulations:</span>
          {[1000, 5000, 10000, 50000].map((n) => (
            <button
              key={n}
              onClick={() => setSims(n)}
              className={`px-2 py-0.5 rounded font-medium transition-colors ${
                sims === n ? "bg-danger text-white" : "bg-surface-alt text-text-secondary hover:text-text-primary"
              }`}
            >
              {n.toLocaleString()}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-text-muted">Horizon:</span>
          {[1, 5, 10].map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={`px-2 py-0.5 rounded font-medium transition-colors ${
                horizon === h ? "bg-danger text-white" : "bg-surface-alt text-text-secondary hover:text-text-primary"
              }`}
            >
              {h}D
            </button>
          ))}
        </div>
        <div className="ml-auto">
          <p className="text-warning text-xs font-medium">
            Compute-intensive — may take up to 30s for 50,000 sims
          </p>
        </div>
      </div>

      <button
        onClick={runMonteCarlo}
        disabled={loading}
        className="w-full py-2 rounded-md text-sm font-medium bg-danger/10 text-danger border border-danger/30 hover:bg-danger hover:text-white transition-colors disabled:opacity-50"
      >
        {loading ? "Running simulation…" : `Run Analysis (${sims.toLocaleString()} paths, ${horizon}D horizon)`}
      </button>

      {result && !result.error && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "VaR 95%", value: fmtPct((result.var95 ?? 0) * 100), danger: true },
              { label: "VaR 99%", value: fmtPct((result.var99 ?? 0) * 100), danger: true },
              { label: "Expected", value: fmtPct((result.expected ?? 0) * 100), danger: false },
              { label: "Worst Case", value: fmtPct((result.worstCase ?? 0) * 100), danger: true },
            ].map(({ label, value, danger }) => (
              <div key={label}>
                <div className="text-xs text-text-muted">{label}</div>
                <div className={`text-lg font-bold tabular-nums ${danger ? "text-danger" : "text-text-primary"}`}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {result.distribution.length > 0 && (
            <div>
              <p className="text-xs text-text-muted mb-1">Return distribution ({result.sims.toLocaleString()} paths)</p>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={result.distribution}
                  margin={{ top: 2, right: 8, left: -20, bottom: 0 }}
                  barCategoryGap="0%"
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} />
                  <XAxis
                    dataKey="bin"
                    tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
                    tick={{ fontSize: 9, fill: palette.axis }}
                    interval={Math.floor(result.distribution.length / 8)}
                  />
                  <YAxis tick={{ fontSize: 9, fill: palette.axis }} />
                  <Tooltip
                    {...tooltip}
                    formatter={(v: number, _: string, props: { payload?: { bin: number } }) => [
                      v,
                      `Return ≈ ${((props.payload?.bin ?? 0) * 100).toFixed(2)}%`,
                    ]}
                  />
                  {result.var95 !== null && (
                    <ReferenceLine x={result.var95} stroke="#c4394a" strokeDasharray="4 2" label={{ value: "VaR95", fill: "#c4394a", fontSize: 9 }} />
                  )}
                  {result.var99 !== null && (
                    <ReferenceLine x={result.var99} stroke="#991b1b" strokeDasharray="4 2" label={{ value: "VaR99", fill: "#991b1b", fontSize: 9 }} />
                  )}
                  <Bar dataKey="count" fill="#c4394a" opacity={0.7} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
      {result?.error && <div className="text-xs text-danger">{result.error}</div>}
    </Card>
  );
}
