"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RatiosResponse, RatioGroup } from "@/lib/types";
import { Card, Skeleton, ZScoreBadge } from "@/components/ui";
import { fmtNum, fmtPctFlex } from "@/lib/format";
import {
  RATIO_GUIDE, ratioTone, ratioRanges, TONE_TEXT, TONE_DOT,
  RISK_METRIC_GUIDES, type RiskMetricGuide,
} from "@/lib/ratioGuide";

const PCT_KEYS = new Set([
  "grossMargin", "operatingMargin", "netMargin", "ebitdaMargin",
  "roa", "roe", "fcfMargin",
]);

// yfinance returns dividendYield as a percentage (e.g. 0.39 = 0.39%), not a fraction
const PCT_DIRECT_KEYS = new Set(["dividendYield"]);

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
  if (PCT_KEYS.has(key)) return fmtPctFlex(v, "fraction");
  if (PCT_DIRECT_KEYS.has(key)) return fmtPctFlex(v, "direct");
  return fmtNum(v);
}

// ──────────────────────────────────────────────────────────────────────────
// Risk metric info row — expandable like RatioRow
// ──────────────────────────────────────────────────────────────────────────

function riskTone(g: RiskMetricGuide, v: number | null): "good" | "normal" | "bad" | null {
  if (v === null || Number.isNaN(v)) return null;
  if (g.dir === "high") {
    if (v >= 1.0) return "good";
    if (v >= 0.5) return "normal";
    return "bad";
  }
  if (g.dir === "low") {
    if (v <= 0.5) return "good";
    if (v <= 1.0) return "normal";
    return "bad";
  }
  // band — for beta
  if (v >= 0.7 && v <= 1.3) return "good";
  if ((v >= 0.4 && v < 0.7) || (v > 1.3 && v <= 2.0)) return "normal";
  return "bad";
}

