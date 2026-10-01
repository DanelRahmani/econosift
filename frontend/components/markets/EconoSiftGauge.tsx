"use client";

import { Card, SemiGauge, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { fmtPrice, fmtPct, currencySymbol } from "@/lib/format";
import type { CompositeFairValue } from "@/lib/types";

const VERDICT_COLORS: Record<string, string> = {
  "Significantly Undervalued": "#16a34a",
  Undervalued: "#86c87a",
  "Fairly Valued": "#d97706",
  Overvalued: "#e57373",
  "Significantly Overvalued": "#c4394a",
  "Insufficient Data": "#8a6770",
};

/** Map upsidePct (clamped to ±50%) to a 0–100 gauge value: 0 = overvalued end, 100 = undervalued end. */
function upsideToGaugeValue(upsidePct: number | null): number {
  if (upsidePct === null) return 50;
  const clamped = Math.max(-0.5, Math.min(0.5, upsidePct));
  return (clamped + 0.5) * 100;
}

// ── Component ────────────────────────────────────────────────────────────────
export function EconoSiftGauge({
  composite,
  spotPrice,
  currency,
}: {
  composite: CompositeFairValue;
  spotPrice: number | null;
  currency: string;
}) {
  const { theme } = useTheme();
  const sym = currencySymbol(currency);
  const verdictColor = VERDICT_COLORS[composite.verdict] ?? "#8a6770";
  const isInsufficient =
    composite.verdict === "Insufficient Data" || composite.value === null;

  // Empty gauge (not a mid-scale "fair value" reading) when there is no composite.
  const gaugeValue = isInsufficient ? 0 : upsideToGaugeValue(composite.upsidePct);
  const gaugeColor = isInsufficient ? "#8a6770" : verdictColor;

  // Upside% sign colour
  const upsideColor =
    composite.upsidePct === null
      ? "#8a6770"
      : composite.upsidePct > 0.02
      ? "#16a34a"
      : composite.upsidePct < -0.02
      ? "#c4394a"
      : "#d97706";

  // Weights breakdown — sort descending by weight
  const weights = Object.entries(composite.weightsUsed ?? {}).sort(
    ([, a], [, b]) => b - a
  );

  return (
    <Card className="flex flex-col items-center gap-4 p-5">
      {/* ── Gauge ── */}
      <div className="w-full flex flex-col items-center">
        <SemiGauge
          value={gaugeValue}
          color={gaugeColor}
          trackColor={chartPalette(theme).grid}
          size={220}
        >
          <div className="flex items-center justify-between px-2 text-[10px] font-medium">
            <span className="text-danger">Overvalued</span>
            <span className="text-warning">Fair Value</span>
            <span className="text-success">Undervalued</span>
          </div>
        </SemiGauge>
      </div>

      {/* ── Center readout ── */}
      <div className="text-center space-y-1 -mt-2">
        {isInsufficient ? (
          <p className="text-text-secondary text-sm leading-snug max-w-[240px]" data-prov="valuation.axiomFairValue">
            <span className="font-semibold text-text-muted">n/a</span>
            {" — "}
            {composite.reason ?? "insufficient data to compute a composite fair value"}
          </p>
        ) : (
          <>
            {/* Verdict */}
            <p className="text-sm font-semibold" style={{ color: verdictColor }} data-prov="valuation.axiomFairValue.verdict">
              {composite.verdict}
            </p>

            {/* Fair value vs spot */}
            <div className="flex items-center justify-center gap-3 text-sm">
              <span className="text-text-secondary text-xs">Fair Value</span>
              <span className="font-mono font-semibold text-text-primary" data-prov="valuation.axiomFairValue">
                {fmtPrice(composite.value, sym)}
              </span>
            </div>
            {spotPrice !== null && (
              <div className="flex items-center justify-center gap-3 text-xs text-text-secondary">
                <span>Spot</span>
                <span className="font-mono" data-prov="valuation.spotPrice">{fmtPrice(spotPrice, sym)}</span>
              </div>
            )}

            {/* Upside % */}
            {composite.upsidePct !== null && (
              <p
                className="text-lg font-bold font-mono"
                style={{ color: upsideColor }}
                data-prov="valuation.axiomFairValue.upsidePct"
              >
                {composite.upsidePct >= 0 ? "+" : ""}
                {fmtPct(composite.upsidePct * 100, 1)} upside
              </p>
            )}
          </>
        )}
      </div>

      {/* ── Model weights breakdown ── */}
      {weights.length > 0 && (
        <div className="w-full border-t border-border pt-3" data-prov="valuation.axiomFairValue">
          <p className="text-xs text-text-muted uppercase tracking-wide mb-2">
            Model weights
          </p>
          <div className="space-y-1.5">
            {weights.map(([model, weight]) => (
              <div key={model} className="flex items-center gap-2">
                <span className="text-xs text-text-secondary truncate flex-1">
                  {model}
                </span>
                {/* Mini bar */}
                <div className="h-1.5 w-20 rounded-full bg-surface-alt overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(100, weight * 100)}%`,
                      backgroundColor: "#2F8F83",
                    }}
                  />
                </div>
                <span className="text-xs font-mono text-text-secondary w-10 text-right">
                  {fmtPct(weight * 100, 0)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
