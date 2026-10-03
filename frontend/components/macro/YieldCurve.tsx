"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { useRefreshNonce } from "@/lib/refresh";
import type { YieldCurveResponse } from "@/lib/types";
import { Card, Skeleton, chartTooltipStyle, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtNum } from "@/lib/format";

export function YieldCurve() {
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  const [data, setData] = useState<YieldCurveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the page's Refresh (P1-20)
  useEffect(() => {
    let live = true;
    api.yieldCurve()
      .then((r) => live && setData(r))
      .catch(() => live && setData(null))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [refreshNonce]);

  const rows = data?.points.map((p) => ({ tenor: p.tenor, yield: p.yield })) ?? [];

  return (
    <Card {...scope}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-sm font-semibold text-text-secondary">US Treasury Yield Curve</h2>
        {data && (
          <span data-prov="inverted" data-prov-ctx="Inversion flag" className={`px-2 py-0.5 rounded-md text-xs font-semibold ${
            data.inverted ? "bg-danger/20 text-danger" : "bg-success/20 text-success"
          }`}>
            {data.inverted ? "⚠ Inverted (recession signal)" : "Normal"}
          </span>
        )}
      </div>

      {loading && !data ? (
        <Skeleton className="h-64" />
      ) : !data || rows.every((r) => r.yield === null) ? (
        <div className="text-text-muted text-sm">Yield data unavailable.</div>
      ) : (
        <>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows}>
                <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
                <XAxis dataKey="tenor" tick={{ fill: pal.axis, fontSize: 12 }} />
                <YAxis tick={{ fill: pal.axis, fontSize: 12 }} domain={["auto", "auto"]}
                  tickFormatter={(v) => `${v}%`} />
                <Tooltip {...chartTooltipStyle(theme)} formatter={(v: number) => `${v?.toFixed(2)}%`} />
                <Line type="monotone" dataKey="yield" stroke="#c4394a" strokeWidth={2}
                  dot={{ r: 4, fill: "#c4394a" }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-4 mt-3 text-xs">
            <span className="text-text-muted" data-prov="spread10y3m" data-prov-ctx="10Y–3M spread">
              10Y–3M spread: <span className={`font-mono ${(data.spread10y3m ?? 0) < 0 ? "text-danger" : "text-text-primary"}`}>
                {data.spread10y3m !== null ? `${fmtNum(data.spread10y3m)}%` : "—"}
              </span>
            </span>
            <span className="text-text-muted" data-prov="spread10y5y" data-prov-ctx="10Y–5Y spread">
              10Y–5Y spread: <span className={`font-mono ${(data.spread10y5y ?? 0) < 0 ? "text-danger" : "text-text-primary"}`}>
                {data.spread10y5y !== null ? `${fmtNum(data.spread10y5y)}%` : "—"}
              </span>
            </span>
          </div>
        </>
      )}
    </Card>
  );
}
