"use client";

import { useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { Holding, MCData, MCPortfolioPoint } from "@/lib/types";

interface Props {
  holdings: Holding[];
  period: string;
}

// Approximate color gradient: low sharpe = blue, high sharpe = red
function sharpeColor(sharpe: number, minS: number, maxS: number): string {
  const t = maxS > minS ? (sharpe - minS) / (maxS - minS) : 0.5;
  const r = Math.round(t * 239 + (1 - t) * 59);
  const g = Math.round(t * 68 + (1 - t) * 130);
  const b = Math.round(t * 68 + (1 - t) * 246);
  return `rgb(${r},${g},${b})`;
}

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: MCPortfolioPoint & { color?: string };
}

function ColorDot({ cx = 0, cy = 0, payload }: DotProps) {
  return <circle cx={cx} cy={cy} r={2} fill={payload?.color ?? "#6366f1"} fillOpacity={0.5} />;
}

export function MonteCarlo({ holdings, period }: Props) {
  const [data, setData] = useState<MCData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const d = await api.portfolioMonteCarlo(holdings, period);
      if (d.error) {
        setError(d.error);
        setData(null);
      } else {
        setData(d);
      }
    } catch {
      setError("Failed to run Monte Carlo simulation");
    } finally {
      setLoading(false);
    }
  }

  const points = data?.points ?? [];
  const sharpes = points.map((p) => p.sharpe ?? 0);
  const minS = Math.min(...sharpes);
  const maxS = Math.max(...sharpes);

  // Points are already sampled to max 5000 by backend
  const pts = points.map((p) => ({
    ...p,
    x: (p.vol ?? 0) * 100,
    y: (p.ret ?? 0) * 100,
    color: sharpeColor(p.sharpe ?? 0, minS, maxS),
  }));

  const maxSharpePt = data?.maxSharpe
    ? [{ ...data.maxSharpe, x: (data.maxSharpe.vol ?? 0) * 100, y: (data.maxSharpe.ret ?? 0) * 100 }]
    : [];

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Monte Carlo Portfolio Simulation</h3>
        <button
          onClick={run}
          disabled={loading || holdings.length === 0}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Running…" : "🔴 Run Monte Carlo"}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-500">{error}</div>
      )}

      {data && (
        <>
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                type="number"
                dataKey="x"
                name="Volatility"
                tickFormatter={(v) => `${v.toFixed(1)}%`}
                tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
                label={{ value: "Volatility (%)", position: "insideBottom", offset: -4, fontSize: 11, fill: "var(--color-text-muted)" }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name="Return"
                tickFormatter={(v) => `${v.toFixed(1)}%`}
                tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
                width={52}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0]?.payload as { x: number; y: number; sharpe: number | null };
                  return (
                    <div className="bg-surface-alt border border-border rounded-lg p-2 text-xs">
                      <p>Vol: {d.x.toFixed(2)}%</p>
                      <p>Return: {d.y.toFixed(2)}%</p>
                      <p>Sharpe: {d.sharpe?.toFixed(2) ?? "—"}</p>
                    </div>
                  );
                }}
              />
              <Scatter name="Portfolios" data={pts} shape={<ColorDot />} />
              <Scatter name="Max Sharpe" data={maxSharpePt} fill="#f59e0b" r={10} />
            </ScatterChart>
          </ResponsiveContainer>

          <div className="flex items-center gap-3 text-xs text-text-muted flex-wrap">
            <span>Low Sharpe</span>
            <div className="flex h-3 w-24 rounded overflow-hidden">
              {Array.from({ length: 12 }, (_, i) => i / 11).map((t, i) => (
                <div
                  key={i}
                  className="flex-1"
                  style={{ backgroundColor: sharpeColor(t * (maxS - minS) + minS, minS, maxS) }}
                />
              ))}
            </div>
            <span>High Sharpe</span>
            <span className="ml-auto flex items-center gap-1">
              <span className="w-3 h-3 bg-amber-500 rounded-full inline-block" /> Max Sharpe
            </span>
          </div>

          {data.maxSharpe && (
            <div className="bg-surface-alt rounded-lg p-3 text-sm">
              <span className="text-text-muted">Max Sharpe Portfolio: </span>
              <span className="font-medium">
                Vol {((data.maxSharpe.vol ?? 0) * 100).toFixed(2)}%
                · Return {((data.maxSharpe.ret ?? 0) * 100).toFixed(2)}%
                · Sharpe {data.maxSharpe.sharpe?.toFixed(2) ?? "—"}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
