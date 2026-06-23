"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ScreenerResponse, ScreenerRow } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { fmtNum, fmtPctFromFraction, exportToCsv } from "@/lib/format";

// Screener fields with how to read & render them.
const FIELDS: { key: string; label: string; group: keyof ScreenerRow | null; pct?: boolean }[] = [
  { key: "peRatio", label: "P/E", group: "valuation" },
  { key: "forwardPE", label: "Fwd P/E", group: "valuation" },
  { key: "pbRatio", label: "P/B", group: "valuation" },
  { key: "dividendYield", label: "Div Yield", group: "valuation", pct: true },
  { key: "debtToEquity", label: "D/E", group: "leverage" },
  { key: "currentRatio", label: "Current", group: "liquidity" },
  { key: "roe", label: "ROE", group: "profitability", pct: true },
  { key: "netMargin", label: "Net Margin", group: "profitability", pct: true },
  { key: "grossMargin", label: "Gross Margin", group: "profitability", pct: true },
  { key: "sharpe", label: "Sharpe", group: null },
  { key: "beta", label: "Beta", group: null },
  { key: "zScore", label: "Z-Score", group: null },
];

interface FilterRow { field: string; op: "lt" | "gt"; value: string; }

function readValue(row: ScreenerRow, key: string): number | null {
  const f = FIELDS.find((x) => x.key === key);
  if (!f) return null;
  const src = f.group === null ? (row as unknown as Record<string, number | null>) : (row[f.group] as Record<string, number | null>);
  return src?.[key] ?? null;
}

function renderValue(row: ScreenerRow, key: string): string {
  const f = FIELDS.find((x) => x.key === key);
  const v = readValue(row, key);
  return f?.pct ? fmtPctFromFraction(v) : fmtNum(v);
}

const DEFAULT_UNIVERSE = "AAPL, MSFT, NVDA, GOOGL, AMZN, META, KO, PG, JPM, XOM, JNJ, WMT";

export function ScreenerTab() {
  const [universe, setUniverse] = useState(DEFAULT_UNIVERSE);
  const [filters, setFilters] = useState<FilterRow[]>([{ field: "peRatio", op: "lt", value: "30" }]);
  const [sort, setSort] = useState("sharpe");
  const [data, setData] = useState<ScreenerResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    const filterStr = filters
      .filter((f) => f.value.trim() !== "" && !Number.isNaN(Number(f.value)))
      .map((f) => `${f.field}:${f.op}:${f.value}`)
      .join(",");
    try {
      setData(await api.screener(universe, filterStr, sort, "1y"));
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  function handleExport() {
    if (!data) return;
    exportToCsv("screener", data.results.map((r) => {
      const row: Record<string, unknown> = { Ticker: r.ticker, Name: r.name, Sector: r.sector ?? "" };
      for (const f of FIELDS) row[f.label] = readValue(r, f.key);
      return row;
    }));
  }

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-sm font-semibold mb-3 text-text-secondary">Universe</h2>
        <textarea
          value={universe}
          onChange={(e) => setUniverse(e.target.value)}
          rows={2}
          className="w-full rounded-lg bg-surface-alt border border-border p-3 text-sm font-mono resize-y focus:outline-none focus:border-accent"
          placeholder="Comma-separated tickers (max 30)"
        />

        <h2 className="text-sm font-semibold mt-5 mb-3 text-text-secondary">Filters</h2>
        <div className="space-y-2">
          {filters.map((f, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <select
                value={f.field}
                onChange={(e) => setFilters((fs) => fs.map((x, j) => j === i ? { ...x, field: e.target.value } : x))}
                className="rounded-md bg-surface-alt border border-border px-2 py-1.5 text-sm"
              >
                {FIELDS.map((fl) => <option key={fl.key} value={fl.key}>{fl.label}</option>)}
              </select>
              <select
                value={f.op}
                onChange={(e) => setFilters((fs) => fs.map((x, j) => j === i ? { ...x, op: e.target.value as "lt" | "gt" } : x))}
                className="rounded-md bg-surface-alt border border-border px-2 py-1.5 text-sm"
              >
                <option value="lt">&lt;</option>
                <option value="gt">&gt;</option>
              </select>
              <input
                type="number" step="any" value={f.value}
                onChange={(e) => setFilters((fs) => fs.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}
                className="w-24 rounded-md bg-surface-alt border border-border px-2 py-1.5 text-sm font-mono"
              />
              <button
                onClick={() => setFilters((fs) => fs.filter((_, j) => j !== i))}
                className="text-text-muted hover:text-danger px-2"
              >×</button>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <button
            onClick={() => setFilters((fs) => [...fs, { field: "roe", op: "gt", value: "0.1" }])}
            className="px-2.5 py-1 rounded-md text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
          >+ Add filter</button>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-text-muted">Sort by</span>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="rounded-md bg-surface-alt border border-border px-2 py-1.5 text-sm"
            >
              {FIELDS.map((fl) => <option key={fl.key} value={fl.key}>{fl.label}</option>)}
            </select>
          </div>
          <button
            onClick={run}
            className="ml-auto px-4 py-1.5 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors"
          >Run screen</button>
        </div>
      </Card>

      {loading ? (
        <Skeleton className="h-48" />
      ) : data ? (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-text-secondary">
              {data.count} of {data.screened} match
            </span>
            <button
              onClick={handleExport}
              className="px-3 py-1 rounded-md text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
            >Export CSV</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-secondary border-b border-border">
                  <th className="text-left py-2 px-3 font-medium sticky left-0 bg-surface">Ticker</th>
                  {FIELDS.map((f) => (
                    <th key={f.key} className={`text-right py-2 px-3 font-medium ${sort === f.key ? "text-accent" : ""}`}>{f.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.results.map((r) => (
                  <tr key={r.ticker} className="border-b border-border/50">
                    <td className="py-2 px-3 font-mono sticky left-0 bg-surface">{r.ticker}</td>
                    {FIELDS.map((f) => (
                      <td key={f.key} className="py-2 px-3 text-right font-mono">{renderValue(r, f.key)}</td>
                    ))}
                  </tr>
                ))}
                {!data.results.length && (
                  <tr><td colSpan={FIELDS.length + 1} className="py-6 text-center text-text-muted">No matches.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card><div className="text-text-muted text-sm">Set filters and run the screen.</div></Card>
      )}
    </div>
  );
}
