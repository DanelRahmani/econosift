"use client";

import {
  interpolateRdYlGn,
  interpolateRdBu,
} from "d3-scale-chromatic";
import { fmtNum } from "@/lib/format";

interface Props {
  min: number;
  max: number;
  unit: string;
  goodDirection: "high" | "low" | "neutral";
}

function buildGradient(goodDirection: "high" | "low" | "neutral"): string {
  const steps = 10;
  const stops = Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps;
    let color: string;
    if (goodDirection === "high") color = interpolateRdYlGn(t);
    else if (goodDirection === "low") color = interpolateRdYlGn(1 - t);
    else color = interpolateRdBu(1 - t);
    return `${color} ${(t * 100).toFixed(0)}%`;
  });
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

export function ColorLegend({ min, max, unit, goodDirection }: Props) {
  const gradient = buildGradient(goodDirection);

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-text-muted">{fmtNum(min)} {unit}</span>
      <div className="flex-1 relative h-4 rounded overflow-hidden" style={{ background: gradient }}>
        {/* no-data swatch */}
      </div>
      <span className="text-xs text-text-muted">{fmtNum(max)} {unit}</span>

      {/* No data swatch */}
      <div className="flex items-center gap-1.5 ml-2">
        <div className="w-4 h-4 rounded" style={{ backgroundColor: "#3a3a4a" }} />
        <span className="text-xs text-text-muted">No data</span>
      </div>
    </div>
  );
}
