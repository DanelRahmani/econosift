"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MAData } from "@/lib/types";
import { Card, KpiStrip, KpiTile } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { CHART_COLORS } from "@/lib/format";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useRefreshNonce } from "@/lib/refresh";

const GRID = "rgb(var(--border))";

/**
 * Merger news (P2-27): Finnhub's merger-category news articles, shown as news.
 * Nothing here is a parsed deal — no acquirer, target or value is inferred; the
 * only tickers shown are the ones Finnhub tagged the article with.
 */
export default function MergersPage() {
  const [data, setData] = useState<MAData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api.mergers().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, [refreshNonce]);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6 p-6">
        <h1 className="text-2xl font-bold">Merger News</h1>
        <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-32 animate-pulse bg-surface-alt rounded" />
        ))}</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">Merger News</h1>
        <div className="text-text-secondary text-sm py-8 text-center">
          Merger news unavailable — Finnhub API may be rate-limited or key not configured.
        </div>
      </div>
    );
  }

  const { news, monthlyCount, sectorCount } = data;
  const tagged = news.filter((n) => n.related.length > 0).length;

  return (
    <div className="max-w-6xl mx-auto space-y-6 p-6" {...scope}>
      <div>
        <h1 className="text-2xl font-bold">Merger News</h1>
        <p className="text-sm text-text-secondary mt-1">
          Merger-category news articles from Finnhub. These are news items, not a deal database: no acquirer,
          target or deal value is inferred from the text.
        </p>
      </div>

      {/* KPI Cards */}
      <KpiStrip>
        <KpiTile prov="news" label="News Items" value={news.length} sub="Latest from Finnhub" />
        <KpiTile prov="news" label="Ticker-tagged" value={tagged} sub="Items Finnhub tagged with a ticker" />
        <KpiTile prov="sectorCount" label="Sectors Mentioned" value={sectorCount.length} />
        <KpiTile label="Source" value={data.source} />
      </KpiStrip>

      {/* News table */}
      {news.length > 0 && (
        <Card className="p-4 overflow-x-auto" data-prov="news">
          <h3 className="font-semibold mb-3">Latest Merger News</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-secondary text-xs">
                <th className="py-2 text-left">Date</th>
                <th className="py-2 text-left">Headline</th>
                <th className="py-2 text-left">Tagged tickers</th>
                <th className="py-2 text-right">Sector</th>
                <th className="py-2 text-right">Source</th>
              </tr>
            </thead>
            <tbody>
              {news.slice(0, 30).map((n, i) => (
                <tr key={i} className="border-b border-border/50" data-prov-ctx={n.headline}>
                  <td className="py-2 text-text-secondary font-mono text-xs">{n.date ?? "—"}</td>
                  <td className="py-2 max-w-md truncate">
                    {n.url ? (
                      <a href={n.url} target="_blank" rel="noopener noreferrer"
                        className="hover:text-accent transition-colors">
                        {n.headline}
                      </a>
                    ) : n.headline}
                  </td>
                  <td className="py-2 font-mono text-xs">{n.related.length ? n.related.join(", ") : "—"}</td>
                  <td className="py-2 text-right text-text-secondary">{n.sector ?? "—"}</td>
                  <td className="py-2 text-right text-text-secondary text-xs">{n.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Monthly count */}
      {monthlyCount.length > 0 && (
        <Card className="p-4" data-prov="monthlyCount">
          <h3 className="font-semibold mb-1">Merger News per Month</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={monthlyCount} margin={{ left: 10, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} name="News items" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Sector count */}
      {sectorCount.length > 0 && (
        <Card className="p-4" data-prov="sectorCount">
          <h3 className="font-semibold mb-1">Merger News by Sector</h3>
          <p className="text-xs text-text-secondary mb-3">
            Sector of a ticker Finnhub tagged the article with; untagged items are not counted.
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={sectorCount} layout="vertical" margin={{ left: 100, right: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="sector" tick={{ fontSize: 11 }} width={90} />
              <Tooltip formatter={(v: number) => [v, "News items"]} />
              <Bar dataKey="count" fill={CHART_COLORS[0]} fillOpacity={0.8} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {news.length === 0 && (
        <div className="text-text-secondary text-sm py-8 text-center">
          No merger news returned. This may be due to Finnhub API rate limits or no recent merger news.
        </div>
      )}
    </div>
  );
}
