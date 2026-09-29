"use client";

import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, ResponsiveContainer,
} from "recharts";
import type { SnowflakeScores } from "@/lib/types";
import { useTheme } from "@/components/ThemeProvider";

const AXES = ["Value", "Growth", "Performance", "Health", "Dividend"];
const SCORE_KEYS: (keyof SnowflakeScores)[] = [
  "value", "growth", "performance", "health", "dividend",
];

const SCORE_COLOR = (score: number | null) => {
  if (score === null) return "#8a6770";
  if (score >= 7) return "#16a34a";
  if (score >= 5) return "#d97706";
  return "#c4394a";
};

interface Props {
  scores: SnowflakeScores;
  overallScore?: number | null;
  size?: number;
}

export function SnowflakeMini({ scores, overallScore, size = 100 }: Props) {
  const { theme } = useTheme();
  const gridColor = theme === "dark" ? "#183e3b" : "#e0ecea";
  const fillColor = theme === "dark" ? "#2F8F83" : "#142A43";

  const radarData = AXES.map((label, i) => ({
    axis: label,
    score: scores[SCORE_KEYS[i]] ?? 0,
    fullMark: 10,
  }));

  const overall = overallScore ?? null;
  const color = SCORE_COLOR(overall);

  return (
    <div style={{ width: size, height: size }} className="relative">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={radarData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <PolarGrid stroke={gridColor} />
          <PolarAngleAxis dataKey="axis" tick={false} />
          <PolarRadiusAxis domain={[0, 10]} tick={false} axisLine={false} />
          <Radar
            dataKey="score"
            stroke={fillColor}
            fill={fillColor}
            fillOpacity={0.3}
            strokeWidth={1}
          />
        </RadarChart>
      </ResponsiveContainer>
      {/* Score overlay */}
      {overall !== null && (
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
        >
          <span
            className="text-xs font-bold"
            style={{ color, textShadow: "0 0 4px rgba(0,0,0,0.6)" }}
          >
            {overall.toFixed(1)}
          </span>
        </div>
      )}
    </div>
  );
}
