"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import { api } from "@/lib/api";
import type { FearGreedResponse } from "@/lib/types";
import { Card, Skeleton, chartTooltipStyle, chartPalette, SemiGauge } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { MetricTooltip } from "@/components/MetricTooltip";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

/**
 * Fear & Greed Index (compute tier 🟢): a semicircular speedometer gauge for
 * the 0–100 composite, a 90-day history area chart, and the per-signal
 * breakdown. Colours run red (fear) → amber (neutral) → green (greed).
 */
export function FearGreedGauge() {
  const { theme } = useTheme();
  const [data, setData] = useState<FearGreedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const scope = useSourceScope(provOf(data));

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
    <Card {...scope}>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-text-secondary">
          <MetricTooltip metricKey="fearGreed">Fear &amp; Greed Index</MetricTooltip>
        </h2>
        <span className="text-xs text-text-muted font-mono">{data.asOf ?? "—"}</span>
      </div>

      <div className="flex flex-col items-center" data-prov="index">
        <Gauge value={value} label={data.label ?? ""} theme={theme} />
      </div>

      {data.history.length > 1 && (
        <div className="h-16 mt-2" data-prov="history">
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
          <div key={s.key} className="flex items-center gap-2 text-xs" data-prov={`signals.${s.key}`} data-prov-ctx={s.label}>
            <span
              className="w-40 shrink-0 text-text-muted truncate"
              title={s.asOf ? `Observation: ${s.asOf}${s.aligned === false ? " (live snapshot)" : ""}` : undefined}
            >
              {s.label}
              {s.stale && <span className="ml-1 text-warning" title={`Stale — last observation ${s.asOf}`}>⚠</span>}
              {s.aligned === false && s.score !== null && <span className="ml-1 text-text-muted">· live</span>}
            </span>
            <div className="flex-1 h-1.5 rounded-full bg-surface-alt overflow-hidden">
              {s.score !== null && (
                <div className="h-full rounded-full" style={{ width: `${s.score}%`, backgroundColor: scoreColor(s.score) }} />
              )}
            </div>
            <span className="w-20 shrink-0 text-right font-mono text-text-secondary">
              {s.score === null
                ? <span title={s.note ?? "No data"}>{s.note ? "building" : "n/a"}</span>
                : `${s.score.toFixed(0)} · ${String(s.label_text ?? "")}`}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Gauge({ value, label, theme }: { value: number; label: string; theme: "light" | "dark" }) {
  return (
    <SemiGauge value={value} color={scoreColor(value)} trackColor={chartPalette(theme).grid} size={200}>
      <div className="flex flex-col items-center">
        <span className="text-3xl font-bold text-text-primary leading-none">{value.toFixed(0)}</span>
        <span className="text-xs font-semibold mt-1" style={{ color: scoreColor(value) }}>{label}</span>
      </div>
    </SemiGauge>
  );
}

function scoreColor(v: number): string {
  if (v < 25) return "#c4394a";
  if (v < 45) return "#ea580c";
  if (v < 55) return "#ca8a04";
  if (v < 75) return "#65a30d";
  return "#16a34a";
}
