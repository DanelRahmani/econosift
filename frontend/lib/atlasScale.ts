// Shared color scale for the Global Macro Atlas choropleth.
//
// Uses a *quantile* scale (equal-count bins) rather than a linear min→max scale
// so that a few extreme outliers (e.g. Guyana's oil-boom GDP growth) don't crush
// every other country into a single mid-range color. Each bin holds ~the same
// number of countries, so the map distinguishes typical countries clearly.
import { scaleQuantile } from "d3-scale";
import { interpolateRdYlGn, interpolateRdBu } from "d3-scale-chromatic";

export type GoodDirection = "high" | "low" | "neutral";

export const NO_DATA_COLOR = "#3a3a4a";
const BINS = 7;

function rampColors(goodDirection: GoodDirection, n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const t = n === 1 ? 0.5 : i / (n - 1);
    if (goodDirection === "high") return interpolateRdYlGn(t);
    if (goodDirection === "low") return interpolateRdYlGn(1 - t);
    // neutral: diverging blue↔red about the median
    return interpolateRdBu(1 - t);
  });
}

export interface AtlasBin {
  color: string;
  lo: number;
  hi: number;
}

export interface AtlasScale {
  colorFor: (v: number | null | undefined) => string;
  bins: AtlasBin[];
  empty: boolean;
}

/**
 * Build a quantile color scale over the supplied (visible) values.
 * `colorFor` returns NO_DATA_COLOR for null/undefined/non-finite inputs.
 */
export function buildAtlasScale(values: number[], goodDirection: GoodDirection): AtlasScale {
  const clean = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (!clean.length) {
    return { colorFor: () => NO_DATA_COLOR, bins: [], empty: true };
  }

  const colors = rampColors(goodDirection, BINS);
  const scale = scaleQuantile<string>().domain(clean).range(colors);

  const sorted = [...clean].sort((a, b) => a - b);
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  const edges = [min, ...scale.quantiles(), max];

  const bins: AtlasBin[] = colors.map((color, i) => ({
    color,
    lo: edges[i],
    hi: edges[i + 1],
  }));

  return {
    colorFor: (v) =>
      v == null || !Number.isFinite(v) ? NO_DATA_COLOR : scale(v as number),
    bins,
    empty: false,
  };
}
