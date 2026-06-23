"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FxResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { fmtNum } from "@/lib/format";

const BASES = ["USD", "EUR", "GBP", "JPY", "CHF"];
const TARGETS = "EUR,GBP,JPY,CNY,CHF,CAD,AUD,INR";

export function FxWidget() {
  const [base, setBase] = useState("USD");
  const [data, setData] = useState<FxResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.fx(base, TARGETS)
      .then((d) => active && setData(d))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [base]);

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text-secondary">
          FX Rates {data?.date ? `· ${data.date}` : ""}
        </h2>
        <select
          className="input text-sm py-1"
          value={base}
          onChange={(e) => setBase(e.target.value)}
        >
          {BASES.map((b) => (
            <option key={b} value={b} className="bg-surface">{b}</option>
          ))}
        </select>
      </div>
      {loading && !data ? (
        <Skeleton className="h-16" />
      ) : (
        <div className="flex flex-wrap gap-3">
          {data && Object.entries(data.rates).map(([ccy, rate]) => (
            <div key={ccy} className="chip">
              <span className="text-text-muted">{base}/{ccy}</span>
              <span className="text-text-primary">{fmtNum(rate, 4)}</span>
            </div>
          ))}
          {data && Object.keys(data.rates).length === 0 && (
            <span className="text-text-muted text-sm">FX data unavailable.</span>
          )}
        </div>
      )}
    </Card>
  );
}
