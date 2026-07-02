"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CotData, CotContract } from "@/lib/types";
import { Card } from "@/components/ui";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function CotIndexBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-text-secondary">—</span>;
  const pct = Math.max(0, Math.min(100, value));
  const color =
    pct >= 70 ? "#10b981" : pct <= 30 ? "#ef4444" : "#f59e0b";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-surface-alt rounded-full h-2 overflow-hidden">
        <div
          className="h-2 rounded-full"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs w-8 text-right">{pct.toFixed(0)}</span>
    </div>
  );
}

function fmt(v: number | null, decimals = 0): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(decimals);
}

export function PositioningTab() {
  const [data, setData] = useState<CotData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .macroCot()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }

  if (error || !data || data.error || data.contracts.length === 0) {
    return (
      <div className="space-y-4">
        <Card className="p-6 text-center">
          <h3 className="font-semibold text-text-secondary mb-2">
            Commitments of Traders (CFTC)
          </h3>
          <p className="text-text-secondary text-sm">
            {data?.error ??
              "COT data unavailable — the CFTC source returned no parseable contracts. It will be retried automatically."}
          </p>
          <p className="text-xs text-text-secondary mt-2">
            Source: CFTC Disaggregated Reports (published weekly)
          </p>
        </Card>
      </div>
    );
  }

  // COT is published weekly; flag the data as stale if it is >2 weeks old.
  const asOfAgeDays = data.asOf
    ? Math.floor((Date.now() - new Date(data.asOf).getTime()) / 86_400_000)
    : null;
  const isStale = asOfAgeDays != null && asOfAgeDays > 14;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-semibold text-lg">
          Commitments of Traders (CFTC)
        </h2>
        <p className="text-xs text-text-secondary mt-1">
          Weekly CFTC data. Large speculator net positioning for key futures
          contracts. Source: {data.source}
          {data.asOf ? ` · as of ${data.asOf}` : ""}
          {isStale && (
            <span className="text-warning">
              {" "}
              · stale — no update in {asOfAgeDays} days
            </span>
          )}
        </p>
      </div>

      {/* Summary Table */}
      <Card className="p-4">
        <h3 className="font-semibold mb-3">Positioning Summary</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-text-secondary border-b border-border">
                <th className="pb-2 pr-4">Contract</th>
                <th className="pb-2 pr-4 text-right">Net Speculator</th>
                <th className="pb-2 pr-4 text-right">Net Commercial</th>
                <th className="pb-2 pr-4 text-right">Open Interest</th>
                <th className="pb-2 min-w-[120px]">COT Index (0–100)</th>
              </tr>
            </thead>
            <tbody>
              {data.contracts.map((c: CotContract) => (
                <tr
                  key={c.code}
                  className="border-b border-border/40 hover:bg-surface-alt/30 transition-colors"
                >
                  <td className="py-2 pr-4">
                    <div className="font-medium">{c.name}</div>
                    <div className="text-xs text-text-secondary">{c.code}</div>
                  </td>
                  <td
                    className={`py-2 pr-4 text-right font-mono font-semibold ${
                      c.net_speculator != null && c.net_speculator >= 0
                        ? "text-success"
                        : "text-danger"
                    }`}
                  >
                    {c.net_speculator != null
                      ? `${c.net_speculator >= 0 ? "+" : ""}${fmt(c.net_speculator)}`
                      : "—"}
                  </td>
                  <td
                    className={`py-2 pr-4 text-right font-mono ${
                      c.net_commercial != null && c.net_commercial >= 0
                        ? "text-success"
                        : "text-danger"
                    }`}
                  >
                    {c.net_commercial != null
                      ? `${c.net_commercial >= 0 ? "+" : ""}${fmt(c.net_commercial)}`
                      : "—"}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono text-text-secondary">
                    {fmt(c.open_interest)}
                  </td>
                  <td className="py-2">
                    <CotIndexBar value={c.cot_index} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-text-secondary mt-3">
          COT Index 0–100: extreme short = 0, extreme long = 100. High ({">"}70) =
          historically bullish; Low ({"<"}30) = historically bearish.
        </p>
      </Card>

      {/* Per-contract sparkline charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.contracts.map((c: CotContract) => {
          if (!c.history || c.history.length === 0) return null;
          const chartData = c.history.map((pt) => ({
            date: pt.date.slice(0, 7),
            "Net Spec": pt.net_spec,
          }));
          return (
            <Card key={c.code} className="p-4">
              <h4 className="text-sm font-semibold mb-1">{c.name}</h4>
              <p className="text-xs text-text-secondary mb-2">
                Net speculator positioning (contracts)
              </p>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => fmt(v)} />
                  <Tooltip
                    formatter={(v: number) => [
                      `${v >= 0 ? "+" : ""}${fmt(v)} contracts`,
                      "Net Spec",
                    ]}
                  />
                  <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" />
                  <Bar dataKey="Net Spec" radius={[2, 2, 0, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={
                          entry["Net Spec"] >= 0 ? "#10b981" : "#ef4444"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
