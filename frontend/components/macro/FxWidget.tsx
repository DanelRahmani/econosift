"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FxResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtNum } from "@/lib/format";
import { useRefreshNonce } from "@/lib/refresh";

const BASES = ["USD", "EUR", "GBP", "JPY", "CHF"];
const TARGETS = "EUR,GBP,JPY,CNY,CHF,CAD,AUD,INR";

export function FxWidget() {
  const [base, setBase] = useState("USD");
  const [data, setData] = useState<FxResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
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
  }, [base, refreshNonce]);

  return (
    <Card {...scope}>
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
            <div key={ccy} className="chip" data-prov={`rates.${ccy}`} data-prov-ctx={`${base}/${ccy}`}>
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
