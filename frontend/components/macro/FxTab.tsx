"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FxHeatmapData, FxPppData, FxPppPair } from "@/lib/types";
import { Card } from "@/components/ui";
import { FxWidget } from "./FxWidget";

function cellBg(change: number | null): string {
  if (change == null) return "bg-surface-alt";
  if (change > 1) return "bg-success/30";
  if (change > 0.25) return "bg-success/15";
  if (change < -1) return "bg-danger/30";
  if (change < -0.25) return "bg-danger/15";
  return "bg-surface-alt";
}

function cellText(change: number | null): string {
  if (change == null) return "text-text-secondary";
  if (change > 0) return "text-success";
  if (change < 0) return "text-danger";
  return "text-text-primary";
}

function pppBadge(ov: number | null) {
  if (ov == null) return null;
  if (ov > 10)
    return (
      <span className="px-1.5 py-0.5 rounded text-xs bg-danger/20 text-danger">
        Overvalued
      </span>
    );
  if (ov < -10)
    return (
      <span className="px-1.5 py-0.5 rounded text-xs bg-success/20 text-success">
        Undervalued
      </span>
    );
  return (
    <span className="px-1.5 py-0.5 rounded text-xs bg-surface-alt text-text-secondary">
      Fair
    </span>
  );
}

export function FxTab() {
  const [heatmap, setHeatmap] = useState<FxHeatmapData | null>(null);
  const [ppp, setPpp] = useState<FxPppData | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [pppLoading, setPppLoading] = useState(true);
  const [heatmapError, setHeatmapError] = useState(false);
  const [pppError, setPppError] = useState(false);

  useEffect(() => {
    api
      .macroFxHeatmap()
      .then(setHeatmap)
      .catch(() => setHeatmapError(true))
      .finally(() => setHeatmapLoading(false));

    api
      .macroFxPpp()
      .then(setPpp)
      .catch(() => setPppError(true))
      .finally(() => setPppLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Existing FX Widget */}
      <FxWidget />

      {/* FX Heatmap */}
      <Card className="p-4">
        <h3 className="font-semibold mb-3">
          Currency Performance Heatmap (1D % Change)
        </h3>
        {heatmapLoading ? (
          <div className="h-32 animate-pulse bg-surface-alt rounded" />
        ) : heatmapError || !heatmap ? (
          <p className="text-text-secondary text-sm">
            FX heatmap unavailable — backend endpoint not yet implemented.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-2">
              {heatmap.crosses.map((cross) => (
                <div
                  key={cross.pair}
                  className={`rounded p-3 text-center ${cellBg(cross.change1d)}`}
                >
                  <div className="text-xs font-semibold text-text-secondary">
                    {cross.pair}
                  </div>
                  <div className={`text-sm font-bold mt-1 ${cellText(cross.change1d)}`}>
                    {cross.change1d != null
                      ? `${cross.change1d >= 0 ? "+" : ""}${cross.change1d.toFixed(2)}%`
                      : "—"}
                  </div>
                </div>
              ))}
            </div>
            {heatmap.asOf && (
              <p className="text-xs text-text-secondary mt-3">
                As of {heatmap.asOf}
              </p>
            )}
          </>
        )}
      </Card>

      {/* PPP Panel */}
      <Card className="p-4">
        <h3 className="font-semibold mb-1">
          Purchasing Power Parity (PPP) Analysis
        </h3>
        <p className="text-xs text-text-secondary mb-4">
          Based on OECD/IMF PPP estimates. Over/undervaluation relative to the
          USD. A currency is overvalued if spot exceeds PPP.
        </p>
        {pppLoading ? (
          <div className="h-32 animate-pulse bg-surface-alt rounded" />
        ) : pppError || !ppp ? (
          <p className="text-text-secondary text-sm">
            PPP data unavailable — backend endpoint not yet implemented.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-secondary border-b border-border">
                  <th className="pb-2 pr-4">Pair</th>
                  <th className="pb-2 pr-4 text-right">Spot Rate</th>
                  <th className="pb-2 pr-4 text-right">PPP Rate</th>
                  <th className="pb-2 pr-4 text-right">Over/Under %</th>
                  <th className="pb-2">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {ppp.pairs.map((pair: FxPppPair) => (
                  <tr
                    key={pair.pair}
                    className="border-b border-border/40 hover:bg-surface-alt/30 transition-colors"
                  >
                    <td className="py-2 pr-4 font-semibold">{pair.pair}</td>
                    <td className="py-2 pr-4 text-right font-mono">
                      {pair.spot?.toFixed(4) ?? "—"}
                    </td>
                    <td className="py-2 pr-4 text-right font-mono">
                      {pair.ppp?.toFixed(4) ?? "—"}
                    </td>
                    <td
                      className={`py-2 pr-4 text-right font-semibold ${
                        pair.overvaluation != null && pair.overvaluation > 0
                          ? "text-danger"
                          : "text-success"
                      }`}
                    >
                      {pair.overvaluation != null
                        ? `${pair.overvaluation >= 0 ? "+" : ""}${pair.overvaluation.toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="py-2">{pppBadge(pair.overvaluation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
