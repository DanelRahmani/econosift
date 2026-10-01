"use client";

import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Label,
} from "recharts";
import type { SectorRotationResponse, SectorBubble } from "@/lib/types";
import { fmtNum } from "@/lib/format";

interface Props {
  data: SectorRotationResponse;
  onSectorClick?: (sector: string) => void;
}

function normAum(aum: number | null, minAum: number, maxAum: number): number {
  if (aum === null || maxAum === minAum) return 60;
  return 30 + ((aum - minAum) / (maxAum - minAum)) * 170;
}

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: SectorBubble;
  size?: number;
  onClick?: (sector: string) => void;
}

function CustomDot({ cx = 0, cy = 0, payload, size = 60, onClick }: DotProps) {
  if (!payload) return null;
  const r = Math.sqrt(size / Math.PI);
  const color = (payload.vsSpy ?? 0) >= 0 ? "#16a34a" : "#c4394a";
  return (
    <g
      onClick={() => onClick && onClick(payload.sector)}
      style={{ cursor: onClick ? "pointer" : undefined }}
      data-prov="sectors.return3m"
      data-prov-ctx={payload.sector}
    >
      <circle cx={cx} cy={cy} r={r} fill={color} fillOpacity={0.75} stroke={color} strokeWidth={1} />
      <text x={cx} y={cy - r - 3} textAnchor="middle" fontSize={10} fill="currentColor">
        {payload.ticker}
      </text>
    </g>
  );
}

export function SectorRotationClock({ data, onSectorClick }: Props) {
  const valid = data.sectors.filter((s) => s.vsSpy !== null && s.return3m !== null);
  const auValues = valid.map((s) => s.aum ?? 0);
  const minAum = Math.min(...auValues);
  const maxAum = Math.max(...auValues);

  const medianReturn = (() => {
    const vals = valid.map((s) => s.return3m as number).sort((a, b) => a - b);
    const mid = Math.floor(vals.length / 2);
    return vals.length % 2 === 0 ? (vals[mid - 1] + vals[mid]) / 2 : vals[mid];
  })();

  const points = valid.map((s) => ({
    ...s,
    _size: normAum(s.aum, minAum, maxAum),
  }));

  const phaseColor: Record<string, string> = {
    Early: "#0065cb",
    Mid: "#16a34a",
    Late: "#ca8a04",
    Recession: "#c4394a",
  };
  const color = phaseColor[data.phase] ?? "#9333ea";

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <span
          className="px-3 py-1 rounded-full text-sm font-semibold text-white"
          style={{ backgroundColor: color }}
          data-prov="phase"
        >
          Phase: {data.phase} <span data-prov="confidence">({data.confidence}% confidence)</span>
        </span>
        {data.regimeQuadrant && (
          <span className="text-sm text-text-secondary" data-prov="regimeQuadrant">
            Macro regime: {data.regimeQuadrant}
            {data.regimePhase && data.regimePhase !== data.phase && (
              <span className="text-text-muted ml-1" data-prov="regimePhase">(suggests {data.regimePhase})</span>
            )}
          </span>
        )}
      </div>

      <div className="relative" data-prov="sectors">
        <ResponsiveContainer width="100%" height={400}>
          <ScatterChart margin={{ top: 20, right: 40, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.15)" />
            <XAxis
              type="number"
              dataKey="vsSpy"
              domain={[-12, 12]}
              tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
              tick={{ fontSize: 11 }}
              stroke="rgba(128,128,128,0.4)"
            >
              <Label value="vs SPY 3M (%)" offset={-10} position="insideBottom" style={{ fontSize: 11 }} />
            </XAxis>
            <YAxis
              type="number"
              dataKey="return3m"
              tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
              tick={{ fontSize: 11 }}
              stroke="rgba(128,128,128,0.4)"
            >
              <Label value="3M Return (%)" angle={-90} position="insideLeft" style={{ fontSize: 11 }} />
            </YAxis>
            <Tooltip
              content={({ payload }) => {
                const p = payload?.[0]?.payload as SectorBubble | undefined;
                if (!p) return null;
                return (
                  <div className="bg-surface border border-border rounded-lg p-2 text-xs shadow-lg">
                    <div className="font-semibold">{p.sector} ({p.ticker})</div>
                    <div>3M Return: {fmtNum(p.return3m)}%</div>
                    <div>vs SPY: {p.vsSpy !== null ? `${p.vsSpy >= 0 ? "+" : ""}${fmtNum(p.vsSpy)}%` : "—"}</div>
                    {p.aum !== null && <div>AUM: ${(p.aum / 1e9).toFixed(1)}B</div>}
                  </div>
                );
              }}
            />
            <ReferenceLine x={0} stroke="rgba(128,128,128,0.5)" strokeDasharray="4 4" />
            <ReferenceLine y={medianReturn} stroke="rgba(128,128,128,0.5)" strokeDasharray="4 4" />
            <Scatter
              data={points}
              shape={(props: DotProps) => <CustomDot {...props} onClick={onSectorClick} />}
            />
          </ScatterChart>
        </ResponsiveContainer>

        {/* Quadrant labels */}
        <div className="absolute top-5 left-8 text-xs text-text-muted font-medium opacity-60">Recession</div>
        <div className="absolute top-5 right-10 text-xs text-text-muted font-medium opacity-60">Early</div>
        <div className="absolute bottom-10 left-8 text-xs text-text-muted font-medium opacity-60">Late</div>
        <div className="absolute bottom-10 right-10 text-xs text-text-muted font-medium opacity-60">Mid</div>
      </div>
    </div>
  );
}
