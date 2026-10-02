"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useValuationFull } from "@/lib/useValuationFull";
import type { ValuationFullResponse, FactorResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtNum, fmtPct } from "@/lib/format";
import { ValuationKpiPanel } from "@/components/markets/ValuationKpiPanel";
import { ValuationModelsGrid } from "@/components/markets/ValuationModelsGrid";
import { EconoSiftGauge } from "@/components/markets/EconoSiftGauge";
import { AnalystPanel } from "@/components/markets/AnalystPanel";
import { SnowflakeChart } from "@/components/markets/SnowflakeChart";

/**
 * Phase 1 valuation engine container. Valuation is per-stock, so when several
 * tickers are loaded we expose a selector and value one at a time. Fetches the
 * full bundle (8 models + composite + fundamentals + analyst) on ticker change
 * (compute tier: runs on load). Fama-French attribution is on-demand (tier 🟡).
 */
export function ValuationEngine({
  tickers,
  onNavigateTab,
}: {
  tickers: string[];
  onNavigateTab?: (tab: string) => void;
}) {
  const [active, setActive] = useState<string>(tickers[0] ?? "");
  const full = useValuationFull(active);
  const data: ValuationFullResponse | null = full.data ?? null;
  const loading = full.isLoading;
  const scope = useSourceScope(provOf(data));

  // Keep the active ticker valid as the ticker list changes.
  useEffect(() => {
    if (!tickers.length) return;
    if (!tickers.includes(active)) setActive(tickers[0]);
  }, [tickers, active]);

  if (!tickers.length) return null;

  return (
    <div className="space-y-6" {...scope} data-prov-ctx={active}>
      {tickers.length > 1 && (
        <div className="flex items-center gap-2" data-hide-print>
          <span className="text-xs text-text-muted">Valuing</span>
          <select
            value={active}
            onChange={(e) => setActive(e.target.value)}
            className="rounded-md bg-surface-alt border border-border px-2 py-1 text-sm text-text-primary font-mono"
          >
            {tickers.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      )}

      {loading && !data ? (
        <div className="space-y-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-64" />
        </div>
      ) : !data ? (
        <Card>
          <div className="text-text-muted">Valuation data unavailable for {active}.</div>
        </Card>
      ) : (
        <div className="space-y-6">
          {data.degraded && (
            <div role="status" className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-text-secondary">
              {full.refreshing ? "Partial data, refreshing… " : "Partial data. "}{data.degradedReason}
            </div>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h3 className="text-sm font-semibold mb-3 text-text-secondary">EconoSift Composite Fair Value</h3>
              <EconoSiftGauge
                composite={data.valuation.axiomFairValue}
                spotPrice={data.valuation.spotPrice}
                currency={data.valuation.currency}
              />
            </Card>
            <Card>
              <h3 className="text-sm font-semibold mb-3 text-text-secondary">Snapshot &amp; Fundamentals</h3>
              <ValuationKpiPanel
                kpis={data.kpis}
                wacc={data.valuation.wacc}
                fundamentals={data.fundamentals}
              />
            </Card>
          </div>

          <SnowflakeChart ticker={active} onAxisClick={onNavigateTab} />

          <Card>
            <h3 className="text-sm font-semibold mb-3 text-text-secondary">Valuation Models</h3>
            <ValuationModelsGrid valuation={data.valuation} />
          </Card>

          <Card>
            <h3 className="text-sm font-semibold mb-3 text-text-secondary">Analyst Data</h3>
            <AnalystPanel analyst={data.analyst} />
          </Card>

          <FamaFrench ticker={active} />
        </div>
      )}
    </div>
  );
}

/** Fama-French factor attribution — compute tier 🟡 (Calculate button). */
function FamaFrench({ ticker }: { ticker: string }) {
  const [model, setModel] = useState<"3" | "5">("3");
  const [data, setData] = useState<FactorResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const scope = useSourceScope(provOf(data));

  function run() {
    setLoading(true);
    setData(null);
    api
      .valuationFactors(ticker, model)
      .then(setData)
      .catch(() => setData({ ticker, model, error: "Factor data unavailable" }))
      .finally(() => setLoading(false));
  }

  return (
    <Card {...scope} data-prov-ctx={ticker}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <h3 className="text-sm font-semibold text-text-secondary">
          Fama-French Factor Attribution
        </h3>
        <div className="flex items-center gap-2" data-hide-print>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value as "3" | "5")}
            className="rounded-md bg-surface-alt border border-border px-2 py-1 text-xs text-text-primary"
          >
            <option value="3">3-Factor</option>
            <option value="5">5-Factor</option>
          </select>
          <button
            onClick={run}
            disabled={loading}
            className="px-3 py-1 rounded-md text-xs font-medium bg-accent text-white disabled:opacity-50"
          >
            {loading ? "Calculating…" : "Calculate"}
          </button>
        </div>
      </div>
      {!data && !loading && (
        <p className="text-xs text-text-muted">
          On-demand regression of returns on the Ken French factors (~3s).
        </p>
      )}
      {loading && <Skeleton className="h-24" />}
      {data && data.error && (
        <p className="text-sm text-text-muted">{data.error}</p>
      )}
      {data && !data.error && data.betas && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-prov="betas">
            {Object.entries(data.betas).map(([k, v]) => (
              <div key={k} className="rounded-lg bg-surface-alt px-3 py-2" data-prov-ctx={k}>
                <div className="text-xs text-text-muted">{k}</div>
                <div className="font-mono text-sm">{fmtNum(v, 3)}</div>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-4 text-xs text-text-muted">
            <span data-prov="alpha">Alpha (ann.): <span className="font-mono text-text-primary">{data.alpha != null ? fmtPct(data.alpha * 100) : "—"}</span></span>
            <span data-prov="rSquared">R²: <span className="font-mono text-text-primary">{fmtNum(data.rSquared, 3)}</span></span>
            <span>n: <span className="font-mono text-text-primary">{data.nObs ?? "—"}</span></span>
          </div>
        </div>
      )}
    </Card>
  );
}
