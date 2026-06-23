"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";

function fmtUptime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h ? `${h}h ${m}m` : m ? `${m}m ${s}s` : `${s}s`;
}

export default function AdminPage() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setData(await api.health());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-display font-bold">Backend Health</h1>
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg text-sm font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
        >Refresh</button>
      </div>

      {loading && !data ? (
        <Skeleton className="h-40" />
      ) : data ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Status" value={data.status.toUpperCase()} tone="pos" />
            <Stat label="Uptime" value={fmtUptime(data.uptimeSeconds)} />
            <Stat
              label="Cache Hit Rate"
              value={data.cache.overallHitRate !== null ? `${(data.cache.overallHitRate * 100).toFixed(1)}%` : "—"}
            />
            <Stat label="FRED API Key" value={data.config.fredApiKey ? "Set" : "Missing"} tone={data.config.fredApiKey ? "pos" : "neg"} />
          </div>

          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Cache Performance by Source</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text-secondary border-b border-border">
                    <th className="text-left py-2 px-3 font-medium">Cache</th>
                    <th className="text-right py-2 px-3 font-medium">Hits</th>
                    <th className="text-right py-2 px-3 font-medium">Misses</th>
                    <th className="text-right py-2 px-3 font-medium">Hit Rate</th>
                    <th className="text-right py-2 px-3 font-medium">Entries</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.cache.byName).map(([name, s]) => (
                    <tr key={name} className="border-b border-border/50">
                      <td className="py-2 px-3 font-mono">{name}</td>
                      <td className="py-2 px-3 text-right font-mono text-success">{s.hits}</td>
                      <td className="py-2 px-3 text-right font-mono text-text-muted">{s.misses}</td>
                      <td className="py-2 px-3 text-right font-mono">{s.hitRate !== null ? `${(s.hitRate * 100).toFixed(0)}%` : "—"}</td>
                      <td className="py-2 px-3 text-right font-mono">{s.size}</td>
                    </tr>
                  ))}
                  {!Object.keys(data.cache.byName).length && (
                    <tr><td colSpan={5} className="py-6 text-center text-text-muted">No cache activity yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-text-muted mt-3">TTL: {Math.round(data.cache.ttlSeconds / 60)} min · auto-refreshes every 15s</p>
          </Card>
        </>
      ) : (
        <Card><div className="text-text-muted text-sm">Could not reach backend.</div></Card>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <Card>
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`text-lg font-mono ${tone === "pos" ? "text-success" : tone === "neg" ? "text-danger" : "text-text-primary"}`}>{value}</div>
    </Card>
  );
}
