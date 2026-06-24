"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MoversResponse, MoverRow } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { fmtNum, fmtLarge } from "@/lib/format";

const TABS = [
  { key: "gainers", label: "Gainers" },
  { key: "losers", label: "Losers" },
  { key: "unusualVolume", label: "Unusual Volume" },
  { key: "newHighs", label: "52W Highs" },
  { key: "newLows", label: "52W Lows" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

/** Top movers from the S&P 500 universe (compute tier 🟢). */
export function TopMovers({ index = "sp500" }: { index?: string }) {
  const [data, setData] = useState<MoversResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("gainers");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.movers(index)
      .then((r) => alive && setData(r))
      .catch(() => alive && setData(null))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [index]);

  if (loading && !data) return <Skeleton className="h-80" />;
  if (!data) return <Card><div className="text-text-muted text-sm">Movers unavailable.</div></Card>;

  const rows = data[tab];

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="text-sm font-semibold text-text-secondary">Top Movers</h2>
        <span className="text-xs text-text-muted font-mono">{data.asOf ?? "—"}</span>
      </div>

      <div className="flex flex-wrap gap-1 mb-3" data-hide-print>
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              tab === t.key ? "bg-accent text-white" : "text-text-muted hover:bg-surface-alt"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="text-text-muted text-sm py-6 text-center">No names match this filter today.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted border-b border-border">
                <th className="text-left font-medium py-2">Ticker</th>
                <th className="text-right font-medium">Price</th>
                <th className="text-right font-medium">1D</th>
                {tab === "unusualVolume" && <th className="text-right font-medium">Vol ×Avg</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <MoverTr key={row.ticker} row={row} showVol={tab === "unusualVolume"} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function MoverTr({ row, showVol }: { row: MoverRow; showVol: boolean }) {
  const up = (row.changePercent ?? 0) >= 0;
  return (
    <tr className="border-b border-border/50 hover:bg-surface-alt/50">
      <td className="py-2">
        <span className="font-mono font-semibold text-text-primary">{row.ticker}</span>
        <span className="text-xs text-text-muted ml-2 truncate">{row.name}</span>
      </td>
      <td className="text-right font-mono">{fmtNum(row.price, 2)}</td>
      <td className={`text-right font-mono ${up ? "text-success" : "text-danger"}`}>
        {row.changePercent === null ? "—" : `${up ? "+" : ""}${row.changePercent.toFixed(2)}%`}
      </td>
      {showVol && (
        <td className="text-right font-mono text-text-secondary">
          {row.volumeRatio ? `${row.volumeRatio.toFixed(1)}×` : "—"}
          {row.volume ? <span className="text-text-muted text-xs ml-1">({fmtLarge(row.volume)})</span> : null}
        </td>
      )}
    </tr>
  );
}
