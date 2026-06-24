"use client";

import { ValuationEngine } from "@/components/markets/ValuationEngine";
import { DcfPanel } from "@/components/markets/DcfPanel";

/**
 * Valuation tab: the Phase 1 valuation engine (8 models + Axiom composite +
 * fundamentals + analyst data) leads, with the interactive two-stage DCF panel
 * (sliders + sensitivity heatmap) below for hands-on scenario work.
 */
export function ValuationTab({ tickers }: { tickers: string[]; period?: string }) {
  if (!tickers.length) return null;
  return (
    <div className="space-y-8">
      <ValuationEngine tickers={tickers} />
      <div>
        <h2 className="text-sm font-semibold mb-3 text-text-secondary">
          Interactive Two-Stage DCF
        </h2>
        <DcfPanel tickers={tickers} />
      </div>
    </div>
  );
}
