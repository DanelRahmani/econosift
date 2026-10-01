"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Quote } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
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
        return <QuoteCard key={t} ticker={t} q={q} />;
      })}
    </div>
  );
}

function QuoteCard({ ticker: t, q }: { ticker: string; q: Quote | null }) {
  const scope = useSourceScope(provOf(q));
  const up = (q?.changePercent ?? 0) >= 0;
  return (
    <Card className="p-4" {...scope} data-prov-ctx={t}>
      <div className="text-xs text-text-muted font-mono">{t}</div>
      <div className="text-sm text-text-secondary truncate">{q?.name ?? "—"}</div>
      <div className="text-xl font-semibold mt-1">
        {fmtPrice(q?.price ?? null, currencySymbol(q?.currency))}
      </div>
      <div className={`text-sm font-medium ${up ? "text-success" : "text-danger"}`} data-prov="changePercent">
        {q?.changePercent != null ? `${up ? "▲" : "▼"} ${fmtPct(Math.abs(q.changePercent))}` : "—"}
      </div>
    </Card>
  );
}
