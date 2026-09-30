"use client";

import { Card, Skeleton } from "@/components/ui";
import { fmtNum, fmtPct, fmtPrice } from "@/lib/format";
import type { OptionsKPIs } from "@/lib/types";

interface Props {
  kpis: OptionsKPIs | null;
  loading: boolean;
}

function IVRankBar({ value }: { value: number | null }) {
  if (value === null) return null;
  const clamped = Math.max(0, Math.min(100, value));
  const color =
    clamped < 33 ? "bg-success" : clamped < 66 ? "bg-warning" : "bg-danger";
  return (
    <div className="mt-2 h-1.5 w-full rounded-full bg-surface-alt overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export function IVKPIRow({ kpis, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (!kpis) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} className="p-4">
            <div className="text-xs text-text-muted mb-1">&nbsp;</div>
            <div className="text-xl font-bold text-text-muted">—</div>
          </Card>
        ))}
      </div>
    );
  }

  const pcRatio = kpis.pcOIRatio;
  const pcColor =
    pcRatio === null
      ? "text-text-primary"
      : pcRatio < 1.0
      ? "text-success"
      : "text-danger";
  const pcLabel =
    pcRatio === null ? null : pcRatio < 1.0 ? "Bullish" : "Bearish";

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {/* IV30 */}
      <Card className="p-4">
        <div className="text-xs text-text-muted mb-1">IV30</div>
        <div className="text-xl font-bold font-mono">
          {kpis.iv30 !== null ? `${fmtNum(kpis.iv30, 1)}%` : "—"}
        </div>
        {kpis.iv30Approximate && (
          <span className="mt-1 inline-block text-[10px] px-1.5 py-0.5 rounded-md bg-warning/20 text-warning font-medium">
            ~nearest expiry
          </span>
        )}
        {!kpis.iv30Approximate && kpis.iv30 !== null && (
          <div className="mt-1 text-[10px] text-text-muted">30-day interp.</div>
        )}
      </Card>

      {/* IV Rank */}
      <Card className="p-4">
        <div className="text-xs text-text-muted mb-1">IV Rank</div>
        <div className="text-xl font-bold font-mono">
          {kpis.ivRank !== null ? fmtNum(kpis.ivRank, 1) : "—"}
        </div>
        {kpis.ivRank === null && kpis.ivHistoryDays != null && (
          <div className="mt-1 text-[10px] text-text-muted" title="IV Rank compares today's IV30 with its own past year; EconoSift records IV30 daily to build that history.">
            Building history ({kpis.ivHistoryDays}/60 sessions)
          </div>
        )}
        {kpis.ivRankApproximate && (
          <span className="mt-1 inline-block text-[10px] px-1.5 py-0.5 rounded-md bg-warning/20 text-warning font-medium">
            &lt;1y history
          </span>
        )}
        <IVRankBar value={kpis.ivRank} />
      </Card>

      {/* IV Percentile */}
      <Card className="p-4">
        <div className="text-xs text-text-muted mb-1">IV Percentile</div>
        <div className="text-xl font-bold font-mono">
          {kpis.ivPercentile !== null ? `${fmtNum(kpis.ivPercentile, 1)}` : "—"}
        </div>
        <IVRankBar value={kpis.ivPercentile} />
      </Card>

      {/* P/C OI Ratio */}
      <Card className="p-4">
        <div className="text-xs text-text-muted mb-1">P/C OI Ratio</div>
        <div className={`text-xl font-bold font-mono ${pcColor}`}>
          {pcRatio !== null ? fmtNum(pcRatio, 2) : "—"}
        </div>
        {pcLabel && (
          <div className={`mt-1 text-[10px] font-medium ${pcColor}`}>
            {pcLabel}
          </div>
        )}
      </Card>

      {/* Max Pain */}
      <Card className="p-4">
        <div className="text-xs text-text-muted mb-1">Max Pain</div>
        <div className="text-xl font-bold font-mono">
          {kpis.maxPain !== null ? fmtPrice(kpis.maxPain) : "—"}
        </div>
        {kpis.spot !== null && kpis.maxPain !== null && (
          <div className="mt-1 text-[10px] text-text-muted">
            Spot {fmtPrice(kpis.spot)}
          </div>
        )}
      </Card>

      {/* Implied Move */}
      <Card className="p-4">
        <div className="text-xs text-text-muted mb-1">Implied Move</div>
        <div className="text-xl font-bold font-mono">
          {kpis.impliedMove !== null ? `±${fmtNum(kpis.impliedMove, 1)}%` : "—"}
        </div>
        <div className="mt-1 text-[10px] text-text-muted">Straddle-based</div>
      </Card>
    </div>
  );
}
