"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Quote } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { fmtPct, fmtPrice, currencySymbol } from "@/lib/format";

export function QuoteCards({ tickers }: { tickers: string[] }) {
  const [quotes, setQuotes] = useState<Record<string, Quote | null>>({});

  useEffect(() => {
    let active = true;
    tickers.forEach(async (t) => {
      try {
        const q = await api.quote(t);
        if (active) setQuotes((prev) => ({ ...prev, [t]: q }));
      } catch {
        if (active) setQuotes((prev) => ({ ...prev, [t]: null }));
      }
    });
    return () => {
      active = false;
    };
  }, [tickers]);

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {tickers.map((t) => {
        const q = quotes[t];
        if (q === undefined) return <Skeleton key={t} className="h-24" />;
        const up = (q?.changePercent ?? 0) >= 0;
        return (
          <Card key={t} className="p-4">
            <div className="text-xs text-text-muted font-mono">{t}</div>
            <div className="text-sm text-text-secondary truncate">{q?.name ?? "—"}</div>
            <div className="text-xl font-semibold mt-1">
              {fmtPrice(q?.price ?? null, currencySymbol(q?.currency))}
            </div>
            <div className={`text-sm font-medium ${up ? "text-success" : "text-danger"}`}>
              {q?.changePercent != null ? `${up ? "▲" : "▼"} ${fmtPct(Math.abs(q.changePercent))}` : "—"}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
