"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import { api } from "@/lib/api";
import type { FearGreedResponse } from "@/lib/types";
import { Card, Skeleton, chartTooltipStyle } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { MetricTooltip } from "@/components/MetricTooltip";

/**
 * Fear & Greed Index (compute tier 🟢): a semicircular speedometer gauge for
 * the 0–100 composite, a 90-day history area chart, and the per-signal
 * breakdown. Colours run red (fear) → amber (neutral) → green (greed).
 */
export function FearGreedGauge() {
  const { theme } = useTheme();
  const [data, setData] = useState<FearGreedResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.fearGreed()
      .then((r) => alive && setData(r))
      .catch(() => alive && setData(null))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  if (loading && !data) return <Skeleton className="h-72" />;
  if (!data || data.index === null)
    return <Card><div className="text-text-muted text-sm">Fear &amp; Greed data unavailable.</div></Card>;

  const value = data.index;

  return (
    <Card>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-text-secondary">
          <MetricTooltip metricKey="fearGreed">Fear &amp; Greed Index</MetricTooltip>
        </h2>
        <span className="text-xs text-text-muted font-mono">{data.asOf ?? "—"}</span>
      </div>

      <div className="flex flex-col items-center">
        <Gauge value={value} label={data.label ?? ""} />
      </div>

      {data.history.length > 1 && (
        <div className="h-16 mt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.history}>
              <defs>
                <linearGradient id="fgFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#c4394a" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#c4394a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis hide domain={[0, 100]} />
              <Tooltip {...chartTooltipStyle(theme)} formatter={(v: number) => [v.toFixed(0), "Index"]} />
              <Area type="monotone" dataKey="value" stroke="#c4394a" fill="url(#fgFill)" strokeWidth={1.5} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="mt-3 space-y-1.5">
        {data.signals.map((s) => (
          <div key={s.key} className="flex items-center gap-2 text-xs">
            <span className="w-40 shrink-0 text-text-muted truncate">{s.label}</span>
            <div className="flex-1 h-1.5 rounded-full bg-surface-alt overflow-hidden">
              {s.score !== null && (
                <div className="h-full rounded-full" style={{ width: `${s.score}%`, backgroundColor: scoreColor(s.score) }} />
              )}
            </div>
            <span className="w-20 shrink-0 text-right font-mono text-text-secondary">
              {s.score === null ? "n/a" : `${s.score.toFixed(0)} · ${s.label_text}`}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// SVG gauge geometry — bottom-open semicircle.
const CX = 110, CY = 105, R = 88, STROKE = 14;

function polar(angleDeg: number, r = R): [number, number] {
  const rad = (angleDeg * Math.PI) / 180;
  return [CX + r * Math.cos(rad), CY - r * Math.sin(rad)];
}
function arcPath(startDeg: number, endDeg: number): string {
  const [x1, y1] = polar(startDeg);
  const [x2, y2] = polar(endDeg);
  return `M ${x1} ${y1} A ${R} ${R} 0 0 0 ${x2} ${y2}`;
}

function Gauge({ value, label }: { value: number; label: string }) {
  const angle = 180 - (value / 100) * 180;
  const [nx, ny] = polar(angle, R - STROKE / 2);

  return (
    <svg viewBox="0 0 220 130" className="w-full max-w-xs">
      {/* Coloured bands: red (fear) → amber (neutral) → green (greed) */}
      <path d={arcPath(180, 120)} fill="none" stroke="#c4394a" strokeWidth={STROKE} strokeLinecap="butt" />
      <path d={arcPath(120, 60)} fill="none" stroke="#ca8a04" strokeWidth={STROKE} />
      <path d={arcPath(60, 0)} fill="none" stroke="#16a34a" strokeWidth={STROKE} strokeLinecap="butt" />

      {/* Tick marks: 0, 25, 50, 75, 100 */}
      {[0, 25, 50, 75, 100].map((v) => {
        const a = 180 - (v / 100) * 180;
        const [tx, ty] = polar(a, R + 14);
        const [ix, iy] = polar(a, R - STROKE / 2 - 4);
        const [ox, oy] = polar(a, R + 4);
        return (
          <g key={v}>
            <line x1={ix} y1={iy} x2={ox} y2={oy} stroke="currentColor" strokeWidth={1} className="text-text-muted" opacity={0.5} />
            <text x={tx} y={ty} textAnchor="middle" dominantBaseline="middle" fill="currentColor" fontSize="9" className="text-text-muted" opacity={0.7}>
              {v}
            </text>
          </g>
        );
      })}

      {/* Needle */}
      <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="currentColor" strokeWidth={2} className="text-text-primary" pointerEvents="none" strokeLinecap="round" />
      <circle cx={CX} cy={CY} r={5} className="fill-text-primary" />

      {/* Value — below the needle pivot */}
      <text x={CX} y={CY + 3} textAnchor="middle" className="fill-text-primary" fontSize="30" fontWeight="700">
        {value.toFixed(0)}
      </text>
      <text x={CX} y={CY - 3} textAnchor="middle" fill={scoreColor(value)} fontSize="11" fontWeight="600">
        {label}
      </text>
    </svg>
  );
}

function scoreColor(v: number): string {
  if (v < 25) return "#c4394a";
  if (v < 45) return "#ea580c";
  if (v < 55) return "#ca8a04";
  if (v < 75) return "#65a30d";
  return "#16a34a";
}
