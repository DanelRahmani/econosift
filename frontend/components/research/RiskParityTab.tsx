"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
  ResponsiveContainer, Legend,
} from "recharts";
import { Card } from "@/components/ui";
import { SearchBar } from "@/components/SearchBar";
import { api } from "@/lib/api";
import type { RiskParityWeights, RiskParityBacktest } from "@/lib/types";

const PERIODS = ["1y", "3y", "5y"] as const;
const COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#3b82f6", "#a855f7", "#ec4899", "#14b8a6"];

const tooltipStyle = {
  backgroundColor: "var(--color-surface-alt)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  fontSize: 12,
};

function pct(v: number | null | undefined, dp = 1): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(dp)}%`;
}

export function RiskParityTab() {
  const [input, setInput] = useState("SPY, TLT, GLD, DJP");
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("3y");
  const [mode, setMode] = useState<"erc" | "invvol">("erc");

  const [weights, setWeights] = useState<RiskParityWeights | null>(null);
  const [loading, setLoading] = useState(false);

  const [backtest, setBacktest] = useState<RiskParityBacktest | null>(null);
  const [btLoading, setBtLoading] = useState(false);

  const tickers = input.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);

  const loadWeights = useCallback(() => {
    if (tickers.length < 2) return;
    setLoading(true);
    setBacktest(null);
    api.riskParity(tickers, period, mode)
      .then(setWeights)
      .catch(() => setWeights(null))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, period, mode]);

  useEffect(() => { loadWeights(); }, [loadWeights]);

  const runBacktest = () => {
    if (tickers.length < 2) return;
    setBtLoading(true);
    api.riskParityBacktest(tickers, period, mode)
      .then(setBacktest)
      .catch(() => setBacktest(null))
      .finally(() => setBtLoading(false));
  };

  const weightRows = (weights?.weights ?? []).filter((w) => w.weight !== null)
    .map((w) => ({ ticker: w.ticker, value: (w.weight ?? 0) * 100 }));
  const rcRows = (weights?.riskContrib ?? []).filter((r) => r.pctContrib !== null)
    .map((r) => ({ ticker: r.ticker, value: (r.pctContrib ?? 0) * 100 }));

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[240px]">
            <label className="block text-xs text-text-muted mb-1">Tickers (multi-asset basket)</label>
            <div className="space-y-2">
              <SearchBar onAdd={(sym) => {
                const current = input.split(",").map(t => t.trim().toUpperCase()).filter(Boolean);
                if (!current.includes(sym.toUpperCase())) {
                  setInput([...current, sym.toUpperCase()].join(", "));
                }
              }} />
              {tickers.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {tickers.map((t) => (
                    <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-alt border border-border text-xs font-mono">
                      {t}
                      <button onClick={() => {
                        const next = tickers.filter(x => x !== t);
                        setInput(next.join(", "));
                      }} className="text-text-muted hover:text-danger leading-none">&times;</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Period</label>
            <div className="flex gap-1">
              {PERIODS.map((p) => (
                <button key={p} onClick={() => setPeriod(p)}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono ${period === p ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"}`}>
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Weighting</label>
            <div className="flex gap-1">
              <button onClick={() => setMode("erc")}
                className={`px-2.5 py-1 rounded-md text-xs ${mode === "erc" ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}>
                ERC
              </button>
              <button onClick={() => setMode("invvol")}
                className={`px-2.5 py-1 rounded-md text-xs ${mode === "invvol" ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}>
                Inverse Vol
              </button>
            </div>
          </div>
        </div>
        {weights?.missing && weights.missing.length > 0 && (
          <p className="text-xs text-warning mt-2">No data for: {weights.missing.join(", ")}</p>
        )}
      </Card>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-3">
            {mode === "erc" ? "Equal Risk Contribution" : "Inverse-Volatility"} Weights
          </h3>
          {loading ? <div className="h-56 animate-pulse bg-surface-alt rounded-lg" />
            : weightRows.length === 0 ? <p className="text-sm text-text-muted">No data.</p>
            : (
            <ResponsiveContainer width="100%" height={Math.max(200, weightRows.length * 44)}>
              <BarChart data={weightRows} layout="vertical" margin={{ left: 8, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-border)" />
                <XAxis type="number" tickFormatter={(v) => `${v.toFixed(0)}%`} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                <YAxis type="category" dataKey="ticker" width={80} tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "monospace" }} />
                <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, "Weight"]} contentStyle={tooltipStyle} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {weightRows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-3">Risk Contribution (%)</h3>
          {loading ? <div className="h-56 animate-pulse bg-surface-alt rounded-lg" />
            : rcRows.length === 0 ? <p className="text-sm text-text-muted">No data.</p>
            : (
            <ResponsiveContainer width="100%" height={Math.max(200, rcRows.length * 44)}>
              <BarChart data={rcRows} layout="vertical" margin={{ left: 8, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-border)" />
                <XAxis type="number" tickFormatter={(v) => `${v.toFixed(0)}%`} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                <YAxis type="category" dataKey="ticker" width={80} tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "monospace" }} />
                <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, "Risk Contribution"]} contentStyle={tooltipStyle} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {rcRows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          <p className="text-xs text-text-muted mt-2">
            ERC equalizes each asset&apos;s share of portfolio risk; inverse-vol weights by 1/σ.
          </p>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-secondary">
            Backtest vs 60/40 <span className="text-text-muted">(monthly rebalance, base 100)</span>
          </h3>
          <button onClick={runBacktest} disabled={btLoading}
            className="px-3 py-1.5 rounded-lg bg-danger/90 hover:bg-danger text-white text-xs font-semibold disabled:opacity-50">
            {btLoading ? "Running…" : "🔴 Run Backtest"}
          </button>
        </div>
        {!backtest && !btLoading && (
          <p className="text-sm text-text-muted">Run the backtest to compare against a 60/40 SPY+AGG benchmark.</p>
        )}
        {btLoading && <div className="h-72 animate-pulse bg-surface-alt rounded-lg" />}
        {backtest && backtest.series.length > 0 && (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={backtest.series} margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} minTickGap={48} />
                <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} domain={["auto", "auto"]} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="strategy" name="Risk Parity" stroke="#6366f1" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="benchmark" name="60/40" stroke="#f59e0b" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
              {([
                ["CAGR", pct(backtest.metrics.strategy.cagr), pct(backtest.metrics.benchmark.cagr)],
                ["Vol", pct(backtest.metrics.strategy.vol), pct(backtest.metrics.benchmark.vol)],
                ["Sharpe", backtest.metrics.strategy.sharpe?.toFixed(2) ?? "—", backtest.metrics.benchmark.sharpe?.toFixed(2) ?? "—"],
                ["Max DD", pct(backtest.metrics.strategy.maxDrawdown), pct(backtest.metrics.benchmark.maxDrawdown)],
              ] as const).map(([label, s, b]) => (
                <div key={label} className="rounded-lg border border-border p-2.5">
                  <div className="text-xs text-text-muted">{label}</div>
                  <div className="text-sm font-mono text-accent">{s}</div>
                  <div className="text-xs font-mono text-text-secondary">60/40: {b}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
