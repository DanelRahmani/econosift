"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MAData } from "@/lib/types";
import { Card } from "@/components/ui";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

export default function MergersPage() {
  const [data, setData] = useState<MAData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.mergers().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6 p-6">
        <h1 className="text-2xl font-bold">M&A Tracker</h1>
        <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-32 animate-pulse bg-surface-alt rounded" />
        ))}</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">M&A Tracker</h1>
        <div className="text-text-secondary text-sm py-8 text-center">
          M&A data unavailable — Finnhub API may be rate-limited or key not configured.
        </div>
      </div>
    );
  }

  const { deals, monthlyVolume, sectorHeatmap } = data;
  const totalDeals = deals.length;
  const totalValue = deals.reduce((s, d) => s + (d.value ?? 0), 0);
  const sectorsWithDeals = sectorHeatmap.length;

  return (
    <div className="max-w-6xl mx-auto space-y-6 p-6">
      <h1 className="text-2xl font-bold">M&A Tracker</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Announced Deals</div>
          <div className="text-2xl font-bold mt-1">{totalDeals}</div>
          <div className="text-xs text-text-secondary mt-0.5">Last 90 days</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Total Deal Value</div>
          <div className="text-2xl font-bold mt-1">
            {totalValue > 0 ? `$${(totalValue / 1000).toFixed(1)}B` : "—"}
          </div>
          <div className="text-xs text-text-secondary mt-0.5">Estimated</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Active Sectors</div>
          <div className="text-2xl font-bold mt-1">{sectorsWithDeals}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Source</div>
          <div className="text-2xl font-bold mt-1 text-sm">{data.source}</div>
        </Card>
      </div>

      {/* Deal Table */}
      {deals.length > 0 && (
        <Card className="p-4 overflow-x-auto">
          <h3 className="font-semibold mb-3">Recent M&A Deals</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-secondary text-xs">
                <th className="py-2 text-left">Date</th>
                <th className="py-2 text-left">Headline</th>
                <th className="py-2 text-right">Value (est.)</th>
                <th className="py-2 text-right">Sector</th>
              </tr>
            </thead>
            <tbody>
              {deals.slice(0, 20).map((d, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-2 text-text-secondary font-mono text-xs">{d.date}</td>
                  <td className="py-2 max-w-md truncate">
                    {d.url ? (
                      <a href={d.url} target="_blank" rel="noopener noreferrer"
                        className="hover:text-accent transition-colors">
                        {d.headline}
                      </a>
                    ) : d.headline}
                  </td>
                  <td className="py-2 text-right font-mono">
                    {d.value ? `$${(d.value >= 1000 ? (d.value / 1000).toFixed(1) + 'B' : d.value.toFixed(0) + 'M')}` : "—"}
                  </td>
                  <td className="py-2 text-right text-text-secondary">{d.sector}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Monthly Volume Chart */}
      {monthlyVolume.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Monthly Deal Volume</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={monthlyVolume} margin={{ left: 10, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Deals" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Sector Heatmap */}
      {sectorHeatmap.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">M&A Activity by Sector</h3>
          <p className="text-xs text-text-secondary mb-3">Deal count by sector (last 90 days).</p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={sectorHeatmap.map((s) => ({ name: s.sector, value: s.dealCount }))}
              layout="vertical" margin={{ left: 100, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
              <Tooltip formatter={(v: number) => [v, "Deals"]} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {sectorHeatmap.map((s) => (
                  <Cell key={s.sector} fill="#3b82f6" fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {deals.length === 0 && (
        <div className="text-text-secondary text-sm py-8 text-center">
          No M&A deals found in the last 90 days. This may be due to Finnhub API rate limits or no recent merger news.
        </div>
      )}
    </div>
  );
}
