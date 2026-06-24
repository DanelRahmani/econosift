"use client";

import type { CAPMData } from "@/lib/types";

interface Props {
  data: CAPMData | null;
  loading: boolean;
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface-alt rounded-lg p-3">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-lg font-bold text-text-primary mt-1">{value}</p>
      {sub && <p className="text-xs text-text-muted mt-0.5">{sub}</p>}
    </div>
  );
}

export function CAPMAttribution({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 animate-pulse">
        <div className="h-4 w-40 bg-border rounded mb-4" />
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-20 bg-surface-alt rounded-lg" />)}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 text-sm text-text-muted">
        CAPM attribution data not available.
      </div>
    );
  }

  if (data.error) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 text-sm text-red-500">
        CAPM error: {data.error}
      </div>
    );
  }

  const annAlpha = data.annAlpha ?? data.alpha;
  const alphaPct = annAlpha !== null ? `${(annAlpha * 100).toFixed(2)}%` : "—";
  const sysRiskPct = data.systematicVarPct !== null ? `${(data.systematicVarPct * 100).toFixed(1)}%` : "—";
  const idioRiskPct = data.idiosyncraticVarPct !== null ? `${(data.idiosyncraticVarPct * 100).toFixed(1)}%` : "—";

  const sysNum = data.systematicVarPct ?? 0;
  const idioNum = data.idiosyncraticVarPct ?? 0;
  const total = sysNum + idioNum || 1;
  const sysPct = (sysNum / total) * 100;
  const idioPct = (idioNum / total) * 100;

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-4">
      <h3 className="font-semibold text-sm">CAPM Attribution</h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="Alpha (ann.)"
          value={alphaPct}
          sub={annAlpha !== null ? (annAlpha >= 0 ? "Outperforming" : "Underperforming") : undefined}
        />
        <MetricCard
          label="Beta"
          value={data.beta !== null ? data.beta.toFixed(2) : "—"}
          sub={data.beta !== null ? (data.beta > 1 ? "More volatile than market" : "Less volatile") : undefined}
        />
        <MetricCard
          label="R²"
          value={data.rSquared !== null ? data.rSquared.toFixed(3) : "—"}
          sub="Explained by market"
        />
        <MetricCard
          label="Systematic Risk"
          value={sysRiskPct}
          sub={`Idiosyncratic: ${idioRiskPct}`}
        />
      </div>

      {/* Risk decomposition bar */}
      <div>
        <p className="text-xs text-text-muted mb-1">Risk Decomposition</p>
        <div className="flex h-4 rounded overflow-hidden text-xs">
          <div
            className="bg-accent flex items-center justify-center text-white"
            style={{ width: `${sysPct}%` }}
          >
            {sysPct > 15 ? `Sys ${sysPct.toFixed(0)}%` : ""}
          </div>
          <div
            className="bg-purple-500 flex items-center justify-center text-white"
            style={{ width: `${idioPct}%` }}
          >
            {idioPct > 15 ? `Idio ${idioPct.toFixed(0)}%` : ""}
          </div>
        </div>
        <div className="flex gap-4 mt-1 text-xs text-text-muted">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-accent inline-block" /> Systematic
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-purple-500 inline-block" /> Idiosyncratic
          </span>
        </div>
      </div>
    </div>
  );
}
