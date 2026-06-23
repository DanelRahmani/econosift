"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RelStrengthResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { fmtPct } from "@/lib/format";

function Cell({ value }: { value: number | null }) {
  const tone = value === null ? "text-text-muted" : value >= 0 ? "text-success" : "text-danger";
  return (
    <td className={`py-2 px-3 text-right font-mono ${tone}`}>
      {value !== null && value >= 0 ? "+" : ""}{fmtPct(value)}
    </td>
  );
}

export function RankingsTab({ tickers }: { tickers: string[] }) {
  const [data, setData] = useState<RelStrengthResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!tickers.length) { setData(null); return; }
    let active = true;
    setLoading(true);
    api.relativeStrength(tickers.join(","))
      .then((r) => active && setData(r))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [tickers]);

  if (!tickers.length) {
    return <Card><div className="text-text-muted text-sm">Add tickers to rank by momentum.</div></Card>;
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold mb-1 text-text-secondary">Relative Strength Rankings</h2>
      <p className="text-xs text-text-muted mb-4">
        Trailing returns and the spread vs. each ticker&apos;s benchmark (Rel). Ranked by 3-month return.
      </p>
      {loading && !data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-secondary border-b border-border">
                <th className="text-left py-2 px-3 font-medium">#</th>
                <th className="text-left py-2 px-3 font-medium">Ticker</th>
                <th className="text-right py-2 px-3 font-medium">1M</th>
                <th className="text-right py-2 px-3 font-medium">1M Rel</th>
                <th className="text-right py-2 px-3 font-medium">3M</th>
                <th className="text-right py-2 px-3 font-medium">3M Rel</th>
                <th className="text-right py-2 px-3 font-medium">6M</th>
                <th className="text-right py-2 px-3 font-medium">6M Rel</th>
              </tr>
            </thead>
            <tbody>
              {data?.rankings.map((r, i) => (
                <tr key={r.ticker} className="border-b border-border/50">
                  <td className="py-2 px-3 text-text-muted font-mono">{i + 1}</td>
                  <td className="py-2 px-3 font-mono">{r.ticker}</td>
                  <Cell value={r.ret1m} />
                  <Cell value={r.ret1mRel} />
                  <Cell value={r.ret3m} />
                  <Cell value={r.ret3mRel} />
                  <Cell value={r.ret6m} />
                  <Cell value={r.ret6mRel} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
