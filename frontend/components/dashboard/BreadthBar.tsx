"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { api } from "@/lib/api";
import type { BreadthResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui";
import { fmtNum } from "@/lib/format";

/**
 * Market breadth bar (compute tier 🟢). Sticky strip of S&P 500 internals:
 * advancers/decliners, new highs/lows, % above SMA50/200, the McClellan
 * oscillator, and the cumulative advance-decline line as a sparkline.
 */
export function BreadthBar({ index = "sp500" }: { index?: string }) {
  const [data, setData] = useState<BreadthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.breadth(index)
      .then((r) => alive && setData(r))
      .catch(() => alive && setData(null))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [index]);

  if (loading && !data) return <Skeleton className="h-20" />;
  if (!data || data.total === 0)
    return (
      <div className="card text-text-muted text-sm">Breadth data unavailable.</div>
    );

  const adv = data.advancing;
  const dec = data.declining;
  const denom = adv + dec || 1;
  const advPct = (adv / denom) * 100;

  return (
    <div className="card sticky top-14 z-30 backdrop-blur bg-surface/90">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="text-sm font-semibold text-text-secondary">
          Market Breadth · S&amp;P 500
        </h2>
        <span className="text-xs text-text-muted font-mono">
          {data.total} stocks · {data.asOf ?? "—"}
        </span>
      </div>

      {/* Advance / decline ratio bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-success font-mono">{adv} advancing</span>
          <span className="text-text-muted">{data.unchanged} unch.</span>
          <span className="text-danger font-mono">{dec} declining</span>
        </div>
        <div className="h-2.5 w-full rounded-full overflow-hidden bg-danger/40 flex">
          <div className="h-full bg-success" style={{ width: `${advPct}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Kpi label="New Highs" value={data.newHighs} tone="up" />
        <Kpi label="New Lows" value={data.newLows} tone="down" />
        <Kpi label="% > SMA50" value={pct(data.pctAboveSma50)} tone={tone(data.pctAboveSma50)} />
        <Kpi label="% > SMA200" value={pct(data.pctAboveSma200)} tone={tone(data.pctAboveSma200)} />
        <Kpi
          label="McClellan Osc"
          value={fmtNum(data.mcclellanOscillator, 1)}
          tone={(data.mcclellanOscillator ?? 0) >= 0 ? "up" : "down"}
        />
        <div className="rounded-lg bg-surface-alt px-3 py-2">
          <div className="text-xs text-text-muted mb-1">Cumulative A/D</div>
          <div className="h-7">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.cumulativeAdLine}>
                <YAxis hide domain={["dataMin", "dataMax"]} />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={trendUp(data.cumulativeAdLine) ? "#16a34a" : "#c4394a"}
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string | number; tone?: "up" | "down" | "flat" }) {
  const color = tone === "up" ? "text-success" : tone === "down" ? "text-danger" : "text-text-primary";
  return (
    <div className="rounded-lg bg-surface-alt px-3 py-2">
      <div className="text-xs text-text-muted">{label}</div>
      <div className={`font-mono text-lg font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function pct(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(0)}%`;
}
function tone(v: number | null): "up" | "down" | "flat" {
  if (v === null) return "flat";
  return v >= 50 ? "up" : "down";
}
function trendUp(series: { value: number }[]): boolean {
  if (series.length < 2) return true;
  return series[series.length - 1].value >= series[0].value;
}
