"use client";
import { useQuery } from "@tanstack/react-query";
import { apiQuery } from "@/lib/queries";
import { Card, PageSkeleton, chartPalette } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf, type Provenance } from "@/lib/provenance";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";

export function TaylorRuleWidget() {
  const taylorQ = useQuery(apiQuery("macroTaylorRule"));
  const res = taylorQ.data;
  const loading = taylorQ.isLoading;
  const error: string | null = taylorQ.error ? String(taylorQ.error) : res?.error ?? null;
  const data: any[] = res && !res.error ? res.data || [] : [];
  const prov: Provenance | undefined = res && !res.error ? provOf(res) : undefined;
  const scope = useSourceScope(prov);
  // Use dark as default since chartPalette dark values work reasonably in both themes
  const pal = chartPalette("dark");

  if (loading) return <PageSkeleton text="Loading Taylor Rule…" />;
  if (error) return <div className="text-red-500 text-sm">Failed to load Taylor Rule data: {error}</div>;
  if (!data.length) return null;

  return (
    <Card className="p-5 space-y-4" {...scope}>
      <h2 className="text-base font-semibold text-text-primary">US Taylor Rule & Output Gap</h2>
      <p className="text-sm text-text-secondary">
        Compares the Effective Federal Funds Rate against a standard Taylor Rule prescription (r* = 2%, π* = 2%) and tracks the US output gap.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="h-64" data-prov="data.taylorRate" data-prov-ctx="Taylor rule implied rate">
          <h3 className="text-xs font-semibold text-text-secondary mb-2">Policy Rate vs Taylor Rule</h3>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" tick={{fontSize: 10, fill: pal.axis}} minTickGap={30} />
              <YAxis domain={['auto', 'auto']} fontSize={10} width={30} tick={{fill: pal.axis}} />
              <Tooltip contentStyle={{background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText}} />
              <Legend wrapperStyle={{fontSize: 12}} />
              <Line type="monotone" dataKey="taylorRate" stroke={CHART_COLORS[1]} name="Taylor Rule" dot={false} strokeWidth={2} />
              <Line type="stepAfter" dataKey="fedFunds" stroke={CHART_COLORS[0]} name="Fed Funds" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="h-64" data-prov="data.outputGap" data-prov-ctx="US output gap">
          <h3 className="text-xs font-semibold text-text-secondary mb-2">US Output Gap (%)</h3>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" tick={{fontSize: 10, fill: pal.axis}} minTickGap={30} />
              <YAxis domain={['auto', 'auto']} fontSize={10} width={30} tick={{fill: pal.axis}} />
              <Tooltip contentStyle={{background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText}} />
              <Line type="monotone" dataKey="outputGap" stroke={CHART_COLORS[3]} name="Output Gap" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}
