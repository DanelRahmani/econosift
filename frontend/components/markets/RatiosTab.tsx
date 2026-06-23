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

const DESCRIPTIONS: Record<string, string> = {
  currentRatio: "Current assets ÷ liabilities — above 1.5 healthy",
  quickRatio: "Excludes inventory from current assets",
  cashRatio: "Strictest liquidity — cash only",
  operatingCFRatio: "Operating cash flow ÷ current liabilities",
  debtToEquity: "Higher = more leveraged",
  debtToAssets: "% of assets financed by debt",
  interestCoverage: "EBIT ÷ interest — ability to pay debt",
  netDebtEbitda: "Years to repay debt from earnings",
  assetTurnover: "Revenue ÷ assets — efficiency",
  inventoryTurnover: "How fast stock is sold",
  receivablesTurnover: "How fast customers pay",
  dso: "Avg days to collect payment",
  grossMargin: "Profit after cost of goods",
  operatingMargin: "Before interest & tax",
  netMargin: "Bottom-line profitability",
  ebitdaMargin: "Cash earnings power",
  roa: "Return on every dollar of assets",
  roe: "Return on shareholder capital",
  fcfMargin: "Free cash flow after capex",
  peRatio: "Price paid per $1 of earnings",
  forwardPE: "Based on next-year estimates",
  pbRatio: "Premium over net asset value",
  psRatio: "Price per dollar of revenue",
  evEbitda: "Popular acquisition multiple",
  evRevenue: "EV per dollar of revenue",
  dividendYield: "Annual dividend ÷ share price",
  eps: "Net income per diluted share",
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
        data-hide-print
      >
        <span className="font-semibold">{title}</span>
        <span className="text-text-muted">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="px-6 pb-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {Object.entries(group).map(([k, v]) => (
            <div key={k} className="flex justify-between items-start border-b border-border/40 py-1.5 gap-2">
              <div className="flex flex-col min-w-0">
                <span className="text-text-secondary">{LABELS[k] ?? k}</span>
                {DESCRIPTIONS[k] && (
                  <span className="text-text-muted text-xs leading-snug">{DESCRIPTIONS[k]}</span>
                )}
              </div>
              <span className="font-mono shrink-0">{fmt(k, v)}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function exportPDF() {
  document.body.classList.add("print-mode");
  window.print();
  document.body.classList.remove("print-mode");
}

export function RatiosTab({ tickers }: { tickers: string[] }) {
  const [selectedTicker, setSelectedTicker] = useState(tickers[0] ?? "");
  const [data, setData] = useState<RatiosResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // If tickers list changes and selected is no longer in it, reset
  useEffect(() => {
    if (!tickers.includes(selectedTicker) && tickers.length > 0) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  useEffect(() => {
    if (!selectedTicker) return;
    let active = true;
    setLoading(true);
    api.ratios(selectedTicker)
      .then((r) => active && setData(r))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [selectedTicker]);

  return (
    <div className="space-y-4">
      {/* Header row: ticker switcher + Export PDF */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {tickers.length > 1 && (
          <div className="flex gap-1">
            {tickers.map((t) => (
              <button
                key={t}
                onClick={() => setSelectedTicker(t)}
                className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
                  selectedTicker === t
                    ? "bg-surface-alt text-text-primary"
                    : "text-text-muted hover:text-text-primary"
                }`}
                data-hide-print
              >
                {t}
              </button>
            ))}
          </div>
        )}
        <button
          onClick={exportPDF}
          className="ml-auto px-3 py-1 rounded-md text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
          data-hide-print
        >
          Export PDF
        </button>
      </div>

      {loading && !data && <Skeleton className="h-64" />}
      {!loading && !data && (
        <div className="text-text-muted text-sm">No ratio data for {selectedTicker}.</div>
      )}
      {data && (
        <>
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
        </>
      )}
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
