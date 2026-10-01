"use client";

import type { ScreenerCacheRow } from "@/lib/types";
import { fmtNum, fmtPct, fmtPctFromFraction, fmtLarge, exportToCsv } from "@/lib/format";
import { ratioTone, TONE_TEXT } from "@/lib/ratioGuide";
import type { ResultTab } from "./ResultTabs";

// ─── Column definitions ────────────────────────────────────────────────────

export interface ColDef {
  key: keyof ScreenerCacheRow;
  label: string;
  render: (row: ScreenerCacheRow) => string;
  tone?: (row: ScreenerCacheRow) => string | undefined;
  align?: "left" | "right";
}

function pct(v: number | null | undefined) {
  return fmtPctFromFraction(v);
}
function chgPct(v: number | null | undefined) {
  return fmtPct(v);
}

const TONE_CHG = (v: number | null) => {
  if (v === null) return undefined;
  return v >= 0 ? "text-success" : "text-danger";
};

function boolFmt(v: boolean | null | undefined) {
  if (v === null || v === undefined) return "—";
  return v ? "Yes" : "No";
}

const ALL_COLS: ColDef[] = [
  { key: "symbol",         label: "Symbol",         render: (r) => r.symbol,                          align: "left" },
  { key: "name",           label: "Name",            render: (r) => r.name,                            align: "left" },
  { key: "sector",         label: "Sector",          render: (r) => r.sector ?? "—",                   align: "left" },
  { key: "industry",       label: "Industry",        render: (r) => r.industry ?? "—",                 align: "left" },
  { key: "price",          label: "Price",           render: (r) => fmtNum(r.price) },
  { key: "changePercent",  label: "Chg%",            render: (r) => chgPct(r.changePercent),
    tone: (r) => TONE_CHG(r.changePercent) },
  { key: "marketCap",      label: "Mkt Cap",         render: (r) => fmtLarge(r.marketCap) },
  { key: "volume",         label: "Volume",          render: (r) => fmtLarge(r.volume) },
  { key: "avgVolume20d",   label: "Avg Vol 20d",     render: (r) => fmtLarge(r.avgVolume20d) },
  { key: "volumeRatio",    label: "Vol Ratio",       render: (r) => fmtNum(r.volumeRatio) },
  { key: "pe",             label: "P/E",             render: (r) => fmtNum(r.pe),
    tone: (r) => { const t = ratioTone("peRatio", r.pe); return t ? TONE_TEXT[t] : undefined; } },
  { key: "forwardPE",      label: "Fwd P/E",         render: (r) => fmtNum(r.forwardPE) },
  { key: "eps",            label: "EPS",             render: (r) => fmtNum(r.eps) },
  { key: "dividendYield",  label: "Div Yield",       render: (r) => fmtPct(r.dividendYield),
    tone: (r) => { const t = ratioTone("dividendYield", r.dividendYield); return t ? TONE_TEXT[t] : undefined; } },
  { key: "beta",           label: "Beta",            render: (r) => fmtNum(r.beta) },
  { key: "pb",             label: "P/B",             render: (r) => fmtNum(r.pb),
    tone: (r) => { const t = ratioTone("pbRatio", r.pb); return t ? TONE_TEXT[t] : undefined; } },
  { key: "evEbitda",       label: "EV/EBITDA",       render: (r) => fmtNum(r.evEbitda) },
  { key: "evFcf",          label: "EV/FCF",          render: (r) => fmtNum(r.evFcf) },
  { key: "fcfYield",       label: "FCF Yield",       render: (r) => pct(r.fcfYield) },
  { key: "roic",           label: "ROIC",            render: (r) => pct(r.roic) },
  { key: "psRatio",        label: "P/S",             render: (r) => fmtNum(r.psRatio) },
  { key: "shortFloat",     label: "Short Float",     render: (r) => pct(r.shortFloat) },
  { key: "shortRatio",     label: "Short Ratio",     render: (r) => fmtNum(r.shortRatio) },
  { key: "grossMargin",    label: "Gross Margin",    render: (r) => pct(r.grossMargin),
    tone: (r) => { const t = ratioTone("grossMargin", r.grossMargin); return t ? TONE_TEXT[t] : undefined; } },
  { key: "operatingMargin",label: "Op Margin",       render: (r) => pct(r.operatingMargin),
    tone: (r) => { const t = ratioTone("operatingMargin", r.operatingMargin); return t ? TONE_TEXT[t] : undefined; } },
  { key: "netMargin",      label: "Net Margin",      render: (r) => pct(r.netMargin),
    tone: (r) => { const t = ratioTone("netMargin", r.netMargin); return t ? TONE_TEXT[t] : undefined; } },
  { key: "roe",            label: "ROE",             render: (r) => pct(r.roe),
    tone: (r) => { const t = ratioTone("roe", r.roe); return t ? TONE_TEXT[t] : undefined; } },
  { key: "roa",            label: "ROA",             render: (r) => pct(r.roa),
    tone: (r) => { const t = ratioTone("roa", r.roa); return t ? TONE_TEXT[t] : undefined; } },
  { key: "debtToEquity",   label: "D/E",             render: (r) => fmtNum(r.debtToEquity),
    tone: (r) => { const t = ratioTone("debtToEquity", r.debtToEquity); return t ? TONE_TEXT[t] : undefined; } },
  { key: "currentRatio",   label: "Current Ratio",   render: (r) => fmtNum(r.currentRatio),
    tone: (r) => { const t = ratioTone("currentRatio", r.currentRatio); return t ? TONE_TEXT[t] : undefined; } },
  { key: "revenueGrowth",  label: "Rev Growth",      render: (r) => pct(r.revenueGrowth) },
  { key: "epsGrowth",      label: "EPS Growth",      render: (r) => pct(r.epsGrowth) },
  { key: "sma50",          label: "SMA 50",          render: (r) => fmtNum(r.sma50) },
  { key: "sma200",         label: "SMA 200",         render: (r) => fmtNum(r.sma200) },
  { key: "aboveSma200",    label: "> SMA200",        render: (r) => boolFmt(r.aboveSma200),
    tone: (r) => r.aboveSma200 === true ? "text-success" : r.aboveSma200 === false ? "text-danger" : undefined },
  { key: "goldenCross",    label: "Golden Cross",    render: (r) => boolFmt(r.goldenCross),
    tone: (r) => r.goldenCross === true ? "text-success" : undefined },
  { key: "rsi14",          label: "RSI 14",          render: (r) => fmtNum(r.rsi14) },
  { key: "high52",         label: "52W High",        render: (r) => fmtNum(r.high52) },
  { key: "low52",          label: "52W Low",         render: (r) => fmtNum(r.low52) },
  { key: "pctFromHigh",    label: "% from High",     render: (r) => pct(r.pctFromHigh),
    tone: (r) => TONE_CHG(r.pctFromHigh) },
  { key: "piotroski",      label: "Piotroski",       render: (r) => fmtNum(r.piotroski, 0) },
  { key: "altmanZ",        label: "Altman Z",        render: (r) => fmtNum(r.altmanZ) },
  { key: "esg",            label: "ESG",             render: (r) => fmtNum(r.esg, 1) },
  { key: "earningsRev30d", label: "Earn Rev 30d",    render: (r) => pct(r.earningsRev30d) },
  // Phase 12 columns
  { key: "macd",           label: "MACD",            render: (r) => fmtNum(r.macd, 4) },
  { key: "macdSignal",     label: "MACD Signal",     render: (r) => fmtNum(r.macdSignal, 4) },
  { key: "bbPctB",         label: "BB %B",           render: (r) => fmtNum(r.bbPctB, 3) },
  { key: "bbSqueeze",      label: "BB Squeeze",      render: (r) => boolFmt(r.bbSqueeze),
    tone: (r) => r.bbSqueeze === true ? "text-warning" : undefined },
  { key: "obv",            label: "OBV",             render: (r) => fmtLarge(r.obv) },
  { key: "cmf20",          label: "CMF 20",          render: (r) => fmtNum(r.cmf20, 3),
    tone: (r) => r.cmf20 != null ? (r.cmf20 > 0 ? "text-success" : "text-danger") : undefined },
  { key: "ichimokuBullish",label: "Ichi Bullish",    render: (r) => boolFmt(r.ichimokuBullish),
    tone: (r) => r.ichimokuBullish === true ? "text-success" : r.ichimokuBullish === false ? "text-danger" : undefined },
  { key: "obvDivergence",  label: "OBV Divergence",  render: (r) => boolFmt(r.obvDivergence),
    tone: (r) => r.obvDivergence === true ? "text-warning" : undefined },
];

