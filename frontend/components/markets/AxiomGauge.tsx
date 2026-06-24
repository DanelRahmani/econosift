"use client";

import { Card } from "@/components/ui";
import { fmtPrice, fmtPct, currencySymbol } from "@/lib/format";
import type { AxiomFairValue } from "@/lib/types";

// ── colour palette (matches app: success #16a34a, danger #c4394a, warning #d97706) ──
const SEGMENT_COLORS = [
  "#c4394a", // Significantly Overvalued  (leftmost, -90° → -54°)
  "#e57373", // Overvalued
  "#d97706", // Fairly Valued             (center, -18° → +18°)
  "#86c87a", // Undervalued
  "#16a34a", // Significantly Undervalued (rightmost, +54° → +90°)
] as const;

const VERDICT_COLORS: Record<string, string> = {
  "Significantly Undervalued": "#16a34a",
  Undervalued: "#86c87a",
  "Fairly Valued": "#d97706",
  Overvalued: "#e57373",
  "Significantly Overvalued": "#c4394a",
  "Insufficient Data": "#8a6770",
};

// ── SVG arc helpers ──────────────────────────────────────────────────────────
const CX = 120;
const CY = 115;
const R = 90;
const STROKE = 22;

/** Convert polar angle (degrees, 0=right, CCW+) to SVG cartesian */
function polar(angleDeg: number, r = R): [number, number] {
  const rad = (angleDeg * Math.PI) / 180;
  return [CX + r * Math.cos(rad), CY - r * Math.sin(rad)];
}

/**
 * Build an SVG arc path for a ring segment.
 * Angles are in standard math convention (0=right, CCW positive).
 * The gauge arc runs from -180° (left) to 0° (right), i.e. a bottom-open
 * semicircle. We divide it into 5 equal 36° segments.
 */
function arcPath(startDeg: number, endDeg: number): string {
  const [x1, y1] = polar(startDeg);
  const [x2, y2] = polar(endDeg);
  // large-arc flag: 1 if arc > 180°
  const large = endDeg - startDeg > 180 ? 1 : 0;
  // Always draw counter-clockwise (sweep=0 in SVG coords where y is flipped)
  return `M ${x1} ${y1} A ${R} ${R} 0 ${large} 0 ${x2} ${y2}`;
}

// Five 36° segments, left→right: -180° → -144° → -108° → -72° → -36° → 0°
// In our convention: starts at 180° (left) and ends at 0° (right) going CCW
// SVG arc: sweep-flag=0 means CCW
const SEGMENTS = [
  { start: 180, end: 144 }, // Significantly Overvalued
  { start: 144, end: 108 }, // Overvalued
  { start: 108, end: 72 },  // Fairly Valued
  { start: 72, end: 36 },   // Undervalued
  { start: 36, end: 0 },    // Significantly Undervalued
];

/**
 * Map upsidePct to a gauge angle in [0°, 180°].
 * upsidePct=0  → center (90°), clamped to [-50%, +50%].
 * upsidePct>0 (undervalued) → right half (0°–90°)
 * upsidePct<0 (overvalued)  → left half (90°–180°)
 *
 * Returns a standard-math angle (0=right, CCW+) for use with polar().
 */
function upsideToDeg(upsidePct: number | null): number {
  if (upsidePct === null) return 90; // center
  const clamped = Math.max(-0.5, Math.min(0.5, upsidePct));
  // Map [-0.5, 0.5] → [180°, 0°]  (left to right)
  return 90 - clamped * 180;
}

/** Needle tip and base coords */
function needlePoints(angleDeg: number): { tip: [number, number]; left: [number, number]; right: [number, number] } {
  const tip = polar(angleDeg, R - STROKE / 2 - 4);
  const perpAngle = angleDeg + 90;
  const baseR = 10;
  const base: [number, number] = [CX, CY];
  const left = polar(perpAngle, baseR);
  const right = polar(perpAngle - 180, baseR);
  return {
    tip,
    left: [CX + (left[0] - CX) * 0.25, CY + (left[1] - CY) * 0.25],
    right: [CX + (right[0] - CX) * 0.25, CY + (right[1] - CY) * 0.25],
  };
}

