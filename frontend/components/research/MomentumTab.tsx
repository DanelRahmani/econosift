"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from "recharts";
import Link from "next/link";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { MomentumResponse, MomentumRank } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

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
  backgroundColor: "var(--color-surface-alt)",
  border: "1px solid var(--color-border)",
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
  const [data, setData] = useState<MomentumResponse | null>(null);
  const [loading, setLoading] = useState(false);
  // Tracks the param combo currently loaded, so the heavy universes only fetch on demand.
  const [loadedKey, setLoadedKey] = useState<string>("");
  const scope = useSourceScope(provOf(data));

  const fetchData = useCallback((u: Universe, s: Signal) => {
    setLoading(true);
    api.momentum(u, s)
      .then((d) => { setData(d); setLoadedKey(`${u}:${s}`); })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  // Dow is cheap → auto-load. NDX/S&P 500 are throttle-prone → require the button.
  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (universe === "dow") fetchData("dow", signal);
    else setData(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [universe, signal, refreshNonce]);

  const needsRun = universe !== "dow" && loadedKey !== `${universe}:${signal}`;

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
            <button onClick={() => fetchData(universe, signal)} disabled={loading}
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
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="decile" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                <YAxis tickFormatter={(v) => `${v.toFixed(0)}%`} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
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
