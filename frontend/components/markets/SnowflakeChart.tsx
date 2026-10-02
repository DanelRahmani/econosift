"use client";

import { useEffect, useState } from "react";
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { SnowflakeResponse } from "@/lib/types";
import { Card, Skeleton, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

// Axis display names and which Markets tab to navigate to on click
const AXES = [
  { key: "value",       label: "Value",       tab: "Valuation" },
  { key: "growth",      label: "Growth",      tab: "Ratios" },
  { key: "performance", label: "Performance", tab: "Ratios" },
  { key: "health",      label: "Health",      tab: "Ratios" },
  { key: "dividend",    label: "Dividend",    tab: "Ratios" },
] as const;

const VERDICT_COLOR: Record<string, string> = {
  Exceptional: "#16a34a",
  Strong:      "#86c87a",
  Moderate:    "#d97706",
  Weak:        "#e57373",
  Poor:        "#c4394a",
  Unknown:     "#8a6770",
};

interface Props {
  ticker: string;
  onAxisClick?: (tab: string) => void;
  compact?: boolean;
}

export function SnowflakeChart({ ticker, onAxisClick, compact = false }: Props) {
  const { theme } = useTheme();
  const palette = chartPalette(theme);
  const [data, setData] = useState<SnowflakeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    api.snowflake(ticker)
      .then(setData)
      .catch(() => setError("Failed to load Snowflake score"))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) {
    return (
      <Card className="p-4 space-y-3">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-48 w-full" />
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="p-4">
        <p className="text-sm text-text-muted">{error ?? "No Snowflake data available"}</p>
      </Card>
    );
  }

  const radarData = AXES.map(({ key, label }) => ({
    axis: label,
    axisKey: key,
    // plot 0 for a missing axis (geometry only); `raw` keeps the truth for labels/tooltip
    score: data.scores[key] ?? 0,
    raw: data.scores[key] ?? null,
    fullMark: 10,
    tabTarget: AXES.find(a => a.key === key)?.tab ?? "Ratios",
  }));

  const verdictColor = VERDICT_COLOR[data.verdict] ?? VERDICT_COLOR.Unknown;
  const overall = data.overallScore?.toFixed(1) ?? "—";

  const fillColor = theme === "dark" ? "#2F8F83" : "#142A43";
  const fillOpacity = theme === "dark" ? 0.25 : 0.20;
  const strokeColor = theme === "dark" ? "#2F8F83" : "#142A43";

  return (
    <Card className="p-4 space-y-3" {...scope} data-prov-ctx={ticker}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Snowflake Score</h3>
          <p className="text-xs text-text-muted">
            <span data-prov="sectorPeers">{data.sectorPeers} sector peers</span> · <span data-prov="sector">{data.sector ?? "Unknown sector"}</span>
          </p>
          {data.peerGroup?.reason && (
            <p className="text-xs text-text-muted" data-prov="peerGroup.reason">{data.peerGroup.reason}</p>
          )}
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold" style={{ color: verdictColor }} data-prov="overallScore">
            {overall}<span className="text-sm font-normal text-text-muted">/10</span>
          </div>
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-md"
            style={{ backgroundColor: `${verdictColor}22`, color: verdictColor }}
            data-prov="verdict"
          >
            {data.verdict}
          </span>
        </div>
      </div>

      {/* Radar Chart */}
      <div style={{ height: compact ? 180 : 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
            <PolarGrid stroke={palette.grid} />
            <PolarAngleAxis
              dataKey="axis"
              tick={({ x, y, payload, index }) => {
                const item = radarData[index];
                const score = item?.score ?? 0;
                const tabTarget = item?.tabTarget ?? "Ratios";
                return (
                  <text
                    x={x}
                    y={y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={10}
                    fill={palette.axis}
                    style={{ cursor: onAxisClick ? "pointer" : "default" }}
                    onClick={() => onAxisClick?.(tabTarget)}
                    data-prov={`scores.${item?.axisKey}`}
                    data-prov-ctx={item?.axis}
                  >
                    {payload.value}
                    {" "}
                    <tspan fontSize={9} fill={verdictColor}>
                      {item?.raw === null || item?.raw === undefined ? "n/a" : score.toFixed(1)}
                    </tspan>
                  </text>
                );
              }}
            />
            <PolarRadiusAxis
              domain={[0, 10]}
              tick={false}
              axisLine={false}
              tickCount={6}
            />
            <Radar
              name="Score"
              dataKey="score"
              stroke={strokeColor}
              fill={fillColor}
              fillOpacity={fillOpacity}
              strokeWidth={1.5}
            />
            <Tooltip
              formatter={(v: number, _n, entry) => {
                const raw = (entry?.payload as { raw?: number | null } | undefined)?.raw;
                return [raw === null ? "n/a" : v.toFixed(1), "Score"];
              }}
              contentStyle={{
                backgroundColor: palette.tooltipBg,
                border: `1px solid ${palette.tooltipBorder}`,
                borderRadius: "8px",
                color: palette.tooltipText,
                fontSize: "12px",
              }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Rewards & Risks */}
      {!compact && (
        <div className="grid grid-cols-2 gap-3 pt-1 items-start">
          <div>
            <p className="text-xs font-semibold text-success mb-1">✓ Strengths</p>
            <ul className="space-y-0.5" data-prov="rewards">
              {data.rewards.map((r, i) => (
                <li key={i} className="text-xs text-text-secondary flex justify-between">
                  <span>{r.label}</span>
                  <span className="text-success font-medium">{r.score.toFixed(1)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-danger mb-1">⚠ Risks</p>
            <ul className="space-y-0.5" data-prov="risks">
              {data.risks.map((r, i) => (
                <li key={i} className="text-xs text-text-secondary flex justify-between">
                  <span>{r.label}</span>
                  <span className="text-danger font-medium">{r.score.toFixed(1)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Card>
  );
}
