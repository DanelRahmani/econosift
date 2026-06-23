"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RatiosResponse, RatioGroup } from "@/lib/types";
import { Card, Skeleton, ZScoreBadge } from "@/components/ui";
import { fmtNum, fmtPctFromFraction } from "@/lib/format";

const PCT_KEYS = new Set([
  "grossMargin", "operatingMargin", "netMargin", "ebitdaMargin",
  "roa", "roe", "fcfMargin", "dividendYield",
]);

const LABELS: Record<string, string> = {
  currentRatio: "Current Ratio", quickRatio: "Quick Ratio", cashRatio: "Cash Ratio",
  operatingCFRatio: "Operating CF Ratio", debtToEquity: "Debt / Equity",
  debtToAssets: "Debt / Assets", interestCoverage: "Interest Coverage",
  netDebtEbitda: "Net Debt / EBITDA", assetTurnover: "Asset Turnover",
  inventoryTurnover: "Inventory Turnover", receivablesTurnover: "Receivables Turnover",
  dso: "DSO (days)", grossMargin: "Gross Margin", operatingMargin: "Operating Margin",
  netMargin: "Net Margin", ebitdaMargin: "EBITDA Margin", roa: "ROA", roe: "ROE",
  fcfMargin: "FCF Margin", peRatio: "P/E", forwardPE: "Forward P/E", pbRatio: "P/B",
  psRatio: "P/S", evEbitda: "EV/EBITDA", evRevenue: "EV/Revenue",
  dividendYield: "Dividend Yield", eps: "EPS",
};

function fmt(key: string, v: number | null): string {
  return PCT_KEYS.has(key) ? fmtPctFromFraction(v) : fmtNum(v);
}

function Group({ title, group }: { title: string; group: RatioGroup }) {
  const [open, setOpen] = useState(true);
  return (
    <Card className="p-0 overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex justify-between items-center px-6 py-4 hover:bg-surface-alt"
      >
        <span className="font-semibold">{title}</span>
        <span className="text-text-muted">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="px-6 pb-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {Object.entries(group).map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-border/40 py-1">
              <span className="text-text-secondary">{LABELS[k] ?? k}</span>
              <span className="font-mono">{fmt(k, v)}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function RatiosTab({ ticker }: { ticker: string }) {
  const [data, setData] = useState<RatiosResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    let active = true;
    setLoading(true);
    api.ratios(ticker)
      .then((r) => active && setData(r))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [ticker]);

  if (loading && !data) return <Skeleton className="h-64" />;
  if (!data) return <div className="text-text-muted text-sm">No ratio data for {ticker}.</div>;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap gap-6 items-center text-sm">
          <span className="font-mono text-lg">{data.ticker}</span>
          <Stat label="Beta" value={fmtNum(data.beta)} />
          <Stat label="Sharpe" value={fmtNum(data.sharpe)} />
          <Stat label="Sortino" value={fmtNum(data.sortino)} />
          <div className="flex items-center gap-2">
            <span className="text-text-secondary">Altman Z</span>
            <ZScoreBadge z={data.zScore} />
          </div>
        </div>
      </Card>
      <Group title="Liquidity" group={data.liquidity} />
      <Group title="Leverage" group={data.leverage} />
      <Group title="Efficiency" group={data.efficiency} />
      <Group title="Profitability" group={data.profitability} />
      <Group title="Valuation Multiples" group={data.valuation} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-text-secondary">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}
