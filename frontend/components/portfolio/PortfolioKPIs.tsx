"use client";

import type { PortfolioAnalysis } from "@/lib/types";
import { MetricTooltip } from "@/components/MetricTooltip";
import { WalkthroughBanner } from "@/components/WalkthroughBanner";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  data: PortfolioAnalysis | null;
  loading: boolean;
}

function fmt(v: number | null | undefined, decimals = 2, suffix = "%") {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(decimals)}${suffix}`;
}

function fmtRaw(v: number | null | undefined, decimals = 2) {
  if (v === null || v === undefined) return "—";
  return v.toFixed(decimals);
}

interface KPICardProps {
  label: React.ReactNode;
  value: string;
  color?: string;
  prov?: string;
}

function KPICard({ label, value, color, prov }: KPICardProps) {
  return (
    <div data-prov={prov} className="bg-surface-alt rounded-lg p-3 flex flex-col gap-1 min-w-[120px]">
      <span className="text-xs text-text-muted">{label}</span>
      <span className={`text-xl font-bold tabular-nums ${color ?? "text-text-primary"}`}>
        {value}
      </span>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-surface-alt rounded-lg p-3 min-w-[120px] animate-pulse">
      <div className="h-3 w-16 bg-border rounded mb-2" />
      <div className="h-7 w-20 bg-border rounded" />
    </div>
  );
}

export function PortfolioKPIs({ data, loading }: Props) {
  const scope = useSourceScope(provOf(data));

  if (loading) {
    return (
      <div className="flex gap-3 flex-wrap">
        {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (!data) return null;

  const m = data.metrics;

  const totalReturn = m.totalReturn !== null ? m.totalReturn * 100 : null;
  const annReturn = m.annReturn !== null ? m.annReturn * 100 : null;
  const annVol = m.annVolatility !== null ? m.annVolatility * 100 : null;
  const maxDD = m.maxDrawdown !== null ? m.maxDrawdown * 100 : null;

  function retColor(v: number | null) {
    if (v === null) return undefined;
    return v >= 0 ? "text-green-500" : "text-red-500";
  }

  function ddColor(v: number | null) {
    if (v === null) return undefined;
    return v <= -10 ? "text-red-500" : "text-text-primary";
  }

  return (
    <div className="flex gap-3 flex-wrap" {...scope}>
      <KPICard
        prov="metrics.totalReturn"
        label={<MetricTooltip metricKey="totalReturn">Total Return</MetricTooltip>}
        value={totalReturn !== null ? `${totalReturn.toFixed(2)}%` : "—"}
        color={retColor(totalReturn)}
      />
      <KPICard
        prov="metrics.annReturn"
        label={<MetricTooltip metricKey="annReturn">Ann. Return</MetricTooltip>}
        value={annReturn !== null ? `${annReturn.toFixed(2)}%` : "—"}
        color={retColor(annReturn)}
      />
      <KPICard
        prov="metrics.annVolatility"
        label={<MetricTooltip metricKey="volatility">Ann. Volatility</MetricTooltip>}
        value={annVol !== null ? `${annVol.toFixed(2)}%` : "—"}
      />
      <KPICard
        prov="metrics.sharpe"
        label={<MetricTooltip metricKey="sharpe">Sharpe Ratio</MetricTooltip>}
        value={m.sharpe !== null ? m.sharpe.toFixed(2) : "—"}
        color={m.sharpe !== null && m.sharpe >= 1 ? "text-green-500" : undefined}
      />
      <KPICard
        prov="metrics.maxDrawdown"
        label={<MetricTooltip metricKey="maxDrawdown">Max Drawdown</MetricTooltip>}
        value={maxDD !== null ? `${maxDD.toFixed(2)}%` : "—"}
        color={ddColor(maxDD)}
      />
      <KPICard
        prov="metrics.beta"
        label={<MetricTooltip metricKey="beta">Beta</MetricTooltip>}
        value={m.beta !== null ? m.beta.toFixed(2) : "—"}
      />
    </div>
  );
}
