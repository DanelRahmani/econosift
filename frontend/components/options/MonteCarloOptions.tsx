"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, Skeleton, chartPalette, chartTooltipStyle } from "@/components/ui";
import { fmtNum, fmtPrice } from "@/lib/format";
import { api } from "@/lib/api";
import type { MCOptionsResult } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  ticker: string;
  expiry: string;
  theme: string;
}

const SIM_OPTIONS = [
  { label: "1K", value: 1000 },
  { label: "5K", value: 5000 },
  { label: "10K", value: 10000 },
] as const;

interface TooltipPayloadEntry {
  value: number | null;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string | number;
}

function DistTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="font-semibold text-text-primary">Bin: {fmtPrice(Number(label))}</div>
      <div className="text-text-secondary">Count: {payload[0]?.value ?? "—"}</div>
    </div>
  );
}

export function MonteCarloOptions({ ticker, expiry, theme }: Props) {
  const p = chartPalette(theme as "light" | "dark");
  const tt = chartTooltipStyle(theme as "light" | "dark");

  const [strike, setStrike] = useState<string>("");
  const [optType, setOptType] = useState<"call" | "put">("call");
  const [sims, setSims] = useState<number>(10000);
  const [result, setResult] = useState<MCOptionsResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(result));

  async function handleRun() {
    const strikeNum = parseFloat(strike);
    if (!strike || isNaN(strikeNum) || strikeNum <= 0) {
      setError("Enter a valid strike price.");
      return;
    }
    if (!expiry) {
      setError("Select an expiry date first.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await api.optionsMonteCarlo(ticker, strikeNum, expiry, optType, sims);
      setResult(res);
      if (res.error) setError(res.error);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
          {/* Strike */}
          <div>
            <label className="block text-xs text-text-muted mb-1">Strike Price ($)</label>
            <input
              type="number"
              value={strike}
              onChange={(e) => setStrike(e.target.value)}
              placeholder="e.g. 185"
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          {/* Call / Put toggle */}
          <div>
            <label className="block text-xs text-text-muted mb-1">Type</label>
            <div className="flex gap-1">
              <button
                onClick={() => setOptType("call")}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  optType === "call"
                    ? "bg-success text-white"
                    : "bg-surface-alt text-text-secondary hover:text-text-primary"
                }`}
              >
                Call
              </button>
              <button
                onClick={() => setOptType("put")}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  optType === "put"
                    ? "bg-danger text-white"
                    : "bg-surface-alt text-text-secondary hover:text-text-primary"
                }`}
              >
                Put
              </button>
            </div>
          </div>

          {/* Sims */}
          <div>
            <label className="block text-xs text-text-muted mb-1">Simulations</label>
            <div className="flex gap-1">
              {SIM_OPTIONS.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setSims(s.value)}
                  className={`flex-1 px-2 py-2 rounded-lg text-xs font-medium transition-colors ${
                    sims === s.value
                      ? "bg-accent text-white"
                      : "bg-surface-alt text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-danger text-white text-sm font-semibold hover:bg-danger/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Running…" : "Run Analysis"}
          </button>
        </div>

        {error && (
          <div className="mt-3 p-2 rounded-md bg-danger/10 border border-danger/30 text-xs text-danger">
            {error}
          </div>
        )}
      </Card>

      {/* Results */}
      {loading && <Skeleton className="h-64 w-full rounded-xl" />}

      {result && !loading && (
        <div className="space-y-4" {...scope}>
          {/* KPI row */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              { label: "MC Price", value: result.price !== null ? fmtPrice(result.price) : "—", prov: "*" },
              { label: "BS Price", value: result.bsPrice !== null ? fmtPrice(result.bsPrice) : "—", prov: "bsPrice" },
              { label: "Std Dev", value: result.std !== null ? fmtPrice(result.std) : "—", prov: "std" },
              { label: "VaR 95%", value: result.var95 !== null ? fmtPrice(result.var95) : "—", prov: "var95" },
              { label: "VaR 99%", value: result.var99 !== null ? fmtPrice(result.var99) : "—", prov: "var99" },
            ].map((kpi) => (
              <Card key={kpi.label} className="p-3" data-prov={kpi.prov}>
                <div className="text-[10px] text-text-muted mb-1">{kpi.label}</div>
                <div className="text-lg font-bold font-mono">{kpi.value}</div>
              </Card>
            ))}
          </div>

          {/* Distribution histogram */}
          {result.distribution?.length > 0 && (
            <Card className="p-4" data-prov="distribution">
              <h4 className="text-sm font-semibold mb-3 text-text-primary">
                Terminal Price Distribution
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={result.distribution.map((d) => ({ bin: d.bin, count: d.count }))}
                  margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={p.grid} vertical={false} />
                  <XAxis
                    dataKey="bin"
                    stroke={p.axis}
                    tick={{ fontSize: 10, fill: p.axis }}
                    tickFormatter={(v) => fmtPrice(v)}
                  />
                  <YAxis stroke={p.axis} tick={{ fontSize: 10, fill: p.axis }} />
                  <Tooltip content={<DistTooltip />} {...tt} />
                  <Bar dataKey="count" fill="#c4394a" fillOpacity={0.75} radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          <div className="text-[10px] text-text-muted text-center">
            {sims.toLocaleString()} GBM paths · Not cached · Results vary between runs ·
            Expiry: {expiry} · Strike: {strike} · {optType.toUpperCase()}
          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="flex items-center justify-center h-32 text-text-muted text-sm">
          Configure inputs above and click &quot;Run Analysis&quot; to price this option
        </div>
      )}
    </div>
  );
}