const COL_MAP = new Map(ALL_COLS.map((c) => [c.key, c]));

function cols(keys: (keyof ScreenerCacheRow)[]): ColDef[] {
  return keys.map((k) => COL_MAP.get(k)!).filter(Boolean);
}

export const TAB_COLS: Record<ResultTab, ColDef[]> = {
  Overview:     cols(["symbol", "name", "sector", "price", "changePercent", "marketCap", "pe", "dividendYield", "beta"]),
  Performance:  cols(["symbol", "price", "changePercent", "high52", "low52", "pctFromHigh", "rsi14"]),
  Technicals:   cols(["symbol", "price", "sma50", "sma200", "aboveSma200", "goldenCross", "rsi14", "volumeRatio", "macd", "bbPctB", "bbSqueeze", "cmf20", "ichimokuBullish", "obvDivergence"]),
  Valuation:    cols(["symbol", "pe", "forwardPE", "pb", "psRatio", "evEbitda", "evFcf", "fcfYield", "eps"]),
  Profitability:cols(["symbol", "grossMargin", "operatingMargin", "netMargin", "roe", "roa", "roic", "debtToEquity", "currentRatio"]),
  Dividends:    cols(["symbol", "dividendYield", "eps", "shortFloat", "shortRatio"]),
  "All Columns":ALL_COLS,
};

