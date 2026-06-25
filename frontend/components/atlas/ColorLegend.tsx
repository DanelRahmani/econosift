"use client";

import { fmtNum } from "@/lib/format";
import { NO_DATA_COLOR, type AtlasBin } from "@/lib/atlasScale";

interface Props {
  bins: AtlasBin[];
  unit: string;
}

export function ColorLegend({ bins, unit }: Props) {
  // Quantile bins: each segment holds ~the same number of countries, so the
  // boundary values are unevenly spaced — that's expected and is what makes the
  // map readable when a few outliers would otherwise dominate a linear scale.
  const edges = bins.length
    ? [bins[0].lo, ...bins.map((b) => b.hi)]
    : [];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          {bins.length ? (
            <>
              <div className="flex h-4 rounded overflow-hidden">
                {bins.map((b, i) => (
                  <div
                    key={i}
                    className="flex-1"
                    style={{ backgroundColor: b.color }}
                    title={`${fmtNum(b.lo)} – ${fmtNum(b.hi)} ${unit}`}
                  />
                ))}
              </div>
              <div className="mt-1 flex justify-between">
                {edges.map((e, i) => (
                  <span key={i} className="text-[10px] tabular-nums text-text-muted">
                    {fmtNum(e)}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <div className="h-4 rounded bg-surface-alt" />
          )}
        </div>

        {/* No data swatch */}
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: NO_DATA_COLOR }} />
          <span className="text-xs text-text-muted">No data</span>
        </div>
      </div>
      <p className="text-[11px] text-text-muted">
        Equal-count bins ({bins.length || 0} quantiles{unit ? `, ${unit}` : ""}) — outlier-robust.
      </p>
    </div>
  );
}
