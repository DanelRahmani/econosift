"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { InflationData } from "@/lib/types";
import { Card } from "@/components/ui";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Bar,
  YAxis as YAxisRight,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({
  label,
  value,
  unit = "%",
  color,
}: {
  label: string;
  value: number | null;
  unit?: string;
  color?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>
        {value != null ? `${value.toFixed(2)}${unit}` : "—"}
      </div>
    </Card>
  );
}

function kpiColor(v: number | null, threshold = 3): string {
  if (v == null) return "";
  if (v > threshold) return "text-danger";
  if (v > 2) return "text-warning";
  return "text-success";
}

export function InflationTab() {
  const [data, setData] = useState<InflationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .macroInflation()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Inflation data unavailable — backend endpoint not yet implemented.
      </div>
    );
  }

  const { kpis, history } = data;

  // Chart 1: CPI vs Core CPI vs PCE vs Core PCE
  const cpiMulti = (history.cpiYoY ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "CPI YoY": pt.value,
    "Core CPI YoY": history.coreCpiYoY?.[i]?.value ?? null,
    "PCE YoY": history.pceYoY?.[i]?.value ?? null,
    "Core PCE YoY": history.corePceYoY?.[i]?.value ?? null,
  }));

  // Chart 2: PPI vs CPI
  const ppiData = (history.ppiYoY ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "PPI YoY": pt.value,
    "CPI YoY": history.cpiYoY?.[i]?.value ?? null,
  }));

  // Chart 3: Breakeven inflation
  const beData = (history.breakeven5y ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "5Y Breakeven": pt.value,
    "10Y Breakeven": history.breakeven10y?.[i]?.value ?? null,
    "5Y5Y Forward": history.forward5y5y?.[i]?.value ?? null,
  }));

  // Chart 4: M2 vs CPI (dual axis)
  const m2Data = (history.m2Yoy ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "M2 YoY %": pt.value,
    "CPI YoY": history.cpiYoY?.[i]?.value ?? null,
  }));

  // Chart 5: Quantity Theory — M2 growth vs Nominal GDP growth
  const qtData = (data.quantityTheory?.nominalGdp ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "Nominal GDP YoY": pt.value,
    "M2 YoY": data.quantityTheory?.m2?.[i]?.value ?? null,
  }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard
          label="CPI YoY"
          value={kpis.cpiYoY}
          color={kpiColor(kpis.cpiYoY)}
        />
        <KpiCard
          label="Core CPI YoY"
          value={kpis.coreCpiYoY}
          color={kpiColor(kpis.coreCpiYoY)}
        />
        <KpiCard
          label="PCE YoY"
          value={kpis.pceYoY}
          color={kpiColor(kpis.pceYoY)}
        />
        <KpiCard
          label="Core PCE YoY"
          value={kpis.corePceYoY}
          color={kpiColor(kpis.corePceYoY)}
        />
        <KpiCard label="5Y Breakeven" value={kpis.breakeven5y} />
      </div>

      {/* Chart 1: Inflation measures multi-line */}
      {cpiMulti.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Inflation Measures (YoY %)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={cpiMulti}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <ReferenceLine y={2} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="CPI YoY" stroke="#ef4444" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="Core CPI YoY" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="PCE YoY" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="Core PCE YoY" stroke="#10b981" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Chart 2: PPI vs CPI */}
      {ppiData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">PPI vs CPI (YoY %)</h3>
          <p className="text-xs text-text-secondary mb-3">
            PPI leads CPI — producer price pressures flow through to consumers
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={ppiData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <Line type="monotone" dataKey="PPI YoY" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="CPI YoY" stroke="#ef4444" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Chart 3: Breakeven Inflation */}
      {beData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Breakeven Inflation Expectations</h3>
          <p className="text-xs text-text-secondary mb-3">
            Market-implied inflation derived from TIPS spreads
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={beData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <ReferenceLine y={2} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4"
                label={{ value: "2% Fed target", fill: "rgba(255,255,255,0.4)", fontSize: 11 }} />
              <Line type="monotone" dataKey="5Y Breakeven" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="10Y Breakeven" stroke="#ef4444" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="5Y5Y Forward" stroke="#10b981" dot={false} strokeWidth={1.5} strokeDasharray="4 4" />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Chart 4: M2 vs CPI */}
      {m2Data.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">M2 Money Supply Growth vs CPI</h3>
          <p className="text-xs text-text-secondary mb-3">
            Excess money supply growth tends to precede inflation with a 12–18 month lag
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={m2Data}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <Line type="monotone" dataKey="M2 YoY %" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="CPI YoY" stroke="#ef4444" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Chart 5: Quantity Theory */}
      {qtData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Quantity Theory of Money (MV = PQ)</h3>
          <p className="text-xs text-text-secondary mb-3">
            M2 growth drives nominal GDP: if velocity (V) is stable, money growth → price level growth
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={qtData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <Line type="monotone" dataKey="Nominal GDP YoY" stroke="#3b82f6" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="M2 YoY" stroke="#8b5cf6" dot={false} strokeWidth={1.5} strokeDasharray="5 5" />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
