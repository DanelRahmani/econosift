"use client";

import { useState } from "react";
import type { SectorFundamentals } from "@/lib/types";
import { fmtNum, fmtPct, fmtPrice, fmtLarge } from "@/lib/format";

interface Props {
  data: SectorFundamentals[];
}

const TABS = ["Overview", "Valuation", "Performance", "Volatility"] as const;
type Tab = (typeof TABS)[number];

function pctColor(v: number | null) {
  if (v === null) return "";
  return v >= 0 ? "text-success" : "text-danger";
}

function signedPct(v: number | null) {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function SectorFundamentalsTable({ data }: Props) {
  const [tab, setTab] = useState<Tab>("Overview");

  return (
    <div>
      <div className="flex gap-1 mb-3 flex-wrap">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              tab === t
                ? "bg-accent text-white"
                : "text-text-secondary hover:text-text-primary hover:bg-surface-alt"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-text-muted text-xs border-b border-border">
              <th className="text-left py-2 pr-4 font-medium">Sector</th>
              {tab === "Overview" && (
                <>
                  <th className="text-right py-2 px-3 font-medium">Price</th>
                  <th className="text-right py-2 px-3 font-medium">1D%</th>
                  <th className="text-right py-2 px-3 font-medium">1Y%</th>
                  <th className="text-right py-2 px-3 font-medium">AUM</th>
                </>
              )}
              {tab === "Valuation" && (
                <>
                  <th className="text-right py-2 px-3 font-medium">P/E</th>
                  <th className="text-right py-2 px-3 font-medium">P/B</th>
                  <th className="text-right py-2 px-3 font-medium">Div Yield</th>
                </>
              )}
              {tab === "Performance" && (
                <>
                  <th className="text-right py-2 px-3 font-medium">1M%</th>
                  <th className="text-right py-2 px-3 font-medium">3M%</th>
                  <th className="text-right py-2 px-3 font-medium">6M%</th>
                  <th className="text-right py-2 px-3 font-medium">1Y%</th>
                </>
              )}
              {tab === "Volatility" && (
                <>
                  <th className="text-right py-2 px-3 font-medium">Beta</th>
                  <th className="text-right py-2 px-3 font-medium">Vol 30D</th>
                  <th className="text-right py-2 px-3 font-medium">Max DD</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.ticker} className="border-b border-border/40 hover:bg-surface-alt/50">
                <td className="py-2 pr-4">
                  <span className="font-medium text-text-primary">{row.sector}</span>
                  <span className="ml-2 text-xs text-text-muted font-mono">{row.ticker}</span>
                </td>
                {tab === "Overview" && (
                  <>
                    <td className="text-right py-2 px-3 font-mono">{fmtPrice(row.price)}</td>
                    <td className={`text-right py-2 px-3 font-mono ${pctColor(row.return1m)}`}>
                      {signedPct(row.return1m)}
                    </td>
                    <td className={`text-right py-2 px-3 font-mono ${pctColor(row.return1y)}`}>
                      {signedPct(row.return1y)}
                    </td>
                    <td className="text-right py-2 px-3 font-mono text-text-secondary">
                      {row.aum !== null ? `$${fmtLarge(row.aum)}` : "—"}
                    </td>
                  </>
                )}
                {tab === "Valuation" && (
                  <>
                    <td className="text-right py-2 px-3 font-mono">{fmtNum(row.trailingPE)}</td>
                    <td className="text-right py-2 px-3 font-mono">{fmtNum(row.priceToBook)}</td>
                    <td className="text-right py-2 px-3 font-mono">{fmtPct(row.dividendYield)}</td>
                  </>
                )}
                {tab === "Performance" && (
                  <>
                    <td className={`text-right py-2 px-3 font-mono ${pctColor(row.return1m)}`}>
                      {signedPct(row.return1m)}
                    </td>
                    <td className={`text-right py-2 px-3 font-mono ${pctColor(row.return3m)}`}>
                      {signedPct(row.return3m)}
                    </td>
                    <td className={`text-right py-2 px-3 font-mono ${pctColor(row.return6m)}`}>
                      {signedPct(row.return6m)}
                    </td>
                    <td className={`text-right py-2 px-3 font-mono ${pctColor(row.return1y)}`}>
                      {signedPct(row.return1y)}
                    </td>
                  </>
                )}
                {tab === "Volatility" && (
                  <>
                    <td className="text-right py-2 px-3 font-mono">{fmtNum(row.beta)}</td>
                    <td className="text-right py-2 px-3 font-mono">{fmtPct(row.vol30d)}</td>
                    <td className={`text-right py-2 px-3 font-mono ${pctColor(row.maxDrawdown)}`}>
                      {fmtPct(row.maxDrawdown)}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
