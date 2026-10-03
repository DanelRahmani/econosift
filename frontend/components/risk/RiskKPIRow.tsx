"use client";

import { Card } from "@/components/ui";
import type { RiskMetric, ExtendedRiskTicker } from "@/lib/types";
import { fmtNum, fmtPctFromFraction } from "@/lib/format";
import { useSourceScope } from "@/components/provenance/SourceScope";
import type { Provenance } from "@/lib/provenance";

interface Props {
  base: RiskMetric | null;
  extended: ExtendedRiskTicker | null;
  ticker: string;
  /** Lookback of the extended metrics (max drawdown), e.g. "3y". */
  period?: string;
  /** `provenance` maps of the responses `base` and `extended` came from. */
  baseProv?: Provenance;
  extendedProv?: Provenance;
}

function KPI({
  label, value, sub, danger = false, prov, scope,
}: { label: string; value: string; sub?: string; danger?: boolean; prov?: string; scope?: Record<string, string> }) {
  return (
    <div className="flex flex-col gap-0.5" data-prov={prov} {...scope}>
      <span className="text-xs text-text-muted">{label}</span>
      <span className={`text-lg font-semibold tabular-nums ${danger ? "text-danger" : "text-text-primary"}`}>
        {value}
      </span>
      {sub && <span className="text-xs text-text-muted">{sub}</span>}
    </div>
  );
}

export function RiskKPIRow({ base, extended, ticker, period, baseProv, extendedProv }: Props) {
  const baseScope = useSourceScope(baseProv);
  const extendedScope = useSourceScope(extendedProv);
  const baseKey = `metrics.${base?.ticker ?? ticker}`;
  const extendedKey = `tickers.${extended?.ticker ?? ticker}`;
  const beta = base?.beta ?? null;
  const vol30 = base?.annVolatility ?? null;
  const sharpe = base?.sharpe ?? null;
  const var95 = base?.var95 ?? null;
  const maxDD = extended?.maxDrawdown ?? null;

  return (
    <Card className="p-4" data-prov-ctx={ticker} {...baseScope}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-sm text-text-secondary uppercase tracking-wide">
          {ticker} — Risk Summary
        </h2>
        <span className="text-xs text-text-muted">1-year window · daily closes</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-6">
        <KPI
          prov={`${baseKey}.beta`}
          label="Beta (vs benchmark)"
          value={fmtNum(beta)}
          sub={beta !== null ? (beta > 1.2 ? "High sensitivity" : beta < 0.8 ? "Low sensitivity" : "Moderate") : undefined}
        />
        <KPI
          prov={`${baseKey}.annVolatility`}
          label="Realised Vol (Ann.)"
          value={vol30 !== null ? fmtPctFromFraction(vol30) : "—"}
          sub="1-year window"
          danger={vol30 !== null && vol30 > 0.4}
        />
        <KPI
          prov={`${extendedKey}.maxDrawdown`}
          scope={extendedScope}
          label={`Max Drawdown${period ? ` (${period.toUpperCase()})` : ""}`}
          value={maxDD !== null ? fmtPctFromFraction(maxDD) : "—"}
          danger={maxDD !== null && maxDD < -0.2}
        />
        <KPI
          prov={`${baseKey}.sharpe`}
          label="Sharpe Ratio (1Y)"
          value={fmtNum(sharpe)}
          sub={sharpe !== null ? (sharpe > 1 ? "Good" : sharpe > 0 ? "Moderate" : "Poor") : undefined}
        />
        <KPI
          prov={`${baseKey}.var95`}
          label="VaR 95% (1-day)"
          value={var95 !== null ? fmtPctFromFraction(var95) : "—"}
          sub="Historical (5th pct.)"
          danger={var95 !== null && var95 < -0.03}
        />
      </div>
    </Card>
  );
}
