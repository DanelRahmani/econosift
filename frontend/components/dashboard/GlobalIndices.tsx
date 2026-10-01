"use client";

import { useEffect, useMemo, useState } from "react";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { api } from "@/lib/api";
import type { IndicesResponse, IndexRow } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtNum } from "@/lib/format";

/** Global equity indices (compute tier 🟢) with region tabs and sparklines. */
export function GlobalIndices() {
  const [data, setData] = useState<IndicesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [region, setRegion] = useState<string>("Americas");
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    let alive = true;
    api.indices()
      .then((r) => alive && setData(r))
      .catch(() => alive && setData(null))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  const rows = useMemo(
    () => (data?.indices ?? []).filter((i) => i.region === region),
    [data, region],
  );

  if (loading && !data) return <Skeleton className="h-80" />;
  if (!data) return <Card><div className="text-text-muted text-sm">Indices unavailable.</div></Card>;

  return (
    <Card {...scope}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="text-sm font-semibold text-text-secondary">Global Indices</h2>
        <div className="flex gap-1" data-hide-print>
          {data.regions.map((r) => (
            <button
              key={r}
              onClick={() => setRegion(r)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                region === r ? "bg-accent text-white" : "text-text-muted hover:bg-surface-alt"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-text-muted border-b border-border">
              <th className="text-left font-medium py-2">Index</th>
              <th className="text-right font-medium">Price</th>
              <th className="text-right font-medium">1D</th>
              <th className="text-center font-medium px-2">5D</th>
              <th className="text-right font-medium">1M</th>
              <th className="text-right font-medium">YTD</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Row key={row.symbol} row={row} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Row({ row }: { row: IndexRow }) {
  const up = (row.change1d ?? 0) >= 0;
  return (
    <tr className="border-b border-border/50 hover:bg-surface-alt/50" data-prov={`indices.${row.symbol}`} data-prov-ctx={row.name}>
      <td className="py-2">
        <div className="font-medium text-text-primary">{row.name}</div>
        <div className="text-xs text-text-muted font-mono">{row.symbol}</div>
      </td>
      <td className="text-right font-mono">{fmtNum(row.price, 2)}</td>
      <td className={`text-right font-mono ${pctColor(row.change1d)}`}>{pct(row.change1d)}</td>
      <td className="px-2 w-20">
        <div className="h-7">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={row.spark.map((v, i) => ({ i, v }))}>
              <YAxis hide domain={["dataMin", "dataMax"]} />
              <Line type="monotone" dataKey="v" stroke={up ? "#16a34a" : "#c4394a"} dot={false} strokeWidth={1.5} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </td>
      <td className={`text-right font-mono ${pctColor(row.change1m)}`}>{pct(row.change1m)}</td>
      <td className={`text-right font-mono ${pctColor(row.changeYtd)}`}>{pct(row.changeYtd)}</td>
    </tr>
  );
}

function pct(v: number | null): string {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function pctColor(v: number | null): string {
  if (v === null) return "text-text-muted";
  return v >= 0 ? "text-success" : "text-danger";
}
