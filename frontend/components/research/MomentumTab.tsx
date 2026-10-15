"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiQuery } from "@/lib/queries";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from "recharts";
import Link from "next/link";
import { Card } from "@/components/ui";
import type { MomentumRank } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

const UNIVERSES = [
  { key: "dow", label: "Dow 30" },
  { key: "ndx", label: "Nasdaq 100" },
  { key: "sp500", label: "S&P 500" },
] as const;
type Universe = (typeof UNIVERSES)[number]["key"];

const SIGNALS = [
  { key: "12m1m", label: "12M-1M" },
  { key: "6m", label: "6M" },
  { key: "3m", label: "3M" },
  { key: "1m", label: "1M" },
] as const;
type Signal = (typeof SIGNALS)[number]["key"];

const tooltipStyle = {
  backgroundColor: "rgb(var(--surface-alt))",
  border: "1px solid rgb(var(--border))",
  borderRadius: 8,
  fontSize: 12,
};

function pct(v: number | null): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`;
}

function RankTable({ title, rows, accent, prov }: { title: string; rows: MomentumRank[]; accent: string; prov: string }) {
  return (
    <div data-prov={prov}>
      <h4 className={`text-xs font-semibold mb-2 ${accent}`}>{title}</h4>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticker} data-prov-ctx={r.ticker} className="border-b border-border/40">
              <td className="py-1.5">
                <Link href={`/markets?ticker=${r.ticker}`} className="font-mono font-semibold hover:text-accent">
                  {r.ticker}
                </Link>
              </td>
              <td className={`py-1.5 text-right font-mono ${(r.momentum ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                {pct(r.momentum)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MomentumTab() {
  const [universe, setUniverse] = useState<Universe>("dow");
  const [signal, setSignal] = useState<Signal>("12m1m");
  // Dow is cheap → auto-load. NDX/S&P 500 are throttle-prone → require the button,
  // which records the param combo it ran for.
  const [runKey, setRunKey] = useState<string>("");
  const currentKey = `${universe}:${signal}`;
  const { data: momentumData, isFetching: loading } = useQuery({
    ...apiQuery("momentum", universe, signal),
    enabled: universe === "dow" || runKey === currentKey,
  });
  const data = universe === "dow" || runKey === currentKey ? momentumData ?? null : null;
  const scope = useSourceScope(provOf(data));

  const needsRun = universe !== "dow" && runKey !== currentKey;

  const deciles = (data?.deciles ?? []).map((d) => ({
    decile: `D${d.decile}`,
    value: (d.avgReturn ?? 0) * 100,
    count: d.count,
  }));

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-end gap-6">
          <div>
            <label className="block text-xs text-text-muted mb-1">Universe</label>
            <div className="flex gap-1">
              {UNIVERSES.map((u) => (
                <button key={u.key} onClick={() => setUniverse(u.key)}
                  className={`px-2.5 py-1 rounded-md text-xs ${universe === u.key ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}>
                  {u.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Signal (prior return)</label>
            <div className="flex gap-1">
              {SIGNALS.map((s) => (
                <button key={s.key} onClick={() => setSignal(s.key)}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono ${signal === s.key ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"}`}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          {universe !== "dow" && (
            <button onClick={() => setRunKey(currentKey)} disabled={loading}
              className="px-3 py-1.5 rounded-lg bg-danger/90 hover:bg-danger text-white text-xs font-semibold disabled:opacity-50">
              {loading ? "Running…" : "🔴 Run"}
            </button>
          )}
        </div>
        <p className="text-xs text-text-muted mt-2">
          Higher deciles = stronger prior return. Large universes load on demand to avoid rate limits.
        </p>
      </Card>

      {needsRun && !loading && (
        <Card><p className="text-sm text-text-muted">Press <span className="font-semibold">Run</span> to compute momentum over the {UNIVERSES.find((u) => u.key === universe)?.label} universe.</p></Card>
      )}

      {loading && <div className="h-72 animate-pulse bg-surface-alt rounded-lg" />}

      {!loading && data && !data.error && data.deciles.length > 0 && (
        <>
          <Card data-prov="deciles" {...scope}>
            <h3 className="text-sm font-semibold text-text-secondary mb-3">
              Decile Average Prior Return {data.asOf && <span className="text-text-muted font-normal">· {data.asOf}</span>}
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={deciles} margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
                <XAxis dataKey="decile" tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }} />
                <YAxis tickFormatter={(v) => `${v.toFixed(0)}%`} tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }} />
                <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, "Avg Prior Return"]} contentStyle={tooltipStyle} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {deciles.map((d, i) => <Cell key={i} fill={d.value >= 0 ? "#10b981" : "#ef4444"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card {...scope}>
            <div className="grid md:grid-cols-2 gap-8">
              <RankTable title="Top Momentum" rows={data.top} accent="text-success" prov="top" />
              <RankTable title="Bottom Momentum" rows={data.bottom} accent="text-danger" prov="bottom" />
            </div>
            {data.missing.length > 0 && (
              <p className="text-xs text-text-muted mt-3">Excluded (insufficient history): {data.missing.join(", ")}</p>
            )}
          </Card>
        </>
      )}

      {!loading && data?.error && (
        <Card><p className="text-sm text-text-muted">Momentum unavailable: {data.error}</p></Card>
      )}
    </div>
  );
}
