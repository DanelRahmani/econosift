"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageSkeleton, chartPalette } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export function FundingLiquidityTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  // Use dark as default since chartPalette dark values work reasonably in both themes
  const pal = chartPalette("dark");

  useEffect(() => {
    api.macroFunding().then(setData).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <PageSkeleton text="Loading funding data…" />;
  if (!data || data.error) return <div className="text-red-500">{data?.error || "Failed to load"}</div>;

  return (
    <div className="space-y-6">
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
                <Tooltip contentStyle={{background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText}} />
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
                <Tooltip contentStyle={{background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText}} />
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
                <Tooltip contentStyle={{background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText}} />
                <Line type="monotone" dataKey="value" stroke={CHART_COLORS[0]} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
