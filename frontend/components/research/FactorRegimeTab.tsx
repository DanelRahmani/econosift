"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { FactorRegimeData } from "@/lib/types";
import { PageSkeleton, Card, chartPalette } from "@/components/ui";
import { CHART_COLORS, fmtPctFromFraction } from "@/lib/format";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";

function signColor(v: number | null | undefined): string {
  if (v == null) return "";
  return v >= 0 ? "text-success" : "text-danger";
}

function Kpi({ label, value, sub, color, big = false }: {
  label: string; value: string; sub?: string; color?: string; big?: boolean;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`${big ? "text-xl" : "text-2xl"} font-bold mt-1 ${color ?? ""}`}>{value}</div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function FactorRegimeTab() {
  const [data, setData] = useState<FactorRegimeData | null>(null);
  const [loading, setLoading] = useState(true);
  const pal = chartPalette("dark");

  useEffect(() => {
    api.researchFactorRegime().then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, []);

  const factorKeys = useMemo(() => (data?.factors ?? []).map((f) => f.factor), [data]);
  const cumulative = data?.cumulative ?? [];
  const tooltipStyle = { background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText };

  if (loading) return <PageSkeleton text="Loading factor regime…" />;
  const kpis = data?.kpis;
  if (!data || !data.factors || data.factors.length === 0 || !kpis) {
    return <Card className="p-4"><p className="text-sm text-text-secondary">Factor regime data unavailable.</p></Card>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-semibold mb-1">Factor Regime &amp; Style Rotation</h2>
        <p className="text-xs text-text-secondary mb-3">
          Fama-French 5-factor + momentum, monthly. Trailing compounded returns identify which style is
          leading the market {data.asOf && <>as of {data.asOf}</>}.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Kpi label="Regime" value={kpis.regime ?? "—"} color="text-accent" big />
          <Kpi label="Leading Factor" value={kpis.leadingFactor ?? "—"} />
          <Kpi label="Mkt-RF (3M)" value={fmtPctFromFraction(kpis.mkt3m)} color={signColor(kpis.mkt3m)} />
          <Kpi label="HML (12M)" value={fmtPctFromFraction(kpis.hml12m)} color={signColor(kpis.hml12m)} />
          <Kpi label="SMB (12M)" value={fmtPctFromFraction(kpis.smb12m)} color={signColor(kpis.smb12m)} />
        </div>
      </div>

      <div className="p-4 bg-surface border border-border rounded-lg shadow-sm">
        <h3 className="font-semibold text-sm mb-2">Cumulative Growth of $1 (last 10 years)</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={cumulative}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" fontSize={10} minTickGap={40} />
              <YAxis domain={["auto", "auto"]} width={44} fontSize={10} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {factorKeys.map((key, i) => (
                <Line key={key} type="monotone" dataKey={key} name={key} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="p-4 bg-surface border border-border rounded-lg shadow-sm overflow-x-auto">
        <h3 className="font-semibold text-sm mb-2">Factor Detail</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-text-secondary border-b border-border">
              <th className="py-1.5 pr-3">Factor</th>
              <th className="py-1.5 pr-3 text-right">1M</th>
              <th className="py-1.5 pr-3 text-right">3M</th>
              <th className="py-1.5 pr-3 text-right">12M</th>
              <th className="py-1.5 text-right">12M Rank</th>
            </tr>
          </thead>
          <tbody>
            {data.factors.map((f) => (
              <tr key={f.factor} className="border-b border-border/50">
                <td className="py-1.5 pr-3 font-medium">{f.factor}</td>
                <td className={`py-1.5 pr-3 text-right ${signColor(f.ret1m)}`}>{fmtPctFromFraction(f.ret1m)}</td>
                <td className={`py-1.5 pr-3 text-right ${signColor(f.ret3m)}`}>{fmtPctFromFraction(f.ret3m)}</td>
                <td className={`py-1.5 pr-3 text-right ${signColor(f.ret12m)}`}>{fmtPctFromFraction(f.ret12m)}</td>
                <td className="py-1.5 text-right">{f.momRank ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