function MetricInfoRow({
  guide,
  value,
  special,
}: {
  guide: RiskMetricGuide;
  value: number | null;
  special?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const tone = riskTone(guide, value);
  const formatted = value !== null && !Number.isNaN(value) ? fmtNum(value) : "—";

  return (
    <div className="border-b border-border/40 last:border-b-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 py-2.5 text-left hover:bg-surface-alt/50 transition-colors"
      >
        <span className={`h-2 w-2 rounded-full shrink-0 ${tone ? TONE_DOT[tone] : "bg-text-muted/40"}`} />
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-text-secondary text-sm">{guide.label}</span>
          <span className="text-text-muted text-xs leading-snug truncate">{guide.blurb}</span>
        </div>
        <span className={`font-mono shrink-0 tabular-nums text-sm ${tone ? TONE_TEXT[tone] : "text-text-primary"}`}>
          {special ?? formatted}
        </span>
        <span className="text-text-muted text-xs w-4 text-center shrink-0" data-hide-print>
          {open ? "−" : "ⓘ"}
        </span>
      </button>

      {open && (
        <div className="pb-3 pl-5 pr-1 text-xs space-y-2">
          <p className="text-text-secondary leading-relaxed">{guide.meaning}</p>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md px-2 py-1.5 bg-success/10">
              <div className="font-semibold text-success">Favorable</div>
              <div className="text-text-secondary font-mono mt-0.5 leading-tight">{guide.good}</div>
            </div>
            <div className="rounded-md px-2 py-1.5 bg-warning/10">
              <div className="font-semibold text-warning">Average</div>
              <div className="text-text-secondary font-mono mt-0.5 leading-tight">{guide.normal}</div>
            </div>
            <div className="rounded-md px-2 py-1.5 bg-danger/10">
              <div className="font-semibold text-danger">Caution</div>
              <div className="text-text-secondary font-mono mt-0.5 leading-tight">{guide.bad}</div>
            </div>
          </div>
          {guide.exception && (
            <p className="text-text-muted leading-relaxed">
              <span className="font-semibold text-text-secondary">Note: </span>
              {guide.exception}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Ratio row (unchanged logic, minor UI polish)
// ──────────────────────────────────────────────────────────────────────────

function RatioRow({ k, v }: { k: string; v: number | null }) {
  const [open, setOpen] = useState(false);
  const tone = ratioTone(k, v);
  const ranges = ratioRanges(k);
  const guide = RATIO_GUIDE[k];
  const shortDesc = DESCRIPTIONS[k];
  const hasGuide = Boolean(ranges && guide);

  return (
    <div className="border-b border-border/40">
      <button
        onClick={() => hasGuide && setOpen((o) => !o)}
        className={`w-full flex items-center gap-3 py-2.5 text-left ${hasGuide ? "hover:bg-surface-alt/50 transition-colors" : "cursor-default"}`}
      >
        <span className={`h-2 w-2 rounded-full shrink-0 ${tone ? TONE_DOT[tone] : "bg-text-muted/40"}`} />
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-text-secondary">{LABELS[k] ?? k}</span>
          {shortDesc && (
            <span className="text-text-muted text-xs leading-snug truncate">{shortDesc}</span>
          )}
        </div>
        <span className={`font-mono shrink-0 tabular-nums ${tone ? TONE_TEXT[tone] : "text-text-primary"}`}>
          {fmt(k, v)}
        </span>
        {hasGuide && (
          <span className="text-text-muted text-xs w-4 text-center shrink-0" data-hide-print>
            {open ? "−" : "ⓘ"}
          </span>
        )}
      </button>

      {open && hasGuide && ranges && (
        <div className="pb-3 pl-5 pr-1 text-xs space-y-2">
          {guide.meaning && <p className="text-text-secondary leading-relaxed">{guide.meaning}</p>}
          <div className="grid grid-cols-3 gap-2">
            <RangePill tone="good" label="Favorable" value={ranges.good} />
            <RangePill tone="normal" label="Average" value={ranges.normal} />
            <RangePill tone="bad" label="Caution" value={ranges.bad} />
          </div>
          {guide.exception && (
            <p className="text-text-muted leading-relaxed">
              <span className="font-semibold text-text-secondary">Note: </span>
              {guide.exception}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function RangePill({ tone, label, value }: { tone: "good" | "normal" | "bad"; label: string; value: string }) {
  const bg = tone === "good" ? "bg-success/10" : tone === "normal" ? "bg-warning/10" : "bg-danger/10";
  return (
    <div className={`rounded-md px-2 py-1.5 ${bg}`}>
      <div className={`font-semibold ${TONE_TEXT[tone]}`}>{label}</div>
      <div className="text-text-secondary font-mono mt-0.5 leading-tight">{value}</div>
    </div>
  );
}

function Group({ title, group }: { title: string; group: RatioGroup }) {
  const [open, setOpen] = useState(true);
  return (
    <Card className="p-0 overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex justify-between items-center px-6 py-4 hover:bg-surface-alt transition-colors"
        data-hide-print
      >
        <span className="font-semibold">{title}</span>
        <span className="text-text-muted">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="px-6 pb-4 grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-0 text-sm">
          {Object.entries(group).map(([k, v]) => (
            <RatioRow key={k} k={k} v={v} />
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

// ──────────────────────────────────────────────────────────────────────────
// Legend card — explains the colour-coding system at a glance
// ──────────────────────────────────────────────────────────────────────────

function LegendCard() {
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
        <span className="font-semibold text-text-primary mr-1">How to read this page:</span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-success inline-block" />
          <span className="text-success font-medium">Favorable</span>
          <span className="text-text-muted">— metric is in a healthy range</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-warning inline-block" />
          <span className="text-warning font-medium">Average</span>
          <span className="text-text-muted">— acceptable but not standout</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-danger inline-block" />
          <span className="text-danger font-medium">Caution</span>
          <span className="text-text-muted">— warrants attention</span>
        </span>
        <span className="flex items-center gap-1.5 text-text-muted">
          <span className="h-2.5 w-2.5 rounded-full bg-text-muted/40 inline-block" />
          <span>No guide available</span>
        </span>
      </div>
      <p className="text-text-muted text-xs mt-2 border-t border-border/40 pt-2">
        Click any <span className="font-semibold text-text-secondary">ⓘ</span> icon to see the metric's definition, Favorable / Average / Caution thresholds, and any known exceptions. Valuation multiples (P/E, P/B, EV/EBITDA, etc.) use{" "}
        <span className="text-success font-medium">green = cheaper</span>,{" "}
        <span className="text-danger font-medium">red = richer</span>.
      </p>
    </Card>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Main component
// ──────────────────────────────────────────────────────────────────────────

export function RatiosTab({ tickers }: { tickers: string[] }) {
  const [selectedTicker, setSelectedTicker] = useState(tickers[0] ?? "");
  const [data, setData] = useState<RatiosResponse | null>(null);
  const [loading, setLoading] = useState(false);

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
          {/* Legend */}
          <LegendCard />

          {/* Risk & Performance metrics card */}
          <Card className="p-0 overflow-hidden">
            <div className="px-6 py-3 border-b border-border/40">
              <span className="font-semibold text-sm">Risk &amp; Performance</span>
            </div>
            <div className="px-6 pb-2">
              <MetricInfoRow
                guide={RISK_METRIC_GUIDES.beta}
                value={data.beta}
              />
              <MetricInfoRow
                guide={RISK_METRIC_GUIDES.sharpe}
                value={data.sharpe}
              />
              <MetricInfoRow
                guide={RISK_METRIC_GUIDES.sortino}
                value={data.sortino}
              />
              <div className="flex items-center py-2.5 gap-3 border-b border-border/40 last:border-b-0">
                <span className="h-2 w-2 rounded-full shrink-0">
                  {data.zScore === null
                    ? <span className="block h-2 w-2 rounded-full bg-text-muted/40" />
                    : data.zScore > 2.99
                    ? <span className="block h-2 w-2 rounded-full bg-success" />
                    : data.zScore >= 1.81
                    ? <span className="block h-2 w-2 rounded-full bg-warning" />
                    : <span className="block h-2 w-2 rounded-full bg-danger" />
                  }
                </span>
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-text-secondary text-sm">Altman Z-Score</span>
                  <span className="text-text-muted text-xs leading-snug truncate">Bankruptcy risk model (5 financial ratios)…</span>
                </div>
                <ZScoreBadge z={data.zScore} />
                <button
                  onClick={() => {
                    const el = document.getElementById("altman-z-info");
                    if (el) {
                      const hidden = el.classList.toggle("hidden");
                      el.classList.toggle("block", hidden);
                    }
                  }}
                  className="text-text-muted text-xs w-4 text-center shrink-0 hover:text-text-primary transition-colors"
                  data-hide-print
                  aria-label="Altman Z-Score info"
                >
                  ⓘ
                </button>
              </div>
              {/* Altman Z info panel (toggled by ⓘ) */}
              <div id="altman-z-info" className="hidden pb-3 pl-5 pr-1 text-xs space-y-2">
                <p className="text-text-secondary leading-relaxed">{RISK_METRIC_GUIDES.altmanZ.meaning}</p>
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-md px-2 py-1.5 bg-success/10">
                    <div className="font-semibold text-success">Safe Zone</div>
                    <div className="text-text-secondary font-mono mt-0.5 leading-tight">{"> 2.99"}</div>
                  </div>
                  <div className="rounded-md px-2 py-1.5 bg-warning/10">
                    <div className="font-semibold text-warning">Grey Zone</div>
                    <div className="text-text-secondary font-mono mt-0.5 leading-tight">1.81 – 2.99</div>
                  </div>
                  <div className="rounded-md px-2 py-1.5 bg-danger/10">
                    <div className="font-semibold text-danger">Distress Zone</div>
                    <div className="text-text-secondary font-mono mt-0.5 leading-tight">{"< 1.81"}</div>
                  </div>
                </div>
                {RISK_METRIC_GUIDES.altmanZ.exception && (
                  <p className="text-text-muted leading-relaxed">
                    <span className="font-semibold text-text-secondary">Note: </span>
                    {RISK_METRIC_GUIDES.altmanZ.exception}
                  </p>
                )}
              </div>
            </div>
          </Card>

          {/* Ratio groups */}
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
