"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { BacktestResponse, BacktestSignalDef } from "@/lib/types";
import { Card, chartPalette } from "@/components/ui";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

/**
 * Signal backtester — Phase 43 (task D2). Compute tier: 🔴 Run Analysis.
 *
 * Never fires on mount: it downloads a price panel and runs a quantile sort.
 *
 * Gross and net are always shown together. The gap between them is the point —
 * a signal that looks good gross and dies net is the normal outcome, and hiding
 * that would make this a marketing tool rather than a research one.
 */

const QUANTILE_COLORS = ["#94a3b8", "#60a5fa", "#34d399", "#fbbf24", "#ef4444"];

function pct(v: number | null | undefined, decimals = 2): string {
  return v != null ? `${(v * 100).toFixed(decimals)}%` : "—";
}

function num(v: number | null | undefined, decimals = 2): string {
  return v != null ? v.toFixed(decimals) : "—";
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${tone ?? ""}`}>{value}</div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function BacktestTab() {
  const [signals, setSignals] = useState<BacktestSignalDef[]>([]);
  const [signal, setSignal] = useState("momentum_12_1");
  const [universe, setUniverse] = useState("sp500");
  const [rebalance, setRebalance] = useState("M");
  const [nQuantiles, setNQuantiles] = useState(5);
  const [costBps, setCostBps] = useState(10);
  const [pit, setPit] = useState(true);

  const [data, setData] = useState<BacktestResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pal = chartPalette("dark");

  useEffect(() => {
    api.backtestSignals().then((r) => setSignals(r.signals)).catch(() => setSignals([]));
  }, []);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const res = await api.runBacktest({
        signal,
        universe,
        period: "10y",
        rebalance,
        nQuantiles,
        costBps,
        longShort: true,
        pointInTimeUniverse: pit,
      });
      setData(res);
      if (!res.available) setError(res.reason ?? "backtest unavailable");
    } catch (e) {
      setError(e instanceof Error ? e.message : "backtest failed");
      setData(null);
    } finally {
      setRunning(false);
    }
  }

  const chart = useMemo(() => {
    if (!data?.quantiles) return [];
    const keys = Object.keys(data.quantiles).sort((a, b) => Number(a) - Number(b));
    const base = data.quantiles[keys[0]]?.equityCurve ?? [];
    return base.map((pt, i) => {
      const row: Record<string, string | number | null> = { date: pt.date };
      for (const k of keys) row[`Q${k}`] = data.quantiles![k].equityCurve[i]?.value ?? null;
      row["Long-Short"] = data.longShort?.equityCurve[i]?.value ?? null;
      return row;
    });
  }, [data]);

  const selected = signals.find((s) => s.key === signal);
  const ls = data?.longShort;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Signal Backtester</h2>
        <p className="text-xs text-text-secondary mt-1">
          Ranks the universe by a signal each rebalance, forms equal-weight quantile
          portfolios, and charges transaction costs against turnover. Positions formed
          at <em>t</em> earn the return from <em>t</em> to <em>t+1</em> — the signal is
          never paired with a return it could not have preceded.
        </p>
      </div>

      {/* Controls */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <label className="text-sm">
            <span className="block text-xs text-text-secondary mb-1">Signal</span>
            <select
              value={signal}
              onChange={(e) => setSignal(e.target.value)}
              className="w-full bg-surface-alt border border-border rounded px-2 py-1.5 text-sm"
            >
              {signals.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </label>

          <label className="text-sm">
            <span className="block text-xs text-text-secondary mb-1">Universe</span>
            <select
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              className="w-full bg-surface-alt border border-border rounded px-2 py-1.5 text-sm"
            >
              <option value="sp500">S&amp;P 500</option>
              <option value="ndx">Nasdaq 100</option>
              <option value="dow">Dow 30</option>
            </select>
          </label>

          <label className="text-sm">
            <span className="block text-xs text-text-secondary mb-1">Rebalance</span>
            <select
              value={rebalance}
              onChange={(e) => setRebalance(e.target.value)}
              className="w-full bg-surface-alt border border-border rounded px-2 py-1.5 text-sm"
            >
              <option value="W">Weekly</option>
              <option value="M">Monthly</option>
              <option value="Q">Quarterly</option>
            </select>
          </label>

          <label className="text-sm">
            <span className="block text-xs text-text-secondary mb-1">Quantiles: {nQuantiles}</span>
            <input
              type="range" min={2} max={10} value={nQuantiles}
              onChange={(e) => setNQuantiles(Number(e.target.value))}
              className="w-full"
            />
          </label>

          <label className="text-sm">
            <span className="block text-xs text-text-secondary mb-1">
              Cost: {costBps} bps per unit turnover
            </span>
            <input
              type="range" min={0} max={100} step={5} value={costBps}
              onChange={(e) => setCostBps(Number(e.target.value))}
              className="w-full"
            />
          </label>

          <label className="flex items-center gap-2 text-sm self-end pb-1">
            <input type="checkbox" checked={pit} onChange={(e) => setPit(e.target.checked)} />
            <span className="text-xs text-text-secondary">
              Point-in-time universe (removes survivorship bias)
            </span>
          </label>
        </div>

        {selected && (
          <p className="text-xs text-text-muted mt-3">{selected.description}</p>
        )}

        <button
          onClick={run}
          disabled={running}
          className={`mt-4 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
            running
              ? "border-border bg-surface-alt text-text-muted cursor-wait"
              : "border-accent/40 bg-accent text-white hover:bg-accent-light"
          }`}
        >
          {running ? "Running…" : "🔴 Run Analysis"}
        </button>
        <span className="ml-3 text-xs text-text-muted">
          Downloads a price panel — expect tens of seconds on a cold cache.
        </span>
      </Card>

      {error && (
        <Card className="p-4">
          <div className="text-sm text-danger">{error}</div>
        </Card>
      )}

      {data?.warning && (
        <Card className="p-4 border-warning/40">
          <div className="text-sm text-warning">{data.warning}</div>
        </Card>
      )}

      {data?.available && ls && (
        <>
          {/* KPI row — net figures, since gross is not what you would have earned */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <Kpi
              label="Long-Short CAGR (net)"
              value={pct(ls.net.cagr)}
              sub={`gross ${pct(ls.gross.cagr)}`}
              tone={(ls.net.cagr ?? 0) >= 0 ? "text-success" : "text-danger"}
            />
            <Kpi label="Sharpe (net)" value={num(ls.net.sharpe)} sub={`gross ${num(ls.gross.sharpe)}`} />
            <Kpi label="Max drawdown" value={pct(ls.net.maxDrawdown)} sub="long-short leg" />
            <Kpi label="Avg turnover" value={pct(data.avgTurnover)} sub="per rebalance, one-way" />
            <Kpi label="Cost drag" value={pct(ls.totalCostDrag)} sub="cumulative, both legs" />
          </div>

          {/* Equity curves */}
          <Card className="p-4">
            <h3 className="font-semibold mb-1">Growth of $1 by quantile (net of costs)</h3>
            <p className="text-xs text-text-secondary mb-3">
              Q1 is the lowest-ranked bucket, Q{data.settings?.nQuantiles} the highest.
              A monotonic fan is the sign of a real cross-sectional effect; crossed or
              tangled lines mean the ranking carries little information.
            </p>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}x`} />
                <Tooltip formatter={(v: number) => (v != null ? `${v.toFixed(3)}x` : "—")} />
                <Legend />
                <ReferenceLine y={1} stroke={pal.axis} strokeDasharray="4 4" />
                {Object.keys(data.quantiles ?? {})
                  .sort((a, b) => Number(a) - Number(b))
                  .map((k, i, arr) => (
                    <Line
                      key={k}
                      type="monotone"
                      dataKey={`Q${k}`}
                      stroke={QUANTILE_COLORS[Math.floor((i / Math.max(arr.length - 1, 1)) * (QUANTILE_COLORS.length - 1))]}
                      dot={false}
                      strokeWidth={1.3}
                    />
                  ))}
                <Line type="monotone" dataKey="Long-Short" stroke="#8b5cf6" dot={false} strokeWidth={2} strokeDasharray="5 3" />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          {/* Detail table */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3">By quantile — gross vs net</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-text-secondary border-b border-border">
                    <th className="py-2 pr-4 font-medium">Bucket</th>
                    <th className="py-2 pr-4 font-medium text-right">CAGR gross</th>
                    <th className="py-2 pr-4 font-medium text-right">CAGR net</th>
                    <th className="py-2 pr-4 font-medium text-right">Vol</th>
                    <th className="py-2 pr-4 font-medium text-right">Sharpe net</th>
                    <th className="py-2 pr-4 font-medium text-right">Max DD</th>
                    <th className="py-2 font-medium text-right">Hit rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {Object.keys(data.quantiles ?? {})
                    .sort((a, b) => Number(a) - Number(b))
                    .map((k) => {
                      const q = data.quantiles![k];
                      return (
                        <tr key={k}>
                          <td className="py-2 pr-4">Q{k}</td>
                          <td className="py-2 pr-4 text-right font-mono">{pct(q.gross.cagr)}</td>
                          <td className="py-2 pr-4 text-right font-mono">{pct(q.net.cagr)}</td>
                          <td className="py-2 pr-4 text-right font-mono">{pct(q.net.vol)}</td>
                          <td className="py-2 pr-4 text-right font-mono">{num(q.net.sharpe)}</td>
                          <td className="py-2 pr-4 text-right font-mono">{pct(q.net.maxDrawdown)}</td>
                          <td className="py-2 text-right font-mono">{pct(q.net.hitRate, 0)}</td>
                        </tr>
                      );
                    })}
                  <tr className="font-semibold">
                    <td className="py-2 pr-4">Long-Short</td>
                    <td className="py-2 pr-4 text-right font-mono">{pct(ls.gross.cagr)}</td>
                    <td className="py-2 pr-4 text-right font-mono">{pct(ls.net.cagr)}</td>
                    <td className="py-2 pr-4 text-right font-mono">{pct(ls.net.vol)}</td>
                    <td className="py-2 pr-4 text-right font-mono">{num(ls.net.sharpe)}</td>
                    <td className="py-2 pr-4 text-right font-mono">{pct(ls.net.maxDrawdown)}</td>
                    <td className="py-2 text-right font-mono">{pct(ls.net.hitRate, 0)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          {/* Run provenance + caveats */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold mb-2">About this run</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-text-secondary mb-3">
              <div>Window<div className="text-text-primary font-mono">{data.start} → {data.end}</div></div>
              <div>Periods<div className="text-text-primary font-mono">{data.periods}</div></div>
              <div>Tickers<div className="text-text-primary font-mono">{data.meta?.tickersWithData}</div></div>
              <div>Point-in-time<div className="text-text-primary font-mono">{data.settings?.universePointInTime ? "yes" : "no"}</div></div>
            </div>
            {data.meta?.universeTruncated && (
              <p className="text-xs text-warning mb-2">
                Universe capped at {data.meta.maxTickers} tickers to keep the download
                tractable, so this is a subset of {data.meta.universe.toUpperCase()}, not
                the full index.
              </p>
            )}
            {!data.settings?.universePointInTime && (
              <p className="text-xs text-warning mb-2">
                Point-in-time universe is off, so this run uses today&apos;s members and
                carries survivorship bias — results are flattered.
              </p>
            )}
            <p className="text-xs text-text-muted">{data.caveat}</p>
          </Card>
        </>
      )}
    </div>
  );
}
