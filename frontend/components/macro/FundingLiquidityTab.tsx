"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { NetLiquidityData } from "@/lib/types";
import { PageSkeleton, Card, chartPalette } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";

function LiqKpi({ label, value, unit = "$tn", sub, color }: {
  label: string; value: number | null | undefined; unit?: string; sub?: string; color?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>
        {value != null ? `${value >= 0 ? "" : "−"}${Math.abs(value).toFixed(2)} ${unit}` : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function FundingLiquidityTab() {
  const [data, setData] = useState<any>(null);
  const [netLiq, setNetLiq] = useState<NetLiquidityData | null>(null);
  const [loading, setLoading] = useState(true);
  // Use dark as default since chartPalette dark values work reasonably in both themes
  const pal = chartPalette("dark");

  useEffect(() => {
    api.macroFunding().then(setData).catch(console.error).finally(() => setLoading(false));
    api.macroNetLiquidity().then(setNetLiq).catch(() => {});
  }, []);

  // Merge net liquidity + SPX by date for the dual-axis overlay
  const overlay = useMemo(() => {
    const nl = netLiq?.history?.netLiquidity ?? [];
    const spxMap = new Map((netLiq?.history?.spx ?? []).map((p) => [p.date, p.value]));
    return nl.map((p) => ({ date: p.date, netLiquidity: p.value, spx: spxMap.get(p.date) ?? null }));
  }, [netLiq]);

  const components = useMemo(() => {
    const h = netLiq?.history;
    if (!h) return [];
    const rrp = new Map(h.rrp.map((p) => [p.date, p.value]));
    const tga = new Map(h.tga.map((p) => [p.date, p.value]));
    const res = new Map(h.reserves.map((p) => [p.date, p.value]));
    return h.fedBalanceSheet.map((p) => ({
      date: p.date,
      fedBalanceSheet: p.value,
      rrp: rrp.get(p.date) ?? null,
      tga: tga.get(p.date) ?? null,
      reserves: res.get(p.date) ?? null,
    }));
  }, [netLiq]);

  // Extended list: most recent 26 weeks, newest first, with WoW change
  const tableRows = useMemo(() => {
    const nl = netLiq?.history?.netLiquidity ?? [];
    return components
      .map((row, i) => ({
        ...row,
        netLiquidity: nl[i]?.value ?? null,
        wow: i > 0 && nl[i]?.value != null && nl[i - 1]?.value != null
          ? (nl[i]!.value as number) - (nl[i - 1]!.value as number)
          : null,
      }))
      .slice(-26)
      .reverse();
  }, [components, netLiq]);

  if (loading) return <PageSkeleton text="Loading funding data…" />;
  if (!data || data.error) return <div className="text-red-500">{data?.error || "Failed to load"}</div>;

  const kpis = netLiq?.kpis;
  const tooltipStyle = { background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText };

  return (
    <div className="space-y-6">
      {/* ── Fed plumbing / net liquidity ─────────────────────────────── */}
      {kpis && (
        <>
          <div>
            <h2 className="font-semibold mb-1">Fed Plumbing — Net Liquidity</h2>
            <p className="text-xs text-text-secondary mb-3">
              Net liquidity = Fed balance sheet (WALCL) − reverse repo (RRP) − Treasury General Account (TGA), weekly.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <LiqKpi label="Net Liquidity" value={kpis.netLiquidity} />
              <LiqKpi
                label="4-Week Change"
                value={kpis.netLiquidity4wChange}
                color={kpis.netLiquidity4wChange != null ? (kpis.netLiquidity4wChange >= 0 ? "text-success" : "text-danger") : undefined}
              />
              <LiqKpi label="Reverse Repo (RRP)" value={kpis.rrp} />
              <LiqKpi label="Treasury Acct (TGA)" value={kpis.tga} />
              <LiqKpi label="Bank Reserves" value={kpis.reserves} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="p-4 bg-surface border border-border rounded-lg shadow-sm">
              <h3 className="font-semibold text-sm mb-2">Net Liquidity vs S&amp;P 500</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={overlay}>
                    <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                    <XAxis dataKey="date" fontSize={10} minTickGap={40} />
                    <YAxis yAxisId="nl" domain={["auto", "auto"]} width={44} fontSize={10} tickFormatter={(v) => `${v}tn`} />
                    <YAxis yAxisId="spx" orientation="right" domain={["auto", "auto"]} width={48} fontSize={10} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line yAxisId="nl" type="monotone" dataKey="netLiquidity" name="Net Liquidity ($tn)" stroke={CHART_COLORS[0]} dot={false} />
                    <Line yAxisId="spx" type="monotone" dataKey="spx" name="S&P 500" stroke={CHART_COLORS[2]} dot={false} strokeDasharray="4 2" connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="p-4 bg-surface border border-border rounded-lg shadow-sm">
              <h3 className="font-semibold text-sm mb-2">Components ($tn)</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={components}>
                    <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                    <XAxis dataKey="date" fontSize={10} minTickGap={40} />
                    <YAxis domain={["auto", "auto"]} width={40} fontSize={10} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="fedBalanceSheet" name="Fed B/S" stroke={CHART_COLORS[1]} dot={false} />
                    <Line type="monotone" dataKey="reserves" name="Reserves" stroke={CHART_COLORS[3]} dot={false} />
                    <Line type="monotone" dataKey="rrp" name="RRP" stroke={CHART_COLORS[0]} dot={false} />
                    <Line type="monotone" dataKey="tga" name="TGA" stroke={CHART_COLORS[2]} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="p-4 bg-surface border border-border rounded-lg shadow-sm overflow-x-auto">
            <h3 className="font-semibold text-sm mb-2">Weekly Detail (last 26 weeks)</h3>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-text-secondary border-b border-border">
                  <th className="py-1.5 pr-3">Week (Wed)</th>
                  <th className="py-1.5 pr-3 text-right">Net Liquidity ($tn)</th>
                  <th className="py-1.5 pr-3 text-right">WoW Δ</th>
                  <th className="py-1.5 pr-3 text-right">Fed B/S</th>
                  <th className="py-1.5 pr-3 text-right">RRP</th>
                  <th className="py-1.5 pr-3 text-right">TGA</th>
                  <th className="py-1.5 text-right">Reserves</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((r) => (
                  <tr key={r.date} className="border-b border-border/50">
                    <td className="py-1.5 pr-3">{r.date}</td>
                    <td className="py-1.5 pr-3 text-right font-medium">{r.netLiquidity?.toFixed(3) ?? "—"}</td>
                    <td className={`py-1.5 pr-3 text-right ${r.wow != null ? (r.wow >= 0 ? "text-success" : "text-danger") : ""}`}>
                      {r.wow != null ? `${r.wow >= 0 ? "+" : ""}${r.wow.toFixed(3)}` : "—"}
                    </td>
                    <td className="py-1.5 pr-3 text-right">{r.fedBalanceSheet?.toFixed(3) ?? "—"}</td>
                    <td className="py-1.5 pr-3 text-right">{r.rrp?.toFixed(3) ?? "—"}</td>
                    <td className="py-1.5 pr-3 text-right">{r.tga?.toFixed(3) ?? "—"}</td>
                    <td className="py-1.5 text-right">{r.reserves?.toFixed(3) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ── Funding rates ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* M2 */}
        <div className="p-4 bg-surface border border-border rounded-lg shadow-sm">
          <h3 className="font-semibold text-sm mb-2">M2 Money Supply</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.m2}>
                <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                <XAxis dataKey="date" hide />
                <YAxis domain={['auto', 'auto']} width={40} fontSize={10} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="value" stroke={CHART_COLORS[1]} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* SOFR */}
        <div className="p-4 bg-surface border border-border rounded-lg shadow-sm">
          <h3 className="font-semibold text-sm mb-2">SOFR</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.sofr}>
                <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                <XAxis dataKey="date" hide />
                <YAxis domain={['auto', 'auto']} width={40} fontSize={10} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="value" stroke={CHART_COLORS[3]} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* CP Spread */}
        <div className="p-4 bg-surface border border-border rounded-lg shadow-sm">
          <h3 className="font-semibold text-sm mb-2">3M CP Spread vs Fed Funds</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.cp_spread}>
                <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                <XAxis dataKey="date" hide />
                <YAxis domain={['auto', 'auto']} width={40} fontSize={10} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="value" stroke={CHART_COLORS[0]} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
