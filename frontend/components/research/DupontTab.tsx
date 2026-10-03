"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Legend,
} from "recharts";
import { Card, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { DupontResponse } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

const GRID = "rgba(255,255,255,0.08)";

const SECTOR_COLORS: Record<string, string> = {
  "Information Technology": "#3b82f6",
  "Financials": "#10b981",
  "Health Care": "#ef4444",
  "Consumer Discretionary": "#f59e0b",
  "Industrials": "#8b5cf6",
  "Consumer Staples": "#06b6d4",
  "Energy": "#f97316",
  "Materials": "#84cc16",
  "Real Estate": "#ec4899",
  "Communication Services": "#6366f1",
  "Utilities": "#14b8a6",
};

const FALLBACK = "#6b7280";

function fmtPct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtMult(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(2)}×`;
}

function KpiCard({ label, value, fmt, sub, prov }: {
  label: string;
  value: number | null;
  fmt: (v: number | null) => string;
  sub?: string;
  prov?: string;
}) {
  return (
    <Card className="p-4" data-prov={prov} data-prov-ctx={sub}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="text-2xl font-bold mt-1">{fmt(value)}</div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function DupontTab() {
  const [data, setData] = useState<DupontResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api
      .researchDupont()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [refreshNonce]);

  if (loading) {
    return <PageSkeleton text="Computing sector DuPont decomposition…" />;
  }

  if (error || !data || data.error) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        DuPont data unavailable — {data?.error || "backend endpoint may be unavailable"}.
      </div>
    );
  }

  const sectors = data.sectors;

  // ROE bar chart data (sorted by ROE desc)
  const roeData = [...sectors]
    .sort((a, b) => (b.roe ?? 0) - (a.roe ?? 0))
    .map((s) => ({
      ...s,
      roePct: s.roe != null ? s.roe * 100 : null,
    }));

  // Component breakdown — top 6 by ROE for readability
  const componentData = [...sectors]
    .sort((a, b) => (b.roe ?? 0) - (a.roe ?? 0))
    .slice(0, 10)
    .map((s) => ({
      sector: s.sector,
      "Net Margin %": s.netMargin != null ? +(s.netMargin * 100).toFixed(1) : 0,
      "Asset Turnover ×": s.assetTurnover != null ? +s.assetTurnover.toFixed(2) : 0,
      "Equity Multiplier ×": s.equityMultiplier != null ? +s.equityMultiplier.toFixed(1) : 0,
    }));

  const bestRoe = sectors.reduce((best, s) =>
    (s.roe ?? -Infinity) > (best.roe ?? -Infinity) ? s : best
  , sectors[0]);
  const bestMargin = sectors.reduce((best, s) =>
    (s.netMargin ?? -Infinity) > (best.netMargin ?? -Infinity) ? s : best
  , sectors[0]);
  const bestTurnover = sectors.reduce((best, s) =>
    (s.assetTurnover ?? -Infinity) > (best.assetTurnover ?? -Infinity) ? s : best
  , sectors[0]);

  return (
    <div className="space-y-6" {...scope}>
      <p className="text-sm text-text-secondary">
        Median DuPont decomposition per GICS sector from {data.tickerCount} S&P 500
        constituents. ROE = Net Profit Margin × Asset Turnover × Equity Multiplier.
      </p>

      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <KpiCard
          label="Highest ROE"
          prov={`sectors.${bestRoe?.sector}.roe`}
          value={bestRoe?.roe ?? null}
          fmt={fmtPct}
          sub={bestRoe?.sector}
        />
        <KpiCard
          label="Highest Margin"
          prov={`sectors.${bestMargin?.sector}.netMargin`}
          value={bestMargin?.netMargin ?? null}
          fmt={fmtPct}
          sub={bestMargin?.sector}
        />
        <KpiCard
          label="Highest Asset Turnover"
          prov={`sectors.${bestTurnover?.sector}.assetTurnover`}
          value={bestTurnover?.assetTurnover ?? null}
          fmt={fmtMult}
          sub={bestTurnover?.sector}
        />
      </div>

      {/* ROE by Sector */}
      <Card className="p-4">
        <h3 className="font-semibold mb-1">Return on Equity by Sector</h3>
        <p className="text-xs text-text-secondary mb-3">
          Median ROE (Net Income / Shareholder Equity) — sorted highest to lowest
        </p>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={roeData} layout="vertical" margin={{ left: 110, right: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
            <XAxis type="number" tickFormatter={(v) => `${v.toFixed(0)}%`} tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="sector"
              tick={{ fontSize: 11 }}
              width={105}
              interval={0}
            />
            <Tooltip
              formatter={(v: number) => [`${v?.toFixed(1)}%`, "ROE"]}
              contentStyle={{
                backgroundColor: "var(--color-surface-alt)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Bar dataKey="roePct" radius={[0, 4, 4, 0]}>
              {roeData.map((entry) => (
                <Cell
                  key={entry.sector}
                  fill={SECTOR_COLORS[entry.sector] || FALLBACK}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* DuPont Component Breakdown Table */}
      <Card className="p-4">
        <h3 className="font-semibold mb-1">DuPont Component Breakdown</h3>
        <p className="text-xs text-text-secondary mb-3">
          Net Profit Margin = NI/Revenue · Asset Turnover = Revenue/Assets · Equity Multiplier = Assets/Equity
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-secondary text-xs">
                <th className="text-left py-2 pr-4">Sector</th>
                <th className="text-right py-2 px-2"># Tickers</th>
                <th className="text-right py-2 px-2">Net Margin</th>
                <th className="text-right py-2 px-2">Asset Turnover</th>
                <th className="text-right py-2 px-2">Equity Mult.</th>
                <th className="text-right py-2 pl-2 font-semibold text-text-primary">ROE</th>
              </tr>
            </thead>
            <tbody>
              {sectors.map((s) => (
                <tr key={s.sector} data-prov-ctx={s.sector} className="border-b border-border/40 hover:bg-surface-alt/50">
                  <td className="py-2 pr-4 font-medium">{s.sector}</td>
                  <td className="py-2 px-2 text-right text-text-secondary">{s.tickerCount}</td>
                  <td data-prov={`sectors.${s.sector}.netMargin`} className="py-2 px-2 text-right font-mono">{fmtPct(s.netMargin)}</td>
                  <td data-prov={`sectors.${s.sector}.assetTurnover`} className="py-2 px-2 text-right font-mono">{fmtMult(s.assetTurnover)}</td>
                  <td data-prov={`sectors.${s.sector}.equityMultiplier`} className="py-2 px-2 text-right font-mono">{fmtMult(s.equityMultiplier)}</td>
                  <td data-prov={`sectors.${s.sector}.roe`} className="py-2 pl-2 text-right font-mono font-semibold">{fmtPct(s.roe)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
