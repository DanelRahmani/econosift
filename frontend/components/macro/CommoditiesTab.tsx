"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CommoditiesData, CommodityRow } from "@/lib/types";
import { Card } from "@/components/ui";
import { OilShockDecomposition } from "./OilShockDecomposition";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({
  label,
  value,
  change,
  unit = "",
}: {
  label: string;
  value: number | null;
  change?: number | null;
  unit?: string;
}) {
  const changeColor =
    change != null && change >= 0 ? "text-success" : "text-danger";
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="text-xl font-bold mt-1">
        {value != null ? `${unit}${value.toFixed(2)}` : "—"}
      </div>
      {change != null && (
        <div className={`text-xs mt-0.5 ${changeColor}`}>
          {change >= 0 ? "+" : ""}
          {change.toFixed(2)}% today
        </div>
      )}
    </Card>
  );
}

function pct(v: number | null) {
  if (v == null) return "—";
  const color = v >= 0 ? "text-success" : "text-danger";
  return (
    <span className={color}>
      {v >= 0 ? "+" : ""}
      {v.toFixed(2)}%
    </span>
  );
}

export function CommoditiesTab() {
  const [data, setData] = useState<CommoditiesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .macroCommodities()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Commodities data unavailable — backend endpoint not yet implemented.
      </div>
    );
  }

  const { kpis } = data;
  const goldOilData = (data.ratios?.goldOilRatio ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Gold/Oil Ratio": pt.value,
  }));
  const commodityIndexData = (data.axiomIndex ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "EconoSift Commodity Index": pt.value,
  }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="WTI Crude ($/bbl)" value={kpis.wti} change={kpis.wtiChange1d} unit="$" />
        <KpiCard label="Gold ($/oz)" value={kpis.gold} change={kpis.goldChange1d} unit="$" />
        <KpiCard label="Natural Gas ($/MMBtu)" value={kpis.natGas} unit="$" />
        <KpiCard label="Copper ($/lb)" value={kpis.copper} unit="$" />
        <KpiCard label="Wheat (¢/bu)" value={kpis.wheat} />
      </div>

      {/* Commodities Table */}
      {data.table && data.table.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Commodities Overview</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-secondary border-b border-border">
                  <th className="pb-2 pr-4">Name</th>
                  <th className="pb-2 pr-4 text-right">Price</th>
                  <th className="pb-2 pr-4 text-right">1D</th>
                  <th className="pb-2 pr-4 text-right">1W</th>
                  <th className="pb-2 pr-4 text-right">1M</th>
                  <th className="pb-2 text-right">YTD</th>
                </tr>
              </thead>
              <tbody>
                {data.table.map((row: CommodityRow) => (
                  <tr
                    key={row.ticker}
                    className="border-b border-border/40 hover:bg-surface-alt/30 transition-colors"
                  >
                    <td className="py-2 pr-4">
                      <div className="font-medium">{row.name}</div>
                      <div className="text-xs text-text-secondary">
                        {row.ticker}
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-right font-mono">
                      {row.price != null ? row.price.toFixed(2) : "—"}
                      {row.unit && <div className="text-[10px] text-text-muted">{row.unit}</div>}
                    </td>
                    <td className="py-2 pr-4 text-right">{pct(row.change1d)}</td>
                    <td className="py-2 pr-4 text-right">{pct(row.change1w)}</td>
                    <td className="py-2 pr-4 text-right">{pct(row.change1m)}</td>
                    <td className="py-2 text-right">{pct(row.changeYtd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.asOf && (
            <p className="text-xs text-text-secondary mt-3">
              As of {data.asOf}{data.source ? ` · Source: ${data.source}` : ""}
            </p>
          )}
        </Card>
      )}

      {/* Gold/Oil Ratio */}
      {goldOilData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Gold/Oil Ratio</h3>
          <p className="text-xs text-text-secondary mb-3">
            High ratio: risk-off (recession fears). Low ratio: risk-on (growth
            optimism / supply shock).
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={goldOilData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [v?.toFixed(1), "Gold/Oil"]} />
              <Line
                type="monotone"
                dataKey="Gold/Oil Ratio"
                stroke="#f59e0b"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* EconoSift Commodity Index */}
      {commodityIndexData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">EconoSift Commodity Index</h3>
          <p className="text-xs text-text-secondary mb-3">
            Equal-weighted basket of major commodities, indexed to 100 at inception.
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={commodityIndexData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [v?.toFixed(1), "Index"]} />
              <Area
                type="monotone"
                dataKey="EconoSift Commodity Index"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.25}
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}
      {/* Oil shock decomposition (Phase 39) */}
      <OilShockDecomposition />
    </div>
  );
}
