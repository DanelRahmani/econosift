"use client";

import { useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { api } from "@/lib/api";
import type { Holding, FrontierData } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  holdings: Holding[];
  period: string;
}

export function EfficientFrontier({ holdings, period }: Props) {
  const [data, setData] = useState<FrontierData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  async function run() {
    if (holdings.length > 20) {
      setError("Efficient frontier requires 20 or fewer holdings.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const d = await api.portfolioFrontier(holdings, period);
      if (d.error) {
        setError(d.error);
        setData(null);
      } else {
        setData(d);
      }
    } catch {
      setError("Failed to compute efficient frontier");
    } finally {
      setLoading(false);
    }
  }

  const frontierPts = (data?.frontier ?? []).map((p) => ({
    x: (p.vol ?? 0) * 100,
    y: (p.ret ?? 0) * 100,
    sharpe: p.sharpe,
  }));

  const currentPt = data?.currentPortfolio
    ? [{ x: (data.currentPortfolio.vol ?? 0) * 100, y: (data.currentPortfolio.ret ?? 0) * 100, sharpe: data.currentPortfolio.sharpe }]
    : [];

  const maxSharpePt = data?.maxSharpe
    ? [{ x: (data.maxSharpe.vol ?? 0) * 100, y: (data.maxSharpe.ret ?? 0) * 100, sharpe: data.maxSharpe.sharpe }]
    : [];

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3" {...scope}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Efficient Frontier</h3>
        <button
          onClick={run}
          disabled={loading || holdings.length === 0}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Running…" : "🔴 Run Efficient Frontier"}
        </button>
      </div>

      {holdings.length > 20 && (
        <p className="text-xs text-amber-500">Warning: more than 20 holdings — frontier may be slow or unavailable.</p>
      )}

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-500">{error}</div>
      )}

      {data && (
        <>
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
              <XAxis
                type="number"
                dataKey="x"
                name="Volatility"
                tickFormatter={(v) => `${v.toFixed(1)}%`}
                tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
                label={{ value: "Volatility (%)", position: "insideBottom", offset: -4, fontSize: 11, fill: "rgb(var(--text-muted))" }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name="Return"
                tickFormatter={(v) => `${v.toFixed(1)}%`}
                tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
                width={52}
                label={{ value: "Return (%)", angle: -90, position: "insideLeft", fontSize: 11, fill: "rgb(var(--text-muted))" }}
              />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                formatter={(value: number, name: string) => [`${value.toFixed(2)}%`, name]}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0]?.payload as { x: number; y: number; sharpe: number };
                  return (
                    <div className="bg-surface-alt border border-border rounded-lg p-2 text-xs">
                      <p>Vol: {d.x.toFixed(2)}%</p>
                      <p>Return: {d.y.toFixed(2)}%</p>
                      <p>Sharpe: {d.sharpe.toFixed(2)}</p>
                    </div>
                  );
                }}
              />
              {/* Frontier line */}
              <Scatter
                name="Frontier"
                data={frontierPts}
                fill="#6366f1"
                fillOpacity={0.6}
                r={3}
                line={{ stroke: "#6366f1", strokeWidth: 1.5 }}
              />
              {/* Current portfolio */}
              <Scatter
                name="Current Portfolio"
                data={currentPt}
                fill="rgb(var(--primary))"
                r={8}
              />
              {/* Max Sharpe */}
              <Scatter
                name="Max Sharpe"
                data={maxSharpePt}
                fill="#f59e0b"
                r={10}
                shape="star"
              />
            </ScatterChart>
          </ResponsiveContainer>
          <div className="flex gap-4 text-xs text-text-muted">
            <span data-prov="frontier" className="flex items-center gap-1"><span className="w-3 h-1 bg-indigo-500 inline-block rounded" /> Frontier</span>
            <span data-prov="currentPortfolio" className="flex items-center gap-1"><span className="w-3 h-3 bg-accent rounded-full inline-block" /> Current Portfolio</span>
            <span data-prov="maxSharpe" className="flex items-center gap-1"><span className="w-3 h-3 bg-amber-500 rounded-full inline-block" /> Max Sharpe</span>
          </div>
        </>
      )}
    </div>
  );
}
