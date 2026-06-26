import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";

export function TaylorRuleWidget() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.macroTaylorRule()
      .then(res => {
        if (res.error) setError(res.error);
        else setData(res.data || []);
      })
      .catch(e => setError(e.toString()))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="h-64 animate-pulse bg-surface rounded"></div>;
  if (error) return <div className="text-red-500 text-sm">Failed to load Taylor Rule data: {error}</div>;
  if (!data.length) return null;

  return (
    <Card className="p-5 space-y-4">
      <h2 className="text-base font-semibold text-text-primary">US Taylor Rule & Output Gap</h2>
      <p className="text-sm text-text-secondary">
        Compares the Effective Federal Funds Rate against a standard Taylor Rule prescription (r* = 2%, π* = 2%) and tracks the US output gap.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="h-64">
          <h3 className="text-xs font-semibold text-text-secondary mb-2">Policy Rate vs Taylor Rule</h3>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" tick={{fontSize: 10}} minTickGap={30} />
              <YAxis domain={['auto', 'auto']} fontSize={10} width={30} />
              <Tooltip contentStyle={{background: '#1f2937', border: 'none', fontSize: 12}} />
              <Legend wrapperStyle={{fontSize: 12}} />
              <Line type="monotone" dataKey="taylorRate" stroke="#10b981" name="Taylor Rule" dot={false} strokeWidth={2} />
              <Line type="stepAfter" dataKey="fedFunds" stroke="#3b82f6" name="Fed Funds" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="h-64">
          <h3 className="text-xs font-semibold text-text-secondary mb-2">US Output Gap (%)</h3>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" tick={{fontSize: 10}} minTickGap={30} />
              <YAxis domain={['auto', 'auto']} fontSize={10} width={30} />
              <Tooltip contentStyle={{background: '#1f2937', border: 'none', fontSize: 12}} />
              <Line type="monotone" dataKey="outputGap" stroke="#f59e0b" name="Output Gap" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}
