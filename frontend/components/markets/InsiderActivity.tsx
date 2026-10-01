"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Form4Response, InsiderTransaction } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

function fmt(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function fmtShares(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

function TypeBadge({ type }: { type: "Buy" | "Sell" }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-semibold ${
        type === "Buy"
          ? "bg-success/20 text-success"
          : "bg-danger/20 text-danger"
      }`}
    >
      {type}
    </span>
  );
}

export function InsiderActivity({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Form4Response | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    api
      .marketForm4(ticker)
      .then((d) => {
        if (d.error) setError(d.error);
        setData(d);
      })
      .catch(() => setError("Failed to load insider transactions"))
      .finally(() => setLoading(false));
  }, [ticker]);

  return (
    <Card className="p-4" {...scope} data-prov-ctx={ticker}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Insider Activity (Form 4)</h3>
        <span className="text-xs bg-surface-alt text-text-secondary px-2 py-0.5 rounded">
          EDGAR EDGAR SEC filings
        </span>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 animate-pulse bg-surface-alt rounded" />
          ))}
        </div>
      ) : error ? (
        <p className="text-text-secondary text-sm">{error}</p>
      ) : !data || data.transactions.length === 0 ? (
        <p className="text-text-secondary text-sm">
          No Form 4 data available for {ticker}.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-text-secondary border-b border-border">
                <th className="pb-2 pr-4">Date</th>
                <th className="pb-2 pr-4">Insider</th>
                <th className="pb-2 pr-4">Title</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4 text-right">Shares</th>
                <th className="pb-2 pr-4 text-right">Price</th>
                <th className="pb-2 text-right">Total Value</th>
              </tr>
            </thead>
            <tbody>
              {data.transactions.map((tx: InsiderTransaction, i: number) => (
                <tr
                  key={i}
                  className="border-b border-border/40 hover:bg-surface-alt/30 transition-colors"
                  data-prov-ctx={tx.insiderName}
                >
                  <td className="py-2 pr-4 text-text-secondary text-xs">
                    {tx.date}
                  </td>
                  <td className="py-2 pr-4 font-medium">{tx.insiderName}</td>
                  <td className="py-2 pr-4 text-text-secondary text-xs">
                    {tx.title ?? "—"}
                  </td>
                  <td className="py-2 pr-4" data-prov="transactions.transactionType">
                    <TypeBadge type={tx.transactionType} />
                  </td>
                  <td className="py-2 pr-4 text-right font-mono">
                    {fmtShares(tx.shares)}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono">
                    {tx.pricePerShare != null
                      ? `$${tx.pricePerShare.toFixed(2)}`
                      : "—"}
                  </td>
                  <td
                    data-prov="transactions.totalValue"
                    className={`py-2 text-right font-mono font-semibold ${
                      tx.transactionType === "Buy" ? "text-success" : "text-danger"
                    }`}
                  >
                    {fmt(tx.totalValue)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
