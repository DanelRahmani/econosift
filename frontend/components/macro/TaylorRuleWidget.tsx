"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, PageSkeleton, chartPalette } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf, type Provenance } from "@/lib/provenance";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";

export function TaylorRuleWidget() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prov, setProv] = useState<Provenance | undefined>(undefined);
  const scope = useSourceScope(prov);
  // Use dark as default since chartPalette dark values work reasonably in both themes
  const pal = chartPalette("dark");

  useEffect(() => {
    setLoading(true);
    api.macroTaylorRule()
      .then(res => {
        if (res.error) setError(res.error);
        else { setData(res.data || []); setProv(provOf(res)); }
      })
      .catch(e => setError(e.toString()))
      .finally(() => setLoading(false));
  }, []);

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
