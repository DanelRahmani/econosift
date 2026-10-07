"use client";

import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { CarryTable, CarryBacktest, CarryRow } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

const tooltipStyle = {
  backgroundColor: "rgb(var(--surface-alt))",
  border: "1px solid rgb(var(--border))",
  borderRadius: 8,
  fontSize: 12,
};

type SortKey = "carry" | "volAdjCarry" | "fxVol" | "foreignRate";

function num(v: number | null, dp = 2, suffix = ""): string {
  return v === null || v === undefined ? "—" : `${v.toFixed(dp)}${suffix}`;
}

export function FxCarryTab() {
  const [table, setTable] = useState<CarryTable | null>(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<SortKey>("carry");

  const [backtest, setBacktest] = useState<CarryBacktest | null>(null);
  const [btLoading, setBtLoading] = useState(false);

  const tableScope = useSourceScope(provOf(table));
  const backtestScope = useSourceScope(provOf(backtest));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    setLoading(true);
    api.carryTable("3y").then(setTable).catch(() => setTable(null)).finally(() => setLoading(false));
  }, [refreshNonce]);

  const runBacktest = () => {
    setBtLoading(true);
    api.carryBacktest("3y").then(setBacktest).catch(() => setBacktest(null)).finally(() => setBtLoading(false));
  };

  const rows = useMemo(() => {
    const r = [...(table?.rows ?? [])];
    r.sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity));
    return r;
  }, [table, sort]);

  const carryColor = (c: CarryRow) =>
    c.carry === null ? "text-text-muted" : c.carry >= 0 ? "text-success" : "text-text-muted";

  const headers: { key: SortKey; label: string }[] = [
    { key: "foreignRate", label: "Policy Rate" },
    { key: "carry", label: "Carry" },
    { key: "fxVol", label: "FX Vol (ann., full period)" },
    { key: "volAdjCarry", label: "Vol-Adj Carry" },
  ];

  return (
    <div className="space-y-6">
      <Card {...tableScope}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-secondary">
            G10 Carry Table {table?.asOf && <span className="text-text-muted font-normal">· as of {table.asOf}</span>}
          </h3>
          {table?.usdRate != null && (
            <span data-prov="usdRate" className="text-xs text-text-muted font-mono">USD funding: {table.usdRate.toFixed(2)}%</span>
          )}
        </div>
        {loading ? <div className="h-64 animate-pulse bg-surface-alt rounded-lg" />
          : !table || table.rows.length === 0 ? (
            <p className="text-sm text-text-muted">
              {table?.error ? `Carry data unavailable: ${table.error}` : "Carry data unavailable (FRED key required for policy rates)."}
            </p>
          ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-muted text-xs border-b border-border">
                  <th className="text-left py-2 pr-3">Pair</th>
                  <th className="text-right py-2 px-3">Spot</th>
                  {headers.map((h) => (
                    <th key={h.key} className="text-right py-2 px-3">
                      <button onClick={() => setSort(h.key)}
                        className={`hover:text-text-primary ${sort === h.key ? "text-accent" : ""}`}>
                        {h.label} {sort === h.key ? "▼" : ""}
                      </button>
                    </th>
                  ))}
                  <th className="text-right py-2 pl-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.ccy} data-prov-ctx={r.pair} className="border-b border-border/50 hover:bg-surface-alt/50">
                    <td className="py-2 pr-3 font-mono font-semibold">{r.pair}</td>
                    <td data-prov={`rows.${r.ccy}.spot`} className="text-right py-2 px-3 font-mono text-text-secondary">{num(r.spot, 4)}</td>
                    <td data-prov={`rows.${r.ccy}.foreignRate`} className="text-right py-2 px-3 font-mono">{num(r.foreignRate, 2, "%")}</td>
                    <td data-prov={`rows.${r.ccy}.carry`} className={`text-right py-2 px-3 font-mono font-semibold ${carryColor(r)}`}>{num(r.carry, 2, "%")}</td>
                    <td data-prov={`rows.${r.ccy}.fxVol`} className="text-right py-2 px-3 font-mono text-text-secondary">{num(r.fxVol, 1, "%")}</td>
                    <td data-prov={`rows.${r.ccy}.volAdjCarry`} className="text-right py-2 px-3 font-mono">{num(r.volAdjCarry, 3)}</td>
                    <td data-prov={`rows.${r.ccy}.foreignRate`} className="text-right py-2 pl-3 font-mono text-text-muted text-xs">{r.rateSource}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-text-muted mt-3">
          Carry = foreign policy rate − USD rate. High-yielders (AUD/NZD) top the table; funding currencies (JPY/CHF) bottom.
        </p>
      </Card>

      <Card {...backtestScope}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-secondary">
            Carry Basket Backtest <span className="text-text-muted">(long top-3 / short bottom-3, vs DXY)</span>
          </h3>
          <button onClick={runBacktest} disabled={btLoading}
            className="px-3 py-1.5 rounded-lg bg-danger/90 hover:bg-danger text-white text-xs font-semibold disabled:opacity-50">
            {btLoading ? "Running…" : "🔴 Run Backtest"}
          </button>
        </div>
        {!backtest && !btLoading && (
          <p className="text-sm text-text-muted">Run the backtest to see the carry basket cumulative return vs the US dollar index.</p>
        )}
        {btLoading && <div className="h-72 animate-pulse bg-surface-alt rounded-lg" />}
        {backtest && backtest.series.length > 0 && (
          <>
            <div data-prov="legs" className="flex flex-wrap gap-4 mb-3 text-xs">
              <span><span className="text-success font-semibold">Long:</span> {backtest.legs.long.join(", ")}</span>
              <span><span className="text-danger font-semibold">Short:</span> {backtest.legs.short.join(", ")}</span>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={backtest.series} margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "rgb(var(--text-muted))" }} minTickGap={48} />
                <YAxis tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }} domain={["auto", "auto"]} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="strategy" name="Carry Basket" stroke="#10b981" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="benchmark" name="DXY" stroke="#f59e0b" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
              {([
                ["CAGR", backtest.metrics.cagr],
                ["Vol", backtest.metrics.vol],
                ["Sharpe", backtest.metrics.sharpe],
                ["Max DD", backtest.metrics.maxDrawdown],
              ] as const).map(([label, v]) => (
                <div key={label} data-prov="metrics" className="rounded-lg border border-border p-2.5">
                  <div className="text-xs text-text-muted">{label}</div>
                  <div className="text-sm font-mono text-accent">
                    {v === null || v === undefined ? "—" : label === "Sharpe" ? v.toFixed(2) : `${v.toFixed(2)}%`}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