// ── Component ────────────────────────────────────────────────────────────────
export function AxiomGauge({
  axiom,
  spotPrice,
  currency,
}: {
  axiom: AxiomFairValue;
  spotPrice: number | null;
  currency: string;
}) {
  const sym = currencySymbol(currency);
  const verdictColor = VERDICT_COLORS[axiom.verdict] ?? "#8a6770";
  const isInsufficient =
    axiom.verdict === "Insufficient Data" || axiom.value === null;

  // Needle angle
  const needleAngle = isInsufficient ? 90 : upsideToDeg(axiom.upsidePct);
  const needle = needlePoints(needleAngle);

  // Upside% sign colour
  const upsideColor =
    axiom.upsidePct === null
      ? "#8a6770"
      : axiom.upsidePct > 0.02
      ? "#16a34a"
      : axiom.upsidePct < -0.02
      ? "#c4394a"
      : "#d97706";

  // Weights breakdown — sort descending by weight
  const weights = Object.entries(axiom.weightsUsed ?? {}).sort(
    ([, a], [, b]) => b - a
  );

  return (
    <Card className="flex flex-col items-center gap-4 p-5">
      {/* ── Gauge SVG ── */}
      <svg
        width="240"
        height="130"
        viewBox="0 0 240 130"
        aria-label={`Axiom Fair Value gauge: ${axiom.verdict}`}
        role="img"
      >
        {/* Background track */}
        <path
          d={arcPath(180, 0)}
          fill="none"
          stroke="#32171c"
          strokeWidth={STROKE}
          strokeLinecap="butt"
        />

        {/* Coloured segments */}
        {SEGMENTS.map((seg, i) => (
          <path
            key={i}
            d={arcPath(seg.start, seg.end)}
            fill="none"
            stroke={isInsufficient ? "#4a3035" : SEGMENT_COLORS[i]}
            strokeWidth={STROKE}
            strokeLinecap="butt"
            opacity={isInsufficient ? 0.4 : 1}
          />
        ))}

        {/* Segment divider ticks */}
        {[144, 108, 72, 36].map((deg) => {
          const inner = polar(deg, R - STROKE / 2 - 1);
          const outer = polar(deg, R + STROKE / 2 + 1);
          return (
            <line
              key={deg}
              x1={inner[0]}
              y1={inner[1]}
              x2={outer[0]}
              y2={outer[1]}
              stroke="#0f0608"
              strokeWidth={2}
            />
          );
        })}

        {/* Needle */}
        {!isInsufficient && (
          <>
            <polygon
              points={`${needle.tip[0]},${needle.tip[1]} ${needle.left[0]},${needle.left[1]} ${needle.right[0]},${needle.right[1]}`}
              fill="#f5eeef"
              stroke="#0f0608"
              strokeWidth={0.5}
            />
            {/* Needle pivot */}
            <circle cx={CX} cy={CY} r={5} fill="#f5eeef" stroke="#0f0608" strokeWidth={1} />
          </>
        )}

        {/* Labels: SO / SU */}
        <text x={10} y={122} fontSize={9} fill="#e57373" textAnchor="start" fontFamily="Inter,system-ui,sans-serif">
          SO
        </text>
        <text x={230} y={122} fontSize={9} fill="#86c87a" textAnchor="end" fontFamily="Inter,system-ui,sans-serif">
          SU
        </text>
        <text x={CX} y={122} fontSize={9} fill="#d97706" textAnchor="middle" fontFamily="Inter,system-ui,sans-serif">
          FV
        </text>
      </svg>

      {/* ── Center readout ── */}
      <div className="text-center space-y-1 -mt-2">
        {isInsufficient ? (
          <p className="text-text-secondary text-sm leading-snug max-w-[220px]">
            Insufficient data to compute a composite fair value.
          </p>
        ) : (
          <>
            {/* Verdict */}
            <p className="text-sm font-semibold" style={{ color: verdictColor }}>
              {axiom.verdict}
            </p>

            {/* Fair value vs spot */}
            <div className="flex items-center justify-center gap-3 text-sm">
              <span className="text-text-secondary text-xs">Fair Value</span>
              <span className="font-mono font-semibold text-text-primary">
                {fmtPrice(axiom.value, sym)}
              </span>
            </div>
            {spotPrice !== null && (
              <div className="flex items-center justify-center gap-3 text-xs text-text-secondary">
                <span>Spot</span>
                <span className="font-mono">{fmtPrice(spotPrice, sym)}</span>
              </div>
            )}

            {/* Upside % */}
            {axiom.upsidePct !== null && (
              <p
                className="text-lg font-bold font-mono"
                style={{ color: upsideColor }}
              >
                {axiom.upsidePct >= 0 ? "+" : ""}
                {fmtPct(axiom.upsidePct * 100, 1)} upside
              </p>
            )}
          </>
        )}
      </div>

      {/* ── Model weights breakdown ── */}
      {weights.length > 0 && (
        <div className="w-full border-t border-border pt-3">
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
                      backgroundColor: "#c4394a",
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
