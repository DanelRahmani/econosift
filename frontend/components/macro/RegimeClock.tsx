"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  type TooltipProps,
} from "recharts";
import { api } from "@/lib/api";
import type { RegimeResponse, RegimePoint, RegimeQuadrant } from "@/lib/types";
import { Card, Skeleton, chartPalette, chartTooltipStyle } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtPct } from "@/lib/format";

// ─── colour maps ────────────────────────────────────────────────────────────

const QUADRANT_BADGE: Record<RegimeQuadrant, string> = {
  Goldilocks:  "bg-success/20 text-success",
  Overheating: "bg-warning/20 text-warning",
  Slowdown:    "bg-blue-500/20 text-blue-400",
  Stagflation: "bg-danger/20 text-danger",
};

const QUADRANT_FILL: Record<RegimeQuadrant, string> = {
  Goldilocks:  "#16a34a",
  Overheating: "#ca8a04",
  Slowdown:    "#3b82f6",
  Stagflation: "#c4394a",
};

function quadrantColor(q: RegimeQuadrant | null): string {
  if (!q) return "#888";
  return QUADRANT_FILL[q];
}

// ─── custom tooltip ──────────────────────────────────────────────────────────

type ScatterPayload = {
  date: string;
  gdpGrowth: number | null;
  cpiInflation: number | null;
  quadrant: RegimeQuadrant | null;
  isCurrent?: boolean;
};

function RegimeTooltip({
  active,
  payload,
  theme,
}: TooltipProps<number, string> & { theme: "light" | "dark" }) {
  const style = chartTooltipStyle(theme);
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as ScatterPayload | undefined;
  if (!d) return null;
  return (
    <div
      style={{
        ...style.contentStyle,
        padding: "8px 12px",
        fontSize: 12,
        minWidth: 160,
      }}
    >
      <p style={{ color: style.labelStyle?.color, marginBottom: 4 }}>{d.date}</p>
      <p>GDP Growth: <strong>{fmtPct(d.gdpGrowth)}</strong></p>
      <p>CPI Inflation: <strong>{fmtPct(d.cpiInflation)}</strong></p>
      {d.quadrant && (
        <p style={{ marginTop: 4 }}>
          Regime: <strong style={{ color: quadrantColor(d.quadrant) }}>{d.quadrant}</strong>
        </p>
      )}
    </div>
  );
}

// ─── main component ──────────────────────────────────────────────────────────

