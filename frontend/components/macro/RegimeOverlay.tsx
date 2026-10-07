"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MacroRegimeData } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

const QUADRANT_STYLES: Record<number, string> = {
  1: "bg-green-500/20 border-green-500/50 text-green-500 dark:text-green-400",
  2: "bg-yellow-500/20 border-yellow-500/50 text-yellow-500 dark:text-yellow-400",
  3: "bg-orange-500/20 border-orange-500/50 text-orange-500 dark:text-orange-400",
  4: "bg-red-500/20 border-red-500/50 text-red-500 dark:text-red-400",
};

const Z_LABEL = (z: number | null) =>
  z != null ? `${z > 0 ? "+" : ""}${z.toFixed(2)}σ` : "—";

export function RegimeOverlay() {
  const [data, setData] = useState<MacroRegimeData | null>(null);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api.macroRegime().then(setData).catch(console.error);
  }, [refreshNonce]);

  if (!data) return null;

  // Backend couldn't compute a regime (e.g. FRED series unavailable) — show a
  // clear reason instead of a broken card with "undefined" fields.
  if (data.available === false || data.regime == null) {
    return (
      <div className="p-4 border border-border rounded-lg mb-6 bg-surface-alt text-text-secondary text-sm">
        <span className="font-semibold text-text-primary">Macro Regime unavailable.</span>{" "}
        {data.reason ?? "Underlying macro data could not be loaded."}
      </div>
    );
  }

  const palette = QUADRANT_STYLES[data.quadrant] ?? "bg-surface-alt border-border text-text-primary";
  const cpiYoy = data.metrics?.cpi_yoy;

  return (
    <div className={`p-4 border rounded-lg mb-6 flex flex-wrap items-center justify-between gap-4 ${palette}`} {...scope}>
      <div>
        <h3 className="font-bold text-sm">
          Macro Regime: {data.regime}{" "}
          <span className="opacity-60">(Q{data.quadrant})</span>
        </h3>
        <p className="text-xs opacity-80 mt-1">
          <span data-prov="growth_z" data-prov-ctx="Growth signal" title={data.growth_indicator ? `Growth input: ${data.growth_indicator}${data.metrics?.growth_as_of ? `, ${data.metrics.growth_as_of}` : ""}` : undefined}>
            Growth: {data.growth_signal} ({Z_LABEL(data.growth_z)})
          </span>{" "}
          · <span data-prov="inflation_z" data-prov-ctx="Inflation signal">Inflation: {data.inflation_signal} ({cpiYoy != null ? `${cpiYoy}%` : "—"} YoY, {Z_LABEL(data.inflation_z)})</span>
        </p>
        {data.metrics?.fed_funds != null && data.metrics?.yield_spread_2y10y != null && (
          <p className="text-xs opacity-70 mt-0.5">
            <span data-prov="metrics.fed_funds" data-prov-ctx="Fed funds rate">Fed Funds: {data.metrics.fed_funds}%</span> · <span data-prov="metrics.yield_spread_2y10y" data-prov-ctx="10y-2y Treasury spread">2s10s: {data.metrics.yield_spread_2y10y}%</span>
          </p>
        )}
      </div>
      <div className="text-right text-xs">
        <div className="font-semibold mb-1">Asset Allocation</div>
        <div className="flex gap-2 flex-wrap justify-end" data-prov="allocation" data-prov-ctx="Asset allocation rule of thumb">
          {Object.entries(data.allocation ?? {}).map(([asset, weight]) => (
            <span key={asset} className="px-2 py-0.5 bg-black/20 dark:bg-white/10 rounded">
              {asset.toUpperCase()}: {weight}%
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