// ─── Component ────────────────────────────────────────────────────────────

interface ScreenerTableProps {
  rows: ScreenerCacheRow[];
  tab: ResultTab;
  sort: string;
  dir: "asc" | "desc";
  onSort: (key: string) => void;
}

export function ScreenerTable({ rows, tab, sort, dir, onSort }: ScreenerTableProps) {
  const columns = TAB_COLS[tab];

  function handleExport() {
    exportToCsv("screener", rows.map((r) => {
      const out: Record<string, unknown> = {};
      for (const c of columns) {
        out[c.label] = c.render(r);
      }
      return out;
    }));
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          onClick={handleExport}
          className="px-3 py-1 rounded-md text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
        >
          Export CSV
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            <tr className="text-text-secondary border-b border-border">
              {columns.map((c, i) => (
                <th
                  key={String(c.key)}
                  onClick={() => onSort(String(c.key))}
                  className={`py-2 px-3 font-medium cursor-pointer select-none hover:text-text-primary transition-colors ${
                    i === 0 ? "text-left sticky left-0 bg-surface z-10" : (c.align === "left" ? "text-left" : "text-right")
                  } ${sort === String(c.key) ? "text-accent" : ""}`}
                >
                  {c.label}
                  {sort === String(c.key) && (
                    <span className="ml-1 text-xs">{dir === "asc" ? "▲" : "▼"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-8 text-center text-text-muted">
                  No results match the current filters.
                </td>
              </tr>
            ) : (
              rows.map((row, ri) => (
                <tr
                  key={row.symbol}
                  className={`border-b border-border/50 hover:bg-surface-alt/40 transition-colors ${
                    ri % 2 === 0 ? "" : "bg-surface-alt/20"
                  }`}
                  data-prov-ctx={row.symbol}
                >
                  {columns.map((c, i) => {
                    const text = c.render(row);
                    const toneCls = c.tone ? c.tone(row) : undefined;
                    return (
                      <td
                        key={String(c.key)}
                        className={`py-2 px-3 font-mono ${
                          i === 0
                            ? "sticky left-0 bg-surface font-semibold text-text-primary z-10"
                            : (c.align === "left" ? "text-left" : "text-right")
                        } ${toneCls ?? "text-text-primary"}`}
                      >
                        {text}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export type { ResultTab };
