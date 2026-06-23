"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ValuationResponse } from "@/lib/types";
import { Card, Skeleton, SignalBadge } from "@/components/ui";
import { fmtNum, fmtPct, fmtPrice, currencySymbol } from "@/lib/format";

interface Params {
  risk_free: number;
  market_premium: number;
  fcf_growth: number;
  terminal_growth: number;
}

const SLIDERS: { key: keyof Params; label: string; min: number; max: number; step: number }[] = [
  { key: "risk_free", label: "Risk-Free Rate", min: 0, max: 0.10, step: 0.001 },
  { key: "market_premium", label: "Market Premium", min: 0, max: 0.15, step: 0.001 },
  { key: "fcf_growth", label: "FCF Growth", min: 0, max: 0.20, step: 0.001 },
  { key: "terminal_growth", label: "Terminal Growth", min: 0, max: 0.05, step: 0.001 },
];

export function ValuationTab({ tickers, period }: { tickers: string[]; period: string }) {
  const [params, setParams] = useState<Params>({
    risk_free: 0.04, market_premium: 0.055, fcf_growth: 0.08, terminal_growth: 0.025,
  });
  const [data, setData] = useState<ValuationResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!tickers.length) return;
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await api.valuation(tickers.join(","), period, params);
        setData(r);
      } catch {
        setData({ valuations: [] });
      } finally {
        setLoading(false);
      }
    }, 500);
    return () => clearTimeout(t);
  }, [tickers, period, params]);

  return (
    <div className="space-y-6">
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {SLIDERS.map((s) => (
            <div key={s.key}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-text-secondary">{s.label}</span>
                <span className="font-mono">{fmtPct(params[s.key] * 100)}</span>
              </div>
              <input
                type="range"
                min={s.min}
                max={s.max}
                step={s.step}
                value={params[s.key]}
                onChange={(e) =>
                  setParams((p) => ({ ...p, [s.key]: parseFloat(e.target.value) }))
                }
                className="w-full accent-accent"
              />
            </div>
          ))}
        </div>
      </Card>

      {loading && !data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data?.valuations.map((v) => (
            <Card key={v.ticker}>
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-lg">{v.ticker}</span>
                <SignalBadge signal={v.signal} />
              </div>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <Row label="Beta" value={fmtNum(v.beta)} />
                <Row label="CAPM Return" value={v.expectedReturn != null ? fmtPct(v.expectedReturn * 100) : "—"} />
                <Row label="Trailing P/E" value={fmtNum(v.trailingPE)} />
                <Row label="Spot" value={fmtPrice(v.spotPrice, currencySymbol(v.currency))} />
                <Row label="DCF Target" value={fmtPrice(v.dcfTarget, currencySymbol(v.currency))} />
              </dl>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-text-secondary">{label}</dt>
      <dd className="text-right font-mono">{value}</dd>
    </>
  );
}
