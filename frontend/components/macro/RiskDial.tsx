"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RiskDialData, RiskDialBacktest } from "@/lib/types";
import { Card, ChartSkeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

/**
 * Composite risk dial — Phase 43 (task D3).
 *
 * The standalone indicators (EBP, SLOOS, ANFCI, HY OAS, term spread, SOFR-IORB)
 * each sit in their own tab. Single-signal timing is where blowups come from,
 * so this blends them, shrinks the result hard toward zero, and emits a
 * continuous exposure multiplier — never a binary in/out call.
 *
 * The dial's own walk-forward backtest is published alongside it, including
 * when it loses. A dial that suggests an exposure without showing its record is
 * an opinion with a number attached.
 */

function pct(v: number | null | undefined, d = 2): string {
  return v != null ? `${(v * 100).toFixed(d)}%` : "—";
}

function num(v: number | null | undefined, d = 2): string {
  return v != null ? v.toFixed(d) : "—";
}

function regimeTone(regime?: string): string {
  if (regime === "risk-off") return "text-danger";
  if (regime === "risk-on") return "text-success";
  return "text-text-primary";
}

export function RiskDial() {
  const [data, setData] = useState<RiskDialData | null>(null);
  const [bt, setBt] = useState<RiskDialBacktest | null>(null);
  const [loading, setLoading] = useState(true);
  const scope = useSourceScope(provOf(data));
  const btScope = useSourceScope(provOf(bt));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api.macroRiskDial()
      .then(setData)
      .catch(() => setData({ available: false, reason: "unavailable" }))
      .finally(() => setLoading(false));
    api.macroRiskDialBacktest().then(setBt).catch(() => setBt(null));
  }, [refreshNonce]);

  if (loading) return <ChartSkeleton />;

  if (!data?.available) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-1">Composite Risk Dial</h3>
        <p className="text-sm text-text-secondary">
          Unavailable — {data?.reason ?? "the upstream sources did not return data"}.
        </p>
      </Card>
    );
  }

  const exposure = data.exposureMultiplier ?? 1;
  // Position within the allowed band, for the bar.
  const lo = data.settings?.minExposure ?? 0.4;
  const hi = data.settings?.maxExposure ?? 1.2;
  const fill = Math.max(0, Math.min(1, (exposure - lo) / (hi - lo)));

  return (
    <div className="space-y-4" {...scope}>
      <div>
        <h2 className="font-semibold text-lg">Composite Risk Dial</h2>
        <p className="text-xs text-text-secondary mt-1">
          One number from the indicators that otherwise sit in separate tabs.
          Each is z-scored against its own trailing window, signed so positive
          always means more risk, averaged, then shrunk 50% toward zero.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="p-4 lg:col-span-1" data-prov="exposureMultiplier" data-prov-ctx="Suggested equity exposure">
          <div className="text-xs text-text-secondary">Suggested equity exposure</div>
          <div className={`text-4xl font-bold mt-1 ${regimeTone(data.regime)}`}>
            {exposure.toFixed(2)}×
          </div>
          <div className="text-xs text-text-secondary mt-1 capitalize" data-prov="regime" data-prov-ctx="Risk regime and composite z-score">
            {data.regime} · composite z {num(data.shrunkZ)} (shrunk from {num(data.compositeZ)})
          </div>

          <div className="mt-3 h-2 w-full bg-surface-alt rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all"
              style={{ width: `${fill * 100}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-text-muted mt-1">
            <span>{lo.toFixed(1)}× defensive</span>
            <span>{hi.toFixed(1)}× aggressive</span>
          </div>

          <div className="text-[11px] text-text-muted mt-3">
            {data.componentsUsed}/{data.componentsPossible} components available
          </div>
        </Card>

        <Card className="p-4 lg:col-span-2">
          <h3 className="font-semibold text-sm mb-3">Contributions</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-secondary border-b border-border">
                  <th className="py-1.5 pr-3 font-medium">Indicator</th>
                  <th className="py-1.5 pr-3 font-medium text-right">z</th>
                  <th className="py-1.5 pr-3 font-medium text-right">Signed</th>
                  <th className="py-1.5 font-medium">Reading</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(data.components ?? []).map((c) => (
                  <tr key={c.key} data-prov={`components.${c.key}`} data-prov-ctx={c.label}>
                    <td className="py-1.5 pr-3">{c.label}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">{num(c.z)}</td>
                    <td
                      className={`py-1.5 pr-3 text-right font-mono ${
                        c.contribution > 0 ? "text-danger" : "text-success"
                      }`}
                    >
                      {c.contribution > 0 ? "+" : ""}{num(c.contribution)}
                    </td>
                    <td className="py-1.5 text-xs text-text-secondary">{c.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-text-muted mt-2">
            Positive signed values push exposure down. The term spread is inverted
            because a <em>low</em> spread is the risk signal.
          </p>
        </Card>
      </div>

      {/* The dial's own record */}
      {bt?.available && (
        <Card className={`p-4 ${bt.beatsStatic ? "" : "border-warning/40"}`} {...btScope}>
          <h3 className="font-semibold text-sm mb-1">
            Does this dial actually help?
          </h3>
          <p className="text-xs text-text-secondary mb-3">
            Walk-forward test over {bt.months} months ({bt.start} → {bt.end}):
            scaling SPY exposure by the dial each month, net of {bt.costBps} bps on
            every change in exposure, against simply holding SPY. Each component is
            z-scored on its trailing window only, never the full sample.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-secondary border-b border-border">
                  <th className="py-1.5 pr-4 font-medium"></th>
                  <th className="py-1.5 pr-4 font-medium text-right">CAGR</th>
                  <th className="py-1.5 pr-4 font-medium text-right">Vol</th>
                  <th className="py-1.5 pr-4 font-medium text-right">Sharpe</th>
                  <th className="py-1.5 font-medium text-right">Max DD</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr data-prov-ctx="Dial-scaled (net)">
                  <td className="py-1.5 pr-4">Dial-scaled (net)</td>
                  <td className="py-1.5 pr-4 text-right font-mono">{pct(bt.timed?.cagr)}</td>
                  <td className="py-1.5 pr-4 text-right font-mono">{pct(bt.timed?.vol)}</td>
                  <td className="py-1.5 pr-4 text-right font-mono">{num(bt.timed?.sharpe)}</td>
                  <td className="py-1.5 text-right font-mono">{pct(bt.timed?.maxDrawdown)}</td>
                </tr>
                <tr data-prov="static" data-prov-ctx="Buy & hold SPY">
                  <td className="py-1.5 pr-4">Buy &amp; hold SPY</td>
                  <td className="py-1.5 pr-4 text-right font-mono">{pct(bt.static?.cagr)}</td>
                  <td className="py-1.5 pr-4 text-right font-mono">{pct(bt.static?.vol)}</td>
                  <td className="py-1.5 pr-4 text-right font-mono">{num(bt.static?.sharpe)}</td>
                  <td className="py-1.5 text-right font-mono">{pct(bt.static?.maxDrawdown)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className={`text-xs mt-3 ${bt.beatsStatic ? "text-success" : "text-warning"}`}>
            {bt.verdict}
          </p>
          <p className="text-[11px] text-text-muted mt-1">
            Average exposure {num(bt.avgExposure)}× — close to 1, so the result is not
            simply a leverage effect. Cumulative cost drag {pct(bt.totalCostDrag)}.
          </p>
        </Card>
      )}

      <Card className="p-4">
        <h4 className="text-sm font-semibold mb-1">Method &amp; limitations</h4>
        <p className="text-xs text-text-secondary">{data.method}</p>
        <p className="text-xs text-text-secondary mt-2">{data.caveat}</p>
      </Card>
    </div>
  );
}
