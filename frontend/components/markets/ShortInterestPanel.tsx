"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ShortInterestData } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { useRefreshNonce } from "@/lib/refresh";

const GRID = "rgba(255,255,255,0.08)";

function squeezeColor(score: number | null): string {
  if (score === null) return "#6b7280";
  if (score > 100) return "#ef4444";
  if (score > 50) return "#f59e0b";
  return "#10b981";
}

export function ShortInterestPanel() {
  const [data, setData] = useState<ShortInterestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api.marketShortInterest("sp500")
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [refreshNonce]);

  if (loading) {
    return <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => (
      <div key={i} className="h-32 animate-pulse bg-surface-alt rounded" />
    ))}</div>;
  }

  if (error || !data) {
    return <div className="text-text-secondary text-sm py-8 text-center">
      Short interest data unavailable — Finnhub API may be rate-limited or key not configured.
    </div>;
  }

  const { mostShorted, squeezeCandidates, sectorSummary, items } = data;

  return (
    <div className="space-y-6" {...scope}>
      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Tickers Tracked</div>
          <div className="text-2xl font-bold mt-1">{items.length}</div>
          <div className="text-xs text-text-secondary mt-0.5">{data.source}</div>
        </Card>
        <Card className="p-4" data-prov={mostShorted[0] ? `mostShorted.${mostShorted[0].ticker}` : undefined} data-prov-ctx={mostShorted[0]?.ticker}>
          <div className="text-xs text-text-secondary">Most Shorted</div>
          <div className="text-2xl font-bold mt-1 text-danger">
            {mostShorted[0]?.ticker ?? "—"}
          </div>
          <div className="text-xs text-text-secondary mt-0.5">
            {mostShorted[0]?.shortFloat != null ? `${mostShorted[0].shortFloat.toFixed(1)}% of float` : ""}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Squeeze Candidates</div>
          <div className="text-2xl font-bold mt-1 text-warning">
            {squeezeCandidates.length}
          </div>
          <div className="text-xs text-text-secondary mt-0.5">
            SI &gt;25% &amp; days &gt;5
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Avg Short Float</div>
          <div className="text-2xl font-bold mt-1">
            {items.length > 0
              ? (items.reduce((s, i) => s + (i.shortFloat ?? 0), 0) / items.filter(i => i.shortFloat != null).length).toFixed(1) + "%"
              : "—"}
          </div>
        </Card>
      </div>

      {/* Most Shorted Table */}
      {mostShorted.length > 0 && (
        <Card className="p-4 overflow-x-auto">
          <h3 className="font-semibold mb-1">Most Shorted Stocks</h3>
          <p className="text-xs text-text-secondary mb-3">
            Ranked by % of float sold short. High short interest may signal bearish sentiment or potential for a short squeeze.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-secondary text-xs">
                <th className="py-2 text-left">Ticker</th>
                <th className="py-2 text-right">Short % Float</th>
                <th className="py-2 text-right">Days to Cover</th>
                <th className="py-2 text-right">Squeeze Score</th>
                <th className="py-2 text-right">Sector</th>
              </tr>
            </thead>
            <tbody>
              {mostShorted.map((item) => (
                <tr key={item.ticker} className="border-b border-border/50" data-prov={`mostShorted.${item.ticker}`} data-prov-ctx={item.ticker}>
                  <td className="py-2 font-mono font-semibold">{item.ticker}</td>
                  <td className={`py-2 text-right font-mono ${(item.shortFloat ?? 0) > 25 ? "text-danger" : (item.shortFloat ?? 0) > 15 ? "text-warning" : ""}`}>
                    {item.shortFloat != null ? `${item.shortFloat.toFixed(1)}%` : "—"}
                  </td>
                  <td className="py-2 text-right font-mono text-text-secondary">
                    {item.daysToCover != null ? item.daysToCover.toFixed(1) : "—"}
                  </td>
                  <td className="py-2 text-right font-mono" style={{ color: squeezeColor(item.squeezeScore) }} data-prov={`mostShorted.${item.ticker}.squeezeScore`}>
                    {item.squeezeScore != null ? item.squeezeScore.toFixed(1) : "—"}
                  </td>
                  <td className="py-2 text-right text-text-secondary" data-prov={`mostShorted.${item.ticker}.sector`}>{item.sector}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Squeeze Candidates */}
      {squeezeCandidates.length > 0 && (
        <Card className="p-4 border-warning/30 bg-warning/5">
          <h3 className="font-semibold mb-1 text-warning">⚠ Short Squeeze Candidates</h3>
          <p className="text-xs text-text-secondary mb-3">
            Stocks with short interest &gt;25% of float AND days-to-cover &gt;5 — elevated squeeze risk.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {squeezeCandidates.map((item) => (
              <div key={item.ticker} className="text-sm" data-prov={`squeezeCandidates.${item.ticker}`} data-prov-ctx={item.ticker}>
                <span className="font-mono font-semibold">{item.ticker}</span>
                <span className="text-text-secondary text-xs ml-1">
                  SI: {item.shortFloat?.toFixed(0)}% · DTC: {item.daysToCover?.toFixed(0)}d
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Sector Short Interest Bar Chart */}
      {sectorSummary.length > 0 && (
        <Card className="p-4" data-prov="sectorSummary">
          <h3 className="font-semibold mb-1">Sector Average Short Interest</h3>
          <p className="text-xs text-text-secondary mb-3">
            Average % of float sold short by sector.
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={sectorSummary.map((s) => ({ name: s.sector, value: s.avgShortFloat }))}
              layout="vertical" margin={{ left: 100, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} width={90} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Avg Short Float"]} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {sectorSummary.map((s) => (
                  <Cell key={s.sector} fill={s.avgShortFloat > 15 ? "#ef4444" : s.avgShortFloat > 8 ? "#f59e0b" : "#10b981"} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
