"use client";

import { Suspense, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { InsiderAggregateResponse } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import Link from "next/link";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({ label, value, sub, prov }: { label: string; value: string; sub?: string; prov?: string }) {
  return (
    <Card className="p-4" data-prov={prov}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

function InsiderPageInner() {
  const [data, setData] = useState<InsiderAggregateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(false);
  const scope = useSourceScope(provOf(data));

  const runAnalysis = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .insiderAggregate()
      .then((d) => {
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => { setLoading(false); setHasRun(true); });
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Insider Trading Aggregator</h1>
        <p className="text-sm text-text-secondary mt-1">
          Aggregated Form 4 insider transactions across S&P 500 — buy/sell ratios, cluster buying, and sector sentiment.
          <span className="ml-2 px-2 py-0.5 rounded bg-warning/20 text-warning text-xs font-semibold">🟡 Compute Tier</span>
        </p>
      </div>

      {!hasRun && !loading && (
        <div className="text-center py-16 space-y-4">
          <p className="text-text-secondary text-sm">
            This analysis iterates over ~500 S&P 500 constituents calling EDGAR Form 4 filings.
            First run takes 60-120 seconds due to rate limiting. Results are cached for 6 hours.
          </p>
          <button
            onClick={runAnalysis}
            className="px-8 py-3 bg-accent text-white rounded-lg text-lg font-semibold hover:bg-accent/90 transition-colors"
          >
            🟡 Run Analysis
          </button>
        </div>
      )}

      {loading && <PageSkeleton text="Aggregating insider transactions across S&P 500… This may take 60-120s." />}

      {error && !loading && (
        <div className="text-danger text-sm py-4 text-center bg-danger/10 rounded-lg">{error}</div>
      )}

      {data && !loading && (
        <div className="space-y-6" {...scope}>
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <KpiCard label="Tickers with Data" value={`${data.tickersWithData}/${data.tickersChecked}`} />
            <KpiCard
              prov="buySellRatio"
              label="Buy/Sell Ratio"
              value={data.buySellRatio != null ? data.buySellRatio.toFixed(2) : "—"}
              sub={data.buySellRatio != null && data.buySellRatio > 1 ? "More buys than sells" : "More sells than buys"}
            />
            <KpiCard prov="valueRatio" label="Total Buy Value" value={`$${(data.totalBuyValue / 1e6).toFixed(0)}M`} />
            <KpiCard prov="valueRatio" label="Total Sell Value" value={`$${(data.totalSellValue / 1e6).toFixed(0)}M`} />
          </div>

          {/* Sector Sentiment */}
          {data.sectorSentiment.length > 0 && (
            <Card className="p-4" data-prov="sectorSentiment">
              <h3 className="font-semibold mb-1">Sector Insider Sentiment</h3>
              <p className="text-xs text-text-secondary mb-3">
                Net buy ratio = (buys − sells) / total. Positive = net buying, negative = net selling.
              </p>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={data.sectorSentiment} layout="vertical" margin={{ left: 110 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => v.toFixed(2)} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="sector" tick={{ fontSize: 11 }} width={105} interval={0} />
                  <Tooltip
                    formatter={(v: number, name: string) => [v.toFixed(3), name]}
                    contentStyle={{ backgroundColor: "var(--color-surface-alt)", border: "1px solid var(--color-border)", borderRadius: 8, fontSize: 12 }}
                  />
                  <Bar dataKey="netBuyRatio" radius={[0, 4, 4, 0]}>
                    {data.sectorSentiment.map((s) => (
                      <Cell key={s.sector} fill={s.netBuyRatio >= 0 ? "#10b981" : "#ef4444"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Cluster Buys */}
          {data.clusterBuys.length > 0 && (
            <Card className="p-4" data-prov="clusterBuys">
              <h3 className="font-semibold mb-1">🟢 Cluster Buys</h3>
              <p className="text-xs text-text-secondary mb-3">
                Stocks with ≥3 unique insiders buying within the last 30 days — potential bullish signal.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-text-secondary text-xs">
                      <th className="text-left py-2 pr-4">Ticker</th>
                      <th className="text-right py-2 px-2">Insiders</th>
                      <th className="text-right py-2 px-2">Transactions</th>
                      <th className="text-right py-2 px-2">Total Value</th>
                      <th className="text-right py-2 pl-2">Date Range</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.clusterBuys.map((c) => (
                      <tr key={c.ticker} className="border-b border-border/40" data-prov-ctx={c.ticker}>
                        <td className="py-2 pr-4">
                          <Link href={`/markets?ticker=${c.ticker}`} className="font-mono font-semibold hover:text-accent">{c.ticker}</Link>
                        </td>
                        <td className="py-2 px-2 text-right text-success font-semibold">{c.insiderCount}</td>
                        <td className="py-2 px-2 text-right">{c.transactionCount}</td>
                        <td className="py-2 px-2 text-right font-mono">${(c.totalValue / 1e6).toFixed(1)}M</td>
                        <td className="py-2 pl-2 text-right text-xs text-text-secondary">{c.dateRange}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Top Trades */}
          {data.topTrades.length > 0 && (
            <Card className="p-4" data-prov="topTrades">
              <h3 className="font-semibold mb-1">Top Individual Insider Trades</h3>
              <p className="text-xs text-text-secondary mb-3">Largest Form 4 transactions by total value across the S&P 500.</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-text-secondary text-xs">
                      <th className="text-left py-2 pr-2">Insider</th>
                      <th className="text-left py-2 px-2">Ticker</th>
                      <th className="text-center py-2 px-2">Type</th>
                      <th className="text-right py-2 px-2">Value</th>
                      <th className="text-right py-2 pl-2">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.topTrades.slice(0, 15).map((tx, i) => (
                      <tr key={i} className="border-b border-border/40" data-prov-ctx={`${tx.insiderName} · ${tx.ticker}`}>
                        <td className="py-2 pr-2 max-w-[180px] truncate" title={tx.insiderName}>{tx.insiderName}</td>
                        <td className="py-2 px-2">
                          <Link href={`/markets?ticker=${tx.ticker}`} className="font-mono hover:text-accent">{tx.ticker}</Link>
                        </td>
                        <td className="py-2 px-2 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${tx.transactionType === "Buy" ? "bg-success/20 text-success" : "bg-danger/20 text-danger"}`}>
                            {tx.transactionType}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-right font-mono">${((tx.totalValue ?? 0) / 1e6).toFixed(1)}M</td>
                        <td className="py-2 pl-2 text-right text-text-secondary text-xs">{tx.date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <p className="text-xs text-text-muted text-center">
            Data from SEC EDGAR Form 4 filings. As of {data.asOf}. Cached for 6 hours.
          </p>
        </div>
      )}
    </div>
  );
}

export default function InsiderPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted">Loading…</div>}>
      <InsiderPageInner />
    </Suspense>
  );
}