export function RegimeClock({
  country,
  countryName,
}: {
  country: string;
  countryName: string;
}) {
  const { theme } = useTheme();
  const pal = chartPalette(theme);

  const [data, setData] = useState<RegimeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  // scrubber index — defaults to last point
  const [scrubIdx, setScrubIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── fetch on country change ──
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    setPlaying(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    api.regime(country, 2000)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        // default scrubber to last valid index
        const validLen = res.series.filter(
          (p) => p.gdpGrowth !== null && p.cpiInflation !== null
        ).length;
        setScrubIdx(Math.max(0, validLen - 1));
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Failed to load regime data.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [country]);

  // ── play / pause logic ──
  const validPoints = (data?.series ?? []).filter(
    (p): p is RegimePoint & { gdpGrowth: number; cpiInflation: number } =>
      p.gdpGrowth !== null && p.cpiInflation !== null
  );

  const advanceIndex = useCallback(() => {
    setScrubIdx((prev) => {
      const next = prev + 1;
      if (next >= validPoints.length) {
        setPlaying(false);
        return validPoints.length - 1;
      }
      return next;
    });
  }, [validPoints.length]);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(advanceIndex, 350);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [playing, advanceIndex]);

  // ── render: loading ──
  if (loading) return <Skeleton className="h-96" />;

  // ── render: error ──
  if (error) {
    return (
      <Card>
        <p className="text-danger text-sm p-4">{error}</p>
      </Card>
    );
  }

  if (!data) return null;

  // ── render: note (source unavailable / empty series) ──
  if (data.note || validPoints.length === 0) {
    return (
      <Card>
        <div className="p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-1">
            Regime Clock — {countryName}
          </h3>
          <p className="text-text-muted text-sm">
            {data.note ?? "No data available for this country."}
          </p>
        </div>
      </Card>
    );
  }

  const { thresholds, current, source, asOf } = data;

  // ── axis domains with padding ──
  const allGdp = validPoints.map((p) => p.gdpGrowth);
  const allCpi = validPoints.map((p) => p.cpiInflation);
  const gdpMin = Math.min(...allGdp, thresholds.gdp);
  const gdpMax = Math.max(...allGdp, thresholds.gdp);
  const cpiMin = Math.min(...allCpi, thresholds.cpi);
  const cpiMax = Math.max(...allCpi, thresholds.cpi);
  const gdpPad = Math.max((gdpMax - gdpMin) * 0.12, 0.3);
  const cpiPad = Math.max((cpiMax - cpiMin) * 0.12, 0.3);
  const xDomain: [number, number] = [
    parseFloat((gdpMin - gdpPad).toFixed(2)),
    parseFloat((gdpMax + gdpPad).toFixed(2)),
  ];
  const yDomain: [number, number] = [
    parseFloat((cpiMin - cpiPad).toFixed(2)),
    parseFloat((cpiMax + cpiPad).toFixed(2)),
  ];

  // ── scrubber-gated path ──
  const safeIdx = Math.min(scrubIdx, validPoints.length - 1);
  const pathPoints = validPoints.slice(0, safeIdx + 1).map((p, i) => ({
    ...p,
    isCurrent: i === safeIdx,
  }));
  const currentDot = pathPoints.length > 0 ? [pathPoints[pathPoints.length - 1]] : [];
  const trailDots = pathPoints.length > 1 ? pathPoints.slice(0, -1) : [];
  const selectedPoint = validPoints[safeIdx] ?? null;

  // ── KPI: use scrubber point, fall back to api current ──
  const kpiPoint = selectedPoint ?? current;

  // badge for quadrant
  const quadrant = kpiPoint?.quadrant ?? null;
  const badgeCls = quadrant ? QUADRANT_BADGE[quadrant] : "bg-text-muted/20 text-text-secondary";

  return (
    <Card {...scope}>
      <div className="p-4 space-y-4">
        {/* header */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-text-primary">
            Regime Clock — {countryName}
          </h3>
          <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${badgeCls}`} data-prov="series.quadrant" data-prov-ctx={`${countryName} regime quadrant`}>
            {quadrant ?? "—"}
          </span>
        </div>

        {/* KPI row */}
        <div className="flex flex-wrap gap-6">
          <div data-prov="series.gdpGrowth" data-prov-ctx={`${countryName} real GDP YoY`}>
            <p className="text-xs text-text-muted uppercase tracking-wide">Real GDP YoY</p>
            <p className="text-lg font-bold text-text-primary">
              {fmtPct(kpiPoint?.gdpGrowth ?? null)}
            </p>
          </div>
          <div data-prov="series.cpiInflation" data-prov-ctx={`${countryName} CPI inflation YoY`}>
            <p className="text-xs text-text-muted uppercase tracking-wide">CPI Inflation YoY</p>
            <p className="text-lg font-bold text-text-primary">
              {fmtPct(kpiPoint?.cpiInflation ?? null)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-muted uppercase tracking-wide">As of</p>
            <p className="text-sm font-medium text-text-secondary">
              {kpiPoint?.date ?? "—"}
            </p>
          </div>
        </div>

        {/* scatter chart */}
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 16, right: 24, bottom: 32, left: 24 }}>
              <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />

              <XAxis
                type="number"
                dataKey="gdpGrowth"
                domain={xDomain}
                name="GDP Growth"
                tick={{ fill: pal.axis, fontSize: 11 }}
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                label={{
                  value: "Real GDP YoY %",
                  position: "insideBottom",
                  offset: -16,
                  fontSize: 11,
                  fill: pal.axis,
                }}
              />

              <YAxis
                type="number"
                dataKey="cpiInflation"
                domain={yDomain}
                name="CPI Inflation"
                tick={{ fill: pal.axis, fontSize: 11 }}
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                label={{
                  value: "CPI Inflation YoY %",
                  angle: -90,
                  position: "insideLeft",
                  offset: 10,
                  fontSize: 11,
                  fill: pal.axis,
                }}
              />

              {/* quadrant tint areas */}
              {/* Goldilocks: high GDP (right), low CPI (bottom) */}
              <ReferenceArea
                x1={thresholds.gdp}
                x2={xDomain[1]}
                y1={yDomain[0]}
                y2={thresholds.cpi}
                fill={QUADRANT_FILL.Goldilocks}
                fillOpacity={0.08}
                strokeOpacity={0}
              />
              {/* Overheating: high GDP, high CPI */}
              <ReferenceArea
                x1={thresholds.gdp}
                x2={xDomain[1]}
                y1={thresholds.cpi}
                y2={yDomain[1]}
                fill={QUADRANT_FILL.Overheating}
                fillOpacity={0.08}
                strokeOpacity={0}
              />
              {/* Slowdown: low GDP, low CPI */}
              <ReferenceArea
                x1={xDomain[0]}
                x2={thresholds.gdp}
                y1={yDomain[0]}
                y2={thresholds.cpi}
                fill={QUADRANT_FILL.Slowdown}
                fillOpacity={0.08}
                strokeOpacity={0}
              />
              {/* Stagflation: low GDP, high CPI */}
              <ReferenceArea
                x1={xDomain[0]}
                x2={thresholds.gdp}
                y1={thresholds.cpi}
                y2={yDomain[1]}
                fill={QUADRANT_FILL.Stagflation}
                fillOpacity={0.08}
                strokeOpacity={0}
              />

              {/* quadrant dividers */}
              <ReferenceLine
                x={thresholds.gdp}
                stroke={pal.axis}
                strokeDasharray="4 3"
                strokeOpacity={0.5}
              />
              <ReferenceLine
                y={thresholds.cpi}
                stroke={pal.axis}
                strokeDasharray="4 3"
                strokeOpacity={0.5}
              />

              {/* quadrant labels — pinned to each quadrant's chart corner so
                  they never overlap each other or the data cluster near the
                  threshold crossing. */}
              <ReferenceLine
                x={xDomain[1]}
                y={yDomain[0]}
                stroke="none"
                label={{
                  value: "Goldilocks",
                  position: "insideBottomRight",
                  fontSize: 9,
                  fill: QUADRANT_FILL.Goldilocks,
                  opacity: 0.8,
                }}
              />
              <ReferenceLine
                x={xDomain[1]}
                y={yDomain[1]}
                stroke="none"
                label={{
                  value: "Overheating",
                  position: "insideTopRight",
                  fontSize: 9,
                  fill: QUADRANT_FILL.Overheating,
                  opacity: 0.8,
                }}
              />
              <ReferenceLine
                x={xDomain[0]}
                y={yDomain[0]}
                stroke="none"
                label={{
                  value: "Slowdown",
                  position: "insideBottomLeft",
                  fontSize: 9,
                  fill: QUADRANT_FILL.Slowdown,
                  opacity: 0.8,
                }}
              />
              <ReferenceLine
                x={xDomain[0]}
                y={yDomain[1]}
                stroke="none"
                label={{
                  value: "Stagflation",
                  position: "insideTopLeft",
                  fontSize: 9,
                  fill: QUADRANT_FILL.Stagflation,
                  opacity: 0.8,
                }}
              />

              <Tooltip
                content={<RegimeTooltip theme={theme} />}
                cursor={{ strokeDasharray: "3 3" }}
              />

              {/* historical trail (faint, coloured by quadrant) */}
              {trailDots.length > 0 && (
                <Scatter
                  data={trailDots}
                  shape={(props: unknown) => {
                    const { cx, cy, payload } = props as {
                      cx: number;
                      cy: number;
                      payload: ScatterPayload;
                    };
                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={3}
                        fill={quadrantColor(payload.quadrant)}
                        fillOpacity={0.35}
                        stroke="none"
                      />
                    );
                  }}
                />
              )}

              {/* current dot (highlighted) */}
              {currentDot.length > 0 && (
                <Scatter
                  data={currentDot}
                  shape={(props: unknown) => {
                    const { cx, cy, payload } = props as {
                      cx: number;
                      cy: number;
                      payload: ScatterPayload;
                    };
                    const color = quadrantColor(payload.quadrant);
                    return (
                      <g>
                        {/* glow ring */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={9}
                          fill={color}
                          fillOpacity={0.18}
                          stroke="none"
                        />
                        {/* main dot */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={6}
                          fill={color}
                          stroke={theme === "dark" ? "#1a0a0c" : "#ffffff"}
                          strokeWidth={2}
                        />
                      </g>
                    );
                  }}
                />
              )}
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* time scrubber */}
        {validPoints.length > 1 && (
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  if (playing) {
                    setPlaying(false);
                  } else {
                    // if at end, restart from beginning
                    if (safeIdx >= validPoints.length - 1) {
                      setScrubIdx(0);
                    }
                    setPlaying(true);
                  }
                }}
                className="flex-shrink-0 px-3 py-1 rounded-md text-xs font-medium
                           bg-surface-alt border border-border text-text-secondary
                           hover:text-text-primary transition-colors"
                aria-label={playing ? "Pause" : "Play"}
              >
                {playing ? "⏸ Pause" : "▶ Play"}
              </button>

              <input
                type="range"
                min={0}
                max={validPoints.length - 1}
                value={safeIdx}
                onChange={(e) => {
                  setPlaying(false);
                  setScrubIdx(Number(e.target.value));
                }}
                className="flex-1 accent-[#c4394a] cursor-pointer"
                aria-label="Time scrubber"
              />

              <span className="flex-shrink-0 text-xs text-text-muted tabular-nums w-24 text-right">
                {selectedPoint?.date ?? "—"}
              </span>
            </div>

            {/* year range labels */}
            <div className="flex justify-between text-xs text-text-muted px-0">
              <span>{validPoints[0]?.date?.slice(0, 4) ?? ""}</span>
              <span>{validPoints[validPoints.length - 1]?.date?.slice(0, 4) ?? ""}</span>
            </div>
          </div>
        )}

        {/* caption */}
        <p className="text-xs text-text-muted">
          Source: {source} · as of {asOf}
        </p>
      </div>
    </Card>
  );
}
