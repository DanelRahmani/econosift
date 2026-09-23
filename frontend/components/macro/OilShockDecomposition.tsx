"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { OilShocksData } from "@/lib/types";
import { Card, ChartSkeleton, chartPalette } from "@/components/ui";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

function fmt(v: number | null | undefined, decimals = 1, suffix = ""): string {
  return v != null ? `${v.toFixed(decimals)}${suffix}` : "—";
}

function Kpi({ label, value, color, sub }: { label: string; value: string; color?: string; sub: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>{value}</div>
      <div className="text-xs text-text-secondary mt-0.5">{sub}</div>
    </Card>
  );
}

export function OilShockDecomposition() {
  const [data, setData] = useState<OilShocksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [months, setMonths] = useState(60);
  const pal = chartPalette("dark");

  useEffect(() => {
    api
      .macroOilShocks()
      .then(setData)
      .catch(() => setData({ available: false, reason: "unavailable" }))
      .finally(() => setLoading(false));
  }, []);

  const chart = useMemo(() => {
    const hist = data?.history ?? [];
    return hist.slice(-months).map((p) => ({
      date: p.date.slice(0, 7),
      Demand: p.demand,
      "Oil-specific": p.supply,
      Total: p.total,
    }));
  }, [data, months]);

  if (loading) return <ChartSkeleton />;

  if (!data?.available) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-1">Oil Shock Decomposition</h3>
        <p className="text-sm text-text-secondary">
          Unavailable — {data?.reason ?? "the upstream source did not return data"}.
        </p>
      </Card>
    );
  }

  const latest = data.latest!;
  const reg = data.regression!;
  const t12 = data.trailing12m!;

  const dominantColor = latest.interpretation === "expansionary" ? "text-success" : "text-danger";

  return (
    <div className="space-y-4">
      <div className="border-t border-border pt-6 mt-2">
        <h2 className="font-semibold text-lg">Oil Shock Decomposition</h2>
        <p className="text-xs text-text-secondary mt-1">
          Kilian (2009) showed the oil <em>price</em> is not an interpretable signal on its
          own: a rise driven by global demand is expansionary for equities, while a
          supply-driven or precautionary rise is contractionary. Kilian &amp; Park (2009)
          find US stock returns respond with opposite signs depending on which dominates.
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi
          label={`Real oil return (${latest.date.slice(0, 7)})`}
          value={fmt(latest.total, 1, "%")}
          color={latest.total >= 0 ? "text-success" : "text-danger"}
          sub="Monthly log return, CPI-deflated"
        />
        <Kpi
          label="Demand component"
          value={fmt(latest.demand, 1, "%")}
          sub="Explained by global activity + copper"
        />
        <Kpi
          label="Oil-specific component"
          value={fmt(latest.supply, 1, "%")}
          sub="Supply / precautionary residual"
        />
        <Kpi
          label="Read-through"
          value={latest.interpretation === "expansionary" ? "Expansionary" : "Contractionary"}
          color={dominantColor}
          sub={`${latest.dominant === "demand" ? "Demand" : "Oil-specific"}-driven this month`}
        />
      </div>

      {/* Decomposition chart */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-semibold">Monthly Return Attribution</h3>
          <div className="flex gap-1">
            {[24, 60, 120].map((m) => (
              <button
                key={m}
                onClick={() => setMonths(m)}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  months === m
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border text-text-muted hover:text-text-primary"
                }`}
              >
                {m}m
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs text-text-secondary mb-3">
          Bars split each month&apos;s real oil move into the part explained by global demand
          proxies and the oil-specific residual. The two sum to the total return net of a
          constant drift term.
        </p>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={chart} stackOffset="sign">
            <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => (v != null ? `${v.toFixed(2)}%` : "—")} />
            <Legend />
            <ReferenceLine y={0} stroke={pal.axis} />
            <Bar dataKey="Demand" stackId="a" fill="#3b82f6" fillOpacity={0.85} />
            <Bar dataKey="Oil-specific" stackId="a" fill="#f59e0b" fillOpacity={0.85} />
            <Line type="monotone" dataKey="Total" stroke="#ef4444" dot={false} strokeWidth={1.4} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      {/* Extended detail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Trailing 12 Months</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-border">
              <tr>
                <td className="py-2 text-text-secondary">Total real oil return</td>
                <td className="py-2 text-right font-mono">{fmt(t12.total, 1, "%")}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Attributed to global demand</td>
                <td className="py-2 text-right font-mono">{fmt(t12.demand, 1, "%")}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Attributed to oil-specific shocks</td>
                <td className="py-2 text-right font-mono">{fmt(t12.supply, 1, "%")}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Months covered</td>
                <td className="py-2 text-right font-mono">{t12.months}</td>
              </tr>
            </tbody>
          </table>
        </Card>

        <Card className="p-4">
          <h3 className="font-semibold mb-3">Model Fit</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-border">
              <tr>
                <td className="py-2 text-text-secondary">Global activity loading (β, t)</td>
                <td className="py-2 text-right font-mono">
                  {fmt(reg.beta_igrea, 3)} <span className="text-text-muted">({fmt(reg.t_igrea, 2)})</span>
                </td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Copper loading (β, t)</td>
                <td className="py-2 text-right font-mono">
                  {fmt(reg.beta_copper, 3)} <span className="text-text-muted">({fmt(reg.t_copper, 2)})</span>
                </td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">R²</td>
                <td className="py-2 text-right font-mono">{fmt(reg.r2, 3)}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Observations</td>
                <td className="py-2 text-right font-mono">{reg.n}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Sample</td>
                <td className="py-2 text-right font-mono text-xs">
                  {reg.sampleStart.slice(0, 7)} → {reg.sampleEnd.slice(0, 7)}
                </td>
              </tr>
            </tbody>
          </table>
          <p className="text-[11px] text-text-muted mt-3">
            A low R² is expected and is itself the point: most oil moves are oil-specific
            rather than global-demand-driven.
          </p>
        </Card>
      </div>

      <Card className="p-4">
        <h4 className="text-sm font-semibold mb-1">Method &amp; limitations</h4>
        <p className="text-xs text-text-secondary">{data.method}</p>
        <p className="text-[11px] text-text-muted mt-2">Sources: {data.sources}</p>
      </Card>
    </div>
  );
}
